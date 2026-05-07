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

    async def consult(self, signal: Signal) -> Tuple[bool, Optional[dict]]:
        """
        Sends the trade signal details to DeepSeek for analysis.
        Returns (is_approved, structured_report_data).
        """
        if not self.api_key:
            logger.warning("DeepSeek API Key missing. Skipping consultation.")
            return True, None

        prompt = (
            f"As a Senior Institutional Analyst (SMC Specialist), analyze this trade setup:\n"
            f"Symbol: {signal.symbol} | Direction: {signal.direction}\n"
            f"Pattern: {signal.pattern} | Entry: {signal.entry}\n"
            f"Liquidity Targets: TP1 {signal.tp1}, TP2 {signal.tp2}\n\n"
            "Requirements:\n"
            "1. Use aggressive institutional terminology (Liquidity sweep, stop-run, mitigation, order block, fvg).\n"
            "2. Provide a structured JSON response with the following keys:\n"
            "   - 'summary': A one-sentence executive summary.\n"
            "   - 'key_factors': A list of 3-4 confluence factors.\n"
            "   - 'liquidity_analysis': Details on liquidity sweeps or targets.\n"
            "   - 'market_structure': Analysis of BOS/CHoCH.\n"
            "   - 'confidence_score': Float between 0.0 and 1.0.\n"
            "   - 'action': Either 'APPROVE' or 'REJECT'.\n"
            "Style: Direct, professional, institutional."
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": "You are a specialized trading AI that outputs valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content_str = data['choices'][0]['message']['content']
                    import json
                    report_data = json.loads(content_str)
                    
                    is_approved = report_data.get("action", "REJECT").upper() == "APPROVE"
                    return is_approved, report_data
                else:
                    logger.error(f"DeepSeek API Error: {response.text}")
                    return True, None

        except Exception as e:
            logger.exception("DeepSeek consultation exception")
            return True, None
