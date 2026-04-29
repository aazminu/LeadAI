# backend/agents/market_agent.py

import logging
import asyncio
from agents.base_agent import BaseAgent, EnrichmentState
from services.census_service import census_service
from services.fred_service import fred_service
from services.hud_service import hud_service

logger = logging.getLogger(__name__)


class MarketAgent(BaseAgent):
    """
    Enriches city-level rental market intelligence by combining:
    - Census ACS    → renter population, vacancy, median income
    - FRED          → rent trends, unemployment, population growth
    - HUD           → fair market rents, affordable vs conventional

    Answers: "Is this city a good market for EliseAI?"

    Outputs:
    1. Renter population + density
    2. City vacancy rate (Census)
    3. Rent growth trend (FRED national)
    4. Employment health (FRED)
    5. Population growth (FRED dynamic)
    6. EliseAI product line signal (HUD + Census)
    7. Market health score (0-100)
    8. Leasing intensity score (0-100) — EliseAI specific
    9. Automation urgency
    """

    agent_name = "market"

    async def run(
        self,
        state: EnrichmentState,
        emitter=None
    ) -> dict:
        try:
            city  = state.get("city", "")
            state_ = state.get("state", "")

            def emit(msg, detail=None, icon="🔍"):
                if emitter:
                    emitter.emit(msg, detail, icon)
                logger.info(f"{msg} {detail or ''}")

            emit(
                f"Starting market enrichment",
                f"{city}, {state_}",
                "🏙️"
            )

            # ── Run all 3 services in parallel ──────────────
            emit(
                "Running 3 market services in parallel",
                "Census + FRED + HUD",
                "⚡"
            )

            census_data, fred_data, hud_data = await asyncio.gather(
                census_service.get_market_data(
                    city, state_, emitter=emitter
                ),
                fred_service.get_market_trends(
                    city, state_, emitter=emitter
                ),
                hud_service.get_affordable_housing_data(
                    city, state_
                ),
                return_exceptions=True
            )

            # Handle failures gracefully
            if isinstance(census_data, Exception):
                logger.error(f"Census failed: {census_data}")
                census_data = {}
            if isinstance(fred_data, Exception):
                logger.error(f"FRED failed: {fred_data}")
                fred_data = {}
            if isinstance(hud_data, Exception):
                logger.error(f"HUD failed: {hud_data}")
                hud_data = {}

            emit("All market services completed", "synthesizing", "✅")

            result = self._synthesize(
                city, state_,
                census_data,
                fred_data,
                hud_data,
                emit
            )

            return self._mark_complete(state, {
                "market_data": result
            })

        except Exception as e:
            return self._mark_error(state, e)

    def _synthesize(
        self,
        city: str,
        state_: str,
        census_data: dict,
        fred_data: dict,
        hud_data: dict,
        emit,
    ) -> dict:

        # ── 1. Renter Population + Density ──────────────────
        renter_population   = census_data.get("renter_occupied_units", 0)
        renter_percentage   = census_data.get("renter_percentage", 0)
        total_population    = census_data.get("total_population", 0)
        market_size         = census_data.get("market_size", "unknown")
        geography_level     = census_data.get("geography_level", f"{city}, {state_}")

        emit(
            f"1. Renter population: {renter_population:,}",
            f"Renter %: {renter_percentage}% | "
            f"Market size: {market_size} | "
            f"Source: Census ACS 2022 | {geography_level}",
            "📊"
        )

        # ── 2. City Vacancy Rate ────────────────────────────
        city_vacancy_rate   = census_data.get("vacancy_rate", 0)
        vacant_units        = census_data.get("vacant_units", 0)

        emit(
            f"2. City vacancy rate: {city_vacancy_rate}%",
            f"{vacant_units:,} vacant units | "
            f"Source: Census ACS 2022 | "
            f"Note: includes all vacant types (seasonal, for-sale, between-renters)",
            "🏘️"
        )

        # ── 3. Rent Growth Trend ────────────────────────────
        rent_trend          = fred_data.get("rent_trend", {})
        rent_pressure       = rent_trend.get("rent_pressure", "unknown")
        rent_yoy            = rent_trend.get("yoy_change_pct", 0)
        rent_series         = rent_trend.get("series_id", "unavailable")

        emit(
            f"3. Rent pressure: {rent_pressure}",
            f"YoY change: {rent_yoy}% | "
            f"Source: FRED {rent_series} (national — city data unavailable)",
            "📌"
        )

        # ── 4. Employment Health ────────────────────────────
        unemployment        = fred_data.get("unemployment", {})
        unemployment_rate   = unemployment.get("unemployment_rate", 0)
        unemployment_level  = unemployment.get("level", "unknown")
        unemployment_geo    = unemployment.get("geography", "unknown")

        emit(
            f"4. Unemployment: {unemployment_rate}% ({unemployment_level})",
            f"Geography: {unemployment_geo} | "
            f"Source: FRED",
            "📌"
        )

        # ── 5. Population Growth ────────────────────────────
        population_trend    = fred_data.get("population_trend", {})
        pop_trend_direction = population_trend.get("trend", "unknown")
        pop_change_pct      = population_trend.get("change_pct", 0)
        pop_series          = population_trend.get("series_id", "unavailable")

        emit(
            f"5. Population trend: {pop_trend_direction}",
            f"Change: {pop_change_pct}% | "
            f"Source: FRED {pop_series}",
            "📌"
        )

        # ── 6. EliseAI Product Line Signal ──────────────────
        median_income       = census_data.get("median_household_income", 0)
        asset_type_signal   = census_data.get("asset_type_signal", "unknown")
        fmr_data            = hud_data.get("fmr_data") or {}
        fmr_2br             = fmr_data.get("fmr_2br", 0)
        affordable_signal   = hud_data.get("affordable_housing_signal", False)
        hud_product_fit     = hud_data.get("eliseai_product_fit", "unknown")

        product_line = self._determine_product_line(
            fmr_2br, median_income, renter_percentage, city
        )

        emit(
            f"6. EliseAI product line: {product_line['product_line']}",
            f"FMR 2BR: ${fmr_2br} | "
            f"Median income: ${median_income:,} | "
            f"Pitch: {product_line['pitch_focus']}",
            "🎯"
        )

        # ── 7. Market Health Score ───────────────────────────
        market_health_score = fred_data.get("market_health_score", 0)
        market_health       = fred_data.get("market_health", "unknown")

        emit(
            f"7. Market health: {market_health} ({market_health_score}/100)",
            f"Source: FRED composite score",
            "📊"
        )

        # ── 8. Leasing Intensity Score ───────────────────────
        leasing_intensity       = fred_data.get("leasing_intensity", "unknown")
        leasing_intensity_score = fred_data.get("leasing_intensity_score", 0)
        leasing_evidence        = fred_data.get("leasing_intensity_evidence", [])

        # Boost leasing intensity with Census signals
        census_boost = 0
        census_boost_evidence = []

        if renter_percentage > 50:
            census_boost += 15
            census_boost_evidence.append(
                f"High renter density {renter_percentage}% — dense leasing market"
            )
        elif renter_percentage > 40:
            census_boost += 8

        if city_vacancy_rate < 5:
            census_boost += 15
            census_boost_evidence.append(
                f"Low city vacancy {city_vacancy_rate}% — tight market"
            )
        elif city_vacancy_rate < 8:
            census_boost += 8

        if renter_population > 200_000:
            census_boost += 10
            census_boost_evidence.append(
                f"Large renter pool {renter_population:,} — high leasing volume"
            )
        elif renter_population > 50_000:
            census_boost += 5

        final_leasing_score = min(
            leasing_intensity_score + census_boost, 100
        )

        if final_leasing_score >= 70:
            final_leasing_intensity = "high"
        elif final_leasing_score >= 40:
            final_leasing_intensity = "moderate"
        else:
            final_leasing_intensity = "low"

        all_leasing_evidence = leasing_evidence + census_boost_evidence

        emit(
            f"8. Leasing intensity: {final_leasing_intensity} "
            f"({final_leasing_score}/100)",
            " | ".join(all_leasing_evidence[:3]),
            "🔴" if final_leasing_intensity == "high"
            else "🟡" if final_leasing_intensity == "moderate"
            else "🟢"
        )

        # ── 9. Automation Urgency ────────────────────────────
        census_urgency  = census_data.get("automation_urgency", "unknown")

        # Combine Census + FRED signals
        automation_urgency = self._compute_automation_urgency(
            census_urgency,
            final_leasing_intensity,
            rent_pressure,
            unemployment_level,
            pop_trend_direction,
        )

        urgency_evidence = []
        if automation_urgency == "high":
            urgency_evidence.append(
                "High leasing volume + market pressure = "
                "urgent need for 24/7 automated leasing"
            )
        elif automation_urgency == "medium":
            urgency_evidence.append(
                "Moderate market conditions — "
                "automation would improve efficiency"
            )
        else:
            urgency_evidence.append(
                "Lower market pressure — "
                "automation valuable but not urgent"
            )

        emit(
            f"9. Automation urgency: {automation_urgency}",
            urgency_evidence[0],
            "⚡" if automation_urgency == "high" else "🕐"
        )

        # ── HUD pitch implications ───────────────────────────
        hud_implications = hud_data.get("pitch_implications", [])

        emit(
            f"HUD product fit: {hud_product_fit}",
            " | ".join(hud_implications[:2]),
            "📌"
        )

        return {
            "city":                     city,
            "state":                    state_,

            # 1. Renter population
            "renter_population":        renter_population,
            "renter_percentage":        renter_percentage,
            "total_population":         total_population,
            "market_size":              market_size,
            "geography_level":          geography_level,

            # 2. City vacancy
            "city_vacancy_rate":        city_vacancy_rate,
            "vacant_units":             vacant_units,

            # 3. Rent growth
            "rent_pressure":            rent_pressure,
            "rent_yoy_change":          rent_yoy,
            "rent_series":              rent_series,
            "rent_geography":           "national",

            # 4. Employment
            "unemployment_rate":        unemployment_rate,
            "unemployment_level":       unemployment_level,
            "unemployment_geography":   unemployment_geo,

            # 5. Population growth
            "population_trend":         pop_trend_direction,
            "population_change_pct":    pop_change_pct,
            "population_series":        pop_series,

            # 6. Product line
            "median_income":            median_income,
            "asset_type_signal":        asset_type_signal,
            "fmr_2br":                  fmr_2br,
            "affordable_signal":        affordable_signal,
            "eliseai_product_line":     product_line["product_line"],
            "eliseai_pitch_focus":      product_line["pitch_focus"],
            "product_line_evidence":    product_line["evidence"],

            # 7. Market health
            "market_health_score":      market_health_score,
            "market_health":            market_health,

            # 8. Leasing intensity
            "leasing_intensity":        final_leasing_intensity,
            "leasing_intensity_score":  final_leasing_score,
            "leasing_intensity_evidence": all_leasing_evidence,

            # 9. Automation urgency
            "automation_urgency":       automation_urgency,
            "automation_urgency_evidence": urgency_evidence,

            # HUD
            "hud_product_fit":          hud_product_fit,
            "hud_pitch_implications":   hud_implications,

            # Raw data for scoring agent
            "census_data":              census_data,
            "fred_data":                fred_data,
            "hud_data":                 hud_data,
        }

    # ── Helper Methods ──────────────────────────────────────────

    def _determine_product_line(
        self,
        fmr_2br: float,
        median_income: int,
        renter_pct: float,
        city: str,
    ) -> dict:
        """
        Determine EliseAI product line from market signals.
        Maps to EliseAI's actual product lines:
        Conventional, Student Housing, Affordable, Single-Family
        """

        # Student housing markets
        student_cities = [
            "college station", "ann arbor", "champaign",
            "boulder", "durham", "athens", "tuscaloosa",
            "gainesville", "tempe", "columbia", "madison",
            "iowa city", "oxford", "chapel hill", "berkeley",
        ]
        if any(c in city.lower() for c in student_cities):
            return {
                "product_line":  "student_housing",
                "pitch_focus":   "surge leasing season automation, "
                                 "renewal campaigns, 24/7 student support",
                "evidence":      f"University market: {city}",
            }

        # Affordable housing
        if fmr_2br and fmr_2br < 1200 and median_income < 50000:
            return {
                "product_line":  "affordable",
                "pitch_focus":   "fair housing compliance, 51-language support, "
                                 "cost reduction for subsidized portfolios",
                "evidence":      f"FMR ${fmr_2br} + median income ${median_income:,}",
            }

        # Workforce housing
        if fmr_2br and fmr_2br < 1800 and median_income < 75000:
            return {
                "product_line":  "conventional_workforce",
                "pitch_focus":   "operational efficiency, leasing automation, "
                                 "staff reduction",
                "evidence":      f"FMR ${fmr_2br} + median income ${median_income:,}",
            }

        # Low density — single family signal
        if renter_pct < 30:
            return {
                "product_line":  "single_family",
                "pitch_focus":   "maintenance automation, resident communication, "
                                 "scale without headcount",
                "evidence":      f"Low renter density {renter_pct}% — "
                                 f"likely single family market",
            }

        # Conventional / luxury
        return {
            "product_line":  "conventional",
            "pitch_focus":   "premium leasing experience, AI-guided tours, "
                             "resident experience, renewal automation",
            "evidence":      f"FMR ${fmr_2br} + median income ${median_income:,}",
        }

    def _compute_automation_urgency(
        self,
        census_urgency: str,
        leasing_intensity: str,
        rent_pressure: str,
        unemployment_level: str,
        population_trend: str,
    ) -> str:
        """
        Combine all market signals into automation urgency.
        High urgency = leasing teams overwhelmed = urgent EliseAI need.
        """
        score = 0

        if census_urgency == "high":        score += 30
        elif census_urgency == "medium":    score += 15

        if leasing_intensity == "high":     score += 30
        elif leasing_intensity == "moderate": score += 15

        if rent_pressure == "high":         score += 20
        elif rent_pressure == "moderate":   score += 10

        if unemployment_level in ["very_low", "low"]:
            score += 10

        if population_trend == "growing":   score += 10
        elif population_trend == "declining": score -= 10

        if score >= 60:     return "high"
        elif score >= 30:   return "medium"
        else:               return "low"

    def _empty_response(self) -> dict:
        return {
            "market_data": {
                "city":                     "",
                "state":                    "",
                "renter_population":        0,
                "renter_percentage":        0,
                "total_population":         0,
                "market_size":              "unknown",
                "geography_level":          "",
                "city_vacancy_rate":        0,
                "vacant_units":             0,
                "rent_pressure":            "unknown",
                "rent_yoy_change":          0,
                "rent_series":              None,
                "rent_geography":           "national",
                "unemployment_rate":        0,
                "unemployment_level":       "unknown",
                "unemployment_geography":   "unknown",
                "population_trend":         "unknown",
                "population_change_pct":    0,
                "population_series":        None,
                "median_income":            0,
                "asset_type_signal":        "unknown",
                "fmr_2br":                  0,
                "affordable_signal":        False,
                "eliseai_product_line":     "unknown",
                "eliseai_pitch_focus":      "",
                "product_line_evidence":    "",
                "market_health_score":      0,
                "market_health":            "unknown",
                "leasing_intensity":        "unknown",
                "leasing_intensity_score":  0,
                "leasing_intensity_evidence": [],
                "automation_urgency":       "unknown",
                "automation_urgency_evidence": [],
                "hud_product_fit":          "unknown",
                "hud_pitch_implications":   [],
                "census_data":              {},
                "fred_data":                {},
                "hud_data":                 {},
            }
        }


# ─── Singleton ──────────────────────────────────────────────────
market_agent = MarketAgent()