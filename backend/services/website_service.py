# backend/services/website_service.py

import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Pages to check for ESG/DEI signals
ESG_PATHS = [
    "/sustainability",
    "/esg",
    "/environment",
    "/green",
    "/carbon",
    "/climate",
]

DEI_PATHS = [
    "/diversity",
    "/dei",
    "/inclusion",
    "/equity",
    "/belonging",
]

CSR_PATHS = [
    "/csr",
    "/corporate-responsibility",
    "/social-responsibility",
    "/community",
    "/impact",
]


class WebsiteService:
    """
    Checks company website for ESG, DEI, and CSR pages.
    Uses HEAD requests only — no full page scraping.
    No API key required.
    Fails gracefully — returns empty dict on any error.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "LeadOS/1.0 janardhanr@janardhanr.com"
            }
        )

    async def check_company_values_pages(
        self,
        company_name: str,
        domain: Optional[str] = None,
    ) -> dict:
        """
        Main entry point for Values Agent.
        Checks if company has ESG/DEI/CSR pages.
        """
        try:
            if not domain:
                domain = self._infer_domain(company_name)

            # Check all page categories
            esg_found   = await self._check_paths(domain, ESG_PATHS)
            dei_found   = await self._check_paths(domain, DEI_PATHS)
            csr_found   = await self._check_paths(domain, CSR_PATHS)

            return self._synthesize(
                company_name, domain,
                esg_found, dei_found, csr_found
            )

        except Exception as e:
            logger.error(f"WebsiteService failed for {company_name}: {e}")
            return self._empty_response(company_name, domain)

    async def _check_paths(
        self,
        domain: str,
        paths: list,
    ) -> list:
        """
        Check which paths exist on the domain.
        Uses HEAD request — no content downloaded.
        """
        found = []
        for path in paths:
            try:
                url = f"https://{domain}{path}"
                response = await self.client.head(url, timeout=5.0)
                if response.status_code in [200, 301, 302]:
                    found.append(path)
            except Exception:
                continue
        return found

    def _infer_domain(self, company_name: str) -> str:
        """Infer domain from company name."""
        import re
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

    def _synthesize(
        self,
        company_name: str,
        domain: str,
        esg_found: list,
        dei_found: list,
        csr_found: list,
    ) -> dict:
        """Synthesize page existence into values signals."""

        has_esg = len(esg_found) > 0
        has_dei = len(dei_found) > 0
        has_csr = len(csr_found) > 0

        # ── Evidence strings ────────────────────────────────
        evidence = []
        if has_esg:
            evidence.append(
                f"ESG/sustainability page found: {esg_found[0]}"
            )
        if has_dei:
            evidence.append(
                f"DEI/diversity page found: {dei_found[0]}"
            )
        if has_csr:
            evidence.append(
                f"CSR/community page found: {csr_found[0]}"
            )

        # ── Pitch implications ──────────────────────────────
        pitch_implications = []
        if has_esg:
            pitch_implications.append(
                "Emphasize EliseAI reduces paper-based processes "
                "and eliminates unnecessary site visits"
            )
        if has_dei:
            pitch_implications.append(
                "Emphasize fair housing compliance and "
                "51-language support for diverse residents"
            )
        if has_csr:
            pitch_implications.append(
                "Emphasize community impact — "
                "faster resident responses improve quality of life"
            )
        if not any([has_esg, has_dei, has_csr]):
            pitch_implications.append(
                "No values pages detected — lead with ROI and efficiency"
            )

        # ── Overall values signal strength ──────────────────
        signal_count = sum([has_esg, has_dei, has_csr])
        if signal_count >= 2:
            values_signal = "strong"
        elif signal_count == 1:
            values_signal = "moderate"
        else:
            values_signal = "none"

        return {
            "company_name":         company_name,
            "domain":               domain,
            "has_esg_page":         has_esg,
            "has_dei_page":         has_dei,
            "has_csr_page":         has_csr,
            "esg_paths_found":      esg_found,
            "dei_paths_found":      dei_found,
            "csr_paths_found":      csr_found,
            "evidence":             evidence,
            "pitch_implications":   pitch_implications,
            "values_signal":        values_signal,
            "data_source":          "Company Website (HEAD requests)",
        }

    def _empty_response(
        self,
        company_name: str,
        domain: Optional[str]
    ) -> dict:
        return {
            "company_name":         company_name,
            "domain":               domain,
            "has_esg_page":         False,
            "has_dei_page":         False,
            "has_csr_page":         False,
            "esg_paths_found":      [],
            "dei_paths_found":      [],
            "csr_paths_found":      [],
            "evidence":             [],
            "pitch_implications":   ["No values pages detected — lead with ROI"],
            "values_signal":        "none",
            "data_source":          "unavailable",
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ─────────────────────────────────────────────────
website_service = WebsiteService()