import logging
import asyncio
import random
from core.signals import Signal, Direction
from platforms.base import BasePlatformAdapter
from core.risk import RiskManager
from ai.deepseek_client import DeepSeekClient
import state_manager as state

logger = logging.getLogger(__name__)

class MarketBot:
    """Institutional execution bot for any market symbol."""
    
    def __init__(self, platform: BasePlatformAdapter, risk_manager: RiskManager, ai_client: DeepSeekClient, symbol: str):
        self.platform = platform
        self.risk = risk_manager
        self.ai = ai_client
        self.symbol = symbol

    async def process_signal(self, signal_data: dict):
        """Processes signals with institutional filters and simulated execution."""
        try:
            # 1. Global Kill Switch check
            if state.SHARED_DATA.get("kill_switch", False):
                logger.warning(f"Bot for {self.symbol} halted by Kill Switch.")
                return

            # 2. Map to Signal Model
            signal = Signal(**signal_data)
            logger.info(f"[{self.symbol}] Processing Signal: {signal.direction} @ {signal.entry}")

            # 3. Execution Bias Filter
            bias = state.SHARED_DATA.get("execution_bias", "TREND")
            if bias == "TREND" and signal.score < 0:
                 logger.warning(f"[{self.symbol}] Trade Filtered: Weak institutional trend alignment.")
                 return

            # 4. AI Consultation (Mandatory for AI_BILATERAL)
            if bias == "AI_BILATERAL":
                is_ai_approved, rationale = await self.ai.consult(signal)
                if not is_ai_approved:
                    logger.warning(f"[{self.symbol}] AI Rejected Trade: {rationale}")
                    return

            # 5. Execution Gateway
            is_demo = state.SHARED_DATA.get("demo_mode", True)
            if not is_demo:
                logger.info(f"[{self.symbol}] Dispatching LIVE order to Platform...")
                res = await self.platform.place_order(signal)
                if res.get("status") == "success":
                    logger.info(f"[{self.symbol}] Order Successfully Placed: {res.get('order_id', res.get('ticket'))}")
                else:
                    logger.error(f"[{self.symbol}] Order Placement Failed: {res.get('message')}")
            else:
                logger.info(f"[{self.symbol}] Simulating DEMO execution...")
                await self._simulate_execution(signal)

        except Exception as e:
            logger.exception(f"Error in MarketBot for {self.symbol}: {e}")

    async def _simulate_execution(self, signal: Signal):
        """Simulates a trade and updates the shared terminal state."""
        logger.info(f"DEBUG: Signal Type: {type(signal)}")
        logger.info(f"DEBUG: Signal Attributes: {signal.__dict__.keys() if hasattr(signal, '__dict__') else 'No __dict__'}")
        trade_id = random.randint(10000, 99999)
        
        # Create 'Active' trade
        new_trade = {
            "id": trade_id,
            "symbol": self.symbol,
            "direction": signal.direction,
            "entry": signal.entry,
            "tp": signal.take_profit_1,
            "sl": signal.stop_loss,
            "status": "ACTIVE",
            "pnl": 0.0,
            "created_at": "JUST NOW"
        }
        
        state.SHARED_DATA["active_trades"].append(new_trade)
        
        # Simulate trade lifecycle
        asyncio.create_task(self._simulate_trade_closure(trade_id))

    async def _simulate_trade_closure(self, trade_id: int):
        """Wait and then simulate the closure of a trade."""
        await asyncio.sleep(15) # Simulated trade duration
        
        active_trades = state.SHARED_DATA["active_trades"]
        trade_idx = next((i for i, t in enumerate(active_trades) if t["id"] == trade_id), None)
        
        if trade_idx is not None:
            trade = active_trades.pop(trade_idx)
            profit = random.uniform(2.0, 20.0) if random.random() > 0.3 else random.uniform(-10.0, -2.0)
            
            trade["status"] = "CLOSED"
            trade["pnl"] = round(profit, 2)
            state.SHARED_DATA["demo_balance"] += profit
            state.SHARED_DATA["trade_history"].insert(0, trade)
            logger.info(f"[{self.symbol}] Trade {trade_id} closed with PnL: ${profit:.2f}")
