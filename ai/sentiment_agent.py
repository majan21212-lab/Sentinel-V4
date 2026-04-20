import os
import httpx
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SentimentAgent:
    """Advanced Sentiment Analysis Agent using Alpha Vantage News Sentiment API."""
    
    def __init__(self):
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.base_url = "https://www.alphavantage.co/query"

    async def get_market_sentiment(self, symbol: str) -> Dict[str, Any]:
        """
        Fetches real-time news sentiment for a specific symbol/market.
        Returns a score from -1.0 (Bearish) to 1.0 (Bullish).
        """
        if not self.api_key:
            logger.warning("ALPHA_VANTAGE_API_KEY not found. Sentiment analysis skipped (Returning Neutral).")
            return {"score": 0.0, "label": "NEUTRAL", "source": "NONE"}

        # Mapping for better Alpha Vantage queries
        query_ticker = symbol.replace("m", "") # remove Exness/Broker suffix
        if "XAU" in query_ticker: query_ticker = "CRYPTO:BTC,GOLD" # Gold often tied to broad market or BTC sentiment in simple APIs

        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": query_ticker,
            "apikey": self.api_key,
            "sort": "LATEST"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.base_url, params=params)
                data = response.json()

                if "feed" in data and len(data["feed"]) > 0:
                    # Average the sentiment score of the latest 5 articles
                    articles = data["feed"][:5]
                    avg_score = sum(float(a["overall_sentiment_score"]) for a in articles) / len(articles)
                    
                    label = "NEUTRAL"
                    if avg_score > 0.15: label = "BULLISH"
                    elif avg_score < -0.15: label = "BEARISH"

                    logger.info(f"Sentiment for {symbol}: {label} ({avg_score:.2f})")
                    return {
                        "score": avg_score,
                        "label": label,
                        "source": "AlphaVantage"
                    }
                
                logger.warning(f"No news feed found for {symbol}. Returning neutral sentiment.")
                return {"score": 0.0, "label": "NEUTRAL", "source": "API_EMPTY"}

        except Exception as e:
            logger.error(f"Sentiment API Request Failed: {str(e)}")
            return {"score": 0.0, "label": "NEUTRAL", "source": "ERROR"}

    def is_aligned(self, direction: str, sentiment: Dict[str, Any]) -> bool:
        """Checks if the proposed trade direction aligns with current sentiment."""
        score = sentiment.get("score", 0.0)
        
        # High-conviction filters
        if direction == "LONG" and score < -0.35:
            logger.warning(f"Trade BLOCKED: LONG requested during Extreme Bearish sentiment ({score})")
            return False
        if direction == "SHORT" and score > 0.35:
            logger.warning(f"Trade BLOCKED: SHORT requested during Extreme Bullish sentiment ({score})")
            return False
            
        return True
