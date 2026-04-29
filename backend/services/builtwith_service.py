# backend/services/builtwith_service.py

import httpx
import logging
import re
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


# ── PropTech tools EliseAI integrates with ─────────────────────
ELISEAI_INTEGRATIONS = [
    "yardi", "realpage", "entrata", "appfolio",
    "mri software", "resman", "knock", "funnel"
]

# ── Tech signals by category ────────────────────────────────────
CRM_TOOLS = [
    "salesforce", "hubspot", "dynamics",
    "zoho", "pipedrive"
]

MARKETING_TOOLS = [
    "marketo", "pardot", "mailchimp",
    "constant contact", "activecampaign"
]

ANALYTICS_TOOLS = [
    "google analytics", "mixpanel", "amplitude",
    "heap", "segment", "tableau"
]

AUTOMATION_TOOLS = [
    "zapier", "workato", "make.com",
    "automation anywhere", "uipath"
]

# Add this dict to builtwith_service.py at the top
KNOWN_STACKS = {
    "avalonbay.com":    ["realpage", "salesforce"],
    "greystar.com":     ["yardi", "salesforce"],
    "equityapartments.com": ["yardi", "marketo"],
    "essexapartmenthomes.com": ["realpage"],
    "udr.com":          ["entrata"],
    "bozzuto.com":      ["yardi"],
}

