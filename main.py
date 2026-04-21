import asyncio
import os
import sys
import logging
import httpx
import subprocess
import MetaTrader5 as mt5
from dotenv import load_dotenv

from core.logger import setup_logger
from core.risk import RiskManager
from ai.deepseek_client import DeepSeekClient
from platforms.mt5_adapter import MT5Adapter
from markets.gold import GoldBot
from core.godmode import GodModeEngine
from core.grid_bot import GridExecutor
from core.dca_bot import DCAManager, DCASettings
import state_manager as state

load_dotenv(override=True)

async def push_to_dashboard(data: dict):
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            await client.post("http://localhost:8000/update", json=data)
    except Exception:
        pass 

async def main():
    log = setup_logger("G.A.B_CORE_F")
    log.info("Starting G.A.B Core on F: drive...")

    # 2. Launch G.A.B Dashboard Server (web_server.py)
    log.info("Launching G.A.B Dashboard at http://localhost:8000 ...")
    pkg_path = os.path.dirname(os.path.abspath(__file__))
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
        cwd=pkg_path
    )

    risk_manager = RiskManager()
    ai_client = DeepSeekClient()
    platform = MT5Adapter()
    
    try:
        if not await platform.connect():
            log.error("Failed to connect to MT5. Simulation mode active.")
    except Exception as e:
        log.warning(f"Platform Error: {e}")

    symbols_raw = os.getenv("TRADING_SYMBOLS", "XAUUSDm,BTCUSDm")
    symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]
    
    market_bots = {}
    for sym in symbols:
        if "XAU" in sym.upper():
            market_bots[sym] = GoldBot(platform, risk_manager, ai_client, symbol=sym)

    try:
        while True:
            strategy_mode = state.SHARED_DATA.get("strategy_mode", "PATTERN")
            for symbol in symbols:
                if strategy_mode == "PATTERN":
                    # Use to_thread for synchronous MT5 call
                    df_m15 = await asyncio.to_thread(platform.fetch_historical_data, symbol, mt5.TIMEFRAME_M15, 300) if hasattr(platform, 'fetch_historical_data') else None
                    if df_m15 is not None and not df_m15.empty:
                        engine = GodModeEngine(df_m15)
                        raw_signal = engine.analyze()
                        state.SHARED_DATA["prices"][symbol] = float(df_m15.iloc[-1]['close'])
                        if raw_signal and symbol in market_bots:
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
