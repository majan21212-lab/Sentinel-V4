import logging
import os
import json
from execution_layer import ExecutionLayer
from ml_validator import MLValidator
from trailing_stop_manager import TrailingStopManager
from partial_close_manager import PartialCloseManager
from hedging_engine import HedgingEngine
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
        "balance": 0.00,
        "active_broker": "DEMO",
        "broker_status": "DISCONNECTED",
        "execution_bias": "TREND",
        "risk_config": {},
        "analytics": {}
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
_hedger = None
_trailer = None
_partial_closer = None

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

def get_hedger() -> HedgingEngine:
    global _hedger
    if _hedger is None:
        _hedger = HedgingEngine(get_executor().risk_engine.config)
    return _hedger

def get_trailer() -> TrailingStopManager:
    global _trailer
    if _trailer is None:
        _trailer = TrailingStopManager(get_executor().risk_engine.config)
    return _trailer

def get_partial_closer() -> PartialCloseManager:
    global _partial_closer
    if _partial_closer is None:
        _partial_closer = PartialCloseManager(get_executor().risk_engine.config)
    return _partial_closer

def reset_executor():
    global _executor
    _executor = None
    return get_executor()

def update_shared_data(key, value):
    global SHARED_DATA
    if key in SHARED_DATA:
        SHARED_DATA[key] = value
        save_shared_state(SHARED_DATA)
