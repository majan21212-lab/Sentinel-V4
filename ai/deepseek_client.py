import os
import httpx
import logging
from typing import Tuple, Optional
from core.signals import Signal

logger = logging.getLogger(__name__)

class DeepSeekClient:
    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        self.base_url = "https://api.deepseek.com/v1" # Example URL
        self.model = os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")

    async def consult(self, signal: Signal) -> Tuple[bool, str]:
        """
        Sends the trade signal details to DeepSeek for analysis.
        Returns (is_approved, reasoning).
        """
        if not self.api_key:
            logger.warning("DeepSeek API Key missing. Skipping consultation.")
            return True, "Auto-approved: AI Consultation skipped."

        prompt = (
            f"As a Senior Institutional Analyst (SMC Specialist), analyze this trade setup:\n"
            f"Symbol: {signal.symbol} | Direction: {signal.direction}\n"
            f"Pattern: {signal.pattern} | Entry: {signal.entry}\n"
            f"Liquidity Targets: TP1 {signal.take_profit_1}, TP2 {signal.take_profit_2}\n\n"
            "Requirements:\n"
            "1. Use aggressive institutional terminology (Liquidity sweep, stop-run, mitigation, order block, fvg).\n"
            "2. Format as a SHORT bulleted list of high-confluence factors.\n"
            "3. Conclude with [APPROVE] or [REJECT].\n"
            "Style: Direct, professional, institutional."
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data['choices'][0]['message']['content']
                    
                    is_approved = "[APPROVE]" in content.upper()
                    return is_approved, content
                else:
                    logger.error(f"DeepSeek API Error: {response.text}")
                    return True, f"Error {response.status_code}: Consultation failed."

        except Exception as e:
            logger.exception("DeepSeek consultation exception")
            return True, f"Exception: {str(e)}"
