import os
import logging
import asyncio
from datetime import datetime
from feed_handler import FeedHandler
from db_utils import setup_database
from strategy import run_strategy, fetch_data, save_signal, calculate_indicators, check_signals
from patterns_engine import PatternsEngine
from execution_layer import ExecutionLayer
from models import Signal
from dotenv import load_dotenv
from ml_validator import MLValidator
import MetaTrader5 as mt5
import threading
import state_manager as state
import schedule
from core.reporting import report_gen

load_dotenv()

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("tradebot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
STRATEGY_MODE = os.getenv("STRATEGY_MODE", "JEWEL_ELITE")  # GOD_MODE or JEWEL_ELITE
BROKER_TYPE   = os.getenv("BROKER_TYPE", "BINANCE")        # BINANCE, ALPACA, or MT5
SYMBOLS       = os.getenv("TRADING_SYMBOLS", "BTC/USDT").split(",")

def get_executor():
    return state.get_executor()

def get_ml_validator():
    return state.get_ml_validator()


# --- Singletons ---



async def run_jewel_elite(symbol: str, df=None) -> None:
    """
    Runs the Chart Patterns PRO / Jewel Elite strategy scanner for one symbol.
    """
    if df is None:
        log.info("💎 Fetching historical data for %s...", symbol)
        df = fetch_data(symbol)
        
    if df is None:
        return

    log.info("💎 Scanning %s for Jewel Elite Patterns (MTF mode)...", symbol)

    # Instantiate engine with MTF data if provided as a dict
    if isinstance(df, dict):
        engine = PatternsEngine(m5_df=df['m5'], m15_df=df.get('m15'), h1_df=df.get('h1'))
    else:
        engine = PatternsEngine(m5_df=df)
        
    raw_signal = engine.detect_patterns()

    if not raw_signal:
        log.info("--- No valid pattern found for %s ---", symbol)
        return

    # ML Validation
    ml = get_ml_validator()
    confidence = ml.predict_confidence(raw_signal)
    if confidence < 0.65:
        log.warning("🛑 💎 ML Check Failed for %s (Confidence: %.1f%%) - Trade Ignored", symbol, confidence * 100)
        return

    raw_signal["symbol"] = symbol
    log.info(
        "🔥 PATTERN DETECTED: %s | Score: %s",
        raw_signal.get("pattern"),
        raw_signal.get("score"),
    )

    # 1. Save to Database
    signal_to_save = {
        "symbol":      symbol,
        "direction":   raw_signal["direction"],
        "entry_price": raw_signal["entry"],
        "take_profit": raw_signal["tp1"],
        "stop_loss":   raw_signal["sl"],
        "timeframe":   "M5",
        "pattern":     raw_signal["pattern"],
        "score":       raw_signal["score"],
        "ml_confidence": confidence,
        "indicators_meta": f"Reason: {raw_signal['reason']}"
    }
    
    from db_utils import get_db_connection
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signals (symbol, direction, entry_price, take_profit, stop_loss, timeframe, pattern, score, ml_confidence, indicators_meta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_to_save["symbol"], signal_to_save["direction"], signal_to_save["entry_price"],
            signal_to_save["take_profit"], signal_to_save["stop_loss"], signal_to_save["timeframe"],
            signal_to_save["pattern"], signal_to_save["score"], signal_to_save["ml_confidence"],
            signal_to_save["indicators_meta"]
        ))
        conn.commit()
        conn.close()

    # 2. Add to Dashboard Feed
    state.SHARED_DATA["signals"].insert(0, {
        "symbol": symbol,
        "direction": raw_signal["direction"],
        "entry": raw_signal["entry"],
        "tp": raw_signal["tp1"],
        "sl": raw_signal["sl"],
        "pattern": raw_signal["pattern"],
        "score": raw_signal["score"],
        "ai_rationale": "SMC TECHNICAL FLOW",
        "created_at": datetime.now().strftime("%H:%M:%S")
    })
    # Keep only the last 10 signals to save bandwidth
    state.SHARED_DATA["signals"] = state.SHARED_DATA["signals"][:10]

    # 3. Automated Execution
    if not state.SHARED_DATA.get("auto_trade", False):
        log.info("--- Auto-Trade is OFF. Skipping execution for %s ---", symbol)
        return

    # FIX #1 – Convert the plain dict from PatternsEngine into the Signal
    # Pydantic model that ExecutionLayer.place_trade() expects.
    # The Signal model uses aliases (stop_loss / take_profit) so we pass
    # them by their alias names and let Pydantic validate everything.
    try:
        signal = Signal(
            symbol=symbol,
            direction=raw_signal["direction"],
            entry=float(raw_signal["entry"]),
            stop_loss=float(raw_signal["sl"]),    # alias for field 'sl'
            take_profit=float(raw_signal["tp1"]), # alias for field 'tp1'
            tp2=float(raw_signal.get("tp2")) if raw_signal.get("tp2") else None,
            score=float(raw_signal.get("score", 0.0)),
            pattern=raw_signal.get("pattern", "JewelElite"),
            reason=raw_signal.get("reason", ""),
        )
    except Exception as exc:
        log.error("❌ Failed to build Signal model from pattern data: %s", exc)
        return

    res = get_executor().place_trade(signal, platform=BROKER_TYPE)
    if res and res.get("status") == "success":
        log.info("✅ Trade Executed Successfully on %s", BROKER_TYPE)
    else:
        msg = res.get("message", "Unknown Error") if res else "No response"
        log.error("❌ Execution Failed on %s: %s", BROKER_TYPE, msg)


