# backend/services/techstack_service.py

import httpx
import logging
import re
from typing import Optional
from config import settings
from utils.step_emitter import StepEmitter

logger = logging.getLogger(__name__)


# ── PropTech EliseAI integrates with ───────────────────────────
ELISEAI_INTEGRATIONS = [
    "yardi", "realpage", "entrata", "appfolio",
    "mri software", "resman", "knock", "funnel",
    "onesite", "buildium", "rent manager",
]

PROPTECH_KEYWORDS = [
    "yardi", "realpage", "appfolio", "entrata",
    "resman", "mri", "onesite", "knock", "funnel",
    "buildium", "rent manager", "propertyware",
    "amsi", "bluemoon", "bostonpost",
]

DATA_KEYWORDS = [
    "sql", "python", "snowflake", "databricks",
    "powerbi", "tableau", "data analytics",
    "business intelligence", "data warehouse",
]

AI_KEYWORDS = [
    "artificial intelligence", "machine learning",
    "ai leasing", "leasing automation", "chatbot",
    "virtual assistant", "natural language",
    "nlp", "conversational ai", "automated",
    "proptech", "smart home", "predictive",
    "digital transformation", "generative ai",
]

CRM_KEYWORDS = [
    "salesforce", "hubspot", "microsoft dynamics",
    "zoho", "pipedrive", "crm",
]

# Add to CLOUD_KEYWORDS
CLOUD_KEYWORDS = [
    "aws", "azure", "google cloud", "gcp",
    "kubernetes", "docker", "terraform",
    "cloud-native", "devops", "ci/cd",
    "serverless", "lambda",              # ← add
]

# Add new category
BACKEND_KEYWORDS = [
    "typescript", "node.js", "python",
    "react", "next.js", "postgresql",
    "graphql", "microservices",
    "rest api", "fastapi", "django",
]

INTEGRATION_KEYWORDS = [
    "api", "webhook", "integration", "rest",
    "middleware", "etl", "data pipeline",
    "zapier", "workato", "mulesoft",
]

ADOPTION_KEYWORDS = [
    "systems adoption", "user adoption",
    "change management", "implementation",
    "software rollout", "platform migration",
]


