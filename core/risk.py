import logging
from typing import Tuple
from .signals import Signal

logger = logging.getLogger(__name__)

class RiskManager:
    def __init__(self, 
                 max_daily_loss_pct: float = 2.0, 
                 max_open_positions: int = 3,
                 risk_per_trade_pct: float = 1.0):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_open_positions = max_open_positions
        self.risk_per_trade_pct = risk_per_trade_pct

    def validate_global_risk(self, open_positions_count: int, daily_pnl_pct: float) -> Tuple[bool, str]:
        """Checks if the bot is allowed to trade based on account-wide metrics."""
        if open_positions_count >= self.max_open_positions:
            return False, f"Risk Denied: Max open positions ({self.max_open_positions}) reached."
        
        if daily_pnl_pct <= -self.max_daily_loss_pct:
            return False, f"Risk Denied: Daily drawdown limit ({self.max_daily_loss_pct}%) hit."
        
        return True, "Global risk validation passed."

    def calculate_position_size(self, equity: float, entry: float, stop_loss: float) -> float:
        """Calculates volume based on fixed % risk per trade."""
        risk_amount = equity * (self.risk_per_trade_pct / 100)
        price_risk = abs(entry - stop_loss)
        
        if price_risk == 0:
            return 0.01 # Minimum sanity floor
            
        qty = risk_amount / price_risk
        return round(qty, 2)

    def validate_signal_sanity(self, signal: Signal) -> Tuple[bool, str]:
        """Checks for illogical SL/TP settings."""
        if signal.direction == "LONG":
            if signal.stop_loss >= signal.entry:
                return False, "Sanity Failed: SL must be below entry for LONG."
            if signal.take_profit_1 <= signal.entry:
                return False, "Sanity Failed: TP must be above entry for LONG."
        else:
            if signal.stop_loss <= signal.entry:
                return False, "Sanity Failed: SL must be above entry for SHORT."
            if signal.take_profit_1 >= signal.entry:
                return False, "Sanity Failed: TP must be below entry for SHORT."
        
        return True, "Signal sanity passed."
