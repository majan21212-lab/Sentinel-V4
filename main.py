import asyncio
import os
import sys
import logging
import httpx
import subprocess
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except (ImportError, OSError):
    mt5 = None
    MT5_AVAILABLE = False

from dotenv import load_dotenv

from core.logger import setup_logger
from core.risk import RiskManager
from ai.deepseek_client import DeepSeekClient
from platforms.mt5_adapter import MT5Adapter
from markets.market_bot import MarketBot
from core.godmode import GodModeEngine
import state_manager as state
from cortex.optimizer import CortexOptimizer


load_dotenv(override=True)

async def main():
    log = setup_logger("JEWEL_ELITE_CORE")
    log.info("Starting Jewel Elite Multi-Market Core...")

    pkg_path = os.path.dirname(os.path.abspath(__file__))
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
        cwd=pkg_path
    )

    risk_manager = RiskManager()
    ai_client = DeepSeekClient()
    platform = MT5Adapter()
    
    try:
        await platform.connect()
    except:
        log.warning("Platform connection failed. Simulation only.")

    market_bots = {}
    cortex = CortexOptimizer()
    last_evolution = datetime.now() - timedelta(hours=1)
    
    try:
        while True:
            # 0. Cortex Evolution Cycle (Run every hour)
            if datetime.now() - last_evolution > timedelta(hours=1):
                log.info("Cortex is evolving...")
                cortex.run_cycle()
                last_evolution = datetime.now()

            # 1. Global Kill Switch
            if state.SHARED_DATA.get("kill_switch", False):
                await asyncio.sleep(2)
                continue

            # Global Activation Check
            if not state.SHARED_DATA.get("is_bot_active", False):
                await asyncio.sleep(2)
                continue

            # Sync Market Bots with Shared State
            active_symbols = state.SHARED_DATA.get("active_markets", [])
            for sym in active_symbols:
                if sym not in market_bots:
                    market_bots[sym] = MarketBot(platform, risk_manager, ai_client, symbol=sym)

            strategy_mode = state.SHARED_DATA.get("strategy_mode", "PATTERN")
            for symbol in active_symbols:
                if strategy_mode == "PATTERN":
                    # Simulated data fetch for demo
                    timeframe = mt5.TIMEFRAME_M15 if MT5_AVAILABLE else 15
                    df_m15 = await asyncio.to_thread(platform.fetch_historical_data, symbol, timeframe, 300) if hasattr(platform, 'fetch_historical_data') else None

                    if df_m15 is not None and not df_m15.empty:
                        engine = GodModeEngine(df_m15)
                        raw_signal = engine.analyze()
                        if raw_signal:
                            asyncio.create_task(market_bots[symbol].process_signal(raw_signal))
                elif strategy_mode == "GRID":
                    log.info(f"GRID MONITORING {symbol}")
                elif strategy_mode == "DCA":
                    log.info(f"DCA MONITORING {symbol}")

            await asyncio.sleep(5) 
    except asyncio.CancelledError:
        log.info("Shutting down...")
    finally:
        dashboard_process.terminate()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
