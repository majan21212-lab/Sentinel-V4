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
from telegram_bot import telegram_bot
from ai.explainability_engine import explain_engine

load_dotenv()

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("sentinel.log", encoding="utf-8"),
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
        log.info("[JEWEL] Fetching historical data for %s...", symbol)
        df = fetch_data(symbol)
        
    if df is None:
        return

    log.info("[JEWEL] Scanning %s for Jewel Elite Patterns (MTF mode)...", symbol)

    # Instantiate engine with MTF data if provided as a dict
    if isinstance(df, dict):
        engine = PatternsEngine(m5_df=df['m5'], m15_df=df.get('m15'), h1_df=df.get('h1'))
    else:
        engine = PatternsEngine(m5_df=df)
        
    raw_signal = engine.detect_patterns()

    if not raw_signal:
        log.info("--- No valid pattern found for %s ---", symbol)
        return

    # 1. ML Validation - THE SENTINEL GATE
    ml = get_ml_validator()
    confidence = ml.predict_confidence(raw_signal)
    
    # Add confidence to shared state for UI visibility
    state.SHARED_DATA["last_ai_confidence"] = round(confidence * 100, 1)
    
    threshold = float(os.getenv("AI_CONFIDENCE_THRESHOLD", 0.80))
    
    if confidence < threshold:
        log.warning("🛡️ AI SENTINEL REJECTED: %s (Confidence: %.1f%% < %.1f%%)", 
                    symbol, confidence * 100, threshold * 100)
        # Update dashboard status
        state.SHARED_DATA["status"] = f"AI REJECTED {symbol}"
        return

    raw_signal["symbol"] = symbol
    log.info(
        "[SIGNAL] PATTERN DETECTED & AI APPROVED: %s | Score: %s | Confidence: %.1f%%",
        raw_signal.get("pattern"),
        raw_signal.get("score"),
        confidence * 100
    )

    # 2. AI Rationale - THE EXPLAINABILITY LAYER
    explain_report = await explain_engine.generate_rationale(Signal(
        symbol=symbol,
        direction=raw_signal["direction"],
        entry=float(raw_signal["entry"]),
        stop_loss=float(raw_signal["sl"]),
        take_profit=float(raw_signal["tp1"]),
        tp2=float(raw_signal.get("tp2")) if raw_signal.get("tp2") else None,
        pattern=raw_signal.get("pattern", "JewelElite"),
        reason=raw_signal.get("reason", "")
    ))
    
    rationale_json = explain_report.json() if explain_report else "No rationale generated."

    # 3. Save to Database
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
        "indicators_meta": f"Reason: {raw_signal['reason']}",
        "ai_rationale": rationale_json
    }
    
    from db_utils import get_db_connection
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signals (symbol, direction, entry_price, take_profit, stop_loss, timeframe, pattern, score, ml_confidence, indicators_meta, ai_rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_to_save["symbol"], signal_to_save["direction"], signal_to_save["entry_price"],
            signal_to_save["take_profit"], signal_to_save["stop_loss"], signal_to_save["timeframe"],
            signal_to_save["pattern"], signal_to_save["score"], signal_to_save["ml_confidence"],
            signal_to_save["indicators_meta"], signal_to_save["ai_rationale"]
        ))
        conn.commit()
        conn.close()

    # 4. Add to Dashboard Feed
    state.SHARED_DATA["signals"].insert(0, {
        "symbol": symbol,
        "direction": raw_signal["direction"],
        "entry": raw_signal["entry"],
        "tp": raw_signal["tp1"],
        "sl": raw_signal["sl"],
        "pattern": raw_signal["pattern"],
        "score": raw_signal["score"],
        "ai_rationale": explain_report.summary if explain_report else "SMC TECHNICAL FLOW",
        "created_at": datetime.now().strftime("%H:%M:%S")
    })
    # Keep only the last 10 signals
    state.SHARED_DATA["signals"] = state.SHARED_DATA["signals"][:10]

    # 4. Automated Execution
    if not state.SHARED_DATA.get("is_bot_active", False):
        log.info("--- Core Engine is OFF. Skipping execution for %s ---", symbol)
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
        
        # Send Telegram Notification
        telegram_bot.send_signal_alert(signal_to_save)
        
        # Record trade for dashboard visibility
        trade_record = {
            "symbol": signal.symbol,
            "direction": signal.direction,
            "entry": signal.entry,
            "tp": signal.tp1,
            "sl": signal.sl,
            "qty": getattr(signal, 'qty', 0.1),
            "pnl": 0.0,
            "status": "ACTIVE",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        active_trades = state.SHARED_DATA.get("active_trades", [])
        active_trades.insert(0, trade_record)
        state.SHARED_DATA["active_trades"] = active_trades[:20] # Keep last 20
        state.save_shared_state(state.SHARED_DATA)
    else:
        msg = res.get("message", "Unknown Error") if res else "No response"
        log.error("❌ Execution Failed on %s: %s", BROKER_TYPE, msg)


async def run_god_mode(symbol: str, df=None) -> None:
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

    # 4. ML Validation - THE SENTINEL GATE
    ml = get_ml_validator()
    confidence = ml.predict_confidence(raw_signal)
    state.SHARED_DATA["last_ai_confidence"] = round(confidence * 100, 1)
    threshold = float(os.getenv("AI_CONFIDENCE_THRESHOLD", 0.85))
    
    if confidence < threshold:
        log.warning("🛡️ AI SENTINEL REJECTED GOD-MODE: %s (Confidence: %.1f%%)", 
                    symbol, confidence * 100)
        state.SHARED_DATA["status"] = f"AI REJECTED {symbol}"
        return

    # 5. AI Rationale - THE EXPLAINABILITY LAYER
    explain_report = await explain_engine.generate_rationale(Signal(
        symbol=symbol,
        direction=raw_signal["type"],
        entry=float(raw_signal["entry"]),
        stop_loss=float(raw_signal["stop_loss"]),
        take_profit=float(raw_signal["take_profit"]),
        pattern="GodMode",
        reason=raw_signal.get("reason", "")
    ))
    
    # 6. Automated Execution
    if not state.SHARED_DATA.get("is_bot_active", False):
        log.info("--- Core Engine is OFF. Skipping execution for %s ---", symbol)
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
            explainability=explain_report
        )
    except Exception as exc:
        log.error("❌ Failed to build Signal model from God-Mode data: %s", exc)
        return

    res = get_executor().place_trade(signal, platform=BROKER_TYPE)
    if res and res.get("status") == "success":
        log.info("✅ God-Mode Trade Executed Successfully on %s", BROKER_TYPE)
        
        # Send Telegram Notification
        telegram_bot.send_signal_alert(raw_signal)
        
        # Record trade for dashboard visibility
        trade_record = {
            "symbol": signal.symbol,
            "direction": signal.direction,
            "entry": signal.entry,
            "tp": signal.tp1,
            "sl": signal.sl,
            "qty": getattr(signal, 'qty', 0.1),
            "pnl": 0.0,
            "status": "ACTIVE",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        active_trades = state.SHARED_DATA.get("active_trades", [])
        active_trades.insert(0, trade_record)
        state.SHARED_DATA["active_trades"] = active_trades[:20]
        state.save_shared_state(state.SHARED_DATA)
    else:
        msg = res.get("message", "Unknown Error") if res else "No response"
        log.error("❌ God-Mode Execution Failed: %s", msg)


def update_pnl():
    """Update floating PnL and close trades that hit TP/SL."""
    active_trades = state.SHARED_DATA.get("active_trades", [])
    if not active_trades:
        return
        
    history = state.SHARED_DATA.get("trade_history", [])
    prices = state.SHARED_DATA.get("prices", {})
    
    still_active = []
    
    for trade in active_trades:
        sym = trade.get("symbol")
        current_price = prices.get(sym)
        if not current_price:
            still_active.append(trade)
            continue
            
        entry = trade["entry"]
        is_long = trade["direction"] == "LONG"
        qty = trade.get("qty", 0.1)
        
        if is_long:
            diff = current_price - entry
        else:
            diff = entry - current_price
            
        # Accurate PnL calculation
        if "BTC" in sym or "ETH" in sym:
            # Crypto: Price diff * qty
            pnl = diff * qty
        elif "XAU" in sym or "GOLD" in sym:
            # Gold: 1 Lot = 100 oz. Price diff * 100 * qty
            pnl = diff * 100 * qty
        elif "XAG" in sym or "SILVER" in sym:
            # Silver: 1 Lot = 5000 oz. Price diff * 5000 * qty
            pnl = diff * 5000 * qty
        elif "JPY" in sym:
            # JPY Pairs: (Price Diff * 100,000 * qty) / Current Price
            # JPY pip is 0.01. Multiplying by 100,000 is still standard unit volume.
            pnl = (diff * 100000 * qty) / current_price
        else:
            # Standard Forex: 1 Lot = 100,000 units
            # PnL = (Price Diff) * 100,000 * qty (assuming USD is quote currency)
            pnl = diff * 100000 * qty
            
        trade["pnl"] = round(pnl, 2)
        
        # Check TP/SL hit
        if is_long:
            if current_price >= trade["tp"] or current_price <= trade["sl"]:
                trade["status"] = "CLOSED"
                history.insert(0, trade)
                continue
        else:
            if current_price <= trade["tp"] or current_price >= trade["sl"]:
                trade["status"] = "CLOSED"
                history.insert(0, trade)
                continue
                
        still_active.append(trade)
        
    state.SHARED_DATA["active_trades"] = still_active
    state.SHARED_DATA["trade_history"] = history[:50]
    state.save_shared_state(state.SHARED_DATA)

async def process_candle(symbol: str, df) -> None:
    """Callback for new candle data from FeedHandler."""
    # Update State for Dashboard
    m5_df = df['m5'] if isinstance(df, dict) else df
    if not m5_df.empty:
        state.SHARED_DATA["prices"][symbol] = float(m5_df['close'].iloc[-1])
        state.SHARED_DATA["status"] = "ONLINE"
        update_pnl()

    # Strategy Execution - DYNAMIC MODE
    if not state.SHARED_DATA.get("is_bot_active", False):
        return

    mode = state.SHARED_DATA.get("strategy_mode", STRATEGY_MODE)
    if mode == "JEWEL_ELITE":
        await run_jewel_elite(symbol, df)
    elif mode == "GOD_MODE":
        await run_god_mode(symbol, df)
    else:
        run_strategy(symbol, df)


async def mt5_polling_loop(symbols: list, timeframe_str: str = "5m") -> None:
    """Fallback loop for MT5 data fetching when Binance feed is unavailable."""
    while True:
        executor = get_executor()
        adapter = executor.adapters.get("mt5")
        if not adapter:
            log.warning("⚠️ MT5 Adapter not available. Is the terminal authorized? Retrying in 60s...")
            # Attempt to re-initialize adapters
            executor._init_adapters()
            await asyncio.sleep(60)
            continue
        break

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
        # Dynamically read active markets from shared state
        current_symbols = state.SHARED_DATA.get("active_markets", symbols)
        if not current_symbols:
            current_symbols = symbols
            
        for symbol in current_symbols:
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


async def pnl_update_loop():
    """Rapid loop to fetch actual positions from MT5 and sync the dashboard state."""
    executor = get_executor()
    adapter = executor.adapters.get("mt5")
    if not adapter: return
    
    while True:
        try:
            # 1. Fetch Actual Positions from MT5
            positions = mt5.positions_get()
            if positions is None:
                log.error("MT5: Failed to fetch positions in PnL loop")
                await asyncio.sleep(5)
                continue

            # 2. Sync Account Balance
            account_info = mt5.account_info()
            if account_info:
                state.SHARED_DATA["balance"] = account_info.balance
                state.SHARED_DATA["equity"] = account_info.equity
                if state.SHARED_DATA.get("demo_mode"):
                    state.SHARED_DATA["demo_balance"] = account_info.balance

            # 3. Rebuild active_trades list from MT5 data
            current_active = []
            history = state.SHARED_DATA.get("trade_history", [])
            existing_active = {str(t.get("ticket")): t for t in state.SHARED_DATA.get("active_trades", [])}

            for p in positions:
                ticket_id = str(p.ticket)
                # Calculate PnL manually for UI responsiveness
                pnl = p.profit + p.swap
                
                # --- [SMART TRAILING MONITOR] ---
                if executor.risk_engine.config.enable_trailing_stop:
                    is_long = p.type == mt5.POSITION_TYPE_BUY
                    entry = p.price_open
                    curr = p.price_current
                    current_sl = p.sl
                    tp = p.tp
                    
                    # Logic: Only trail if we are in profit
                    in_profit = (curr > entry) if is_long else (curr < entry)
                    
                    if in_profit and tp > 0:
                        total_dist = abs(tp - entry)
                        prog_dist = abs(curr - entry)
                        progress = prog_dist / total_dist if total_dist > 0 else 0
                        
                        # 1. Break-Even Activation (at 50% progress)
                        activation = executor.risk_engine.config.trailing_stop_activation_pct
                        if progress >= activation:
                            be_level = entry + (0.0001 if is_long else -0.0001) # tiny buffer
                            # Only move if we haven't moved past BE yet
                            if (is_long and current_sl < be_level) or (not is_long and (current_sl > be_level or current_sl == 0)):
                                log.info(f"🛡️ Smart Trailing: Moving Ticket {p.ticket} to Break-Even (+50% goal hit)")
                                adapter.modify_order(p.ticket, be_level, tp)
                        
                        # 2. Continuous Trailing (Once past 75% progress or fixed distance)
                        dist_pct = executor.risk_engine.config.trailing_stop_distance_pct / 100
                        trail_price = curr * (1 - dist_pct) if is_long else curr * (1 + dist_pct)
                        
                        if (is_long and trail_price > current_sl) or (not is_long and (trail_price < current_sl or current_sl == 0)):
                            # Ensure we don't move SL too close (min 50 points)
                            if abs(trail_price - curr) > (curr * 0.0005):
                                log.info(f"🎢 Smart Trailing: Ratcheting Ticket {p.ticket} SL to {trail_price:.5f}")
                                adapter.modify_order(p.ticket, trail_price, tp)
                # -------------------------------

                # Check if we already have this trade recorded (to keep our custom metadata like 'time')
                if ticket_id in existing_active:
                    trade = existing_active[ticket_id]
                    trade["pnl"] = round(pnl, 2)
                    trade["current_price"] = p.price_current
                else:
                    # New trade detected directly from MT5
                    trade = {
                        "ticket": p.ticket,
                        "symbol": p.symbol,
                        "direction": "LONG" if p.type == mt5.POSITION_TYPE_BUY else "SHORT",
                        "entry": p.price_open,
                        "tp": p.tp,
                        "sl": p.sl,
                        "qty": p.volume,
                        "pnl": round(pnl, 2),
                        "status": "ACTIVE",
                        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                current_active.append(trade)

            # 4. Check for trades that were in our list but are now gone from MT5 (Closed)
            current_tickets = {str(p.ticket) for p in positions}
            for ticket, trade in existing_active.items():
                if ticket not in current_tickets:
                    # Trade was closed externally (or via our button)
                    trade["status"] = "CLOSED"
                    trade["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # Add to history if not already there
                    if not any(str(h.get("ticket")) == ticket for h in history):
                        history.insert(0, trade)
            
            state.SHARED_DATA["active_trades"] = current_active
            state.SHARED_DATA["trade_history"] = history[:50]
            
            # 5. Periodically Save Equity Snapshot (Every 100 loops ~ 3 mins)
            if not hasattr(pnl_update_loop, "counter"): pnl_update_loop.counter = 0
            pnl_update_loop.counter += 1
            if pnl_update_loop.counter >= 100:
                pnl_update_loop.counter = 0
                equity = state.SHARED_DATA.get("equity", state.SHARED_DATA.get("balance", 0))
                try:
                    from db_utils import get_db_connection
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO equity_history (total_equity) VALUES (?)", (equity,))
                        conn.commit()
                        conn.close()
                except Exception as e:
                    log.error(f"Equity Log Error: {e}")

            # Broadcast update by saving state
            state.save_shared_state(state.SHARED_DATA)

        except Exception as e:
            log.error("PnL/Sync Loop Error: %s", e)
        await asyncio.sleep(2)

async def failsafe_monitor_loop():
    """
    Sentinel Heartbeat & Drawdown Guard.
    Pings brokers and monitors account health to trigger emergency lockdown if needed.
    """
    log.info("🛡️ Sentinel Fail-Safe Monitor Active (Heartbeat: 15s)")
    executor = get_executor()
    
    while True:
        try:
            # 1. Connectivity Heartbeat
            active_platform = os.getenv("DEFAULT_BROKER", "MT5").lower()
            adapter = executor.adapters.get(active_platform)
            
            if adapter:
                if not adapter.is_connected():
                    log.error(f"🚨 HEARTBEAT LOST: Connection to {active_platform.upper()} failed. Attempting recovery...")
                    telegram_bot.send_message(f"⚠️ *SENTINEL ALERT: Connection Lost*\nBroker: {active_platform.upper()}\nAttempting auto-recovery...")
                    executor.reconnect_all()
                else:
                    # Connection is fine
                    pass
            
            # 2. Hard Drawdown Guard
            equity = state.SHARED_DATA.get("equity", 0)
            if equity > 0:
                is_safe, msg = executor.risk_engine.validate_drawdown(equity)
                if not is_safe:
                    log.critical(f"🚨 {msg}")
                    # EMERGENCY LOCKDOWN
                    state.SHARED_DATA["kill_switch"] = True
                    state.SHARED_DATA["is_bot_active"] = False
                    state.SHARED_DATA["status"] = "LOCKDOWN"
                    
                    # Liquidate All
                    executor.close_all()
                    
                    telegram_bot.send_message(f"🚨 *SENTINEL EMERGENCY LOCKDOWN*\n{msg}\nAll positions liquidated. Trading halted.")
                    state.save_shared_state(state.SHARED_DATA)
                    
                    # Stop loop if in lockdown (requires manual reset)
                    break 

        except Exception as e:
            log.error(f"Failsafe Monitor Error: {e}")
        
        await asyncio.sleep(15) 

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
            asyncio.create_task(pnl_update_loop())
            asyncio.create_task(telegram_bot.poll_commands())
            asyncio.create_task(failsafe_monitor_loop())
            await mt5_polling_loop(symbols, timeframe_str="5m")
        except KeyboardInterrupt:
            log.info("Shutting down...")
        except Exception as e:
            log.error(f"Fatal error in MT5 polling loop: {e}")
    else:
        # Default: Use Binance WebSockets via FeedHandler
        feed = FeedHandler(callback=process_candle, timeframe="5m")
        try:
            asyncio.create_task(telegram_bot.poll_commands())
            asyncio.create_task(failsafe_monitor_loop())
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
