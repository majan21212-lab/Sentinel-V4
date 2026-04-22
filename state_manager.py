import logging
import os
import json
from execution_layer import ExecutionLayer
from ml_validator import MLValidator

log = logging.getLogger(__name__)

# --- SHARED STATE PERSISTENCE ---
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shared_state.json")

def load_shared_state():
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
        "is_bot_active": False,
        "kill_switch": False,
        "demo_balance": 200.00,
        "execution_bias": "TREND",
        "risk_config": {},
        "analytics": {}
    }
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                saved = json.load(f)
                defaults.update(saved)
        except Exception as e:
            log.warning(f"State: Error loading state: {e}")
    return defaults

def save_shared_state(data):
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
