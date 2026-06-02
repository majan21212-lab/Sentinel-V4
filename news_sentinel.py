"""
news_sentinel.py — TradeBot v3.1 Elite
Real-time economic news scanner powered by DeepSeek AI.
Fetches the ForexFactory economic calendar and live headlines,
then uses DeepSeek to classify risk level before each trade.
"""

import os
import re
import json
import logging
import threading
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
DEEPSEEK_API_KEY   = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL   = "https://api.deepseek.com/v1/chat/completions"
BLOCK_WINDOW_MINS  = 30   # block trading N minutes before/after a high-impact event
REFRESH_INTERVAL   = 600  # re-fetch calendar every 10 minutes

# Currency codes embedded in each symbol (e.g. EURUSDm → EUR, USD)
_SYMBOL_CURRENCIES = {
    "EURUSDm": ["EUR", "USD"],
    "GBPUSDm": ["GBP", "USD"],
    "USDJPYm": ["USD", "JPY"],
    "XAUUSDm": ["USD", "XAU", "GOLD"],
    "XAGUSDm": ["USD", "XAG", "SILVER"],
    "BTCUSDm": ["BTC", "USD", "CRYPTO"],
    "ETHUSDm": ["ETH", "USD", "CRYPTO"],
    "AAPLm":   ["USD", "STOCKS"],
    "TSLAm":   ["USD", "STOCKS"],
    "US30m":   ["USD", "STOCKS", "INDEX"],
    "USTECm":  ["USD", "STOCKS", "INDEX"],
    "USOILm":  ["USD", "OIL"],
}

# High-impact event keywords — these trigger a block even without AI classification
_HIGH_IMPACT_KEYWORDS = [
    "non-farm", "nfp", "fomc", "federal reserve", "interest rate decision",
    "cpi", "inflation", "gdp", "employment", "unemployment", "payroll",
    "central bank", "ecb", "boj", "boe", "rba", "snb",
    "retail sales", "pmi manufacturing", "pmi services",
]


# ── Shared state (refreshed by background thread) ────────────────────────────
_state_lock      = threading.Lock()
_events: list    = []          # list of dicts from ForexFactory calendar
_headlines: list = []          # list of news headline strings
_last_refresh    = None        # datetime of last successful refresh
_ai_cache: dict  = {}          # symbol → (verdict, expires_at)


# ── Public API ────────────────────────────────────────────────────────────────

def is_safe_to_trade(symbol: str) -> tuple[bool, str]:
    """
    Main entry point called by execution_layer before every trade.
    Returns (True, "") if safe, or (False, reason_string) if blocked.
    """
    _ensure_running()

    # 1. Check upcoming high-impact economic events
    blocked, reason = _check_calendar_events(symbol)
    if blocked:
        return False, reason

    # 2. Check AI sentiment analysis (uses cache to avoid spamming API)
    if DEEPSEEK_API_KEY:
        blocked, reason = _check_ai_sentiment(symbol)
        if blocked:
            return False, reason

    return True, ""


def get_upcoming_events(hours_ahead: int = 4) -> list[dict]:
    """Return a list of economic events in the next N hours (for the dashboard)."""
    _ensure_running()
    cutoff = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
    now    = datetime.now(timezone.utc)
    with _state_lock:
        return [e for e in _events if now <= e.get("time_utc", now) <= cutoff]


def get_news_summary() -> dict:
    """Return current news state for the dashboard."""
    return {
        "last_refresh":    _last_refresh.isoformat() if _last_refresh else "Never",
        "events_loaded":   len(_events),
        "headlines_loaded": len(_headlines),
    }


# ── Calendar fetching ─────────────────────────────────────────────────────────

def _fetch_forexfactory_rss() -> list[dict]:
    """
    Fetch the ForexFactory RSS feed and parse upcoming economic events.
    Falls back to an empty list if the feed is unreachable.
    """
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
    events = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        for item in root.iter("event"):
            title    = _text(item, "title")
            country  = _text(item, "country")
            impact   = _text(item, "impact")
            date_str = _text(item, "date")
            time_str = _text(item, "time")

            if not date_str:
                continue

            # Parse event time — FF uses US Eastern time (EST/EDT)
            try:
                raw = f"{date_str} {time_str}".strip()
                # Try to parse; fallback to midnight UTC
                try:
                    dt_naive = datetime.strptime(raw, "%m-%d-%Y %I:%M%p")
                except ValueError:
                    dt_naive = datetime.strptime(date_str, "%m-%d-%Y")

                # ForexFactory times are US Eastern — add 4h offset to get UTC (EDT)
                dt_utc = dt_naive.replace(tzinfo=timezone.utc) + timedelta(hours=4)
            except Exception:
                continue

            events.append({
                "title":    title.lower() if title else "",
                "country":  country.upper() if country else "",
                "impact":   impact.upper() if impact else "",   # HIGH | MEDIUM | LOW
                "time_utc": dt_utc,
            })

        log.info("NewsSentinel: loaded %d events from ForexFactory", len(events))
    except Exception as exc:
        log.warning("NewsSentinel: ForexFactory RSS fetch failed: %s", exc)

    return events


def _fetch_headlines() -> list[str]:
    """
    Fetch recent financial headlines from a free public RSS feed.
    Uses Reuters business feed (no API key needed).
    """
    urls = [
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
        "https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml",
    ]
    headlines = []
    for url in urls:
        try:
            resp = requests.get(url, timeout=8)
            root = ET.fromstring(resp.text)
            for item in root.iter("item"):
                title = _text(item, "title")
                if title:
                    headlines.append(title.lower())
            if headlines:
                break
        except Exception:
            continue

    log.info("NewsSentinel: loaded %d headlines", len(headlines))
    return headlines[:50]   # keep only the most recent 50


