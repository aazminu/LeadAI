# backend/agents/identity_agent.py

import re
import logging
import httpx
from typing import Optional
from agents.base_agent import BaseAgent, EnrichmentState
from utils.step_emitter import StepEmitter

logger = logging.getLogger(__name__)


class IdentityAgent(BaseAgent):
    """
    Infers contact identity signals from name and email.
    Pure Python — no AI needed.

    Methods (in priority order):
    1. Google LinkedIn snippet search → extracts verified title
    2. Company website team page search → confirms seniority
    3. Email pattern inference → fallback (60-70% accurate)

    Video note: Hunter.io ($0 — 25 free lookups/mo) would add
    email verification + title data as a paid upgrade path.
    """

    agent_name = "identity"

    EXECUTIVE_PREFIXES = [
        "ceo", "coo", "cfo", "cto", "cpo",
        "vp", "svp", "evp", "president",
        "chief", "founder", "owner", "principal",
        "managing", "partner",
    ]

    SENIOR_PREFIXES = [
        "director", "dir", "head", "senior", "sr",
        "lead", "manager", "mgr",
    ]

    # Title keywords that confirm decision maker status
    EXECUTIVE_TITLE_KEYWORDS = [
        "ceo", "coo", "cfo", "cto", "president",
        "founder", "owner", "partner", "principal",
        "vp", "vice president", "svp", "evp",
    ]

    SENIOR_TITLE_KEYWORDS = [
        "director", "head of", "senior manager",
        "regional manager", "general manager",
        "senior director", "managing director",
    ]

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10.0,
            headers={
                # Mimic browser to avoid blocks
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    async def run(self, state: EnrichmentState, emitter=None) -> dict:
        try:
            name    = state.get("name", "")
            email   = state.get("email", "")
            company = state.get("company", "")

            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            # Step 1
            emit("Analyzing email pattern", email, "📧")
            email_signals = self._analyze_email(email)
            emit(
                f"Email pattern: {email_signals.get('pattern')}",
                email_signals.get('evidence'),
                "✅"
            )

            # Step 2
            emit("Parsing name", name, "👤")
            name_signals = self._analyze_name(name)
            emit(
                f"Greeting name: {name_signals.get('greeting_name')}",
                None, "✅"
            )

            # Step 3
            emit(
                "Analyzing email domain",
                email.split("@")[1] if "@" in email else "",
                "🌐"
            )
            domain_signals = self._analyze_domain(email, company)
            emit(
                f"Corporate email: {domain_signals.get('is_corporate')}",
                f"Domain matches company: {domain_signals.get('domain_matches_company')}",
                "✅"
            )

            
            # Step 4
            emit("Searching LinkedIn via Exa", f"{name} {company}", "🔎")
            linkedin_title, linkedin_url = await self._exa_linkedin_lookup(
                name, company
            )
            if linkedin_title:
                emit("LinkedIn title found", linkedin_title, "✅")
                emit("LinkedIn profile URL", linkedin_url, "🔗")
            else:
                emit(
                    "LinkedIn title not found",
                    "falling back to email pattern",
                    "⚠️"
                )

            # Step 5
            website_title = None
            if not linkedin_title:
                domain = domain_signals.get("domain", "")
                if domain:
                    emit(
                        "Checking company website team page",
                        f"https://{domain}",
                        "🌐"
                    )
                    website_title = await self._company_website_lookup(
                        name, domain
                    )
                    if website_title:
                        emit("Found on company website", website_title, "✅")
                    else:
                        emit(
                            "Not found on company website",
                            "using email pattern only",
                            "⚠️"
                        )

            # Step 6
            emit("Computing decision maker probability", None, "⚙️")
            result = self._synthesize(
                name, email, company,
                email_signals, name_signals,
                domain_signals, linkedin_title, website_title,
                linkedin_url,
            )

            emit(
                f"DM probability: {result['dm_probability']}",
                f"{result['dm_classification']} — "
                f"{result.get('verified_title') or result['seniority']}",
                "🎯"
            )

            return self._mark_complete(state, {"identity_data": result})

            emit(
                f"DM probability: {result['dm_probability']}",
                f"{result['dm_classification']} — {result.get('verified_title') or result['seniority']}",
                "🎯"
            )

            return self._mark_complete(state, {"identity_data": result})

        except Exception as e:
            return self._mark_error(state, e)

    # ── Method 2: Google LinkedIn Snippet ──────────────────────

    async def _google_linkedin_lookup(
        self,
        name: str,
        company: str,
    ) -> Optional[str]:
        """
        Search Google for LinkedIn snippet to extract job title.
        Free, no API key needed.

        Google snippets look like:
        "Sarah Johnson - VP of Leasing - Greystar | LinkedIn"
        We extract the middle part as the title.

        Accuracy: ~85% when a result is found.
        Falls back gracefully if blocked or not found.
        """
        try:
            query = f'"{name}" "{company}" site:linkedin.com'
            response = await self.client.get(
                "https://www.google.com/search",
                params={"q": query},
            )

            if response.status_code != 200:
                logger.info(f"Google search returned {response.status_code}")
                return None

            text = response.text

            # Pattern 1: "Name - Title - Company | LinkedIn"
            pattern1 = rf'{re.escape(name)}\s*[-–]\s*([^-–|<>]+?)\s*[-–]'
            match = re.search(pattern1, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if self._is_valid_title(title):
                    logger.info(f"LinkedIn title found: {title}")
                    return title

            # Pattern 2: Look for title in meta description
            pattern2 = r'<span[^>]*>([^<]*(?:director|manager|vp|president|chief|head|senior|founder|owner)[^<]*)</span>'
            match2 = re.search(pattern2, text, re.IGNORECASE)
            if match2:
                title = match2.group(1).strip()
                if self._is_valid_title(title):
                    logger.info(f"Meta title found: {title}")
                    return title

            return None

        except Exception as e:
            logger.warning(f"Google LinkedIn lookup failed: {e}")
            return None

    # ── Method 4: Company Website Team Page ────────────────────

    async def _company_website_lookup(
        self,
        name: str,
        domain: str,
    ) -> Optional[str]:
        """
        Check company website team/leadership pages
        to confirm if person appears and extract title.

        Common paths: /team, /leadership, /about/team,
                      /about-us, /our-team, /management

        Accuracy: ~70% for companies with public team pages.
        Many large property managers publish leadership teams.
        """
        team_paths = [
            "/team",
            "/leadership",
            "/about/team",
            "/about/leadership",
            "/our-team",
            "/management",
            "/about-us",
            "/company/team",
        ]

        name_parts = name.lower().split()
        first_name = name_parts[0] if name_parts else ""
        last_name  = name_parts[-1] if len(name_parts) > 1 else ""

        for path in team_paths:
            try:
                url = f"https://{domain}{path}"
                response = await self.client.get(url, timeout=5.0)

                if response.status_code != 200:
                    continue

                page_text = response.text.lower()

                # Check if person's name appears on this page
                if first_name in page_text and last_name in page_text:
                    # Try to extract title near their name
                    title = self._extract_title_near_name(
                        response.text, name
                    )
                    if title:
                        logger.info(
                            f"Website title found at {path}: {title}"
                        )
                        return title

                    # Name found but no title extracted —
                    # still a strong seniority signal
                    logger.info(
                        f"Name found on {path} — leadership confirmed"
                    )
                    return "leadership_confirmed"

            except Exception:
                continue

        return None

    def _extract_title_near_name(
        self,
        html: str,
        name: str
    ) -> Optional[str]:
        """
        Extract job title from HTML near a person's name.
        Looks for common title patterns in surrounding text.
        """
        try:
            # Find position of name in HTML
            name_pos = html.lower().find(name.lower())
            if name_pos == -1:
                return None

            # Look at 500 chars around the name
            snippet = html[
                max(0, name_pos - 100):name_pos + 400
            ]

            # Remove HTML tags
            clean = re.sub(r'<[^>]+>', ' ', snippet)
            clean = re.sub(r'\s+', ' ', clean).strip()

            # Look for title keywords in the snippet
            all_keywords = (
                self.EXECUTIVE_TITLE_KEYWORDS +
                self.SENIOR_TITLE_KEYWORDS
            )
            for keyword in all_keywords:
                if keyword.lower() in clean.lower():
                    # Extract phrase containing the keyword
                    pattern = rf'([A-Z][^.!?\n]{{0,50}}{keyword}[^.!?\n]{{0,50}})'
                    match = re.search(pattern, clean, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()[:100]

            return None

        except Exception:
            return None

    def _is_valid_title(self, title: str) -> bool:
        """
        Validate that extracted text is actually a job title.
        Filters out garbage matches.
        """
        if not title:
            return False

        # Too short or too long
        if len(title) < 3 or len(title) > 80:
            return False

        # Contains URL artifacts
        if any(x in title.lower() for x in ["http", "www", "linkedin", "..."]):
            return False

        # Contains at least one title-like word
        title_words = [
            "manager", "director", "vp", "president",
            "chief", "head", "senior", "founder",
            "owner", "officer", "lead", "partner",
            "associate", "analyst", "coordinator",
            "specialist", "executive", "supervisor",
        ]
        return any(w in title.lower() for w in title_words)

    # ── Email Pattern Analysis (Fallback) ──────────────────────

    def _analyze_email(self, email: str) -> dict:
        if not email or "@" not in email:
            return {"seniority": "unknown", "pattern": "invalid"}

        local = email.split("@")[0].lower()

        for prefix in self.EXECUTIVE_PREFIXES:
            if prefix in local:
                return {
                    "seniority": "executive",
                    "pattern":   "role_based",
                    "evidence":  f"'{prefix}' in email",
                    "dm_signal": True,
                }

        for prefix in self.SENIOR_PREFIXES:
            if prefix in local:
                return {
                    "seniority": "senior",
                    "pattern":   "role_based",
                    "evidence":  f"'{prefix}' in email",
                    "dm_signal": True,
                }

        if re.match(r'^[a-z]$', local):
            return {
                "seniority": "executive",
                "pattern":   "single_initial",
                "evidence":  "Single initial = likely founder",
                "dm_signal": True,
            }

        if re.match(r'^[a-z]\.[a-z]+$', local):
            return {
                "seniority": "senior",
                "pattern":   "initial_lastname",
                "evidence":  "Initial.Lastname = senior professional",
                "dm_signal": True,
            }

        if re.match(r'^[a-z]+\.[a-z]+$', local):
            return {
                "seniority": "mid_level",
                "pattern":   "firstname_lastname",
                "evidence":  "Firstname.Lastname = standard professional",
                "dm_signal": False,
            }

        if re.match(r'^[a-z]+$', local) and len(local) > 2:
            return {
                "seniority": "senior",
                "pattern":   "firstname_only",
                "evidence":  "First name only = likely senior",
                "dm_signal": True,
            }

        if re.search(r'\d', local):
            return {
                "seniority": "junior",
                "pattern":   "has_numbers",
                "evidence":  "Numbers in email = likely junior",
                "dm_signal": False,
            }

        return {
            "seniority": "unknown",
            "pattern":   "unrecognized",
            "evidence":  "Could not determine from email pattern",
            "dm_signal": False,
        }
    
    async def _exa_linkedin_lookup(
        self,
        name: str,
        company: str,
    ) -> tuple[Optional[str], Optional[str]]:   # ← returns (title, url)
        try:
            from exa_py import Exa
            from config import get_settings
            get_settings.cache_clear()
            settings = get_settings()

            if not settings.exa_api_key:
                return None, None

            exa = Exa(api_key=settings.exa_api_key)

            results = exa.search_and_contents(
                f"{name} {company} LinkedIn",
                num_results=3,
                include_domains=["linkedin.com"],
                text=True,
            )

            if not results.results:
                return None, None

            for result in results.results:
                text      = result.text or ""
                title     = result.title or ""
                url       = result.url or ""           # ← capture URL
                highlights = getattr(result, 'highlights', []) or []

                # Debug prints
                print(f"Exa result:")
                print(f"  URL: {url}")
                print(f"  Title: {title}")
                print(f"  Text preview: {text[:200]}")

                # Pattern match on title
                pattern = rf'{re.escape(name)}\s*[-–]\s*([^-–|]+?)\s*[-–]'
                match = re.search(pattern, title, re.IGNORECASE)
                if match:
                    extracted = match.group(1).strip()
                    extracted = re.sub(r'#\s*', '', extracted)
                    extracted = re.sub(r'\|.*$', '', extracted)
                    extracted = extracted.strip()
                    if self._is_valid_title(extracted):
                        return extracted, url           # ← return url too

                # Parse highlights
                for highlight in highlights:
                    if not isinstance(highlight, str):
                        continue
                    role_pattern = r'((?:CEO|Founder|President|VP|Director|Head|Chief)[^\n\|]{0,50}(?:at|@)[^\n\|]{0,50})'
                    role_match = re.search(role_pattern, highlight, re.IGNORECASE)
                    if role_match:
                        extracted = role_match.group(1).strip()
                        extracted = re.sub(r'#\s*', '', extracted)
                        extracted = re.sub(r'\|.*$', '', extracted)
                        extracted = extracted.strip()
                        if self._is_valid_title(extracted):
                            return extracted, url       # ← return url too

                # Parse text content
                if text:
                    for keyword in (
                        self.EXECUTIVE_TITLE_KEYWORDS +
                        self.SENIOR_TITLE_KEYWORDS
                    ):
                        if keyword.lower() in text.lower():
                            pos = text.lower().find(keyword.lower())
                            snippet = text[max(0, pos-30):pos+60]
                            clean = re.sub(r'\s+', ' ', snippet).strip()
                            clean = re.sub(r'#\s*', '', clean)
                            clean = re.sub(r'\|.*$', '', clean)
                            if self._is_valid_title(clean):
                                return clean, url       # ← return url too

            return None, None

        except Exception as e:
            logger.warning(f"Exa LinkedIn lookup failed: {e}")
            return None, None

    def _analyze_name(self, name: str) -> dict:
        if not name:
            return {"has_full_name": False, "first_name": ""}

        parts = name.strip().split()
        return {
            "has_full_name":  len(parts) >= 2,
            "first_name":     parts[0] if parts else "",
            "last_name":      parts[-1] if len(parts) >= 2 else "",
            "greeting_name":  parts[0] if parts else name,
        }

    def _analyze_domain(self, email: str, company: str) -> dict:
        if not email or "@" not in email:
            return {
                "domain":                 "unknown",
                "is_corporate":           False,
                "domain_matches_company": False,
            }

        domain = email.split("@")[1].lower()
        personal = [
            "gmail.com", "yahoo.com", "hotmail.com",
            "outlook.com", "icloud.com", "aol.com",
        ]
        is_corporate = domain not in personal
        company_clean = re.sub(r'[^a-z0-9]', '', company.lower())
        domain_clean  = re.sub(r'[^a-z0-9]', '', domain.split(".")[0])
        domain_matches = (
            company_clean in domain_clean or
            domain_clean in company_clean
        )

        return {
            "domain":                 domain,
            "is_corporate":           is_corporate,
            "domain_matches_company": domain_matches,
        }

    # ── Synthesize All Signals ──────────────────────────────────

    def _synthesize(
        self,
        name: str,
        email: str,
        company: str,
        email_signals: dict,
        name_signals: dict,
        domain_signals: dict,
        linkedin_title: Optional[str],
        website_title: Optional[str],
        linkedin_url: Optional[str],
    ) -> dict:

        # ── Determine final title and seniority ────────────────
        # Priority: LinkedIn > Website > Email pattern
        verified_title = None
        title_source   = "email_pattern"
        seniority      = email_signals.get("seniority", "unknown")

        if linkedin_title and linkedin_title != "leadership_confirmed":
            verified_title = linkedin_title
            title_source   = "linkedin_google_snippet"
            seniority      = self._seniority_from_title(linkedin_title)

        elif website_title == "leadership_confirmed":
            title_source = "company_website"
            # Bump seniority up — they're on leadership page
            if seniority not in ["executive", "senior"]:
                seniority = "senior"

        elif website_title and website_title != "leadership_confirmed":
            verified_title = website_title
            title_source   = "company_website"
            seniority      = self._seniority_from_title(website_title)

        # ── Decision maker probability ──────────────────────────
        dm_probability = 0.0

        if seniority == "executive":    dm_probability += 0.6
        elif seniority == "senior":     dm_probability += 0.4
        elif seniority == "mid_level":  dm_probability += 0.2
        elif seniority == "junior":     dm_probability += 0.05

        if domain_signals.get("is_corporate"):           dm_probability += 0.2
        if email_signals.get("dm_signal"):               dm_probability += 0.1
        if domain_signals.get("domain_matches_company"): dm_probability += 0.1

        # Boost if we have verified title
        if title_source in ["linkedin_google_snippet", "company_website"]:
            dm_probability = min(dm_probability + 0.1, 1.0)

        dm_probability = min(round(dm_probability, 2), 1.0)

        if dm_probability >= 0.7:
            dm_classification = "likely_decision_maker"
        elif dm_probability >= 0.4:
            dm_classification = "possible_decision_maker"
        elif dm_probability >= 0.2:
            dm_classification = "influencer"
        else:
            dm_classification = "individual_contributor"

        return {
            "name":                     name,
            "email":                    email,
            "company":                  company,
            "first_name":               name_signals.get("first_name"),
            "last_name":                name_signals.get("last_name"),
            "greeting_name":            name_signals.get("greeting_name"),
            "verified_title":           verified_title,
            "title_source":             title_source,
            "seniority":                seniority,
            "seniority_evidence":       email_signals.get("evidence"),
            "domain":                   domain_signals.get("domain"),
            "is_corporate_email":       domain_signals.get("is_corporate"),
            "domain_matches_company":   domain_signals.get("domain_matches_company"),
            "linkedin_found":           linkedin_title is not None,
            "website_found":            website_title is not None,
            "dm_probability":           dm_probability,
            "dm_classification":        dm_classification,
            "recommended_greeting":     f"Hi {name_signals.get('greeting_name', name)}",
            "linkedin_url": linkedin_url,
        }

    def _seniority_from_title(self, title: str) -> str:
        """Infer seniority from a verified job title string."""
        title_lower = title.lower()

        for kw in self.EXECUTIVE_TITLE_KEYWORDS:
            if kw in title_lower:
                return "executive"

        for kw in self.SENIOR_TITLE_KEYWORDS:
            if kw in title_lower:
                return "senior"

        if any(w in title_lower for w in ["manager", "supervisor"]):
            return "mid_level"

        return "mid_level"

    def _empty_response(self) -> dict:
        return {
            "identity_data": {
                "name":                     "",
                "email":                    "",
                "company":                  "",
                "first_name":               "",
                "last_name":                "",
                "greeting_name":            "",
                "verified_title":           None,
                "title_source":             "none",
                "seniority":                "unknown",
                "seniority_evidence":       "",
                "domain":                   "unknown",
                "is_corporate_email":       False,
                "domain_matches_company":   False,
                "linkedin_found":           False,
                "website_found":            False,
                "dm_probability":           0.0,
                "dm_classification":        "unknown",
                "recommended_greeting":     "Hi there",
                "linkedin_url": None,
            }
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ──────────────────────────────────────────────────
identity_agent = IdentityAgent()