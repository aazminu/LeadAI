# backend/services/news_service.py

import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

NEWSAPI_BASE_URL = "https://newsapi.org/v2"


class NewsService:
    """
    Fetches recent news for companies and markets
    from NewsAPI. Used by Company Agent and Values Agent.
    Fails gracefully — returns empty dict on any error.
    """

    def __init__(self):
        self.api_key = settings.news_api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        # Look back 30 days
        self.from_date = (
            datetime.now() - timedelta(days=30)
        ).strftime("%Y-%m-%d")

    async def get_company_news(
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
                f"Searching news for {company_name}",
                "last 30 days",
                "📰"
            )
            articles = await self._fetch_articles(company_name)
            emit(
                f"Found {len(articles)} articles",
                company_name,
                "✅" if articles else "⚠️"
            )

            market_articles = []
            if city:
                emit(
                    f"Searching market news",
                    f"{city}, {state} multifamily real estate",
                    "🏘️"
                )
                market_articles = await self._fetch_articles(
                    f"{city} {state} multifamily real estate"
                )
                emit(
                    f"Found {len(market_articles)} market articles",
                    f"{city} {state}",
                    "✅" if market_articles else "⚠️"
                )

            result = self._synthesize(
                company_name,
                articles,
                market_articles,
                city,
                state
            )

            # Emit key signals found
            if result.get("is_expanding"):
                emit(
                    "Expansion signal detected",
                    result["expansion_signals"][0]["title"] if result["expansion_signals"] else "",
                    "📈"
                )
            if result.get("funding_signals"):
                emit(
                    "Funding signal detected",
                    result["funding_signals"][0]["title"] if result["funding_signals"] else "",
                    "💰"
                )
            if result.get("leadership_signals"):
                emit(
                    "Leadership change detected",
                    result["leadership_signals"][0]["title"] if result["leadership_signals"] else "",
                    "👔"
                )
            if result.get("has_pain_signals"):
                emit(
                    "Pain signals detected",
                    result["pain_signals"][0]["title"] if result["pain_signals"] else "",
                    "⚠️"
                )
            if result.get("has_esg_news"):
                emit(
                    "ESG signals detected",
                    result["esg_signals"][0]["title"] if result["esg_signals"] else "",
                    "🌱"
                )

            emit(
                f"Buying signal: {result['buying_signal']}",
                f"Score: {result['buying_signal_score']}/100",
                "🎯"
            )

            return result

        except Exception as e:
            logger.error(f"NewsService failed for {company_name}: {e}")
            return self._empty_response(company_name)

    async def _fetch_articles(
        self,
        query: str,
        page_size: int = 10
    ) -> list:
        """Fetch articles from NewsAPI."""
        try:
            response = await self.client.get(
                f"{NEWSAPI_BASE_URL}/everything",
                params={
                    "q":          query,
                    "from":       self.from_date,
                    "sortBy":     "relevancy",
                    "pageSize":   page_size,
                    "language":   "en",
                    "apiKey":     self.api_key,
                }
            )
            response.raise_for_status()
            data = response.json()
            return data.get("articles", [])

        except Exception as e:
            logger.warning(f"NewsAPI fetch failed for '{query}': {e}")
            return []

    def _synthesize(
        self,
        company_name: str,
        articles: list,
        market_articles: list,
        city: str,
        state: str,
    ) -> dict:
        """Analyze articles and extract signals."""

        # ── Signal detection keywords ───────────────────────
        expansion_keywords = [
            "acqui", "expand", "new properties",
            "new development", "new community",
            "growth", "portfolio", "opens"
        ]
        funding_keywords = [
            "funding", "raises", "investment",
            "capital", "series", "million", "billion"
        ]
        leadership_keywords = [
            "appoints", "names", "hires", "ceo",
            "president", "chief", "executive", "joins"
        ]
        tech_keywords = [
            "technology", "ai", "automation",
            "proptech", "digital", "software", "platform"
        ]
        pain_keywords = [
            "staffing", "shortage", "overwhelm",
            "lawsuit", "complaint", "slow", "understaffed"
        ]
        esg_keywords = [
            "sustainability", "esg", "green",
            "carbon", "environment", "diversity", "dei"
        ]

        # ── Analyze each article ────────────────────────────
        signals = {
            "expansion":    [],
            "funding":      [],
            "leadership":   [],
            "tech":         [],
            "pain":         [],
            "esg":          [],
        }

        for article in articles:
            title = (article.get("title") or "").lower()
            description = (article.get("description")or "").lower()
            text = f"{title} {description}"

            for keyword in expansion_keywords:
                if keyword in text:
                    signals["expansion"].append({
                        "title":       article.get("title"),
                        "date":        article.get("publishedAt", "")[:10],
                        "source":      article.get("source", {}).get("name"),
                        "url":         article.get("url"),
                        "keyword":     keyword,
                    })
                    break

            for keyword in funding_keywords:
                if keyword in text:
                    signals["funding"].append({
                        "title":   article.get("title"),
                        "date":    article.get("publishedAt", "")[:10],
                        "source":  article.get("source", {}).get("name"),
                        "keyword": keyword,
                    })
                    break

            for keyword in leadership_keywords:
                if keyword in text:
                    signals["leadership"].append({
                        "title":   article.get("title"),
                        "date":    article.get("publishedAt", "")[:10],
                        "source":  article.get("source", {}).get("name"),
                        "keyword": keyword,
                    })
                    break

            for keyword in tech_keywords:
                if keyword in text:
                    signals["tech"].append({
                        "title":   article.get("title"),
                        "date":    article.get("publishedAt", "")[:10],
                        "source":  article.get("source", {}).get("name"),
                        "keyword": keyword,
                    })
                    break

            for keyword in pain_keywords:
                if keyword in text:
                    signals["pain"].append({
                        "title":   article.get("title"),
                        "date":    article.get("publishedAt", "")[:10],
                        "source":  article.get("source", {}).get("name"),
                        "keyword": keyword,
                    })
                    break

            for keyword in esg_keywords:
                if keyword in text:
                    signals["esg"].append({
                        "title":   article.get("title"),
                        "date":    article.get("publishedAt", "")[:10],
                        "source":  article.get("source", {}).get("name"),
                        "keyword": keyword,
                    })
                    break

        # ── Buying signal score ─────────────────────────────
        buying_signal_score = 0
        if signals["expansion"]:    buying_signal_score += 30
        if signals["funding"]:      buying_signal_score += 25
        if signals["leadership"]:   buying_signal_score += 20
        if signals["tech"]:         buying_signal_score += 15
        if signals["pain"]:         buying_signal_score += 10

        buying_signal_score = min(buying_signal_score, 100)

        # ── Classify buying signal ──────────────────────────
        if buying_signal_score >= 50:
            buying_signal = "strong"
        elif buying_signal_score >= 25:
            buying_signal = "moderate"
        elif buying_signal_score > 0:
            buying_signal = "weak"
        else:
            buying_signal = "none"

        # ── Top headlines ───────────────────────────────────
        top_headlines = [
            {
                "title":  a.get("title"),
                "date":   a.get("publishedAt", "")[:10],
                "source": a.get("source", {}).get("name"),
                "url":    a.get("url"),
            }
            for a in articles[:3]
        ]

        # ── Market headlines ────────────────────────────────
        market_headlines = [
            {
                "title":  a.get("title"),
                "date":   a.get("publishedAt", "")[:10],
                "source": a.get("source", {}).get("name"),
            }
            for a in market_articles[:3]
        ]

        return {
            "company_name":         company_name,
            "total_articles_found": len(articles),
            "top_headlines":        top_headlines,
            "market_headlines":     market_headlines,

            # Signals
            "expansion_signals":    signals["expansion"][:3],
            "funding_signals":      signals["funding"][:2],
            "leadership_signals":   signals["leadership"][:2],
            "tech_signals":         signals["tech"][:2],
            "pain_signals":         signals["pain"][:2],
            "esg_signals":          signals["esg"][:2],

            # Summary scores
            "buying_signal_score":  buying_signal_score,
            "buying_signal":        buying_signal,
            "is_tech_forward":      len(signals["tech"]) > 0,
            "has_esg_news":         len(signals["esg"]) > 0,
            "has_pain_signals":     len(signals["pain"]) > 0,
            "is_expanding":         len(signals["expansion"]) > 0,

            "data_source": "NewsAPI",
        }

    def _empty_response(self, company_name: str) -> dict:
        return {
            "company_name":         company_name,
            "total_articles_found": 0,
            "top_headlines":        [],
            "market_headlines":     [],
            "expansion_signals":    [],
            "funding_signals":      [],
            "leadership_signals":   [],
            "tech_signals":         [],
            "pain_signals":         [],
            "esg_signals":          [],
            "buying_signal_score":  0,
            "buying_signal":        "none",
            "is_tech_forward":      False,
            "has_esg_news":         False,
            "has_pain_signals":     False,
            "is_expanding":         False,
            "data_source":          "unavailable",
        }

    async def close(self):
        await self.client.aclose()


# ─── Singleton ─────────────────────────────────────────────────
news_service = NewsService()