# ── Calendar risk check ───────────────────────────────────────────────────────

def _check_calendar_events(symbol: str) -> tuple[bool, str]:
    """Block if a HIGH-impact event is within the BLOCK_WINDOW_MINS window."""
    now     = datetime.now(timezone.utc)
    window  = timedelta(minutes=BLOCK_WINDOW_MINS)
    currencies = _SYMBOL_CURRENCIES.get(symbol, ["USD"])

    with _state_lock:
        for event in _events:
            impact   = event.get("impact", "")
            country  = event.get("country", "")
            title    = event.get("title", "")
            evt_time = event.get("time_utc")

            if not evt_time:
                continue

            # Only care about HIGH impact events
            if impact not in ("HIGH",):
                # Also catch keyword-matched events even if impact isn't tagged
                is_keyword = any(kw in title for kw in _HIGH_IMPACT_KEYWORDS)
                if not is_keyword:
                    continue

            # Check if event is within the time window (before OR after)
            time_diff = abs((evt_time - now).total_seconds() / 60)
            if time_diff > BLOCK_WINDOW_MINS:
                continue

            # Check if the event currency is relevant to the traded symbol
            is_relevant = (
                country in currencies or
                any(c in country for c in currencies) or
                "USD" in currencies  # USD events affect almost everything
            )

            if is_relevant:
                mins_away = int((evt_time - now).total_seconds() / 60)
                direction = "in" if mins_away >= 0 else f"{abs(mins_away)} min ago"
                reason = (
                    f"🚨 HIGH-IMPACT EVENT: '{event['title'].upper()}' "
                    f"({country}) {direction} {abs(mins_away)} min. Trading BLOCKED."
                )
                return True, reason

    return False, ""


# ── AI Sentiment check ────────────────────────────────────────────────────────

def _check_ai_sentiment(symbol: str) -> tuple[bool, str]:
    """
    Ask DeepSeek to assess if current headlines make this symbol dangerous to trade.
    Results are cached for 15 minutes to preserve API quota.
    """
    global _ai_cache

    now = datetime.now(timezone.utc)
    cache_entry = _ai_cache.get(symbol)
    if cache_entry:
        verdict, expires_at = cache_entry
        if now < expires_at:
            # Return cached result
            if verdict == "BLOCK":
                return True, f"🧠 AI Sentiment: Market conditions unfavorable for {symbol} (cached)."
            return False, ""

    # Build a short news summary for DeepSeek
    with _state_lock:
        sample = _headlines[:15]

    if not sample:
        return False, ""   # No headlines → don't block

    news_text = "\n".join(f"- {h}" for h in sample)
    currencies = _SYMBOL_CURRENCIES.get(symbol, ["USD"])

    prompt = f"""You are a professional forex risk analyst. 
Given these recent financial headlines, assess if it is SAFE or RISKY to open a new trade on {symbol} 
(currencies involved: {', '.join(currencies)}).

Headlines:
{news_text}

Respond with ONLY one word: SAFE or BLOCK.
- BLOCK if there is extreme fear, a major crisis, a central bank surprise, or a geopolitical shock affecting these currencies.
- SAFE in all other cases. When in doubt, say SAFE.
"""

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model":      "deepseek-chat",
                "messages":   [{"role": "user", "content": prompt}],
                "max_tokens": 5,
                "temperature": 0,
            },
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()["choices"][0]["message"]["content"].strip().upper()
        verdict = "BLOCK" if "BLOCK" in raw else "SAFE"

    except Exception as exc:
        log.warning("NewsSentinel: DeepSeek API error: %s — defaulting to SAFE", exc)
        verdict = "SAFE"

    # Cache result for 15 minutes
    _ai_cache[symbol] = (verdict, now + timedelta(minutes=15))
    log.info("NewsSentinel: AI verdict for %s = %s", symbol, verdict)

    if verdict == "BLOCK":
        return True, f"🧠 AI Sentiment: Market conditions unfavorable for {symbol} right now."
    return False, ""


# ── Background refresh thread ─────────────────────────────────────────────────

_thread_started = False

def _ensure_running():
    global _thread_started
    if not _thread_started:
        _thread_started = True
        t = threading.Thread(target=_refresh_loop, daemon=True, name="NewsSentinel")
        t.start()
        log.info("NewsSentinel: background refresh thread started.")
        # Do an immediate first fetch so data is ready right away
        _do_refresh()


def _refresh_loop():
    """Background thread: refresh news every REFRESH_INTERVAL seconds."""
    while True:
        time.sleep(REFRESH_INTERVAL)
        _do_refresh()


def _do_refresh():
    global _events, _headlines, _last_refresh
    try:
        new_events    = _fetch_forexfactory_rss()
        new_headlines = _fetch_headlines()
        with _state_lock:
            _events    = new_events
            _headlines = new_headlines
            _last_refresh = datetime.now(timezone.utc)
    except Exception as exc:
        log.warning("NewsSentinel: refresh error: %s", exc)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _text(element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""


# ── Module self-test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Fetching ForexFactory calendar...")
    events = _fetch_forexfactory_rss()
    print(f"Loaded {len(events)} events.")
    for e in events[:5]:
        print(f"  {e['time_utc']} | {e['impact']:6s} | {e['country']:5s} | {e['title']}")

    print("\nFetching headlines...")
    headlines = _fetch_headlines()
    print(f"Loaded {len(headlines)} headlines.")
    for h in headlines[:5]:
        print(f"  {h}")

    print("\nSafety check for XAUUSDm:")
    safe, reason = _check_calendar_events("XAUUSDm")
    print(f"  Blocked={safe}, Reason={reason or 'None'}")
