import requests
import logging

log = logging.getLogger(__name__)

class SentimentEngine:
    def __init__(self):
        self.fear_greed_url = "https://api.alternative.me/fng/"
        self.current_sentiment = "NEUTRAL"
        self.score = 50
        self.update_sentiment()

    def update_sentiment(self):
        """Fetches the latest Fear & Greed index score."""
        try:
            response = requests.get(self.fear_greed_url, timeout=10)
            data = response.json()
            if data and "data" in data:
                fng = data["data"][0]
                self.score = int(fng["value"])
                self.current_sentiment = fng["value_classification"].upper()
                log.info(f"📊 Market Sentiment: {self.current_sentiment} ({self.score}/100)")
        except Exception as e:
            log.error(f"Sentiment Fetch Error: {e}")

    def get_bias_multiplier(self, direction: str) -> float:
        """
        Returns a risk multiplier based on market sentiment.
        - Extreme Fear (< 25): Scale down Shorts (dangerous bottom)
        - Extreme Greed (> 75): Scale down Longs (dangerous top)
        """
        if self.score <= 25 and direction == "SHORT":
            return 0.5 # High risk of reversal, reduce short size
        if self.score >= 75 and direction == "LONG":
            return 0.5 # High risk of correction, reduce long size
            
        return 1.0

# Singleton instance
sentiment_engine = SentimentEngine()