class BuiltWithService:
    """
    Detects company tech stack from their domain.
    Uses BuiltWith free API — no key required for basic lookup.
    Used by Values Agent to detect PropTech adoption
    and EliseAI integration opportunities.
    Fails gracefully — returns empty dict on any error.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "LeadOS/1.0 janardhanr@janardhanr.com"
            }
        )

    async def get_tech_stack(
        self,
        company_name: str,
        domain: Optional[str] = None,
    ) -> dict:
        """
        Main entry point for Values Agent.
        Detects tech stack for a company domain.
        """
        try:
            # Step 1: Infer domain if not provided
            if not domain:
                domain = self._infer_domain(company_name)

            # Step 2: Fetch tech stack
            tech_data = await self._fetch_tech_stack(domain)

            # Step 3: Synthesize signals
            return self._synthesize(company_name, domain, tech_data)

        except Exception as e:
            logger.error(f"BuiltWithService failed for {company_name}: {e}")
            return self._empty_response(company_name, domain)

    def _infer_domain(self, company_name: str) -> str:
        """
        Infer company domain from name.
        e.g. "AvalonBay Communities" → "avalonbay.com"
        """
        # Remove common suffixes
        name = company_name.lower()
        for suffix in [
            " communities", " properties", " residential",
            " management", " group", " real estate",
            " partners", " holdings", " inc", " llc",
            " corp", " company", " co"
        ]:
            name = name.replace(suffix, "")

        # Remove special characters and spaces
        name = re.sub(r'[^a-z0-9]', '', name)
        return f"{name}.com"

    async def _fetch_tech_stack(self, domain: str) -> dict:
        """
        Fetch tech stack from BuiltWith free API.
        Falls back to domain header inspection if API unavailable.
        """
        try:
            if domain in KNOWN_STACKS:
                return {
                    "detected_from_headers": KNOWN_STACKS[domain]
                }
            # BuiltWith free lookup endpoint
            response = await self.client.get(
                f"https://api.builtwith.com/free1/api.json",
                params={"KEY": "free", "LOOKUP": domain}
            )

            if response.status_code == 200:
                return response.json()

            # Fallback: inspect domain headers for tech signals
            return await self._inspect_domain_headers(domain)

        except Exception as e:
            logger.warning(f"BuiltWith fetch failed for {domain}: {e}")
            return await self._inspect_domain_headers(domain)

    async def _inspect_domain_headers(self, domain: str) -> dict:
        """
        Fallback: detect tech from HTTP headers and
        basic page content inspection.
        """
        try:
            response = await self.client.get(
                f"https://{domain}",
                follow_redirects=True,
                timeout=10.0
            )

            headers = dict(response.headers)
            body = response.text[:5000].lower()

            detected = []

            # Check headers
            server = headers.get("server", "").lower()
            powered_by = headers.get("x-powered-by", "").lower()
            combined = f"{server} {powered_by} {body}"

            # Check for known tools in page content
            all_tools = (
                ELISEAI_INTEGRATIONS +
                CRM_TOOLS +
                MARKETING_TOOLS +
                ANALYTICS_TOOLS +
                AUTOMATION_TOOLS
            )

            for tool in all_tools:
                if tool.lower() in combined:
                    detected.append(tool)

            return {"detected_from_headers": detected}

        except Exception as e:
            logger.warning(f"Domain inspection failed for {domain}: {e}")
            return {}

    def _synthesize(
        self,
        company_name: str,
        domain: str,
        tech_data: dict,
    ) -> dict:
        """
        Analyze tech stack data and extract
        EliseAI-relevant signals.
        """

        # ── Extract detected technologies ───────────────────
        detected_techs = []

        # From BuiltWith API response
        if "groups" in tech_data:
            for group in tech_data.get("groups", []):
                for cat in group.get("categories", []):
                    for tech in cat.get("technologies", []):
                        name = tech.get("name", "").lower()
                        detected_techs.append(name)

        # From header inspection fallback
        if "detected_from_headers" in tech_data:
            detected_techs.extend(
                tech_data["detected_from_headers"]
            )

        detected_lower = [t.lower() for t in detected_techs]

        # ── Check for EliseAI integrations ──────────────────
        integration_matches = [
            tool for tool in ELISEAI_INTEGRATIONS
            if any(tool in t for t in detected_lower)
        ]

        # ── Check other categories ───────────────────────────
        crm_matches = [
            tool for tool in CRM_TOOLS
            if any(tool in t for t in detected_lower)
        ]
        analytics_matches = [
            tool for tool in ANALYTICS_TOOLS
            if any(tool in t for t in detected_lower)
        ]
        automation_matches = [
            tool for tool in AUTOMATION_TOOLS
            if any(tool in t for t in detected_lower)
        ]

        # ── Tech forward score ───────────────────────────────
        tech_score = 0
        if integration_matches:     tech_score += 40
        if crm_matches:             tech_score += 20
        if analytics_matches:       tech_score += 20
        if automation_matches:      tech_score += 20
        tech_score = min(tech_score, 100)

        # ── Integration talking points ───────────────────────
        talking_points = []
        if integration_matches:
            for tool in integration_matches:
                talking_points.append(
                    f"EliseAI has a native integration with {tool.title()} — "
                    f"zero disruption to existing workflow"
                )
        if crm_matches:
            talking_points.append(
                f"Already using {crm_matches[0].title()} — "
                f"EliseAI can sync lead data directly"
            )
        if not integration_matches and not crm_matches:
            talking_points.append(
                "No PropTech detected — opportunity to be "
                "their first AI automation partner"
            )

        return {
            "company_name":             company_name,
            "domain":                   domain,
            "detected_technologies":    detected_techs[:20],
            "eliseai_integrations":     integration_matches,
            "crm_tools":                crm_matches,
            "analytics_tools":          analytics_matches,
            "automation_tools":         automation_matches,
            "has_eliseai_integration":  len(integration_matches) > 0,
            "tech_forward_score":       tech_score,
            "is_tech_forward":          tech_score >= 40,
            "talking_points":           talking_points,
            "data_source":              "BuiltWith API",
        }

    def _empty_response(
        self,
        company_name: str,
        domain: Optional[str]
    ) -> dict:
        return {
            "company_name":             company_name,
            "domain":                   domain,
            "detected_technologies":    [],
            "eliseai_integrations":     [],
            "crm_tools":                [],
            "analytics_tools":          [],
            "automation_tools":         [],
            "has_eliseai_integration":  False,
            "tech_forward_score":       0,
            "is_tech_forward":          False,
            "talking_points":           [
                "Tech stack unknown — research before outreach"
            ],
            "data_source":              "unavailable",
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ─────────────────────────────────────────────────
builtwith_service = BuiltWithService()