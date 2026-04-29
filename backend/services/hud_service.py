# backend/services/hud_service.py

import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# HUD API — no key required for Fair Market Rents
HUD_BASE_URL = "https://www.huduser.gov/hudapi/public"

# HUD FMR entity type codes
ENTITY_TYPE_METRO = "metro"
ENTITY_TYPE_COUNTY = "county"


class HUDService:
    """
    Fetches affordable housing data from the
    US Department of Housing and Urban Development API.

    No API key required.
    Provides Fair Market Rents and income limit data
    to identify affordable housing markets for Values Agent
    and Market Agent.
    Fails gracefully — returns empty dict on any error.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
        )

    async def _get_headers(self) -> dict:
        """
        Returns headers with fresh token each time.
        Avoids stale token from singleton initialization.
        """
        from config import get_settings
        get_settings.cache_clear()
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.hud_api_token}",
            "User-Agent": "LeadOS/1.0"
        }
    
    
    async def get_affordable_housing_data(
        self,
        city: str,
        state: str,
        emitter=None,        # ← add this
    ) -> dict:
        def emit(msg, detail=None, icon="🔍"):
            if emitter:
                emitter.emit(msg, detail, icon)
            logger.info(f"{msg} {detail or ''}")

        try:
            emit(f"Fetching HUD data", f"{city}, {state}", "🏠")
            
            state_fips = self._get_state_fips(state)
            if not state_fips:
                emit("State FIPS not found", state, "❌")
                return self._empty_response(city, state)

            fmr_data = await self._get_fair_market_rents(city, state, state_fips)
            income_limits = await self._get_income_limits(city, state, state_fips)

            result = self._synthesize(city, state, fmr_data, income_limits)

            # Emit key findings
            if fmr_data:
                emit(
                    f"FMR 2BR: ${fmr_data.get('fmr_2br', 0)}",
                    f"Source: HUD Fair Market Rents {fmr_data.get('year')} | "
                    f"{fmr_data.get('area_name')}",
                    "📌"
                )
            emit(
                f"Product fit: {result['eliseai_product_fit']}",
                " | ".join(result.get('pitch_implications', [])[:2]),
                "🎯"
            )

            return result

        except Exception as e:
            logger.error(f"HUDService failed for {city}, {state}: {e}")
            return self._empty_response(city, state)

    async def _get_fair_market_rents(
        self,
        city: str,
        state: str,
        state_fips: str,
    ) -> Optional[dict]:
        try:
            headers = await self._get_headers()

            # Step 1: Get all metro areas
            url = f"{HUD_BASE_URL}/fmr/listMetroAreas"
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            metros = response.json()  # returns a list directly

            # Step 2: Find matching metro for city
            city_lower = city.lower().strip()
            matching_metro = None
            for metro in metros:
                area_name = metro.get("area_name", "").lower()
                if city_lower in area_name:
                    matching_metro = metro
                    break

            if not matching_metro:
                logger.info(f"No HUD metro found for {city}, {state}")
                return None

            # Step 3: Fetch state FMR data using state abbreviation
            state_upper = state.upper().strip()
            fmr_url = f"{HUD_BASE_URL}/fmr/statedata/{state_upper}"
            fmr_response = await self.client.get(fmr_url, headers=headers)
            fmr_response.raise_for_status()
            fmr_data = fmr_response.json()

            # Step 4: Find city in metro areas list
            metro_areas = fmr_data.get("data", {}).get("metroareas", [])
            for area in metro_areas:
                area_name = area.get("metro_name", "").lower()
                if city_lower in area_name:
                    return {
                        "area_name":    area.get("metro_name"),
                        "fmr_0br":      area.get("Efficiency", 0),
                        "fmr_1br":      area.get("One-Bedroom", 0),
                        "fmr_2br":      area.get("Two-Bedroom", 0),
                        "fmr_3br":      area.get("Three-Bedroom", 0),
                        "fmr_4br":      area.get("Four-Bedroom", 0),
                        "year":         fmr_data.get("data", {}).get("year"),
                    }

            return None

        except Exception as e:
            logger.warning(f"FMR fetch failed for {city}: {e}")
            return None

    async def _get_income_limits(
        self,
        city: str,
        state: str,
        state_fips: str,
    ) -> Optional[dict]:
        """
        Fetch county-level FMR data as proxy for income limits.
        HUD income limits endpoint is unavailable — 
        county FMR data gives us equivalent affordability signals.
        """
        try:
            headers = await self._get_headers()
            state_upper = state.upper().strip()

            # Use FMR county endpoint — works reliably
            url = f"{HUD_BASE_URL}/fmr/listCounties/{state_upper}"
            response = await self.client.get(url, headers=headers)
            response.raise_for_status()
            counties = response.json()

            if not isinstance(counties, list):
                counties = counties.get("data", [])

            # Find matching county for city
            city_lower = city.lower().strip()
            matching = None

            for county in counties:
                name = str(county.get("county_name", "")).lower()
                if city_lower in name:
                    matching = county
                    break

            # Fallback — use first county in state
            if not matching and counties:
                matching = counties[0]

            if not matching:
                return None

            # Fetch detailed FMR for this county
            fips = matching.get("fips_code")
            if not fips:
                return None

            return {
            "county_name":          matching.get("county_name"),
            "fips_code":            fips,
            "fmr_2br":              matching.get("Two-Bedroom", 0),
            "fmr_1br":              matching.get("One-Bedroom", 0),
            "fmr_0br":              matching.get("Efficiency", 0),
            "fmr_3br":              matching.get("Three-Bedroom", 0),
            "fmr_4br":              matching.get("Four-Bedroom", 0),
            "median_family_income": 0,
            "year":                 None,
        }

        except Exception as e:
            logger.warning(f"County FMR fetch failed for {city}: {e}")
            return None
                

    def _find_metro_entity(
        self,
        city: str,
        state: str,
        metros: list
    ) -> Optional[str]:
        """Find HUD metro entity ID for a city."""
        city_lower = city.lower().strip()
        state_upper = state.upper().strip()

        if not isinstance(metros, list):
            metros = metros.get("data", []) if isinstance(metros, dict) else []

        for metro in metros:
            name = str(metro.get("metro_name", "")).lower()
            if city_lower in name and state_upper in str(metro).upper():
                return metro.get("entity_id") or metro.get("cbsa_code")

        # Broader search — just city name
        for metro in metros:
            name = str(metro.get("metro_name", "")).lower()
            if city_lower in name:
                return metro.get("entity_id") or metro.get("cbsa_code")

        return None

    def _find_matching_county(
        self,
        city: str,
        counties: list
    ) -> Optional[dict]:
        """Find county matching a city name."""
        city_lower = city.lower().strip()

        if not isinstance(counties, list):
            counties = counties.get("data", []) if isinstance(counties, dict) else []

        for county in counties:
            name = str(county.get("county_name", "")).lower()
            if city_lower in name:
                return county

        return None

    def _extract_fmr(
        self,
        fmr_data: dict,
        city: str,
        entity_id: str
    ) -> Optional[dict]:
        """Extract and structure FMR values."""
        try:
            # HUD returns nested data structure
            data = fmr_data.get("data", fmr_data)
            areas = data.get("basicdata", [])

            for area in areas:
                area_name = str(area.get("area_name", "")).lower()
                if city.lower() in area_name:
                    return {
                        "area_name":        area.get("area_name"),
                        "fmr_0br":          area.get("Efficiency", 0),
                        "fmr_1br":          area.get("One-Bedroom", 0),
                        "fmr_2br":          area.get("Two-Bedroom", 0),
                        "fmr_3br":          area.get("Three-Bedroom", 0),
                        "fmr_4br":          area.get("Four-Bedroom", 0),
                        "year":             data.get("year"),
                    }

            return None

        except Exception as e:
            logger.warning(f"FMR extraction failed: {e}")
            return None

    def _extract_income_limits(self, il_data: dict) -> Optional[dict]:
        """Extract income limit thresholds from county FMR data."""
        try:
            return {
                "very_low_income_limit":    0,
                "low_income_limit":         0,
                "extremely_low_limit":      0,
                "median_family_income":     il_data.get("median_family_income", 0),
                "county_name":              il_data.get("county_name"),
                "fmr_2br":                  il_data.get("fmr_2br", 0),
                "year":                     il_data.get("year"),
            }
        except Exception as e:
            logger.warning(f"Income limit extraction failed: {e}")
            return None

    def _synthesize(
        self,
        city: str,
        state: str,
        fmr_data: Optional[dict],
        income_limits: Optional[dict],
    ) -> dict:
        """
        Synthesize HUD data into actionable signals
        for the Market Agent and Values Agent.

        Key output: is this an affordable housing market?
        And if so, which EliseAI product line fits?
        """

        # ── Affordable housing classification ──────────────
        affordable_signal = False
        affordable_confidence = "low"
        affordable_evidence = []
        eliseai_product_fit = "conventional"  # default

        if fmr_data:
            fmr_2br = fmr_data.get("fmr_2br", 0)

            # Low FMR = affordable market
            # HUD threshold: metro areas with 2BR FMR < $1,200
            # are typically affordable/workforce markets
            if fmr_2br and fmr_2br < 1200:
                affordable_signal = True
                affordable_confidence = "high"
                affordable_evidence.append(
                    f"2BR Fair Market Rent ${fmr_2br}/mo below $1,200 threshold"
                )
                eliseai_product_fit = "affordable"

            elif fmr_2br and fmr_2br < 1800:
                affordable_signal = True
                affordable_confidence = "medium"
                affordable_evidence.append(
                    f"2BR Fair Market Rent ${fmr_2br}/mo suggests workforce housing"
                )
                eliseai_product_fit = "workforce"

            else:
                affordable_evidence.append(
                    f"2BR Fair Market Rent ${fmr_2br}/mo suggests conventional/luxury market"
                )

        if income_limits:
            median = income_limits.get("median_family_income", 0)
            very_low = income_limits.get("very_low_income_limit", 0)

            if median and very_low:
                affordable_evidence.append(
                    f"Area median income ${median:,}, "
                    f"very low income limit ${very_low:,}"
                )

            # Strong affordable signal if median income is low
            if median and median < 60000:
                affordable_signal = True
                if affordable_confidence == "low":
                    affordable_confidence = "medium"

        # ── EliseAI pitch angle from HUD data ─────────────
        pitch_implications = []

        if eliseai_product_fit == "affordable":
            pitch_implications = [
                "EliseAI Affordable Housing product is the right fit",
                "Emphasize fair housing compliance and multilingual support",
                "Highlight cost reduction for budget-constrained operators",
                "51-language support critical for diverse resident base",
            ]
        elif eliseai_product_fit == "workforce":
            pitch_implications = [
                "Workforce housing operators need automation at low cost",
                "Emphasize operational efficiency and staff reduction",
                "Maintenance automation highly relevant",
            ]
        else:
            pitch_implications = [
                "Conventional/luxury market — emphasize resident experience",
                "AI-guided tours and premium leasing automation",
                "Renewal and delinquency management relevant",
            ]

        return {
            "city":                     city,
            "state":                    state,

            # FMR data
            "fmr_available":            fmr_data is not None,
            "fmr_data":                 fmr_data,

            # Income limits
            "income_limits_available":  income_limits is not None,
            "income_limits":            income_limits,

            # Synthesized signals
            "affordable_housing_signal":    affordable_signal,
            "affordable_confidence":        affordable_confidence,
            "affordable_evidence":          affordable_evidence,
            "eliseai_product_fit":          eliseai_product_fit,
            "pitch_implications":           pitch_implications,

            "data_source": "HUD Fair Market Rents & Income Limits API",
        }

    def _get_state_fips(self, state: str) -> Optional[str]:
        """Convert state abbreviation to FIPS code."""
        fips_map = {
            "AL": "01", "AK": "02", "AZ": "04", "AR": "05",
            "CA": "06", "CO": "08", "CT": "09", "DE": "10",
            "FL": "12", "GA": "13", "HI": "15", "ID": "16",
            "IL": "17", "IN": "18", "IA": "19", "KS": "20",
            "KY": "21", "LA": "22", "ME": "23", "MD": "24",
            "MA": "25", "MI": "26", "MN": "27", "MS": "28",
            "MO": "29", "MT": "30", "NE": "31", "NV": "32",
            "NH": "33", "NJ": "34", "NM": "35", "NY": "36",
            "NC": "37", "ND": "38", "OH": "39", "OK": "40",
            "OR": "41", "PA": "42", "RI": "44", "SC": "45",
            "SD": "46", "TN": "47", "TX": "48", "UT": "49",
            "VT": "50", "VA": "51", "WA": "53", "WV": "54",
            "WI": "55", "WY": "56", "DC": "11",
        }
        return fips_map.get(state.upper().strip())

    def _empty_response(self, city: str, state: str) -> dict:
        return {
            "city":                         city,
            "state":                        state,
            "fmr_available":                False,
            "fmr_data":                     None,
            "income_limits_available":      False,
            "income_limits":                None,
            "affordable_housing_signal":    False,
            "affordable_confidence":        "unknown",
            "affordable_evidence":          [],
            "eliseai_product_fit":          "unknown",
            "pitch_implications":           [],
            "data_source":                  "unavailable",
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ─────────────────────────────────────────────────
hud_service = HUDService()