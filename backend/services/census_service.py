# backend/services/census_service.py

import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)

CENSUS_BASE_URL = "https://api.census.gov/data"
ACS_YEAR = "2022"
ACS_DATASET = "acs/acs5"

CENSUS_VARIABLES = {
    "B01003_001E": "total_population",
    "B25003_001E": "total_occupied_units",
    "B25003_002E": "owner_occupied_units",
    "B25003_003E": "renter_occupied_units",
    "B19013_001E": "median_household_income",
    "B25002_001E": "total_housing_units",
    "B25002_003E": "vacant_units",
}


class CensusService:
    """
    Fetches demographic and housing data from
    US Census Bureau ACS 5-Year Estimates API.
    No API key required.
    """

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_market_data(
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
                f"Fetching Census data",
                f"{city}, {state}",
                "📊"
            )

            state_fips = await self._get_state_fips(state)
            if not state_fips:
                emit("State FIPS not found", state, "❌")
                return self._empty_response(city, state)

            place_code = await self._get_place_code(city, state_fips)

            if place_code:
                emit(
                    "City-level data found",
                    f"{city}, {state}",
                    "✅"
                )
                raw = await self._fetch_place_data(state_fips, place_code)
            else:
                emit(
                    "Falling back to county-level data",
                    city,
                    "⚠️"
                )
                raw = await self._fetch_county_data(city, state_fips)

            if not raw:
                return self._empty_response(city, state)

            result = self._parse_and_enrich(raw, city, state)

            # Emit key findings with citations
            emit(
                f"Renter population: {result['renter_occupied_units']:,}",
                f"Source: Census ACS 2022 | {result['geography_level']}",
                "📌"
            )
            emit(
                f"Renter percentage: {result['renter_percentage']}%",
                f"Source: Census ACS 2022 | market size: {result['market_size']}",
                "📌"
            )
            emit(
                f"Median income: ${result['median_household_income']:,}",
                f"Source: Census ACS 2022 | asset type: {result['asset_type_signal']}",
                "📌"
            )
            emit(
                f"City vacancy rate: {result['vacancy_rate']}%",
                f"Source: Census ACS 2022 | {result['vacant_units']:,} vacant units",
                "📌"
            )
            emit(
                f"Automation urgency: {result['automation_urgency']}",
                f"Low vacancy + high renter % = high leasing velocity",
                "🎯"
            )

            return result

        except Exception as e:
            logger.error(f"CensusService failed for {city}, {state}: {e}")
            return self._empty_response(city, state)

    async def _get_state_fips(self, state: str) -> Optional[str]:
        state_fips_map = {
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
        upper = state.upper().strip()
        if upper in state_fips_map:
            return state_fips_map[upper]

        name_to_abbr = {
            "alabama": "AL", "alaska": "AK", "arizona": "AZ",
            "arkansas": "AR", "california": "CA", "colorado": "CO",
            "connecticut": "CT", "delaware": "DE", "florida": "FL",
            "georgia": "GA", "hawaii": "HI", "idaho": "ID",
            "illinois": "IL", "indiana": "IN", "iowa": "IA",
            "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
            "maine": "ME", "maryland": "MD", "massachusetts": "MA",
            "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
            "missouri": "MO", "montana": "MT", "nebraska": "NE",
            "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
            "new mexico": "NM", "new york": "NY", "north carolina": "NC",
            "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
            "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
            "south carolina": "SC", "south dakota": "SD", "tennessee": "TN",
            "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
            "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
            "wyoming": "WY", "district of columbia": "DC",
        }
        abbr = name_to_abbr.get(state.lower().strip())
        if abbr:
            return state_fips_map[abbr]
        return None

    async def _get_place_code(
        self,
        city: str,
        state_fips: str
    ) -> Optional[str]:
        try:
            url = (
                f"{CENSUS_BASE_URL}/{ACS_YEAR}/{ACS_DATASET}"
                f"?get=NAME&for=place:*&in=state:{state_fips}"
            )
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            city_lower = city.lower().strip()
            
            best_match = None
            best_score = 0

            for row in data[1:]:
                name = row[0].lower()
                place_code = row[-1]
                score = 0

                # Exact city name match
                if f"{city_lower} city" in name:
                    score = 100          # "philadelphia city" ✅

                elif city_lower == name.split(",")[0].strip():
                    score = 90           # exact name before comma

                elif name.startswith(city_lower + " city"):
                    score = 95

                elif name.startswith(city_lower + " borough"):
                    score = 50           # borough is less likely

                elif name.startswith(city_lower + " township"):
                    score = 30           # township even less likely

                elif city_lower in name:
                    score = 20           # partial match — last resort

                if score > best_score:
                    best_score = score
                    best_match = place_code

            return best_match

        except Exception as e:
            logger.warning(f"Place code lookup failed: {e}")
            return None
    


    async def _fetch_place_data(
        self,
        state_fips: str,
        place_code: str
    ) -> Optional[dict]:
        try:
            variables = ",".join(CENSUS_VARIABLES.keys())
            url = (
                f"{CENSUS_BASE_URL}/{ACS_YEAR}/{ACS_DATASET}"
                f"?get=NAME,{variables}"
                f"&for=place:{place_code}"
                f"&in=state:{state_fips}"
            )
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            if len(data) < 2:
                return None
            return dict(zip(data[0], data[1]))
        except Exception as e:
            logger.warning(f"Place data fetch failed: {e}")
            return None

    async def _fetch_county_data(
        self,
        city: str,
        state_fips: str
    ) -> Optional[dict]:
        try:
            variables = ",".join(CENSUS_VARIABLES.keys())
            url = (
                f"{CENSUS_BASE_URL}/{ACS_YEAR}/{ACS_DATASET}"
                f"?get=NAME,{variables}"
                f"&for=county:*"
                f"&in=state:{state_fips}"
            )
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()
            city_lower = city.lower().strip()
            headers = data[0]
            for row in data[1:]:
                if city_lower in row[0].lower():
                    return dict(zip(headers, row))
            if len(data) > 1:
                return dict(zip(headers, data[1]))
            return None
        except Exception as e:
            logger.warning(f"County data fetch failed: {e}")
            return None

    def _parse_and_enrich(
        self,
        raw: dict,
        city: str,
        state: str
    ) -> dict:
        def safe_int(val) -> int:
            try:
                v = int(val)
                return max(v, 0)
            except (TypeError, ValueError):
                return 0

        total_pop       = safe_int(raw.get("B01003_001E"))
        total_occupied  = safe_int(raw.get("B25003_001E"))
        owner_occupied  = safe_int(raw.get("B25003_002E"))
        renter_occupied = safe_int(raw.get("B25003_003E"))
        median_income   = safe_int(raw.get("B19013_001E"))
        total_housing   = safe_int(raw.get("B25002_001E"))
        vacant_units    = safe_int(raw.get("B25002_003E"))

        renter_pct = (
            round(renter_occupied / total_occupied * 100, 1)
            if total_occupied > 0 else 0
        )
        vacancy_rate = (
            round(vacant_units / total_housing * 100, 1)
            if total_housing > 0 else 0
        )

        if renter_occupied > 100_000:
            market_size = "large"
        elif renter_occupied > 30_000:
            market_size = "medium"
        else:
            market_size = "small"

        if median_income < 40_000:
            asset_type_signal = "affordable"
        elif median_income < 75_000:
            asset_type_signal = "workforce"
        elif median_income < 120_000:
            asset_type_signal = "conventional"
        else:
            asset_type_signal = "luxury"

        automation_urgency = "low"
        if renter_pct > 45 and vacancy_rate < 5:
            automation_urgency = "high"
        elif renter_pct > 35 or vacancy_rate < 8:
            automation_urgency = "medium"

        return {
            "city":                     city,
            "state":                    state,
            "total_population":         total_pop,
            "renter_occupied_units":    renter_occupied,
            "owner_occupied_units":     owner_occupied,
            "total_housing_units":      total_housing,
            "vacant_units":             vacant_units,
            "median_household_income":  median_income,
            "renter_percentage":        renter_pct,
            "vacancy_rate":             vacancy_rate,
            "market_size":              market_size,
            "asset_type_signal":        asset_type_signal,
            "automation_urgency":       automation_urgency,
            "data_source":              "US Census ACS 5-Year Estimates 2022",
            "geography_level":          raw.get("NAME", f"{city}, {state}"),
        }

    def _empty_response(self, city: str, state: str) -> dict:
        return {
            "city":                     city,
            "state":                    state,
            "total_population":         0,
            "renter_occupied_units":    0,
            "owner_occupied_units":     0,
            "total_housing_units":      0,
            "vacant_units":             0,
            "median_household_income":  0,
            "renter_percentage":        0,
            "vacancy_rate":             0,
            "market_size":              "unknown",
            "asset_type_signal":        "unknown",
            "automation_urgency":       "unknown",
            "data_source":              "unavailable",
            "geography_level":          f"{city}, {state}",
        }

    async def close(self):
        await self.client.aclose()


census_service = CensusService()