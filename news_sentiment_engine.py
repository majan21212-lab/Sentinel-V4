import requests
import logging
import re

log = logging.getLogger(__name__)

class NewsSentimentEngine:
    def __init__(self):
        self.news_api_url = "https://cryptopanic.com/api/v1/posts/?auth_token=YOUR_TOKEN&public=true" # Placeholder
        self.bias_map = {
            "hawkish": -0.5, # USD Strong, Crypto/Gold Weak
            "dovish": 0.5,   # USD Weak, Crypto/Gold Strong
            "bullish": 0.5,
            "bearish": -0.5,
            "crash": -1.0,
            "moon": 1.0,
            "inflation": -0.5,
            "rate cut": 0.8
        }
        self.current_global_bias = 0.0

    def analyze_headlines(self, headlines: list[str]):
        """
        Performs keyword-based sentiment analysis on a list of headlines.
        """
        score = 0.0
        for text in headlines:
            text = text.lower()
            for word, weight in self.bias_map.items():
                if word in text:
                    score += weight
        
        # Normalize score
        if score > 2.0: self.current_global_bias = 1.0 # Very Bullish
        elif score < -2.0: self.current_global_bias = -1.0 # Very Bearish
        else: self.current_global_bias = score / 2.0
        
        log.info(f"📰 News Sentiment Bias: {self.current_global_bias:+.2f}")

    def get_news_multiplier(self, direction: str, symbol: str) -> float:
        """
        Adjusts risk based on the alignment of the trade with current news sentiment.
        """
        if direction == "LONG" and self.current_global_bias < -0.5:
            return 0.5 # Scale down longs in bearish news
        if direction == "SHORT" and self.current_global_bias > 0.5:
            return 0.5 # Scale down shorts in bullish news
            
        return 1.0

# Singleton instance
news_sentiment = NewsSentimentEngine()
