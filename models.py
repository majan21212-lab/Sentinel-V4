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

class Signal(BaseModel):
    symbol: str
    direction: Direction
    entry: float
    sl: float = Field(..., alias="stop_loss")
    tp1: float = Field(..., alias="take_profit")
    tp2: Optional[float] = None
    qty: float = 0.01
    score: float = 0.0
    pattern: Optional[str] = "GodMode"
    reason: Optional[str] = ""
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        populate_by_name = True

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
    ai_scaling_symbols: list[str] = Field(default_factory=list) # Symbols to apply scaling to
    min_multiplier: float = 0.5
    max_multiplier: float = 1.5

class AccountStatus(BaseModel):
    platform: str
    equity: float
    balance: float
    open_positions: int
    active_symbols: list[str] = Field(default_factory=list)
    daily_pnl: float