def run_god_mode(symbol: str, df=None) -> None:
    """
    Runs the God-Mode (14-Factor) strategy scanner for one symbol.
    """
    if df is None:
        log.info("🔥 Fetching historical data for %s...", symbol)
        df = fetch_data(symbol)
        
    if df is None:
        return

    log.info("🔥 Scanning %s for God-Mode Setup...", symbol)

    # 1. Calculate Indicators
    df = calculate_indicators(df, symbol)
    
    # 2. Check for Signals
    raw_signal = check_signals(df, symbol)

    if not raw_signal:
        log.info("--- No God-Mode Setup found for %s ---", symbol)
        return

    log.info(
        "🔥 GOD-MODE SIGNAL DETECTED: %s | Score: %s",
        raw_signal.get("type"),
        raw_signal.get("score"),
    )

    # 3. Save to Database
    save_signal(raw_signal)

    # 4. Automated Execution
    if not state.SHARED_DATA.get("auto_trade", False):
        log.info("--- Auto-Trade is OFF. Skipping execution for %s ---", symbol)
        return

    # Convert to Signal Pydantic Model
    try:
        signal = Signal(
            symbol=symbol,
            direction=raw_signal["type"],
            entry=float(raw_signal["entry"]),
            stop_loss=float(raw_signal["stop_loss"]),
            take_profit=float(raw_signal["take_profit"]),
            score=float(raw_signal.get("score", 0.0)),
            pattern="GodMode",
            reason=raw_signal.get("reason", ""),
        )
    except Exception as exc:
        log.error("❌ Failed to build Signal model from God-Mode data: %s", exc)
        return

    res = get_executor().place_trade(signal, platform=BROKER_TYPE)
    if res and res.get("status") == "success":
        log.info("✅ God-Mode Trade Executed Successfully on %s", BROKER_TYPE)
    else:
        msg = res.get("message", "Unknown Error") if res else "No response"
        log.error("❌ God-Mode Execution Failed: %s", msg)


async def process_candle(symbol: str, df) -> None:
    """Callback for new candle data from FeedHandler."""
    # Update State for Dashboard
    m5_df = df['m5'] if isinstance(df, dict) else df
    if not m5_df.empty:
        state.SHARED_DATA["prices"][symbol] = float(m5_df['close'].iloc[-1])
        state.SHARED_DATA["status"] = "ONLINE"

    # Strategy Execution
    if STRATEGY_MODE == "JEWEL_ELITE":
        await run_jewel_elite(symbol, df)
    elif STRATEGY_MODE == "GOD_MODE":
        run_god_mode(symbol, df)
    else:
        run_strategy(symbol, df)