class TechStackService:
    """
    Detects company tech stack using three free methods:

    1. Exa.ai → finds exact careers page URL
    2. Exa.ai → fetches actual job posting content
               (handles JS-rendered pages that httpx cannot)
    3. Python → extracts tech keywords from job text
    4. httpx  → HTTP header inspection as secondary signal

    Paid upgrade path (mention in video):
    → BuiltWith API ($295/mo) = complete verified stack
    → No scraping needed, real-time data

    Used by Company Agent to determine:
    - EliseAI integration opportunities
    - Tech sophistication of the company
    - Outreach talking points
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    async def get_tech_stack(
        self,
        company_name: str,
        domain: Optional[str] = None,
        emitter=None,           # ← accept emitter
    ) -> dict:
        try:
            if not domain:
                domain = self._infer_domain(company_name)

            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            # Step 1
            emit(
                "Searching for careers page",
                f"domain: {domain}",
                "🔎"
            )
            careers_url = await self._find_careers_url(
                company_name, domain
            )
            emit(
                "Careers page found" if careers_url else "Careers page not found",
                careers_url,
                "✅" if careers_url else "⚠️"
            )

            # Step 2
            emit(
                "Fetching job postings via Exa",
                "searching technical + operations roles",
                "📄"
            )
            job_text, job_urls = await self._get_job_content_via_exa(
                company_name, domain
            )
            emit(
                f"Fetched {len(job_urls)} job postings",
                ", ".join(job_urls[:3]),
                "📋"
            )

            # Step 3
            emit(
                "Scanning job descriptions for tech keywords",
                "PropTech, AI, CRM, Cloud, Integration",
                "🧠"
            )
            job_tech = self._extract_tech_from_text(job_text)

            # Report findings
            all_found = []
            for category, keywords in job_tech.items():
                if keywords:
                    all_found.extend(keywords)
                    emit(
                        f"Found {category} tools",
                        ", ".join(keywords),
                        "✅"
                    )

            if not all_found:
                emit(
                    "No tech keywords found in job postings",
                    "falling back to header inspection",
                    "⚠️"
                )

            # Step 4
            emit(
                "Inspecting website headers",
                f"https://{domain}",
                "🌐"
            )
            header_tech = await self._inspect_headers(domain)

            # Step 5
            emit(
                "Computing tech stack profile",
                None,
                "⚙️"
            )
            result = self._synthesize(
                company_name, domain,
                careers_url, job_tech, header_tech
            )

            # Final score
            emit(
                f"Tech forward score: {result['tech_forward_score']}/100",
                f"EliseAI integrations: {result['eliseai_integrations'] or 'none detected'}",
                "🎯"
            )

            return result

        except Exception as e:
            logger.error(f"TechStackService failed: {e}")
            return self._empty_response(company_name, domain)

    # ── Step 1: Find Careers URL ────────────────────────────────

    async def _find_careers_url(
        self,
        company_name: str,
        domain: str,
    ) -> Optional[str]:
        """
        Use Exa.ai to find the exact careers page URL.
        Every company uses different paths — Exa handles this.
        """
        try:
            from exa_py import Exa
            from config import get_settings
            get_settings.cache_clear()
            s = get_settings()

            if not s.exa_api_key:
                return await self._guess_careers_url(domain)

            exa = Exa(api_key=s.exa_api_key)

            results = exa.search(
                f"{company_name} careers jobs hiring",
                num_results=3,
                include_domains=[domain],
            )

            if results.results:
                for result in results.results:
                    url = result.url or ""
                    if any(kw in url.lower() for kw in [
                        "career", "job", "hire",
                        "work", "join", "opportunity"
                    ]):
                        logger.info(f"Careers URL: {url}")
                        return url
                return results.results[0].url

            return await self._guess_careers_url(domain)

        except Exception as e:
            logger.warning(f"Exa careers search failed: {e}")
            return await self._guess_careers_url(domain)

    async def _guess_careers_url(self, domain: str) -> Optional[str]:
        """Fallback: try common careers page paths."""
        common_paths = [
            "/careers", "/jobs", "/join-us",
            "/work-with-us", "/about/careers",
            "/company/careers", "/opportunities",
        ]
        for path in common_paths:
            try:
                url = f"https://{domain}{path}"
                response = await self.client.head(
                    url, timeout=5.0
                )
                if response.status_code == 200:
                    return url
            except Exception:
                continue
        return None

    # ── Step 2: Get Job Content via Exa ────────────────────────

    async def _get_job_content_via_exa(
        self,
        company_name: str,
        domain: str,
    ) -> tuple[str, list]:        # ← returns (text, urls)
        try:
            from exa_py import Exa
            from config import get_settings
            get_settings.cache_clear()
            s = get_settings()

            if not s.exa_api_key:
                return "", []

            exa = Exa(api_key=s.exa_api_key)

            tech_results = exa.search_and_contents(
                f"{company_name} software engineer IT "
                f"developer technology job requirements",
                num_results=5,
                include_domains=[
                    domain, f"jobs.{domain}",
                    f"careers.{domain}",
                    "greenhouse.io", "lever.co", "linkedin.com",
                ],
                text=True,
                highlights=True,
            )

            ops_results = exa.search_and_contents(
                f"{company_name} leasing operations "
                f"property management systems job requirements",
                num_results=5,
                include_domains=[
                    domain, f"jobs.{domain}",
                    f"careers.{domain}",
                    "indeed.com", "linkedin.com",
                ],
                text=True,
                highlights=True,
            )

            combined_text = ""
            urls = []

            for result in list(tech_results.results or []) + list(ops_results.results or []):
                text = result.text or ""
                title = result.title or ""
                highlights = getattr(result, 'highlights', []) or []
                highlight_text = " ".join(
                    h for h in highlights if isinstance(h, str)
                )
                combined_text += f" {title} {text} {highlight_text}"
                if result.url:
                    urls.append(result.url)

            return combined_text.lower(), urls

        except Exception as e:
            logger.warning(f"Exa job search failed: {e}")
            return "", []

    # ── Step 3: Extract Tech Keywords ──────────────────────────

    def _extract_tech_from_text(self, text: str) -> dict:
        """Extract technology keywords from job posting text."""
        if not text:
            return {
                "proptech": [], "ai": [], "crm": [],
                "cloud": [], "data": [], "integration": [],
                "adoption": [],
            }

        return {
            "proptech":    self._find_keywords(text, PROPTECH_KEYWORDS),
            "ai":          self._find_keywords(text, AI_KEYWORDS),
            "crm":         self._find_keywords(text, CRM_KEYWORDS),
            "cloud":       self._find_keywords(text, CLOUD_KEYWORDS),
            "data":        self._find_keywords(text, DATA_KEYWORDS),
            "integration": self._find_keywords(text, INTEGRATION_KEYWORDS),
            "adoption":    self._find_keywords(text, ADOPTION_KEYWORDS),
            "backend": self._find_keywords(text, BACKEND_KEYWORDS),
        }

    def _find_keywords(self, text: str, keywords: list) -> list:
        """Find which keywords appear in text."""
        found = []
        for kw in keywords:
            if kw.lower() in text:
                found.append(kw)
        return found

    # ── Step 4: Header Inspection ───────────────────────────────

    async def _inspect_headers(self, domain: str) -> dict:
        """
        Inspect HTTP headers and homepage for tech signals.
        Secondary signal — less reliable than job postings.
        """
        try:
            response = await self.client.get(
                f"https://{domain}",
                timeout=8.0
            )
            headers = dict(response.headers)
            body = response.text[:3000].lower()
            combined = f"{str(headers).lower()} {body}"

            return {
                "proptech": self._find_keywords(
                    combined, PROPTECH_KEYWORDS
                ),
                "crm":      self._find_keywords(
                    combined, CRM_KEYWORDS
                ),
                "cloud":    self._find_keywords(
                    combined, CLOUD_KEYWORDS
                ),
            }

        except Exception as e:
            logger.warning(f"Header inspection failed: {e}")
            return {}


    
    def _classify_tech_maturity(
        self,
        proptech: list,
        crm: list,
        cloud: list,
        data: list,
        integration: list,
        backend: list,
        ai: list,
        adoption: list,
    ) -> dict:
        """
        Classify tech maturity level 1-4.
        Based on breadth and sophistication of tools detected.
        """
        score = 0
        evidence = []

        # Level 2 signals
        if proptech:
            score += 25
            evidence.append(f"Uses PropTech: {', '.join(proptech[:2])}")

        # Level 3 signals
        if crm:
            score += 20
            evidence.append(f"Uses CRM: {', '.join(crm[:2])}")
        if integration:
            score += 15
            evidence.append("API/integration roles detected")
        if adoption:
            score += 15
            evidence.append("Systems adoption roles — actively implementing")

        # Level 4 signals
        if cloud:
            score += 10
            evidence.append(f"Cloud infrastructure: {', '.join(cloud[:2])}")
        if data:
            score += 10
            evidence.append(f"Data tools: {', '.join(data[:2])}")
        if backend:
            score += 10
            evidence.append("Engineering roles — tech-first company")
        if ai:
            score += 15
            evidence.append("AI/automation interest confirmed")

        score = min(score, 100)

        # Classify level
        if score >= 75:
            level = 4
            label = "Advanced"
            description = "Full enterprise tech stack — understands software ROI deeply"
            eliseai_angle = "Lead with integration story and ROI metrics"
        elif score >= 50:
            level = 3
            label = "Established"
            description = "Multi-tool stack — tech-forward operator"
            eliseai_angle = "Lead with efficiency gains and existing integrations"
        elif score >= 25:
            level = 2
            label = "Basic"
            description = "Single PMS tool — has started digitizing"
            eliseai_angle = "Lead with ease of implementation alongside existing PMS"
        else:
            level = 1
            label = "Manual"
            description = "No tech detected — likely manual operations"
            eliseai_angle = "Lead with ROI and time savings — be educational"

        return {
            "level":        level,
            "label":        label,
            "score":        score,
            "description":  description,
            "eliseai_angle": eliseai_angle,
            "evidence":     evidence,
        }
    # ── Step 5: Synthesize ──────────────────────────────────────

    def _synthesize(
        self,
        company_name: str,
        domain: str,
        careers_url: Optional[str],
        job_tech: dict,
        header_tech: dict,
        
    ) -> dict:
        """
        Combine all signals into unified tech stack profile.
        """

        # Merge from both sources
        all_proptech = list(set(
            job_tech.get("proptech", []) +
            header_tech.get("proptech", [])
        ))
        all_crm = list(set(
            job_tech.get("crm", []) +
            header_tech.get("crm", [])
        ))
        all_cloud = list(set(
            job_tech.get("cloud", []) +
            header_tech.get("cloud", [])
        ))

        ai_signals          = job_tech.get("ai", [])
        data_signals        = job_tech.get("data", [])
        integration_signals = job_tech.get("integration", [])
        adoption_signals    = job_tech.get("adoption", [])
        
        # ── EliseAI integration matches ─────────────────────
        eliseai_integrations = [
            tool for tool in ELISEAI_INTEGRATIONS
            if tool in all_proptech
        ]

        # In _synthesize:
        backend_signals = job_tech.get("backend", [])

        tech_score = 0
        if eliseai_integrations:    tech_score += 40
        if ai_signals:              tech_score += 25
        if all_crm:                 tech_score += 15
        if integration_signals:     tech_score += 10
        if all_cloud:               tech_score += 10
        if adoption_signals:        tech_score += 10
        if backend_signals:         tech_score += 5   # ← add
        tech_score = min(tech_score, 100)
       

        is_tech_forward = tech_score >= 30
        is_ai_aware     = len(ai_signals) > 0
        is_adopting_new_software = len(adoption_signals) > 0

        # ── Talking points ──────────────────────────────────
        talking_points = []

        if eliseai_integrations:
            for tool in eliseai_integrations:
                talking_points.append(
                    f"EliseAI has native integration with "
                    f"{tool.title()} — zero disruption to "
                    f"existing workflow"
                )

        if is_ai_aware:
            talking_points.append(
                "Job postings mention AI/automation — "
                "company is actively evaluating AI tools"
            )

        if is_adopting_new_software:
            talking_points.append(
                "Hiring Systems Adoption roles — "
                "actively implementing new software, "
                "ideal timing for EliseAI conversation"
            )

        if all_crm:
            talking_points.append(
                f"Uses {all_crm[0].title()} CRM — "
                f"EliseAI can sync lead data directly"
            )

        if not eliseai_integrations and not is_ai_aware:
            talking_points.append(
                "No PropTech detected in job postings — "
                "opportunity to be first AI automation partner"
            )

        tech_maturity = self._classify_tech_maturity(
        all_proptech, all_crm, all_cloud,
        data_signals, integration_signals,
        backend_signals, ai_signals, adoption_signals
)

        return {
            "backend_tools": job_tech.get("backend", []),
            "company_name":             company_name,
            "domain":                   domain,
            "careers_url":              careers_url,

            # Tech by category
            "proptech_detected":        all_proptech,
            "ai_signals":               ai_signals,
            "crm_tools":                all_crm,
            "cloud_tools":              all_cloud,
            "data_tools":               data_signals,
            "integration_tools":        integration_signals,
            "adoption_signals":         adoption_signals,

            # EliseAI specific
            "eliseai_integrations":     eliseai_integrations,
            "has_eliseai_integration":  len(eliseai_integrations) > 0,
            "is_ai_aware":              is_ai_aware,
            "is_adopting_new_software": is_adopting_new_software,

            # Scores
            "tech_forward_score":       tech_score,
            "is_tech_forward":          is_tech_forward,

            #tech maturity
            "tech_maturity":    tech_maturity,
            "tech_maturity_level": tech_maturity["level"],
            "tech_maturity_label": tech_maturity["label"],

            # Outreach
            "talking_points":           talking_points,

            # Metadata
            "data_source": "Exa.ai + careers page + header inspection",
            "data_source_note": (
                "Paid upgrade: BuiltWith API ($295/mo) "
                "for complete verified tech stack"
            ),
        }

    def _infer_domain(self, company_name: str) -> str:
        name = company_name.lower()
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
        domain: Optional[str]
    ) -> dict:
        return {
            "company_name":             company_name,
            "domain":                   domain,
            "careers_url":              None,
            "proptech_detected":        [],
            "ai_signals":               [],
            "crm_tools":                [],
            "cloud_tools":              [],
            "data_tools":               [],
            "integration_tools":        [],
            "adoption_signals":         [],
            "eliseai_integrations":     [],
            "has_eliseai_integration":  False,
            "is_ai_aware":              False,
            "is_adopting_new_software": False,
            "tech_forward_score":       0,
            "is_tech_forward":          False,
            "talking_points":           [
                "Tech stack unknown — research before outreach"
            ],
            "data_source":              "unavailable",
            "data_source_note":         "",
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ──────────────────────────────────────────────────
techstack_service = TechStackService()