import asyncio
import os
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

load_dotenv(override=True)

async def push_to_dashboard(data: dict):
    """Helper to push live updates to the local dashboard."""
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            await client.post("http://localhost:8000/update", json=data)
    except Exception:
        pass # Dashboard might not be ready

async def main():
    # 1. Setup Logging
    log = setup_logger("SentinelV4")
    log.info("Starting Sentinel V4 Advanced Mode with God Mode Engine + Dashboard...")

    # 2. Launch Dashboard Server in separate process
    log.info("Launching Sentinel Dashboard at http://localhost:8000 ...")
    pkg_path = os.path.dirname(os.path.abspath(__file__))
    dashboard_process = subprocess.Popen(
        ["python", "-m", "uvicorn", "dashboard.app:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
        cwd=pkg_path
    )

    # 3. Initialise Components
    risk_manager = RiskManager()
    ai_client = DeepSeekClient()
    platform = MT5Adapter()
    
    # Connect to MT5
    if not await platform.connect():
        log.error("Failed to connect to MT5. Exiting.")
        return

    # 3. Initialise Market Bots Mapping
    symbols_raw = os.getenv("TRADING_SYMBOLS", "XAUUSD")
    symbols = [s.strip() for s in symbols_raw.split(",") if s.strip()]
    
    # We map specific suffixes to their respective bots
    market_bots = {}
    for sym in symbols:
        if "XAU" in sym.upper():
            market_bots[sym] = GoldBot(platform, risk_manager, ai_client, symbol=sym)
        else:
            log.warning(f"No specific bot implemented for {sym}. Scanning with God Mode but no handler assigned.")

    # 4. Main Service Loop
    log.info(f"Service operational. Active Market Polling for: {symbols}")
    try:
        while True:
            for symbol in symbols:
                log.info(f"Scanning {symbol} with God Mode Advanced Engine (M15 + H1 Confluence)...")
                
                # Fetch M15 and H1 data concurrently
                tasks = [
                    platform.fetch_historical_data(symbol, mt5.TIMEFRAME_M15, 300),
                    platform.fetch_historical_data(symbol, mt5.TIMEFRAME_H1, 300)
                ]
                results = await asyncio.gather(*tasks)
                df_m15, df_h1 = results
                
                if df_m15 is not None and not df_m15.empty:
                    # Sort by index for indicator accuracy
                    df_m15 = df_m15.sort_index()
                    if df_h1 is not None:
                        df_h1 = df_h1.sort_index()
                    
                    engine = GodModeEngine(df_m15, h1_df=df_h1)
                    raw_signal = engine.analyze()
                    
                    # Push Market Update to Dashboard
                    latest_price = float(df_m15.iloc[-1]['close'])
                    score = float(raw_signal['score']) if raw_signal else 50.0 # Default Neutral
                    await push_to_dashboard({
                        "type": "market_update",
                        "symbol": symbol,
                        "price": latest_price,
                        "score": score
                    })
                    
                    if raw_signal:
                        log.info(f"GOD MODE PATTERN DETECTED [{symbol}]: {raw_signal['direction']} | Score: {raw_signal['score']:.1f}%")
                        raw_signal['symbol'] = symbol
                        
                        # Push Signal to Dashboard
                        await push_to_dashboard({
                            "type": "signal",
                            "symbol": symbol,
                            "direction": raw_signal['direction'],
                            "entry": raw_signal['entry'],
                            "rationale": "God Mode Advanced IPA Pattern"
                        })
                        
                        # Dispatch to the specific bot if mapped
                        if symbol in market_bots:
                            asyncio.create_task(market_bots[symbol].process_signal(raw_signal))
                        else:
                            log.warning(f"Pattern found for {symbol} but no bot handler assigned.")
                    else:
                        log.info(f"--- No God Mode Setup Detected for {symbol} ---")
                else:
                    log.warning(f"Failed to fetch historical data for {symbol}.")

            # Sleep until next check interval
            await asyncio.sleep(60) 
            
    except asyncio.CancelledError:
        log.info("Service shutting down...")
    finally:
        dashboard_process.terminate()
        await platform.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
