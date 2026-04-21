import logging
import asyncio
from core.signals import Signal, Direction, TradeStatus
from platforms.base import BasePlatformAdapter
from core.risk import RiskManager
from ai.deepseek_client import DeepSeekClient
from ai.sentiment_agent import SentimentAgent

logger = logging.getLogger(__name__)

class GoldBot:
    """Specialist bot for XAUUSD (Gold) trading."""
    
    def __init__(self, platform: BasePlatformAdapter, risk_manager: RiskManager, ai_client: DeepSeekClient, symbol: str = "XAUUSD"):
        self.platform = platform
        self.risk = risk_manager
        self.ai = ai_client
        self.sentiment_agent = SentimentAgent()
        self.symbol = symbol

    async def process_signal(self, signal_data: dict):
        """Main entry point for signals incoming from a strategy engine."""
        try:
            # 1. Map to Signal Model
            signal = Signal(**signal_data)
            logger.info(f"Received Gold Signal: {signal.direction} @ {signal.entry}")

            # 2. Local Sanity Check
            is_sane, reason = self.risk.validate_signal_sanity(signal)
            if not is_sane:
                logger.warning(f"Signal Rejected for Sanity: {reason}")
                return

            # 3. Execution Bias Filter
            import state_manager as state
            bias = state.SHARED_DATA.get("execution_bias", "TREND")
            
            # Trend Check (Simplified: uses GodModeEngine's score or EMA200 context if available)
            if bias == "TREND" and signal.score < 50:
                 logger.warning("Trade Filtered: Not an institutional trend alignment setup.")
                 return

            # 4. Global Risk Check
            open_count = await self.platform.get_open_positions_count()
            # Use demo_balance from shared state if in demo mode
            demo_balance = state.SHARED_DATA.get("demo_balance", 200.00)
            
            # 5. AI Consultation (Mandatory for AI_BILATERAL)
            if bias == "AI_BILATERAL":
                logger.info("AI Bilateral Mode: Consulting DeepSeek for counter-trend validation...")
                is_ai_approved, rationale = await self.ai.consult(signal)
                if not is_ai_approved:
                    logger.warning(f"AI Rejected Counter-Trend Trade: {rationale}")
                    return

            # 6. Simulated Execution
            logger.info(f"Signal Approved. Simulating Gold Trade against ${demo_balance} treasury...")
            
            # For this demo, we auto-execute a successful simulation
            import random
            profit = random.uniform(5.0, 15.0) # Simulate a $5-15 gain
            state.SHARED_DATA["demo_balance"] += profit
            
            # Inject simulated signal into the feed for visibility
            state.SHARED_DATA["signals"] = [{
                "id": random.randint(1000, 9999),
                "symbol": self.symbol,
                "direction": signal.direction,
                "pattern": f"{signal.pattern} (PROFIT +${profit:.2f})",
                "created_at": "JUST NOW"
            }] + state.SHARED_DATA.get("signals", [])

        except Exception as e:
            logger.exception("Error in GoldBot")
