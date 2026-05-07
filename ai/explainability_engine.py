import logging
from typing import Optional
from models import Signal, ExplainabilityReport
from ai.deepseek_client import DeepSeekClient

logger = logging.getLogger(__name__)

class ExplainabilityEngine:
    def __init__(self):
        self.ai_client = DeepSeekClient()

    async def generate_rationale(self, signal: Signal) -> Optional[ExplainabilityReport]:
        """
        Generates a structured explainability report for a given signal.
        """
        logger.info(f"Generating AI Rationale for {signal.symbol}...")
        
        is_approved, report_data = await self.ai_client.consult(signal)
        
        if not report_data:
            logger.warning("AI Consultation failed or returned no data.")
            return None
            
        try:
            report = ExplainabilityReport(
                summary=report_data.get("summary", "No summary provided."),
                key_factors=report_data.get("key_factors", []),
                liquidity_analysis=report_data.get("liquidity_analysis"),
                market_structure=report_data.get("market_structure"),
                ai_confidence_score=report_data.get("confidence_score", 0.0)
            )
            return report
        except Exception as e:
            logger.error(f"Failed to parse ExplainabilityReport: {e}")
            return None

# Singleton instance
explain_engine = ExplainabilityEngine()
