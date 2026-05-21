import logging
import os
import json
from execution_layer import ExecutionLayer
from ml_validator import MLValidator
import threading

log = logging.getLogger(__name__)

# --- SHARED STATE PERSISTENCE ---
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared_state.json")
STATE_LOCK = threading.Lock()

_LAST_VALID_STATE = None

def load_shared_state():
    global _LAST_VALID_STATE
    defaults = {
        "prices": {},
        "status": "INITIALIZING",
        "signals": [],
        "auto_trade": False,
        "demo_mode": True,
        "active_profile": "CONSERVATIVE",
        "strategy_mode": "PATTERN",
        "active_trades": [],
        "pending_orders": [],
        "trade_history": [],
        "active_markets": ["XAUUSDm", "BTCUSDm"],
        "market_configs": {
            "XAUUSDm": {"enabled": True, "strategy": "JEWEL_ELITE"},
            "BTCUSDm": {"enabled": True, "strategy": "JEWEL_ELITE"}
        },
        "is_bot_active": False,
        "kill_switch": False,
        "demo_balance": 200.00,
        "execution_bias": "TREND",
        "risk_config": {},
        "analytics": {},
        "user_profile": {
            "name": "Commander",
            "username": "admin",
            "password": "password123",
            "photo_url": ""
        }
    }
    if os.path.exists(STATE_FILE):
        with STATE_LOCK:
            try:
                with open(STATE_FILE, "r") as f:
                    saved = json.load(f)
                    defaults.update(saved)
                    _LAST_VALID_STATE = defaults
                    return defaults
            except Exception as e:
                # log.warning(f"State: Error loading state: {e}") # Silenced to avoid spamming logs during normal file contention
                if _LAST_VALID_STATE is not None:
                    return _LAST_VALID_STATE
            
    return defaults

def save_shared_state(data):
    with STATE_LOCK:
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            log.error(f"State: Error saving state: {e}")

SHARED_DATA = load_shared_state()

_executor = None
_ml_validator = None

def get_executor() -> ExecutionLayer:
    global _executor
    if _executor is None:
        _executor = ExecutionLayer()
        try:
            if os.path.exists("risk_settings.json"):
                with open("risk_settings.json", "r") as f:
                    config_data = json.load(f)
                    if hasattr(_executor.risk_engine.config, 'model_validate'):
                        _executor.risk_engine.config = type(_executor.risk_engine.config)(**config_data)
                    else:
                        _executor.risk_engine.update_config(config_data)
        except Exception as e:
            log.warning(f"State: Error loading risk settings: {e}")
            
    return _executor

def get_ml_validator() -> MLValidator:
    global _ml_validator
    if _ml_validator is None:
        _ml_validator = MLValidator()
    return _ml_validator

def update_shared_data(key, value):
    global SHARED_DATA
    if key in SHARED_DATA:
        SHARED_DATA[key] = value
        save_shared_state(SHARED_DATA)

# ── Deduplication helpers ──────────────────────────────────────────────────────

# In-memory set of ticket IDs already moved to trade_history this session.
# Prevents the same closed trade from being appended on every polling cycle.
_LOGGED_CLOSED_TICKETS: set = set()

def record_closed_trade(trade: dict):
    """
    Safely moves a completed trade into trade_history exactly ONCE.
    Call this whenever a trade's status transitions to CLOSED/STOPPED/TP.

    Parameters
    ----------
    trade : dict  — the trade dict (must contain a 'ticket' key).
    """
    global SHARED_DATA, _LOGGED_CLOSED_TICKETS
    ticket = str(trade.get("ticket", ""))
    if not ticket or ticket in _LOGGED_CLOSED_TICKETS:
        return  # already logged — skip

    _LOGGED_CLOSED_TICKETS.add(ticket)
    history = SHARED_DATA.get("trade_history", [])
    # Prepend and cap at 200 entries
    history.insert(0, dict(trade))
    SHARED_DATA["trade_history"] = history[:200]
    save_shared_state(SHARED_DATA)
    log.info(f"📋 Trade #{ticket} moved to history (total: {len(SHARED_DATA['trade_history'])})")

