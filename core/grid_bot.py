import logging
from typing import List, Dict
from models import Signal

log = logging.getLogger(__name__)

class GridExecutor:
    """
    Implements a Neutral Grid Trading strategy.
    Placing Buy/Sell orders at fixed intervals within a range.
    """
    def __init__(self, platform_adapter, bottom_price: float, top_price: float, grid_levels: int):
        self.adapter = platform_adapter
        self.bottom = bottom_price
        self.top = top_price
        self.levels = grid_levels
        self.grid_spacing = (top_price - bottom_price) / grid_levels
        self.active_grids = []

    def generate_grid_levels(self) -> List[float]:
        """Calculates exact horizontal price levels for the grid."""
        return [self.bottom + (i * self.grid_spacing) for i in range(self.levels + 1)]

    async def initialize_grid(self, symbol: str, current_price: float, lot_size: float):
        """
        Initializes the grid by placing pending orders.
        - Buy orders below current price.
        - Sell orders above current price.
        """
        levels = self.generate_grid_levels()
        log.info(f"🕸️ Initializing Grid for {symbol} | Range: {self.bottom}-{self.top} | Levels: {self.levels}")
        
        for price in levels:
            if price < current_price:
                # Place Buy Limit
                await self._place_limit_order(symbol, "BUY", price, lot_size)
            elif price > current_price:
                # Place Sell Limit
                await self._place_limit_order(symbol, "SELL", price, lot_size)

    async def _place_limit_order(self, symbol: str, direction: str, price: float, qty: float):
        """Internal helper to dispatch limit order to adapter."""
        try:
            # We wrap the signal for consistency with basic execution layer
            fake_signal = Signal(
                symbol=symbol,
                direction=direction,
                entry=price,
                stop_loss=0.0, # Grids often don't use hard stops per level
                take_profit=price + self.grid_spacing if direction == "BUY" else price - self.grid_spacing
            )
            # This would interface with the platform adapter's native limit order method
            # For now, we log the intent.
            log.info(f"📝 Grid Order Queued: {direction} {symbol} @ {price:.2f}")
        except Exception as e:
            log.error(f"❌ Grid Initialization Error: {e}")

    def update_grid(self, current_price: float):
        """
        Logic to handle grid rebalancing when an order is filled.
        (Usually triggered by a webhook or polling).
        """
        # Logic: If a Buy is filled, place a Sell one level up.
        # Logic: If a Sell is filled, place a Buy one level down.
        pass
