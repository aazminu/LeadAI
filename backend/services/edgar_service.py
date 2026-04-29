# backend/services/edgar_service.py

import httpx
import re
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
EDGAR_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts"

# Real estate SIC codes
REAL_ESTATE_SICS = [
    "6500", "6510", "6512", "6513",
    "6514", "6515", "6552", "6726",
      # REITs
]

# Add at top of edgar_service.py
KNOWN_CIKS = {
    "avalonbay":            "0000915912",
    "avalonbay communities": "0000915912",
    "equity residential":   "0000906107",
    "invitation homes":     "0001687229",
    "camden property":      "0000906163",
    "camden property trust": "0000906163",
    "udr":                  "0000074260",
    "udr inc":              "0000074260",
    "essex property":       "0000920522",
    "nmi holdings":         "0001547903",
    "mid-america":          "0000912595",
    "independence realty":  "0001466085",
}
KNOWN_DOMAINS = {
    "cardinal group":       "cardinalgroup.com",
    "stellar management":   "stellar-mgmt.com",
    "bozzuto":              "bozzuto.com",
    "greystar":             "greystar.com",
    "lincoln property":     "lpc.com",
}


class EDGARService:
    """
    Fetches company intelligence from SEC EDGAR + Exa about page.

    Public company path:
    1. Find CIK from EDGAR
    2. Get filings (8-K events, SIC code)
    3. Get company facts (revenue, employees, units)

    Private company path:
    1. CIK not found → private confirmed
    2. Exa → find about page URL
    3. Scrape about page → extract size signals

    Both paths feed company_agent with:
    - is_public, is_real_estate
    - company_size, units_managed
    - revenue, employee_count
    - growth signals (8-K events)
    - about_page_text (raw — scoring agent reads this)
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "LeadOS janardhanr@janardhanr.com",
                "Accept": "application/json",
            }
        )

    async def get_company_intelligence(
        self,
        company_name: str,
        emitter=None,
    ) -> dict:
        """Main entry point for Company Agent."""

        def emit(msg, detail=None, icon="🔍"):
            if emitter:
                emitter.emit(msg, detail, icon)
            logger.info(f"{msg} {detail or ''}")

        try:
            emit("Searching SEC EDGAR", company_name, "🏛️")

            # Step 1: Find CIK
            cik = await self._find_company_cik(company_name)

            if cik:
                # ── PUBLIC COMPANY PATH ─────────────────────
                emit("Public company found", f"CIK: {cik}", "✅")

                emit("Fetching SEC filings", None, "📄")
                filings = await self._get_recent_filings(cik)

                emit(
                    "Fetching SEC company facts",
                    "revenue, employees, units",
                    "💰"
                )
                facts = await self._get_company_facts(cik)

                result = self._synthesize_public(
                    company_name, cik, filings, facts
                )

                # Emit confirmed facts with sources
                if result.get("annual_revenue"):
                    emit(
                        f"Revenue: ${result['annual_revenue']:,.0f}",
                        f"Source: SEC EDGAR 10-K | CIK: {cik}",
                        "📌"
                    )
                if result.get("units_managed"):
                    emit(
                        f"Units managed: {result['units_managed']:,.0f}",
                        f"Source: SEC EDGAR 10-K | CIK: {cik}",
                        "📌"
                    )
                if result.get("properties_count"):
                    emit(
                        f"Properties: {result['properties_count']:,.0f}",
                        f"Source: SEC EDGAR 10-K | CIK: {cik}",
                        "📌"
                    )
                if result.get("net_income"):
                    emit(
                        f"Net income: ${result['net_income']:,.0f}",
                        f"Source: SEC EDGAR 10-K | CIK: {cik}",
                        "📌"
                    )
                if result.get("total_assets"):
                    emit(
                        f"Total assets: ${result['total_assets']:,.0f}",
                        f"Source: SEC EDGAR 10-K | CIK: {cik}",
                        "📌"
                    )

                emit(
                    f"Public company confirmed — size: {result['company_size']}",
                    f"Ticker: {result.get('ticker')} | Exchange: {result.get('exchange')}",
                    "📈"
                )

                if result.get("has_recent_material_event"):
                    emit(
                        f"Recent material events detected",
                        f"{result.get('recent_8k_count')} SEC 8-K filings — verify at sec.gov",
                        "⚡"
                    )

                return result

            else:
                # ── PRIVATE COMPANY PATH ────────────────────
                emit(
                    "Not found in EDGAR — private company",
                    "searching about page via Exa",
                    "⚠️"
                )

                # Find about page
                emit(
                    "Searching for company about page",
                    company_name,
                    "🔎"
                )
                about_url = await self._exa_about_page_lookup(company_name)

                if about_url:
                    emit("About page found", about_url, "✅")

                    emit("Scraping about page", about_url, "📄")
                    try:
                        about_text = await self._scrape_about_page(
                            about_url, company_name
                        )
                    except Exception as e:
                        logger.warning(f"Scrape failed: {e}")
                        about_text = ""

                    emit(
                        f"Scraped {len(about_text)} chars",
                        about_text[:100] + "..." if about_text else "empty",
                        "✅" if about_text else "⚠️"
                    )
                else:
                    emit("About page not found", None, "❌")
                    about_text = ""

                result = self._synthesize_private(
                    company_name, about_url, about_text
                )

                # Emit cited facts with sources
                for field, citation in result.get("citations", {}).items():
                    value = citation["value"]
                    formatted = f"{value:,}" if isinstance(
                        value, (int, float)
                    ) else str(value)
                    emit(
                        f"Found {field}: {formatted}",
                        f"Source: {citation['source']} | "
                        f"Evidence: \"{citation['evidence']}\"",
                        "📌"
                    )

                if not result.get("citations"):
                    emit(
                        "Could not extract structured data",
                        f"Raw text available at: {about_url} — SDR should verify manually",
                        "⚠️"
                    )

                emit(
                    f"Private company — size: {result['company_size']}",
                    f"Real estate: {result['is_real_estate']} | "
                    f"Units: {result.get('units_managed')}",
                    "🎯"
                )

                return result

        except Exception as e:
            logger.error(f"EDGARService failed for {company_name}: {e}")
            return self._empty_response(company_name, "error")

    # ── Public: Find CIK ────────────────────────────────────────

    async def _find_company_cik(
        self,
        company_name: str
    ) -> Optional[str]:

        # Check known CIKs first
        name_lower = company_name.lower().strip()
        for key, cik in KNOWN_CIKS.items():
            if key in name_lower or name_lower in key:
                return cik

        # Clean name before searching
        # Remove apostrophes and special chars that break EDGAR
        cleaned = company_name.strip()
        cleaned = cleaned.replace("'", "")   # McDonald's → McDonalds
        cleaned = cleaned.replace("'", "")   # smart quotes
        cleaned = cleaned.replace(",", "")   # UDR, Inc → UDR Inc
        cleaned = cleaned.replace(".", "")   # dots

        try:
            response = await self.client.get(
                "https://www.sec.gov/cgi-bin/browse-edgar",
                params={
                    "company":     cleaned,
                    "CIK":         "",
                    "type":        "10-K",
                    "dateb":       "",
                    "owner":       "include",
                    "count":       "10",  # ← get more results
                    "search_text": "",
                    "action":      "getcompany",
                    "output":      "atom",
                }
            )

            if response.status_code == 200:
                text = response.text
                cik = self._extract_best_cik(text, company_name)
                if cik:
                    return cik

            return None

        except Exception as e:
            logger.warning(f"CIK lookup failed: {e}")
            return None


    def _extract_best_cik(
        self,
        atom_text: str,
        company_name: str,
    ) -> Optional[str]:
        """
        Extract the best matching CIK from EDGAR atom response.
        Prefers exact name matches over partial matches.
        """
        import re
        from xml.etree import ElementTree as ET

        try:
            # Try XML parsing for better matching
            root = ET.fromstring(atom_text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)

            name_lower = company_name.lower().replace("'", "")

            best_cik = None
            best_score = 0

            for entry in entries:
                # Get company name from entry
                title = entry.find("atom:title", ns)
                if title is None:
                    continue

                entry_name = title.text or ""
                entry_lower = entry_name.lower()

                # Get CIK from entry ID or content
                id_elem = entry.find("atom:id", ns)
                if id_elem is None:
                    continue

                cik_match = re.search(r'CIK=(\d+)', id_elem.text or "")
                if not cik_match:
                    continue

                cik = cik_match.group(1).zfill(10)

                # Score the match
                score = 0
                if name_lower in entry_lower:
                    score += 2
                if entry_lower.startswith(name_lower[:5]):
                    score += 1

                if score > best_score:
                    best_score = score
                    best_cik = cik

            if best_cik:
                return best_cik

        except Exception:
            pass

        # Fallback — original regex approach
        ciks = re.findall(r'CIK=(\d+)', atom_text)
        if ciks:
            return ciks[0].zfill(10)

        return None

    def _extract_cik_from_atom(self, text: str) -> Optional[str]:
        """Extract CIK from EDGAR atom response."""
        try:
            pattern = r'CIK=(\d+)'
            matches = re.findall(pattern, text)
            if matches:
                return matches[0].zfill(10)
            return None
        except Exception:
            return None

    # ── Public: Get Filings ─────────────────────────────────────

    async def _get_recent_filings(self, cik: str) -> Optional[dict]:
        """Get recent SEC filings for a company."""
        try:
            url = f"{EDGAR_SUBMISSIONS_URL}/CIK{cik}.json"
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Filings fetch failed: {e}")
            return None

    # ── Public: Get Company Facts ───────────────────────────────

    async def _get_company_facts(self, cik: str) -> dict:
        """
        Fetch financial facts from SEC XBRL API.
        Returns revenue, employees, units, assets.
        Free, no key required.
        """
        try:
            url = f"{EDGAR_COMPANY_FACTS_URL}/CIK{cik}.json"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            facts = data.get("facts", {})
            us_gaap = facts.get("us-gaap", {})
            dei = facts.get("dei", {})

            return {
                "annual_revenue":    self._extract_latest_fact(
                    us_gaap, "Revenues"
                ) or self._extract_latest_fact(
                    us_gaap, "RevenueFromContractWithCustomerExcludingAssessedTax"
                ),
                "total_assets":      self._extract_latest_fact(
                    us_gaap, "Assets"
                ),
                "net_income":        self._extract_latest_fact(
                    us_gaap, "NetIncomeLoss"
                ),
                "employee_count":    self._extract_latest_fact(
                    dei, "EntityNumberOfEmployees"
                ),
                "units_managed":     self._extract_latest_fact(
                    us_gaap, "NumberOfUnitsInRealEstateProperty"
                ) or self._extract_latest_fact(
                    us_gaap, "NumberOfRealEstateProperties"
                ),
                "properties_count":  self._extract_latest_fact(
                    us_gaap, "NumberOfRealEstateProperties"
                ),
            }

        except Exception as e:
            logger.warning(f"Company facts fetch failed: {e}")
            return {}

    def _extract_latest_fact(
        self,
        section: dict,
        fact_name: str
    ) -> Optional[float]:
        try:
            fact = section.get(fact_name, {})
            units = fact.get("units", {})

            # Try all unit types — SEC uses custom ones
            # USD for financials, pure for counts,
            # home for apartment units, community for properties
            all_values = []
            for unit_type in units.values():
                all_values.extend(unit_type)

            if not all_values:
                return None

            # Prefer annual 10-K filings
            annual = [
                v for v in all_values
                if v.get("form") in ["10-K", "10-K/A"]
            ]

            if annual:
                annual.sort(
                    key=lambda x: x.get("end", ""),
                    reverse=True
                )
                return float(annual[0].get("val", 0))

            # Fallback — most recent any filing
            all_values.sort(
                key=lambda x: x.get("end", ""),
                reverse=True
            )
            return float(all_values[0].get("val", 0))

        except Exception:
            return None

    # ── Private: Exa About Page ─────────────────────────────────

    async def _exa_about_page_lookup(
        self,
        company_name: str,
    ) -> Optional[str]:
        try:
            from exa_py import Exa
            from config import get_settings
            get_settings.cache_clear()
            s = get_settings()

            if not s.exa_api_key:
                return None

            exa = Exa(api_key=s.exa_api_key)
            domain = self._infer_domain(company_name)

            # Step 1: Try domain-specific search first
            try:
                results = exa.search(
                    f"{company_name} about company overview",
                    num_results=3,
                    include_domains=[domain],
                )
                if results.results:
                    for result in results.results:
                        url = result.url or ""
                        if any(kw in url.lower() for kw in [
                            "about", "company", "overview",
                            "who-we-are", "our-story"
                        ]):
                            return url
            except Exception:
                pass

            # Step 2: Broader search WITHOUT domain restriction
            # Add "property management" to disambiguate
            results = exa.search(
                f"{company_name} property management real estate about us company overview",
                num_results=5,
            )

            if results.results:
                for result in results.results:
                    url = result.url or ""
                    title = (result.title or "").lower()
                    
                    # Must contain company name in title
                    company_words = company_name.lower().split()
                    name_match = any(
                        word in title 
                        for word in company_words 
                        if len(word) > 3
                    )
                    
                    if name_match and any(kw in url.lower() for kw in [
                        "about", "company", "overview",
                        "who-we-are", "our-story"
                    ]):
                        return url

                # Last resort — first result that matches company name
                for result in results.results:
                    title = (result.title or "").lower()
                    company_words = company_name.lower().split()
                    if any(word in title for word in company_words if len(word) > 3):
                        return result.url

            return None

        except Exception as e:
            logger.warning(f"Exa about page lookup failed: {e}")
            return None

    # ── Private: Scrape About Page ──────────────────────────────

    async def _scrape_about_page(
        self,
        url: str,
        company_name: str,
    ) -> str:
        """
        Fetch about page content.
        Tries Exa first (handles JS) then httpx fallback.
        """
        try:
            from exa_py import Exa
            from config import get_settings
            get_settings.cache_clear()
            s = get_settings()

            if s.exa_api_key:
                exa = Exa(api_key=s.exa_api_key)
                results = exa.get_contents(
                    [url],
                    text=True,
                    highlights=True,
                )
                if results.results:
                    result = results.results[0]
                    text = result.text or ""
                    highlights = getattr(result, 'highlights', []) or []
                    highlight_text = " ".join(
                        h for h in highlights
                        if isinstance(h, str)
                    )
                    combined = f"{text} {highlight_text}"
                    if combined.strip():
                        logger.info(
                            f"Exa fetched about page: {len(combined)} chars"
                        )
                        return combined[:8000]

        except Exception as e:
            logger.warning(f"Exa about page fetch failed: {e}")

        # Fallback: httpx
        try:
            response = await self.client.get(
                url, timeout=10.0, follow_redirects=True
            )
            if response.status_code != 200:
                return ""

            html = response.text
            html = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL)
            html = re.sub(r'<style[^>]*>.*?</style>', ' ', html, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:8000]

        except Exception as e:
            logger.warning(f"httpx about page fetch failed: {e}")
            return ""

    # ── Synthesize Public ───────────────────────────────────────

    def _synthesize_public(
        self,
        company_name: str,
        cik: str,
        filings: Optional[dict],
        facts: dict,
    ) -> dict:
        """Combine EDGAR filings + facts for public companies."""

        # Basic company info from filings
        name            = filings.get("name", company_name) if filings else company_name
        sic             = filings.get("sic", "") if filings else ""
        sic_description = filings.get("sicDescription", "") if filings else ""
        tickers         = filings.get("tickers", []) if filings else []
        exchanges       = filings.get("exchanges", []) if filings else []

        # Is real estate?
        is_real_estate = (
            any(sic.startswith(s[:3]) for s in REAL_ESTATE_SICS) or
            "real estate" in sic_description.lower() or
            "reit" in sic_description.lower()
        )

        # Recent filings
        recent = filings.get("filings", {}).get("recent", {}) if filings else {}
        filing_types = recent.get("form", [])[:20]
        filing_dates = recent.get("filingDate", [])[:20]

        has_8k = "8-K" in filing_types
        recent_8k_dates = [
            filing_dates[i]
            for i, f in enumerate(filing_types)
            if f == "8-K" and i < len(filing_dates)
        ]

        # Financial facts
        annual_revenue  = facts.get("annual_revenue")
        total_assets    = facts.get("total_assets")
        net_income      = facts.get("net_income")
        employee_count  = facts.get("employee_count")
        units_managed   = facts.get("units_managed")
        properties_count = facts.get("properties_count")

        # Company size from facts
        company_size = self._classify_size_public(
            annual_revenue, units_managed, employee_count
        )

        # Growth signals from 8-K
        growth_signals = []
        if recent_8k_dates:
            growth_signals.append(
                f"{len(recent_8k_dates)} recent SEC 8-K filings — material events"
            )

        # Buying signals
        buying_signals = []
        if tickers:
            buying_signals.append(
                f"Publicly traded on {', '.join(exchanges)} — enterprise account"
            )
        if is_real_estate:
            buying_signals.append(
                f"Confirmed real estate operator — SIC: {sic_description}"
            )
        if recent_8k_dates:
            buying_signals.append(
                "Recent material events — actively changing"
            )
            # Add before return statement in _synthesize_public:
        # Remove 6798 from residential check
# Instead check SIC description for residential keywords
        RESIDENTIAL_SICS = ["6512", "6513", "6514", "6515"]

        is_residential = (
            any(sic.startswith(s[:4]) for s in RESIDENTIAL_SICS) or
            any(x in sic_description.lower() for x in [
                "apartment", "residential", "dwelling",
                "housing", "multifamily"
            ])
        )

        # For 6798 REITs — need additional check
        # Equinix SIC=6798 but is NOT residential
        # AvalonBay SIC=6798 but IS residential
        # Differentiate by company facts — if units_managed exists → residential
        if sic == "6798" and not is_residential:
            if facts.get("units_managed"):
                is_residential = True

        return {
            "company_name":             company_name,
            "cik":                      cik,
            "is_public":                True,
            "is_real_estate":           is_real_estate,

            # Stock
            "ticker":                   tickers[0] if tickers else None,
            "exchange":                 exchanges[0] if exchanges else None,
            "sic_code":                 sic,
            "sic_description":          sic_description,

            # Financials
            "annual_revenue":           annual_revenue,
            "total_assets":             total_assets,
            "net_income":               net_income,
            "employee_count":           employee_count,
            "units_managed":            units_managed,
            "properties_count":         properties_count,

            # Size
            "company_size":             company_size,
            "is_residential":   is_residential,  # public REITs — check SIC more carefully
            "aum":              None,
            "citations":        {},
            # Growth signals
            "has_recent_material_event": has_8k,
            "recent_8k_count":          len(recent_8k_dates),
            "recent_8k_dates":          recent_8k_dates[:3],
            "growth_signals":           growth_signals,

            # Buying signals
            "buying_signals":           buying_signals,

            # About page (not needed for public)
            "about_page_url":           None,
            "about_page_text":          None,

            "data_source":              "SEC EDGAR",
        }

    # ── Synthesize Private ──────────────────────────────────────

    def _synthesize_private(
        self,
        company_name: str,
        about_url: Optional[str],
        about_text: str,
    ) -> dict:
        text_lower = about_text.lower()

        # ── Units managed ───────────────────────────────────
        # Look for CURRENT units — prefer millions first
        # then hundreds of thousands, then smaller numbers
        # ── Units managed ───────────────────────────────────
        units_managed = None
        units_evidence = ""

        # Pattern 1: "X million units/homes/apartments"
        million_pattern = r'([\d.]+)\s*million\s*(?:multifamily\s*)?(?:units|apartments|homes|beds|residences)'
        million_match = re.search(million_pattern, text_lower)
        if million_match:
            units_managed = int(float(million_match.group(1)) * 1_000_000)
            units_evidence = million_match.group(0)

        # Pattern 2: "100,000+" format with managed
        if not units_managed:
            plus_pattern = r'([\d,]+)\+?\s*(?:residences|units|apartments|homes)\s*managed'
            plus_match = re.search(plus_pattern, text_lower)
            if plus_match:
                try:
                    val = int(plus_match.group(1).replace(",", ""))
                    if val > 1000:
                        units_managed = val
                        units_evidence = plus_match.group(0)
                except ValueError:
                    pass

        # Pattern 3: Large numbers with commas
        if not units_managed:
            large_pattern = r'([\d,]+)\s*(?:multifamily\s*)?(?:units|apartments|homes|beds)\s*(?:under management|managed|globally)'
            large_match = re.search(large_pattern, text_lower)
            if large_match:
                try:
                    val = int(large_match.group(1).replace(",", ""))
                    if val > 10000:
                        units_managed = val
                        units_evidence = large_match.group(0)
                except ValueError:
                    pass

        # ── Revenue vs AUM ──────────────────────────────────
        # Critical distinction:
        # AUM = assets under management (much larger number)
        # Revenue = actual income (smaller)
        # We want revenue — not AUM
        annual_revenue = None
        aum = None

        # Detect AUM separately
        aum_pattern = r'\$([\d.]+)\s*(billion|million)\s*(?:of\s*)?(?:assets under management|aum|investment portfolio)'
        aum_match = re.search(aum_pattern, text_lower)
        if aum_match:
            amount = float(aum_match.group(1))
            unit = aum_match.group(2)
            aum = amount * 1_000_000_000 if unit == "billion" else amount * 1_000_000

        # Revenue — look for explicit revenue mentions
        # NOT AUM, NOT "real estate valued at", NOT "development assets"
        revenue_pattern = r'\$([\d.]+)\s*(billion|million)\s*(?:in\s*)?(?:revenue|annual revenue|total revenue|construction annual revenue)'
        rev_match = re.search(revenue_pattern, text_lower)
        if rev_match:
            amount = float(rev_match.group(1))
            unit = rev_match.group(2)
            annual_revenue = amount * 1_000_000_000 if unit == "billion" else amount * 1_000_000

        # ── Employee count ──────────────────────────────────
        employee_count = None
        emp_patterns = [
            r'([\d,]+)\+?\s*(?:team members|employees|associates|staff|professionals)',
            r'team of\s*([\d,]+)',
            r'over\s*([\d,]+)\s*(?:team members|employees)',
        ]
        for pattern in emp_patterns:
            emp_match = re.search(pattern, text_lower)
            if emp_match:
                try:
                    employee_count = int(emp_match.group(1).replace(",", ""))
                    if employee_count > 100:  # filter noise
                        break
                    else:
                        employee_count = None
                except ValueError:
                    pass

        # ── Is real estate ──────────────────────────────────
        is_real_estate = any(x in text_lower for x in [
            "apartment", "residential", "property management",
            "real estate", "multifamily", "housing",
            "reit", "leasing", "rental", "tenant",
            "communities", "units under management",
        ])

        # ── Company size ────────────────────────────────────
        company_size = self._classify_size_private(
            units_managed, employee_count, annual_revenue, text_lower
        )

        # ── Growth signals ──────────────────────────────────
        growth_signals = []
        if any(x in text_lower for x in [
            "expanding", "growing", "new markets",
            "recently acquired", "opened", "launched",
            "expansion", "new communities"
        ]):
            growth_signals.append("Growth language on about page")

        # ── Buying signals ──────────────────────────────────
        buying_signals = []
        # ── Is real estate ──────────────────────────────────
        # Strong positive signals — clearly property management
        strong_re_signals = [
            "property management",
            "apartment",
            "multifamily",
            "units under management",
            "residential communities",
            "leasing consultant",
            "rental housing",
            "reit",
            "real estate investment trust",
            "apartment homes",
            "property manager",
        ]

        # Weak positive signals — could be real estate but not certain
        weak_re_signals = [
            "real estate",
            "properties",
            "housing",
            "residential",
            "leasing",
            "rental",
            "tenant",
        ]

        # Negative signals — definitely NOT a property manager
        negative_signals = [
            # Food & Restaurant
            "restaurant", "burger", "food chain",
            "fast food", "dining", "cuisine",
            "grocery", "supermarket",
            # Healthcare & Pharma
            "pharmaceutical", "health care", "hospital",
            "medical", "clinic", "patient",
            "drug", "medicine", "healthcare",
            # Technology
            "software company", "saas", "cloud platform",
            "cybersecurity", "semiconductor",
            # Industrial & Storage
            "storage units", "self storage",
            "data center", "server farm",
            "warehouse", "logistics",
            "manufacturing", "industrial",
            # Education
            "school", "university", "college",
            "education", "academic", "campus",
            "students learn", "curriculum",
            # Retail
            "retail store", "e-commerce",
            "fashion", "clothing",
            # Finance
            "investment bank", "hedge fund",
            "insurance company", "brokerage",
            # Other
            "nonprofit organization",
            "government agency",
        ]

        has_negative = any(x in text_lower for x in negative_signals)
        has_strong   = any(x in text_lower for x in strong_re_signals)
        has_weak     = any(x in text_lower for x in weak_re_signals)

        is_real_estate = (
            not has_negative and
            (has_strong or has_weak)
        )
        # Strong residential signals
        RESIDENTIAL_SIGNALS = [
            "apartment", "multifamily", "residential",
            "leasing", "rental housing", "units under management",
            "property management", "communities", "residents",
            "renter", "tenant", "student housing",
            "single family", "affordable housing",
            "build to rent", "BTR",
        ]

        # Non-residential real estate — disqualify
        NON_RESIDENTIAL_SIGNALS = [
            "data center", "industrial", "warehouse",
            "self-storage", "retail mall", "office building",
            "shopping center", "net lease", "logistics",
            "healthcare facility", "senior care",
        ]

        is_residential = (
            any(x in text_lower for x in RESIDENTIAL_SIGNALS) and
            not any(x in text_lower for x in NON_RESIDENTIAL_SIGNALS) and
            not has_negative    # ← add this — reuse existing negative check
        )
            # After extracting each value, build a citations dict
        citations = {}

        if units_managed:
            citations["units_managed"] = {
                "value":    units_managed,
                "source":   about_url,
                "evidence": units_evidence
            }

        if aum:
            citations["aum"] = {
                "value":  aum,
                "source": about_url,
                "evidence": aum_match.group(0)
            }

        if annual_revenue:
            citations["annual_revenue"] = {
                "value":  annual_revenue,
                "source": about_url,
                "evidence": rev_match.group(0)
            }

        if employee_count:
            citations["employee_count"] = {
                "value":  employee_count,
                "source": about_url,
                "evidence": emp_match.group(0)
            }

        return {
            "company_name":              company_name,
            "cik":                       None,
            "is_public":                 False,
            "is_real_estate":            is_real_estate,
            "is_residential":            is_residential,
            "ticker":                    None,
            "exchange":                  None,
            "sic_code":                  None,
            "sic_description":           None,
            "annual_revenue":            annual_revenue,
            "aum":                       aum,
            "total_assets":              None,
            "net_income":                None,
            "employee_count":            employee_count,
            "units_managed":             units_managed,
            "properties_count":          None,
            "company_size":              company_size,
            "has_recent_material_event": False,
            "recent_8k_count":           0,
            "recent_8k_dates":           [],
            "growth_signals":            growth_signals,
            "buying_signals":            buying_signals,
            "about_page_url":            about_url,
            "about_page_text":           about_text,
            "data_source":               "Exa + About Page",
            "citations": citations,
        }
    # ── Size Classification ─────────────────────────────────────

    def _classify_size_public(
        self,
        revenue: Optional[float],
        units: Optional[float],
        employees: Optional[float],
    ) -> str:
        """Classify public company size from financial facts."""

        if units:
            if units > 50000:   return "enterprise"
            if units > 10000:   return "large"
            if units > 1000:    return "medium"
            return "small"

        if revenue:
            if revenue > 500_000_000:   return "enterprise"
            if revenue > 100_000_000:   return "large"
            if revenue > 10_000_000:    return "medium"
            return "small"

        if employees:
            if employees > 1000:    return "enterprise"
            if employees > 200:     return "large"
            if employees > 50:      return "medium"
            return "small"

        return "unknown"

    def _classify_size_private(
        self,
        units: Optional[int],
        employees: Optional[int],
        revenue: Optional[float],
        text: str,
    ) -> str:
        """Classify private company size from about page signals."""

        if units:
            if units > 50000:   return "enterprise"
            if units > 10000:   return "large"
            if units > 1000:    return "medium"
            return "small"

        if revenue:
            if revenue > 500_000_000:   return "enterprise"
            if revenue > 100_000_000:   return "large"
            if revenue > 10_000_000:    return "medium"
            return "small"

        if employees:
            if employees > 1000:    return "enterprise"
            if employees > 200:     return "large"
            if employees > 50:      return "medium"
            return "small"

        # Word signals — last resort
        if any(x in text for x in [
            "largest", "leading", "global",
            "international", "nationwide", "fortune"
        ]):
            return "large"

        if any(x in text for x in [
            "regional", "growing", "mid-size"
        ]):
            return "medium"

        return "unknown"

    def _infer_domain(self, company_name: str) -> str:
        # Check known domains first
        name_lower = company_name.lower().strip()
        for key, domain in KNOWN_DOMAINS.items():
            if key in name_lower:
                return domain

        # Fall back to inference
        name = name_lower
        for suffix in [
            " communities", " properties", " residential",
            " management", " group", " real estate",
            " partners", " holdings", " inc", " llc",
            " corp", " company", " co"
        ]:
            name = name.replace(suffix, "")
        name = re.sub(r'[^a-z0-9]', '', name)
        return f"{name}.com"

    def _empty_response(
        self,
        company_name: str,
        reason: str
    ) -> dict:
        return {
            "company_name":             company_name,
            "cik":                      None,
            "is_public":                False,
            "is_real_estate":           False,
            "is_residential":            False,
            "ticker":                   None,
            "exchange":                 None,
            "sic_code":                 None,
            "sic_description":          None,
            "annual_revenue":           None,
            "total_assets":             None,
            "net_income":               None,
            "employee_count":           None,
            "units_managed":            None,
            "properties_count":         None,
            "company_size":             "unknown",
            "has_recent_material_event": False,
            "recent_8k_count":          0,
            "recent_8k_dates":          [],
            "growth_signals":           [],
            "buying_signals":           [],
            "citations":                 {},
            "about_page_url":           None,
            "about_page_text":          None,
            "data_source":              "unavailable",
            "reason":                   reason,
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ──────────────────────────────────────────────────
edgar_service = EDGARService()