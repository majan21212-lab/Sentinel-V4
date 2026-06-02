import logging
import MetaTrader5 as mt5
from models import RiskConfig

log = logging.getLogger(__name__)

class PartialCloseManager:
    def __init__(self, config: RiskConfig):
        self.config = config
        # Track which partials have been hit for each ticket
        # format: {ticket: {"TP1": True, "TP2": False}}
        self.tracking = {}

    def process_partial_closes(self, active_trades: list):
        """
        Monitors active trades and closes portions of the position at defined TP levels.
        """
        positions = mt5.positions_get()
        if not positions:
            return

        for pos in positions:
            ticket = pos.ticket
            symbol = pos.symbol
            curr_price = pos.price_current
            pos_type = pos.type # 0 = Buy, 1 = Sell
            total_vol = pos.volume
            
            # Find the original signal data for this symbol/ticket to get TP targets
            # (In a production system, we'd pull this from the DB by ticket)
            # For now, we'll check if the comment contains our TP markers or pull from shared_state
            
            # Simplified Logic: Check against targets if available in signal history
            # For this demo, let's assume we pull targets from a simplified lookup
            targets = self._get_targets_for_position(pos)
            if not targets:
                continue

            if ticket not in self.tracking:
                self.tracking[ticket] = {"TP1": False, "TP2": False}

            # TP1 Check (50% close)
            if not self.tracking[ticket]["TP1"]:
                tp1_price = targets.get("tp1")
                if tp1_price and self._is_target_hit(pos_type, curr_price, tp1_price):
                    close_vol = round(total_vol * self.config.tp_ratios.get("TP1", 0.5), 2)
                    if self._execute_partial_close(pos, close_vol, "TP1"):
                        self.tracking[ticket]["TP1"] = True

            # TP2 Check (25% close)
            elif not self.tracking[ticket]["TP2"]:
                tp2_price = targets.get("tp2")
                if tp2_price and self._is_target_hit(pos_type, curr_price, tp2_price):
                    close_vol = round(total_vol * self.config.tp_ratios.get("TP2", 0.5), 2) # Close half of remaining
                    if self._execute_partial_close(pos, close_vol, "TP2"):
                        self.tracking[ticket]["TP2"] = True

    def _is_target_hit(self, pos_type, curr_price, target_price):
        if pos_type == 0: # BUY
            return curr_price >= target_price
        else: # SELL
            return curr_price <= target_price

    def _get_targets_for_position(self, pos):
        """Mock target retrieval - in live, pull from DB/State."""
        # For demo purposes, we'll look for TP1/TP2 in the position comment or magic
        # In this implementation, we will use a global lookup from shared_state
        return None # To be replaced with state lookup in app.py integration

    def _execute_partial_close(self, pos, volume, label):
        """Sends a partial close order to MT5."""
        if volume < 0.01: return False
        
        # To close a portion, we send a deal in the OPPOSITE direction
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "volume": float(volume),
            "type": close_type,
            "price": pos.price_current,
            "magic": pos.magic,
            "comment": f"Sentinel Partial {label}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            log.error(f"❌ Partial Close {label} failed: {result.comment}")
            return False
        
        log.info(f"💰 PROFIT BANKED: Partial {label} hit for {pos.symbol}. Closed {volume} lots.")
        
        # 🛡️ AUTO-BREAKEVEN: Move SL to Entry if TP1 is hit
        if label == "TP1":
            self._move_to_breakeven(pos)
            
        return True

    def _move_to_breakeven(self, pos):
        """Moves the Stop Loss to the entry price (price_open)."""
        entry_price = pos.price_open
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": float(entry_price),
            "tp": float(pos.tp),
            "magic": pos.magic,
            "comment": "Sentinel Breakeven",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            log.info(f"🛡️ AUTO-BREAKEVEN: {pos.symbol} Stop Loss moved to Entry ({entry_price:.5f})")
        else:
            log.error(f"❌ Breakeven failed for {pos.symbol}: {result.comment}")

# Instance will be managed by app.py
