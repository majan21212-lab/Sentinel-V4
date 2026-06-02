import datetime
import pytz

class MarketHours:
    def __init__(self):
        # Default to UTC for global consistency
        self.tz = pytz.UTC

    def is_market_open(self, symbol: str) -> bool:
        """
        Checks if the market for a given symbol is currently open.
        """
        now = datetime.datetime.now(self.tz)
        weekday = now.weekday()  # Monday is 0, Sunday is 6
        hour = now.hour
        
        # Crypto is 24/7
        crypto_keywords = ["BTC", "ETH", "SOL", "DOT", "LINK", "AVAX"]
        if any(k in symbol.upper() for k in crypto_keywords):
            return True

        # Forex & Metals (XAU, XAG)
        # Generally: Sunday 22:00 UTC to Friday 21:00 UTC
        
        # Friday Close: 21:00 UTC
        if weekday == 4: # Friday
            if hour >= 21:
                return False
        
        # Saturday: Closed
        if weekday == 5:
            return False
            
        # Sunday Open: 22:00 UTC
        if weekday == 6:
            if hour < 22:
                return False
                
        # Weekdays (Mon-Thu) are generally open
        # Note: Some assets like Gold (XAU) have a 1-hour daily break (21:00-22:00 UTC)
        if "XAU" in symbol.upper() or "XAG" in symbol.upper():
            if hour == 21:
                return False
                
        return True

    def get_market_status(self, symbol: str) -> str:
        if self.is_market_open(symbol):
            return "OPEN"
        return "CLOSED"

market_hours = MarketHours()
