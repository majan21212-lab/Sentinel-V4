import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import logging
import os

log = logging.getLogger(__name__)

class NewsFilter:
    def __init__(self, cache_ttl_minutes=180):
        self.url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
        self.events = []
        self.last_update = None
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)

    def update_events(self):
        """Fetches the latest news events from ForexFactory."""
        try:
            if self.last_update and (datetime.now() - self.last_update < self.cache_ttl):
                return

            log.info("📅 Fetching fresh Economic Calendar from ForexFactory...")
            response = requests.get(self.url, timeout=10)
            if response.status_code != 200:
                log.error(f"Failed to fetch news: {response.status_code}")
                return

            root = ET.fromstring(response.content)
            new_events = []
            for item in root.findall('event'):
                event = {
                    "title": item.find('title').text,
                    "country": item.find('country').text,
                    "date": item.find('date').text,
                    "time": item.find('time').text,
                    "impact": item.find('impact').text, # High, Medium, Low
                }
                
                # ForexFactory format: 05-02-2026 8:30am
                dt_str = f"{event['date']} {event['time']}"
                try:
                    # Note: ForexFactory XML is typically in ET (New York) time.
                    # We handle the offset or assume system time alignment for now.
                    event['datetime'] = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                    new_events.append(event)
                except Exception as e:
                    continue

            self.events = new_events
            self.last_update = datetime.now()
            log.info(f"✅ News Filter: Loaded {len(self.events)} events for the week.")
        except Exception as e:
            log.error(f"News Filter Update Error: {e}")

    def is_volatile_now(self, symbol: str, buffer_minutes=30, min_impact="High"):
        """Checks if a high-impact news event for the symbol's currency is nearby."""
        self.update_events()
        
        now = datetime.now()
        # Extract currencies from symbol (e.g. XAUUSDm -> XAU, USD)
        relevant_currencies = []
        for curr in ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "NZD"]:
            if curr in symbol:
                relevant_currencies.append(curr)
        
        # Gold/Silver/Oil usually move on USD news
        if any(x in symbol for x in ["XAU", "XAG", "GOLD", "OIL", "US30", "NAS100"]):
            relevant_currencies.append("USD")

        for event in self.events:
            if event['country'] in relevant_currencies:
                # Impact level filter
                impact_levels = {"High": 3, "Medium": 2, "Low": 1}
                if impact_levels.get(event['impact'], 0) < impact_levels.get(min_impact, 3):
                    continue

                diff = abs((event['datetime'] - now).total_seconds() / 60)
                if diff <= buffer_minutes:
                    return True, f"{event['impact']} Impact: {event['title']} ({event['country']})"
                    
        return False, None

# Singleton instance
news_filter = NewsFilter()
