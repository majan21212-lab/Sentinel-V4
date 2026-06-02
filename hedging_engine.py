import logging
from models import RiskConfig, Signal, Direction
from db_utils import get_db_connection

log = logging.getLogger(__name__)

class HedgingEngine:
    def __init__(self, config: RiskConfig):
        self.config = config
        self.active_hedges = {} # {symbol: hedge_ticket}

    def monitor_and_hedge(self, global_pnl: float, total_equity: float, execution_layer):
        """
        Monitors global unrealized PnL and deploys hedges if thresholds are breached.
        """
        if not self.config.hedging_enabled:
            return

        pnl_pct = (global_pnl / total_equity) * 100 if total_equity > 0 else 0
        
        # 🚨 THRESHOLD BREACHED: Deploy Hedge
        if pnl_pct <= -self.config.hedge_threshold_pct:
            log.warning(f"🛡️ DYNAMIC HEDGING: Threshold breached ({pnl_pct:.2f}%). Deploying protective hedges.")
            self._deploy_global_hedge(execution_layer)
        
        # ✅ RECOVERY: Close Hedges
        elif pnl_pct >= -1.0 and self.active_hedges:
            log.info(f"🟢 HEDGING RECOVERY: Market stabilized ({pnl_pct:.2f}%). Liquidating hedges.")
            self._liquidate_hedges(execution_layer)

    def _deploy_global_hedge(self, execution_layer):
        """
        Opens a hedge position (Short on a core asset) to offset global downside.
        Usually US30 or BTC are good global proxies.
        """
        hedge_symbol = "US30m" # Default global hedge
        if hedge_symbol in self.active_hedges:
            return

        hedge_signal = Signal(
            symbol=hedge_symbol,
            direction="SHORT",
            entry=0, # Market execution
            stop_loss=0,
            take_profit=0,
            pattern="DynamicHedge",
            score=100.0,
            reason="Global Drawdown Protection"
        )
        
        # Use low qty for hedge (e.g., 0.1 lots)
        hedge_signal.qty = 0.1
        
        res = execution_layer.place_trade(hedge_signal)
        if res.get("status") == "success":
            ticket = res.get("ticket") or "BRIDGE_HEDGE"
            self.active_hedges[hedge_symbol] = ticket
            log.info(f"✅ Global Hedge deployed on {hedge_symbol}")

    def _liquidate_hedges(self, execution_layer):
        """Closes all active hedge positions."""
        for symbol in list(self.active_hedges.keys()):
            execution_layer.close_symbol(symbol)
            del self.active_hedges[symbol]
        log.info("🛡️ All dynamic hedges liquidated.")

# Example singleton logic will be integrated into app.py
