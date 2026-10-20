import os
import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None

SENTIMENT_ENABLED = os.getenv("SENTIMENT_ENABLED", "false").lower() == "true"
SENTIMENT_API_KEY = os.getenv("SENTIMENT_API_KEY", "")
CACHE_TTL_SECONDS = int(os.getenv("SENTIMENT_CACHE_TTL", "900"))  # 15 min


class SentimentAnalyzer:
    """Analiza sentimiento de mercado para filtrar señales de trading.

    Usa NewsAPI (o compatible) cuando SENTIMENT_API_KEY está configurada.
    Si no hay API key o el servicio falla, devuelve NEUTRAL (no filtra).
    """

    POSITIVE_KEYWORDS = [
        "surge", "rally", "bullish", "soar", "gain", "record", "adopt", "approval",
        "etf", "partnership", "upgrade", "breakout", "moon", "buy", "accumulate",
        "optimistic", "recover", "high", "boost", "institutional",
    ]
    NEGATIVE_KEYWORDS = [
        "crash", "plunge", "bearish", "dump", "hack", "ban", "lawsuit", "sec",
        "fraud", "scam", "sell-off", "liquidation", "fear", "collapse", "warning",
        "investigation", "restrict", "delist", "bankrupt", "loss",
    ]

    def __init__(self):
        self._cache = {}
        self._cache_time = {}

    def _fetch_news(self, symbol: str) -> list:
        if requests is None or not SENTIMENT_API_KEY:
            return []
        base = symbol.replace("USDT", "").replace("BUSD", "")
        query = f"{base} cryptocurrency"
        try:
            resp = requests.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 20,
                    "from": (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d"),
                },
                headers={"X-Api-Key": SENTIMENT_API_KEY},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Sentiment API status %s", resp.status_code)
                return []
            return resp.json().get("articles", [])
        except Exception as e:
            logger.warning("Sentiment fetch failed: %s", e)
            return []

    def _score_text(self, text: str) -> int:
        text = text.lower()
        score = 0
        for kw in self.POSITIVE_KEYWORDS:
            if kw in text:
                score += 1
        for kw in self.NEGATIVE_KEYWORDS:
            if kw in text:
                score -= 1
        return score

    def get_sentiment(self, symbol: str) -> dict:
        """Devuelve {score, label, articles, source} para el símbolo."""
        if not SENTIMENT_ENABLED:
            return {"score": 0, "label": "NEUTRAL", "articles": 0, "source": "disabled"}

        now = time.time()
        if symbol in self._cache and (now - self._cache_time.get(symbol, 0)) < CACHE_TTL_SECONDS:
            return self._cache[symbol]

        articles = self._fetch_news(symbol)
        if not articles:
            result = {"score": 0, "label": "NEUTRAL", "articles": 0, "source": "unavailable"}
            self._cache[symbol] = result
            self._cache_time[symbol] = now
            return result

        total_score = 0
        for art in articles:
            title = art.get("title") or ""
            desc = art.get("description") or ""
            total_score += self._score_text(f"{title} {desc}")

        if total_score > 2:
            label = "POSITIVE"
        elif total_score < -2:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"

        result = {
            "score": total_score,
            "label": label,
            "articles": len(articles),
            "source": "newsapi",
        }
        self._cache[symbol] = result
        self._cache_time[symbol] = now
        return result

    def filter_signal(self, symbol: str, signal: str) -> tuple[str, str]:
        """Ajusta una señal BUY/SELL según el sentimiento.

        Devuelve (señal_ajustada, razón).
        - BUY en sentimiento NEGATIVE fuerte -> HOLD (no comprar contra el mercado)
        - SELL en sentimiento POSITIVE fuerte -> HOLD (no vender contra el mercado)
        """
        if not SENTIMENT_ENABLED or signal == "HOLD":
            return signal, ""

        sentiment = self.get_sentiment(symbol)
        label = sentiment["label"]

        if signal == "BUY" and label == "NEGATIVE":
            return "HOLD", f"sentimiento negativo (score={sentiment['score']})"
        if signal == "SELL" and label == "POSITIVE":
            return "HOLD", f"sentimiento positivo (score={sentiment['score']})"
        return signal, ""


_analyzer = None


def get_analyzer() -> SentimentAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer()
    return _analyzer