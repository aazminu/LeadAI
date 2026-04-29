# backend/services/adzuna_service.py

import httpx
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search/1"


# Find existing adoption keywords and replace with:
ADOPTION_KEYWORDS = [
    "systems adoption",
    "systems implementation",
    "software implementation",
    "proptech implementation",
    "platform migration",
    "software rollout",
    "change management",
    "technology implementation",
    "systems administrator",
    "software trainer",
    "implementation specialist",
]

class AdzunaService:
    """
    Fetches job posting data from Adzuna API.
    Used by Values Agent to detect staffing signals
    and company growth indicators.
    Fails gracefully — returns empty dict on any error.
    """

    def __init__(self):
        self.app_id = settings.adzuna_app_id
        self.app_key = settings.adzuna_app_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_hiring_signals(
        self,
        company_name: str,
        city: str = "",
        state: str = "",
        emitter=None,
    ) -> dict:
        try:
            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            emit(
                f"Searching job postings for {company_name}",
                f"city: {city}" if city else "all locations",
                "👔"
            )

            jobs = await self._fetch_jobs(company_name, city)

            emit(
                f"Found {len(jobs)} job postings",
                f"{company_name} in {city}" if city else company_name,
                "✅" if jobs else "⚠️"
            )

            result = self._synthesize(company_name, city, state, jobs)

            # Emit key hiring signals
            if result.get("leasing_jobs", 0) > 0:
                emit(
                    f"Leasing roles: {result['leasing_jobs']}",
                    "High leasing hiring = understaffing signal" if result["leasing_jobs"] >= 3 else "Some leasing activity",
                    "🏠" 
                )

            if result.get("maintenance_jobs", 0) > 0:
                emit(
                    f"Maintenance roles: {result['maintenance_jobs']}",
                    "Maintenance automation opportunity",
                    "🔧"
                )

            if result.get("tech_jobs", 0) > 0:
                emit(
                    f"Tech roles: {result['tech_jobs']}",
                    "Tech-forward hiring signal",
                    "💻"
                )

            if result.get("leadership_jobs", 0) > 0:
                emit(
                    f"Leadership roles: {result['leadership_jobs']}",
                    "New exec = vendor evaluation window",
                    "👤"
                )
            if result.get("adoption_jobs", 0) > 0:
                emit(
                    f"Software adoption roles: {result['adoption_jobs']}",
                    "Actively implementing new software — ideal timing",
                    "⚙️"
                )
                
            emit(
                f"Automation urgency: {result['automation_urgency']}",
                f"Total jobs: {result['total_jobs_found']}",
                "🎯"
            )

            if result.get("pain_points"):
                for pain in result["pain_points"]:
                    emit("Pain point detected", pain, "⚠️")

            return result

        except Exception as e:
            logger.error(f"AdzunaService failed for {company_name}: {e}")
            return self._empty_response(company_name)

    async def _fetch_jobs(
        self,
        company_name: str,
        city: str = "",
        results_per_page: int = 20,
    ) -> list:
        """Fetch job postings for a company."""
        try:
            params = {
                "app_id":           self.app_id,
                "app_key":          self.app_key,
                "results_per_page": results_per_page,
                "what_or":          company_name,
                "content-type":     "application/json",
            }
            if city:
                params["where"] = city

            response = await self.client.get(
                ADZUNA_BASE_URL,
                params=params
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

        except Exception as e:
            logger.warning(f"Adzuna fetch failed for {company_name}: {e}")
            return []

    def _synthesize(
        self,
        company_name: str,
        city: str,
        state: str,
        jobs: list,
    ) -> dict:
        """Analyze job postings for signals."""

        # ── Job category keywords ───────────────────────────
        leasing_keywords = [
            "leasing", "leasing agent", "leasing consultant",
            "leasing manager", "leasing specialist"
        ]
        property_mgmt_keywords = [
            "property manager", "community manager",
            "resident manager", "asset manager"
        ]
        maintenance_keywords = [
            "maintenance", "technician", "hvac",
            "facilities", "groundskeeper"
        ]
        tech_keywords = [
            "software", "engineer", "developer",
            "technology", "it ", "data", "product"
        ]
        leadership_keywords = [
            "director", "vp ", "vice president",
            "chief", "head of", "senior director"
        ]

        # ── Categorize jobs ─────────────────────────────────
        categorized = {
            "leasing":      [],
            "property_mgmt": [],
            "maintenance":  [],
            "tech":         [],
            "leadership":   [],
            "adoption":[],
            "other":        [],
        }

        for job in jobs:
            title = (job.get("title") or "").lower()
            category = job.get("category", {}).get("label", "")

            matched = False
            for keyword in leasing_keywords:
                if keyword in title:
                    categorized["leasing"].append(job)
                    matched = True
                    break

            if not matched:
                for keyword in property_mgmt_keywords:
                    if keyword in title:
                        categorized["property_mgmt"].append(job)
                        matched = True
                        break

            if not matched:
                for keyword in maintenance_keywords:
                    if keyword in title:
                        categorized["maintenance"].append(job)
                        matched = True
                        break

            if not matched:
                for keyword in tech_keywords:
                    if keyword in title:
                        categorized["tech"].append(job)
                        matched = True
                        break

            if not matched:
                for keyword in leadership_keywords:
                    if keyword in title:
                        categorized["leadership"].append(job)
                        matched = True
                        break
            if not matched:
                for keyword in ADOPTION_KEYWORDS:
                    if keyword in title:
                        categorized["adoption"].append(job)
                        matched = True
                        break

            if not matched:
                categorized["other"].append(job)

        # ── Signals ─────────────────────────────────────────
        leasing_count = len(categorized["leasing"])
        maintenance_count = len(categorized["maintenance"])
        tech_count = len(categorized["tech"])
        leadership_count = len(categorized["leadership"])
        adoption_count   = len(categorized["adoption"])
        total_count = len(jobs)

        # Heavy leasing hiring = understaffed = automation urgency
        understaffing_signal = leasing_count >= 3
        tech_forward_signal = tech_count >= 2
        growth_signal = total_count >= 10
        leadership_change = leadership_count >= 1
        is_adopting_new_software = adoption_count >= 1

        # ── Pain points ─────────────────────────────────────
        pain_points = []
        if understaffing_signal:
            pain_points.append(
                f"Hiring {leasing_count} leasing roles — likely understaffed"
            )
        if maintenance_count >= 3:
            pain_points.append(
                f"Hiring {maintenance_count} maintenance roles — maintenance automation opportunity"
            )
        if leadership_change:
            pain_points.append(
                "Leadership hiring — new exec = vendor evaluation window"
            )

        # ── Automation urgency ───────────────────────────────
        if understaffing_signal and total_count >= 10:
            automation_urgency = "high"
        elif understaffing_signal or total_count >= 5:
            automation_urgency = "medium"
        else:
            automation_urgency = "low"

        # ── Top job titles ───────────────────────────────────
        top_jobs = [
            {
                "title":    j.get("title"),
                "location": j.get("location", {}).get("display_name"),
                "salary":   j.get("salary_min"),
            }
            for j in jobs[:5]
        ]

        return {
            "company_name":         company_name,
            "city":                 city,
            "state":                state,
            "total_jobs_found":     total_count,
            "leasing_jobs":         leasing_count,
            "maintenance_jobs":     maintenance_count,
            "tech_jobs":            tech_count,
            "leadership_jobs":      leadership_count,
            "top_jobs":             top_jobs,
            "pain_points":          pain_points,
            "understaffing_signal": understaffing_signal,
            "tech_forward_signal":  tech_forward_signal,
            "growth_signal":        growth_signal,
            "leadership_change":    leadership_change,
            "adoption_jobs":              adoption_count,
            "is_adopting_new_software":   is_adopting_new_software,
            "automation_urgency":   automation_urgency,
            "data_source":          "Adzuna Jobs API",
        }

    def _empty_response(self, company_name: str) -> dict:
        return {
            "company_name":         company_name,
            "city":                 "",
            "state":                "",
            "total_jobs_found":     0,
            "leasing_jobs":         0,
            "maintenance_jobs":     0,
            "tech_jobs":            0,
            "leadership_jobs":      0,
            "top_jobs":             [],
            "pain_points":          [],
            "understaffing_signal": False,
            "tech_forward_signal":  False,
            "growth_signal":        False,
            "leadership_change":    False,
            "adoption_jobs":              0,
            "is_adopting_new_software":   False,
            "automation_urgency":         "unknown",
            "data_source":                "unavailable",
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ─────────────────────────────────────────────────
adzuna_service = AdzunaService()