async def mt5_polling_loop(symbols: list, timeframe_str: str = "5m") -> None:
    """Fallback loop for MT5 data fetching when Binance feed is unavailable."""
    executor = get_executor()
    adapter = executor.adapters.get("mt5")
    if not adapter:
        log.error("❌ MT5 Adapter not available in ExecutionLayer. Polling aborted.")
        return

    # Map timeframe string to MT5 constant
    tf_map = {
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "1h": mt5.TIMEFRAME_H1,
        "1d": mt5.TIMEFRAME_D1,
    }
    mt5_tf = tf_map.get(timeframe_str, mt5.TIMEFRAME_M5)

    log.info("💎 Starting MT5 Polling (MTF: M5, M15, H1) for %s", symbols)
    
    while True:
        for symbol in symbols:
            try:
                # Concurrent MTF fetching
                tasks = [
                    asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_M5, 500),
                    asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_M15, 200),
                    asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_H1, 200),
                ]
                results = await asyncio.gather(*tasks)
                
                m5_df, m15_df, h1_df = results
                
                if not m5_df.empty:
                    # Pass MTF bundle to processor
                    bundle = {
                        'm5': m5_df,
                        'm15': m15_df if not m15_df.empty else None,
                        'h1': h1_df if not h1_df.empty else None
                    }
                    await process_candle(symbol, bundle)
            except Exception as e:
                log.error("❌ Error polling %s: %s", symbol, e)
        
        await asyncio.sleep(60) # Poll every minute for status

def run_scheduler():
    """Weekly reporting scheduler thread."""
    log.info("📅 Initializing Weekly Reporting Scheduler (SMC Reports)...")
    # Schedule weekly report for Saturday night
    schedule.every().saturday.at("23:59").do(report_gen.generate_weekly_report)
    
    while True:
        schedule.run_pending()
        import time
        time.sleep(60)


async def main_loop() -> None:
    log.info("========================================")
    log.info("🚀 TradeBot v4 Advanced Mode (Phase 1)")
    log.info("========================================")

    # Initialise Database
    log.info("Initialising Database...")
    setup_database()

    # Warm up the executor so MT5 / other adapters connect before the first job
    get_executor()

    # Launch Web Dashboard Server
    log.info("🌐 Launching Mobile Web Dashboard on http://0.0.0.0:8000")
    
    # Pre-sync state
    state.SHARED_DATA["auto_trade"] = os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true"
    state.SHARED_DATA["demo_mode"] = os.getenv("DEMO_MODE", "true").lower() == "true"
    state.SHARED_DATA["active_profile"] = os.getenv("ACTIVE_PROFILE", "CONSERVATIVE")
    state.SHARED_DATA["risk_config"] = get_executor().risk_engine.config.dict()
    
    import web_server
    web_thread = threading.Thread(target=web_server.run_server, daemon=True)
    web_thread.start()
    
    # Launch Scheduler Thread
    if os.getenv("REPORTING_ENABLED", "false").lower() == "true":
        sched_thread = threading.Thread(target=run_scheduler, daemon=True)
        sched_thread.start()

    symbols = [s.strip() for s in SYMBOLS if s.strip()]
    
    if BROKER_TYPE == "MT5":
        # Multi-Broker Fix: Use MT5 Polling for MT5-specific accounts
        try:
            state.SHARED_DATA["status"] = "ONLINE"
            await mt5_polling_loop(symbols, timeframe_str="5m")
        except KeyboardInterrupt:
            log.info("Shutting down...")
        except Exception as e:
            log.error(f"Fatal error in MT5 polling loop: {e}")
    else:
        # Default: Use Binance WebSockets via FeedHandler
        feed = FeedHandler(callback=process_candle, timeframe="5m")
        try:
            await feed.start(symbols)
        except KeyboardInterrupt:
            log.info("Shutting down...")
        except Exception as e:
            log.error(f"Fatal error in Binance feed loop: {e}")
        finally:
            await feed.close()


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        pass
