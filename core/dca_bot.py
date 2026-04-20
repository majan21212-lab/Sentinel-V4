import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

@dataclass
class DCASettings:
    base_order_size: float
    safety_order_size: float
    price_deviation: float # % drop to trigger safety order
    max_safety_orders: int
    step_scale: float = 1.0 # Multiplier for price_deviation
    size_scale: float = 1.0 # Multiplier for order_size

class DCAManager:
    """
    Manages Dollar Cost Averaging (DCA) logic for a single symbol.
    Lowers the average entry price by scaling in during drawdowns.
    """
    def __init__(self, symbol: str, settings: DCASettings):
        self.symbol = symbol
        self.settings = settings
        self.active_orders = 0
        self.avg_price = 0.0
        self.total_qty = 0.0

    def calculate_next_safety_order(self, current_price: float) -> Optional[dict]:
        """
        Determines if a new Safety Order (SO) should be placed.
        """
        if self.active_orders >= self.settings.max_safety_orders:
            return None

        # Logic: Calculate deviation from average price
        target_deviation = self.settings.price_deviation * (self.settings.step_scale ** self.active_orders)
        actual_deviation = ((self.avg_price - current_price) / self.avg_price) * 100

        if actual_deviation >= target_deviation:
            next_size = self.settings.safety_order_size * (self.settings.size_scale ** self.active_orders)
            log.info(f"⚖️ DCA Safety Order Triggered for {self.symbol} | Deviation: {actual_deviation:.2f}% | Next Size: {next_size}")
            return {
                "symbol": self.symbol,
                "price": current_price,
                "qty": next_size,
                "order_index": self.active_orders + 1
            }
        
        return None

    def update_state(self, fill_price: float, fill_qty: float):
        """Updates internal average price and quantity after a fill."""
        new_total_qty = self.total_qty + fill_qty
        self.avg_price = ((self.avg_price * self.total_qty) + (fill_price * fill_qty)) / new_total_qty
        self.total_qty = new_total_qty
        self.active_orders += 1
        log.info(f"🔄 DCA State Updated | Total Qty: {self.total_qty:.4f} | Avg Price: {self.avg_price:.2f}")

    def get_tp_price(self, target_pct: float) -> float:
        """Calculates the TP price based on current average entry."""
        return self.avg_price * (1 + (target_pct / 100))
