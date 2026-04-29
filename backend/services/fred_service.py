# backend/services/fred_service.py

import httpx
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred"

NATIONAL_SERIES = {
    "rent_inflation":   "CUSR0000SEHA",
    "vacancy_rate":     "RRVRUSQ156N",
    "housing_index":    "CSUSHPINSA",
}



class FREDService:
    """
    Fetches economic and rental market trend data
    from the Federal Reserve Economic Data API.
    """

    def __init__(self):
        self.api_key = settings.fred_api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_market_trends(
        self,
        city: str,
        state: str,
        emitter=None,
    ) -> dict:
        def emit(msg, detail=None, icon="🔍"):
            if emitter:
                emitter.emit(msg, detail, icon)
            logger.info(f"{msg} {detail or ''}")

        try:
            emit(
                f"Fetching FRED economic data",
                f"{city}, {state}",
                "📈"
            )

            metro_series_id = await self._get_metro_code(city, state)
            emit(
                f"Metro series: {metro_series_id or 'not found — using state'}",
                None,
                "✅" if metro_series_id else "⚠️"
            )

            # Run all series fetches
            rent_trend      = await self._get_rent_trend(metro_series_id)
            unemployment    = await self._get_unemployment(metro_series_id, state)
            vacancy_trend   = await self._get_vacancy_trend()
            hpi_trend       = await self._get_hpi_trend(metro_series_id)
            population      = await self._get_population_trend(city)

            # Emit findings with citations
            if rent_trend.get("available"):
                emit(
                    f"Rent pressure: {rent_trend['rent_pressure']}",
                    f"YoY change: {rent_trend['yoy_change_pct']}% | "
                    f"Source: FRED {rent_trend['series_id']} (national — city data unavailable)",
                    "📌"
                )

            if unemployment.get("available"):
                emit(
                    f"Unemployment: {unemployment['unemployment_rate']}% "
                    f"({unemployment['level']})",
                    f"Source: FRED | geography: {unemployment['geography']}",
                    "📌"
                )

            if vacancy_trend.get("available"):
                emit(
                    f"National vacancy: {vacancy_trend['vacancy_rate']}% "
                    f"({vacancy_trend['trend']})",
                    f"Source: FRED RRVRUSQ156N",
                    "📌"
                )

            if population.get("available"):
                emit(
                    f"Population trend: {population['trend']}",
                    f"Change: {population['change_pct']}% | "
                    f"Source: FRED {population['series_id']}",
                    "📌"
                )

            result = self._synthesize(
                city, state,
                rent_trend,
                unemployment,
                vacancy_trend,
                hpi_trend,
                population,
                metro_series_id
            )

            emit(
                f"Market health: {result['market_health']} "
                f"({result['market_health_score']}/100)",
                f"Leasing intensity: {result['leasing_intensity']}",
                "🎯"
            )

            return result

        except Exception as e:
            logger.error(f"FREDService failed for {city}, {state}: {e}")
            return self._empty_response(city, state)

    async def _get_metro_code(
        self,
        city: str,
        state: str
    ) -> Optional[str]:
        try:
            url = f"{FRED_BASE_URL}/series/search"
            params = {
                "search_text":      f"{city} {state} unemployment",
                "api_key":          self.api_key,
                "file_type":        "json",
                "search_type":      "full_text",
                "filter_variable":  "frequency",
                "filter_value":     "Monthly",
                "limit":            5,
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            for series in data.get("seriess", []):
                series_id = series.get("id", "")
                if "URN" in series_id or "UR" in series_id:
                    return series_id
            return None
        except Exception as e:
            logger.warning(f"Metro lookup failed: {e}")
            return None

    async def _fetch_series(
        self,
        series_id: str,
        limit: int = 12,
        sort_order: str = "desc"
    ) -> Optional[list]:
        try:
            url = f"{FRED_BASE_URL}/series/observations"
            params = {
                "series_id":         series_id,
                "api_key":           self.api_key,
                "file_type":         "json",
                "limit":             limit,
                "sort_order":        sort_order,
                "observation_start": "2020-01-01",
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            observations = data.get("observations", [])
            valid = [
                {"date": o["date"], "value": float(o["value"])}
                for o in observations
                if o["value"] != "."
            ]
            return valid if valid else None
        except Exception as e:
            logger.warning(f"FRED series {series_id} failed: {e}")
            return None

    async def _get_rent_trend(
        self,
        metro_code: Optional[str]
    ) -> dict:
        series_id = NATIONAL_SERIES["rent_inflation"]
        observations = await self._fetch_series(series_id, limit=24)
        if not observations or len(observations) < 2:
            return {"available": False}

        latest   = observations[0]["value"]
        year_ago = observations[min(12, len(observations)-1)]["value"]
        yoy_change = round(((latest - year_ago) / year_ago) * 100, 2)

        if yoy_change > 7:      pressure = "high"
        elif yoy_change > 3:    pressure = "moderate"
        elif yoy_change > 0:    pressure = "low"
        else:                   pressure = "declining"

        return {
            "available":        True,
            "latest_value":     latest,
            "yoy_change_pct":   yoy_change,
            "rent_pressure":    pressure,
            "series_id":        series_id,
            "latest_date":      observations[0]["date"],
        }

    async def _get_unemployment(
        self,
        metro_code: Optional[str],
        state: str
    ) -> dict:
        if metro_code:
            observations = await self._fetch_series(metro_code, limit=3)
            if observations:
                rate = observations[0]["value"]
                return {
                    "available":            True,
                    "unemployment_rate":    rate,
                    "level":                self._classify_unemployment(rate),
                    "geography":            "metro",
                    "date":                 observations[0]["date"],
                }

        state_series_map = {
            "TX": "TXUR", "CA": "CAUR", "FL": "FLUR",
            "NY": "NYUR", "GA": "GAUR", "AZ": "AZUR",
            "NC": "NCUR", "TN": "TNUR", "CO": "COUR",
            "WA": "WAUR", "OR": "ORUR", "NV": "NVUR",
            "IL": "ILUR", "OH": "OHUR", "PA": "PAUR",
            "MI": "MIUR", "MN": "MNUR", "MO": "MOUR",
            "VA": "VAUR", "MD": "MDUR", "DC": "DCUR",
            "MA": "MAUR", "NJ": "NJUR", "IN": "INUR",
            "ID": "IDUR", "SC": "SCUR", "UT": "UTUR",
            "KS": "KSUR", "OK": "OKUR", "LA": "LAUR",
            "AL": "ALUR", "AR": "ARUR", "WI": "WIUR",
            "KY": "KYUR", "IA": "IAUR", "MS": "MSUR",
            "NM": "NMUR", "NE": "NEUR", "WV": "WVUR",
            "HI": "HIUR", "AK": "AKUR", "MT": "MTUR",
            "ND": "NDUR", "SD": "SDUR", "WY": "WYUR",
            "VT": "VTUR", "NH": "NHUR", "ME": "MEUR",
            "RI": "RIUR", "CT": "CTUR", "DE": "DEUR",
        }
        series_id = state_series_map.get(state.upper().strip(), "UNRATE")
        observations = await self._fetch_series(series_id, limit=3)
        if observations:
            rate = observations[0]["value"]
            return {
                "available":            True,
                "unemployment_rate":    rate,
                "level":                self._classify_unemployment(rate),
                "geography":            "state" if series_id != "UNRATE" else "national",
                "date":                 observations[0]["date"],
            }
        return {"available": False}

    async def _get_vacancy_trend(self) -> dict:
        observations = await self._fetch_series(
            NATIONAL_SERIES["vacancy_rate"], limit=8
        )
        if not observations or len(observations) < 2:
            return {"available": False}

        latest = observations[0]["value"]
        prev   = observations[1]["value"]
        change = round(latest - prev, 2)

        return {
            "available":        True,
            "vacancy_rate":     latest,
            "quarter_change":   change,
            "trend":            "tightening" if change < 0 else "loosening",
            "date":             observations[0]["date"],
        }

    async def _get_hpi_trend(
        self,
        metro_code: Optional[str]
    ) -> dict:
        observations = await self._fetch_series(
            NATIONAL_SERIES["housing_index"], limit=24
        )
        if not observations or len(observations) < 12:
            return {"available": False}

        latest   = observations[0]["value"]
        year_ago = observations[min(12, len(observations)-1)]["value"]
        yoy_change = round(((latest - year_ago) / year_ago) * 100, 2)

        return {
            "available":            True,
            "hpi_latest":           latest,
            "yoy_change_pct":       yoy_change,
            "renter_pool_impact":   "expanding" if yoy_change > 3 else "stable",
            "date":                 observations[0]["date"],
        }

    async def _get_population_trend(self, city: str) -> dict:
        """
        Get population growth trend for a city.
        Uses dynamic FRED search — no hardcoding.
        Falls back gracefully if not found.
        """
        # Dynamic search only — no hardcoded map
        series_id = await self._search_population_series(city)

        if not series_id:
            return {"available": False}

        observations = await self._fetch_series(series_id, limit=5)
        if not observations or len(observations) < 2:
            return {"available": False}

        latest = observations[0]["value"]
        older  = observations[-1]["value"]
        change = round(((latest - older) / older) * 100, 2)

        return {
            "available":    True,
            "series_id":    series_id,
            "latest_value": latest,
            "change_pct":   change,
            "trend":        "growing" if change > 0 else "declining",
            "date":         observations[0]["date"],
        }

    async def _search_population_series(
        self,
        city: str
    ) -> Optional[str]:
        """
        Dynamically find population series for any city.
        Searches FRED for metro population index.
        """
        try:
            url = f"{FRED_BASE_URL}/series/search"
            params = {
                "search_text":  f"{city} population",
                "api_key":      self.api_key,
                "file_type":    "json",
                "limit":        10,
                "order_by":     "popularity",  # ← most relevant first
                "sort_order":   "desc",
            }
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            city_lower = city.lower()

            for series in data.get("seriess", []):
                sid   = series.get("id", "")
                title = series.get("title", "").lower()
                freq  = series.get("frequency_short", "")

                # Must contain city name and population
                if city_lower in title and "population" in title:
                    # Prefer annual frequency
                    if freq in ["A", "Q"]:
                        return sid

            # Second pass — less strict
            for series in data.get("seriess", []):
                sid   = series.get("id", "")
                title = series.get("title", "").lower()
                if city_lower in title and "pop" in sid.upper():
                    return sid

            return None

        except Exception as e:
            logger.warning(f"Population series search failed: {e}")
            return None

    def _classify_unemployment(self, rate: float) -> str:
        if rate < 3.5:      return "very_low"
        elif rate < 5.0:    return "low"
        elif rate < 7.0:    return "moderate"
        else:               return "high"

    def _synthesize(
        self,
        city: str,
        state: str,
        rent_trend: dict,
        unemployment: dict,
        vacancy_trend: dict,
        hpi_trend: dict,
        population: dict,
        metro_code: Optional[str],
    ) -> dict:

        score = 50  # baseline

        # Rent pressure
        if rent_trend.get("available"):
            pressure = rent_trend.get("rent_pressure")
            if pressure == "high":          score += 20
            elif pressure == "moderate":    score += 10
            elif pressure == "declining":   score -= 15

        # Unemployment
        if unemployment.get("available"):
            level = unemployment.get("level")
            if level == "very_low":     score += 15
            elif level == "low":        score += 10
            elif level == "high":       score -= 20

        # Vacancy trend
        if vacancy_trend.get("available"):
            if vacancy_trend.get("trend") == "tightening":
                score += 10
            else:
                score -= 5

        # HPI
        if hpi_trend.get("available"):
            if hpi_trend.get("renter_pool_impact") == "expanding":
                score += 5

        # Population trend — NEW
        if population.get("available"):
            if population.get("trend") == "growing":
                score += 15
            elif population.get("trend") == "declining":
                score -= 10

        market_health_score = max(0, min(100, score))

        if market_health_score >= 75:       market_health = "strong"
        elif market_health_score >= 50:     market_health = "moderate"
        elif market_health_score >= 25:     market_health = "weak"
        else:                               market_health = "distressed"

        # ── Leasing intensity — NEW ─────────────────────────
        # Combines rent pressure + unemployment + population
        # into one EliseAI-specific metric
        leasing_score = 0
        leasing_evidence = []

        if rent_trend.get("available"):
            pressure = rent_trend.get("rent_pressure")
            if pressure == "high":
                leasing_score += 35
                leasing_evidence.append(
                    f"High rent growth {rent_trend['yoy_change_pct']}% — "
                    f"operators under pressure"
                )
            elif pressure == "moderate":
                leasing_score += 20
                leasing_evidence.append(
                    f"Moderate rent growth {rent_trend['yoy_change_pct']}%"
                )

        if unemployment.get("available"):
            level = unemployment.get("level")
            if level in ["very_low", "low"]:
                leasing_score += 25
                leasing_evidence.append(
                    f"Low unemployment {unemployment['unemployment_rate']}% — "
                    f"renters employed and mobile"
                )

        if population.get("available"):
            if population.get("trend") == "growing":
                leasing_score += 25
                leasing_evidence.append(
                    f"Growing population +{population['change_pct']}% — "
                    f"expanding renter pool"
                )
            elif population.get("trend") == "declining":
                leasing_score -= 15
                leasing_evidence.append("Declining population — shrinking market")

        if vacancy_trend.get("available"):
            if vacancy_trend.get("trend") == "tightening":
                leasing_score += 15
                leasing_evidence.append(
                    "Tightening vacancy — high demand, fast leasing needed"
                )

        leasing_score = max(0, min(100, leasing_score))

        if leasing_score >= 70:     leasing_intensity = "high"
        elif leasing_score >= 40:   leasing_intensity = "moderate"
        else:                       leasing_intensity = "low"

        return {
            "city":                     city,
            "state":                    state,
            "metro_code":               metro_code,
            "metro_found":              metro_code is not None,

            # Individual series
            "rent_trend":               rent_trend,
            "unemployment":             unemployment,
            "vacancy_trend":            vacancy_trend,
            "hpi_trend":                hpi_trend,
            "population_trend":         population,

            # Market health
            "market_health_score":      market_health_score,
            "market_health":            market_health,

            # In _get_rent_trend, add to return dict:
            "geography": "national",
            "geography_note": "City-specific rent data unavailable — using US national CPI",

            # Leasing intensity — EliseAI specific
            "leasing_intensity":        leasing_intensity,
            "leasing_intensity_score":  leasing_score,
            "leasing_intensity_evidence": leasing_evidence,

            "data_source": "Federal Reserve Economic Data (FRED)",
        }

    def _empty_response(self, city: str, state: str) -> dict:
        return {
            "city":                     city,
            "state":                    state,
            "metro_code":               None,
            "metro_found":              False,
            "rent_trend":               {"available": False},
            "unemployment":             {"available": False},
            "vacancy_trend":            {"available": False},
            "hpi_trend":                {"available": False},
            "population_trend":         {"available": False},
            "market_health_score":      0,
            "market_health":            "unknown",
            "leasing_intensity":        "unknown",
            "leasing_intensity_score":  0,
            "leasing_intensity_evidence": [],
            "data_source":              "unavailable",
        }

    async def close(self):
        await self.client.aclose()


fred_service = FREDService()