# backend/services/walkscore_service.py

import httpx
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

WALKSCORE_BASE_URL = "https://api.walkscore.com/score"


class WalkScoreService:
    """
    Fetches walkability, transit, and bike scores
    for a property address from WalkScore API.
    Used by Property Agent.
    Fails gracefully — returns empty dict on any error.
    """

    def __init__(self):
        self.api_key = settings.walkscore_api_key
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_property_scores(
        self,
        address: str,
        city: str,
        state: str,
    ) -> dict:
        """
        Main entry point for Property Agent.
        Returns walkability signals for a property address.
        Requires geocoding the address to lat/lon first.
        """
        try:
            # Step 1: Geocode address to lat/lon
            lat, lon = await self._geocode_address(
                address, city, state
            )
            if not lat or not lon:
                logger.warning(f"Could not geocode: {address}, {city}, {state}")
                return self._empty_response(address, city, state)

            # Step 2: Get WalkScore
            scores = await self._fetch_scores(
                address, city, state, lat, lon
            )
            if not scores:
                return self._empty_response(address, city, state)

            # Step 3: Synthesize signals
            return self._synthesize(address, city, state, scores, lat, lon)

        except Exception as e:
            logger.error(f"WalkScoreService failed for {address}: {e}")
            return self._empty_response(address, city, state)

    async def _geocode_address(
        self,
        address: str,
        city: str,
        state: str,
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Geocode address to lat/lon using
        OpenStreetMap Nominatim — free, no key needed.
        """
        try:
            full_address = f"{address}, {city}, {state}, USA"
            response = await self.client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q":        full_address,
                    "format":   "json",
                    "limit":    1,
                },
                headers={
                    "User-Agent": "LeadOS/1.0 janardhanr@janardhanr.com"
                }
            )
            response.raise_for_status()
            results = response.json()

            if results:
                return float(results[0]["lat"]), float(results[0]["lon"])

            return None, None

        except Exception as e:
            logger.warning(f"Geocoding failed for {address}: {e}")
            return None, None

    async def _fetch_scores(
        self,
        address: str,
        city: str,
        state: str,
        lat: float,
        lon: float,
    ) -> Optional[dict]:
        """Fetch WalkScore, TransitScore, BikeScore."""
        try:
            full_address = f"{address}, {city}, {state}"
            response = await self.client.get(
                WALKSCORE_BASE_URL,
                params={
                    "format":   "json",
                    "address":  full_address,
                    "lat":      lat,
                    "lon":      lon,
                    "wsapikey": self.api_key,
                    "transit":  1,
                    "bike":     1,
                }
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.warning(f"WalkScore fetch failed: {e}")
            return None

    def _synthesize(
        self,
        address: str,
        city: str,
        state: str,
        scores: dict,
        lat: float,
        lon: float,
    ) -> dict:
        """Synthesize WalkScore data into property signals."""

        walk_score    = scores.get("walkscore", 0)
        walk_desc     = scores.get("description", "")
        transit_score = scores.get("transit", {}).get("score", 0)
        transit_desc  = scores.get("transit", {}).get("description", "")
        bike_score    = scores.get("bike", {}).get("score", 0)
        bike_desc     = scores.get("bike", {}).get("description", "")

        # ── Urban classification ────────────────────────────
        if walk_score >= 90:
            urban_class = "walker_paradise"
        elif walk_score >= 70:
            urban_class = "very_walkable"
        elif walk_score >= 50:
            urban_class = "somewhat_walkable"
        elif walk_score >= 25:
            urban_class = "car_dependent"
        else:
            urban_class = "rural"

        # ── Leasing velocity signal ─────────────────────────
        # High walkability = dense urban = high prospect volume
        # = urgent need for 24/7 automated leasing
        if walk_score >= 70 or transit_score >= 50:
            leasing_velocity = "high"
        elif walk_score >= 50:
            leasing_velocity = "medium"
        else:
            leasing_velocity = "low"

        # ── EliseAI product fit from location ──────────────
        if urban_class in ["walker_paradise", "very_walkable"]:
            product_fit = "conventional_urban"
            automation_case = (
                "High foot traffic and prospect volume — "
                "24/7 AI leasing automation drives immediate ROI"
            )
        elif urban_class == "somewhat_walkable":
            product_fit = "conventional_suburban"
            automation_case = (
                "Suburban market — AI follow-up and tour scheduling "
                "reduces manual leasing workload"
            )
        else:
            product_fit = "single_family_or_rural"
            automation_case = (
                "Lower density — maintenance automation "
                "and resident communication most relevant"
            )

        return {
            "address":          address,
            "city":             city,
            "state":            state,
            "latitude":         lat,
            "longitude":        lon,

            # Raw scores
            "walk_score":       walk_score,
            "walk_description": walk_desc,
            "transit_score":    transit_score,
            "transit_description": transit_desc,
            "bike_score":       bike_score,
            "bike_description": bike_desc,

            # Derived signals
            "urban_classification":  urban_class,
            "leasing_velocity":      leasing_velocity,
            "product_fit":           product_fit,
            "automation_case":       automation_case,

            "data_source": "WalkScore API + OpenStreetMap Nominatim",
        }

    def _empty_response(
        self,
        address: str,
        city: str,
        state: str
    ) -> dict:
        return {
            "address":              address,
            "city":                 city,
            "state":                state,
            "latitude":             None,
            "longitude":            None,
            "walk_score":           0,
            "walk_description":     "unavailable",
            "transit_score":        0,
            "transit_description":  "unavailable",
            "bike_score":           0,
            "bike_description":     "unavailable",
            "urban_classification": "unknown",
            "leasing_velocity":     "unknown",
            "product_fit":          "unknown",
            "automation_case":      "unavailable",
            "data_source":          "unavailable",
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ─────────────────────────────────────────────────
walkscore_service = WalkScoreService()