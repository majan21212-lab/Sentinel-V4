from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class ExecutionMode(str, Enum):
    DEMO = "DEMO"
    LIVE = "LIVE"

class RiskProfile(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    OPTIMAL = "OPTIMAL"
    AGGRESSIVE = "AGGRESSIVE"

class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"

class Signal(BaseModel):
    symbol: str
    direction: Direction
    entry: float
    sl: float = Field(..., alias="stop_loss")
    tp1: float = Field(..., alias="take_profit")
    tp2: Optional[float] = None
    tp3: Optional[float] = None
    qty: float = 0.01
    score: float = 0.0
    pattern: Optional[str] = "GodMode"
    reason: Optional[str] = ""
    bot_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True

class OptionSignal(Signal):
    contract_symbol: Optional[str] = None
    strike: Optional[float] = None
    expiry: Optional[str] = None
    option_type: Optional[OptionType] = None

class WebhookSignal(BaseModel):
    id: str
    action: str  # buy, sell, partial_exit, final_exit, breakeven
    ticker: str
    price: float
    sl: Optional[float] = None
    tp: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class RiskConfig(BaseModel):
    active_profile: RiskProfile = RiskProfile.CONSERVATIVE
    execution_mode: ExecutionMode = ExecutionMode.DEMO
    max_daily_loss_pct: float = 2.0
    max_open_positions: int = 3
    risk_per_asset: Dict[str, float] = Field(default_factory=lambda: {
        "XAUUSDm": 1.0,
        "BTCUSDm": 2.0,
        "DEFAULT": 0.5
    })
    min_order_value_usd: float = 10.0
    ai_scaling_symbols: list[str] = Field(default_factory=list) 
    min_multiplier: float = 0.5
    max_multiplier: float = 1.5
    
    # --- Prop Firm Shield ---
    prop_firm_mode: bool = False
    max_daily_drawdown_pct: float = 4.5  # Typical limit is 5%, we stay safe at 4.5%
    max_total_drawdown_pct: float = 9.0   # Typical limit is 10%, we stay safe at 9%
    emergency_stop_active: bool = False
    
    # --- MTF Confluence ---
    mtf_confluence_enabled: bool = True
    check_h1_trend: bool = True
    check_h4_trend: bool = True
    bridge_mode_enabled: bool = False
    bridge_weighting: dict[str, float] = {"mt5": 1.0, "binance": 1.0, "alpaca": 1.0}
    hedging_enabled: bool = False
    hedge_threshold_pct: float = 2.5
    trailing_stop_enabled: bool = False
    trailing_stop_atr_multiplier: float = 2.5
    
    # --- Multi-TP Scaling ---
    tp_ratios: Dict[str, float] = Field(default_factory=lambda: {
        "TP1": 0.50, # 50%
        "TP2": 0.25, # 25%
        "TP3": 0.25  # Remaining 25%
    })
    
    # --- News Filter Shield ---
    news_filter_enabled: bool = True
    news_buffer_mins: int = 30
    news_impact_min: str = "High" 
    min_ml_confidence: float = 0.45
    fixed_capital_usd: float = 200.0  # ONLY use this amount for risk calculation

class AccountStatus(BaseModel):
    platform: str
    equity: float
    balance: float
    open_positions: int
    active_symbols: list[str] = Field(default_factory=list)
    daily_pnl: float
