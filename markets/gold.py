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

            # 3. Sentiment Analysis (Advanced Mode)
            sentiment_data = await self.sentiment_agent.get_market_sentiment(self.symbol)
            if not self.sentiment_agent.is_aligned(signal.direction, sentiment_data):
                logger.warning(f"Trade Blocked by Sentiment Filter: {sentiment_data['label']} ({sentiment_data['score']})")
                return

            # 4. Global Risk Check
            open_count = await self.platform.get_open_positions_count()
            # Mocking daily pnl for now
            is_risk_safe, risk_reason = self.risk.validate_global_risk(open_count, 0.0)
            if not is_risk_safe:
                logger.warning(risk_reason)
                return

            # 5. Position Sizing
            balance_data = await self.platform.get_balance()
            equity = balance_data.get("equity", 0.0)
            signal.quantity = self.risk.calculate_position_size(equity, signal.entry, signal.stop_loss)
            logger.info(f"Calculated Qty: {signal.quantity}")

            # 6. AI Consultation
            signal.status = TradeStatus.CONSULTING
            is_ai_approved, rationale = await self.ai.consult(signal)
            signal.ai_rationale = rationale
            
            if not is_ai_approved:
                logger.warning(f"AI Rejected Trade: {rationale}")
                signal.status = TradeStatus.REJECTED
                return

            # 7. Execution
            logger.info("Signal Approved. Dispatching to platform...")
            signal.status = TradeStatus.APPROVED
            result = await self.platform.place_order(signal)
            
            if result.get("status") == "success":
                signal.status = TradeStatus.EXECUTED
                logger.info(f"Gold Trade Executed: {result.get('ticket')}")
            else:
                signal.status = TradeStatus.FAILED
                logger.error(f"Gold Trade Execution Failed: {result.get('message')}")

        except Exception as e:
            logger.exception("Error in GoldBot")
