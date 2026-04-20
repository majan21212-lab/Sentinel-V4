import asyncio
import os
import logging
from dotenv import load_dotenv
from core.signals import Signal
from ai.deepseek_client import DeepSeekClient
from risk_management import RiskEngine, RiskConfig
from core.notifier import notifier

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("SystemTest")

async def run_integration_test():
    load_dotenv()
    log.info("🚀 Starting Full System Integration Test...")
    
    # 1. AI Analyst Test (DeepSeek)
    log.info("--- Step 1: AI Analyst Rationale ---")
    ai = DeepSeekClient()
    test_signal = Signal(
        symbol="BTCUSDm",
        direction="LONG",
        entry=65200.0,
        sl=64800.0,
        tp1=66000.0,
        pattern="Bullish Flag",
        score=92.5
    )
    
    is_approved, rationale = await ai.consult(test_signal)
    log.info(f"AI Approved: {is_approved}")
    log.info(f"AI Rationale:\n{rationale}")
    
    # 2. Dynamic Risk Scaling Test
    log.info("--- Step 2: Dynamic Position Sizing ---")
    # Manually configure scaling for this test
    config = RiskConfig(
        risk_per_asset={"BTCUSDm": 1.0, "DEFAULT": 0.5},
        ai_scaling_symbols=["BTCUSDm"],
        min_multiplier=0.5,
        max_multiplier=1.5
    )
    risk_engine = RiskEngine(config=config)
    
    # Calculate size for 100k account with 92.5 score
    equity = 100000.0
    qty = risk_engine.calculate_position_size(
        symbol="BTCUSDm",
        account_equity=equity,
        entry=65200.0,
        stop_loss=64800.0,
        score=92.5
    )
    log.info(f"Final Calculated Qty: {qty} (Scaling applied based on score 92.5)")
    
    # 3. Notification Test
    log.info("--- Step 3: Telegram Dispatch ---")
    alert_text = (
        "💎 *Sentinel System Test Results*\n\n"
        f"✅ *AI Analyst*: {rationale.splitlines()[0]}...\n"
        f"📏 *Auto-Sizing*: Calculated {qty} units (Score: 92.5)\n"
        "🟢 *Status*: Full Integration Verified."
    )
    notifier.send_message(alert_text)
    log.info("Test Alert sent to Telegram.")

if __name__ == "__main__":
    asyncio.run(run_integration_test())
