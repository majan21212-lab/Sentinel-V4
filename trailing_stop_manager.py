import logging
import MetaTrader5 as mt5
from strategy import _atr, fetch_data
from models import RiskConfig

log = logging.getLogger(__name__)

class TrailingStopManager:
    def __init__(self, config: RiskConfig):
        self.config = config

    def process_mt5_trailing_stops(self, adapter):
        """
        Iterates through active MT5 positions and updates SL based on ATR volatility.
        """
        if not self.config.trailing_stop_enabled:
            return

        positions = mt5.positions_get()
        if not positions:
            return

        for pos in positions:
            symbol = pos.symbol
            ticket = pos.ticket
            curr_sl = pos.sl
            curr_price = pos.price_current
            pos_type = pos.type # 0 = Buy, 1 = Sell
            
            # 1. Fetch Volatility (ATR)
            df = fetch_data(symbol, timeframe='15m', limit=50) # Use M15 for trailing stop ATR
            if df is None or len(df) < 14:
                continue
                
            atr_val = _atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
            trail_dist = atr_val * self.config.trailing_stop_atr_multiplier
            
            # 2. Calculate New SL
            new_sl = 0
            if pos_type == 0: # BUY
                target_sl = curr_price - trail_dist
                # Only move SL UP
                if target_sl > curr_sl + (atr_val * 0.2): # Add small buffer to avoid spamming updates
                    new_sl = target_sl
            elif pos_type == 1: # SELL
                target_sl = curr_price + trail_dist
                # Only move SL DOWN
                if curr_sl == 0 or target_sl < curr_sl - (atr_val * 0.2):
                    new_sl = target_sl

            # 3. Update SL if valid
            if new_sl > 0:
                self._modify_sl(ticket, symbol, new_sl, pos.tp)

    def _modify_sl(self, ticket, symbol, new_sl, tp):
        """Sends a modification request to MT5."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": float(new_sl),
            "tp": float(tp),
            "magic": 20260415,
            "comment": "Sentinel ATR Trail",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            # log.error(f"Trailing Stop Failed for {symbol} (Ticket {ticket}): {result.comment}")
            pass
        else:
            log.info(f"🛡️ ATR TRAILING STOP: Updated {symbol} SL to {new_sl:.5f}")

# Example singleton logic will be integrated into app.py
