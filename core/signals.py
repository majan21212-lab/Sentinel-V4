from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"

class TradeStatus(str, Enum):
    PENDING = "PENDING"
    CONSULTING = "CONSULTING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"

class Signal(BaseModel):
    id: Optional[str] = None
    symbol: str
    direction: Direction
    entry: float
    stop_loss: float = Field(..., alias="sl")
    take_profit_1: float = Field(..., alias="tp1")
    take_profit_2: Optional[float] = Field(None, alias="tp2")
    quantity: float = 0.0
    pattern: str = "Institutional"
    timeframe: str = "H1"
    timestamp: datetime = Field(default_factory=datetime.now)
    status: TradeStatus = TradeStatus.PENDING
    ai_rationale: Optional[str] = None

    class Config:
        populate_by_name = True
        use_enum_values = True

class SignalLog(BaseModel):
    signal: Signal
    platform: str
    execution_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
