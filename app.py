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
    
    threshold = float(os.getenv("AI_CONFIDENCE_THRESHOLD", 0.90))
    is_ai_approved = confidence >= threshold

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

    # 3. Save to Database (Persist even if rejected)
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
        "ai_rationale": rationale_json,
        "outcome": 0 if is_ai_approved else -2 # -2 for AI REJECTED status
    }
    
    from db_utils import get_db_connection
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signals (symbol, direction, entry_price, take_profit, stop_loss, timeframe, pattern, score, ml_confidence, indicators_meta, ai_rationale, outcome, broker)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_to_save["symbol"], signal_to_save["direction"], signal_to_save["entry_price"],
            signal_to_save["take_profit"], signal_to_save["stop_loss"], signal_to_save["timeframe"],
            signal_to_save["pattern"], signal_to_save["score"], signal_to_save["ml_confidence"],
            signal_to_save["indicators_meta"], signal_to_save["ai_rationale"], signal_to_save["outcome"],
            BROKER_TYPE
        ))
        conn.commit()
        conn.close()

    # 4. Add to Dashboard Feed instantly
    status_label = "ACTIVE" if is_ai_approved else "REJECTED"
    state.SHARED_DATA["signals"].insert(0, {
        "id": f"SIG-{int(datetime.now().timestamp())}",
        "symbol": symbol,
        "direction": raw_signal["direction"],
        "entry": raw_signal["entry"],
        "tp": raw_signal["tp1"],
        "sl": raw_signal["sl"],
        "pattern": raw_signal["pattern"],
        "score": raw_signal["score"],
        "confidence": f"{int(confidence*100)}%",
        "status": status_label,
        "broker": BROKER_TYPE,
        "ai_rationale": explain_report.summary if explain_report else "SMC TECHNICAL FLOW",
        "created_at": datetime.now().strftime("%H:%M:%S")
    })
    # Keep only the last 15 signals
    state.SHARED_DATA["signals"] = state.SHARED_DATA["signals"][:15]

    if not is_ai_approved:
        log.warning("🛡️ AI SENTINEL REJECTED: %s (Confidence: %.1f%% < %.1f%%)", 
                    symbol, confidence * 100, threshold * 100)
        state.SHARED_DATA["status"] = f"AI REJECTED {symbol}"
        return

    raw_signal["symbol"] = symbol
    log.info(
        "[SIGNAL] PATTERN DETECTED & AI APPROVED: %s | Score: %s | Confidence: %.1f%%",
        raw_signal.get("pattern"),
        raw_signal.get("score"),
        confidence * 100
    )

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

    brokers_to_execute = [BROKER_TYPE]
    mirror_brokers = os.getenv("MIRROR_BROKERS", "")
    if mirror_brokers:
        additional = [b.strip() for b in mirror_brokers.split(",") if b.strip()]
        for b in additional:
            if b not in brokers_to_execute:
                brokers_to_execute.append(b)

    success_count = 0
    for broker in brokers_to_execute:
        res = get_executor().place_trade(signal, platform=broker)
        if res and res.get("status") == "success":
            log.info("✅ Trade Executed Successfully on %s", broker.upper())
            success_count += 1
        else:
            msg = res.get("message", "Unknown Error") if res else "No response"
            log.error("❌ Execution Failed on %s: %s", broker.upper(), msg)
            
    if success_count > 0:
        # Send Telegram Notification ONCE
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
    threshold = float(os.getenv("AI_CONFIDENCE_THRESHOLD", 0.90))
    
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
    
    # 5.5 Add to Dashboard Feed instantly
    state.SHARED_DATA["signals"].insert(0, {
        "id": f"SIG-{int(datetime.now().timestamp())}",
        "symbol": symbol,
        "direction": raw_signal["type"],
        "entry": raw_signal["entry"],
        "tp": raw_signal["take_profit"],
        "sl": raw_signal["stop_loss"],
        "pattern": "GodMode",
        "score": raw_signal["score"],
        "confidence": f"{int(confidence*100)}%",
        "status": "ACTIVE",
        "broker": BROKER_TYPE,
        "ai_rationale": explain_report.summary if explain_report else "GOD-MODE TECHNICAL FLOW",
        "created_at": datetime.now().strftime("%H:%M:%S")
    })
    state.SHARED_DATA["signals"] = state.SHARED_DATA["signals"][:15]
    
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

    brokers_to_execute = [BROKER_TYPE]
    mirror_brokers = os.getenv("MIRROR_BROKERS", "")
    if mirror_brokers:
        additional = [b.strip() for b in mirror_brokers.split(",") if b.strip()]
        for b in additional:
            if b not in brokers_to_execute:
                brokers_to_execute.append(b)

    success_count = 0
    for broker in brokers_to_execute:
        res = get_executor().place_trade(signal, platform=broker)
        if res and res.get("status") == "success":
            log.info("✅ God-Mode Trade Executed Successfully on %s", broker.upper())
            success_count += 1
        else:
            msg = res.get("message", "Unknown Error") if res else "No response"
            log.error("❌ God-Mode Execution Failed on %s: %s", broker.upper(), msg)

    if success_count > 0:
        # Send Telegram Notification ONCE
        telegram_bot.send_signal_alert(raw_signal)
        
        # Record trade for dashboard visibility ONCE
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
            # Global Exness Fix: Ensure the suffix is ALWAYS a lowercase 'm'
            symbol = symbol.upper()
            if symbol.endswith('M'):
                symbol = symbol[:-1] + 'm'
            try:
                # Concurrent MTF fetching with timeout to prevent loop hanging
                tasks = [
                    asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_M5, 500),
                    asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_M15, 200),
                    asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_H1, 200),
                ]
                # Wait maximum 15s for MT5 response
                results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=15.0)
                
                m5_df, m15_df, h1_df = results
                
                if not m5_df.empty:
                    # Pass MTF bundle to processor
                    bundle = {
                        'm5': m5_df,
                        'm15': m15_df if not m15_df.empty else None,
                        'h1': h1_df if not h1_df.empty else None
                    }
                    await process_candle(symbol, bundle)
            except asyncio.TimeoutError:
                log.error("⏳ MT5 Polling Timeout for %s - terminal might be unresponsive", symbol)
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
    """Rapid loop to fetch actual positions from all brokers and sync the dashboard state."""
    executor = get_executor()
    
    while True:
        try:
            # 1. Initialize broker stats if missing
            if "broker_stats" not in state.SHARED_DATA:
                state.SHARED_DATA["broker_stats"] = {}

            # 2. Loop through all active adapters
            for broker_id, adapter in executor.adapters.items():
                try:
                    balance_info = adapter.get_balance()
                    if balance_info:
                        equity = 0.0
                        balance = 0.0
                        
                        if broker_id == "mt5":
                            equity = balance_info.get("equity", 0)
                            balance = balance_info.get("balance", 0)
                        elif broker_id == "binance":
                            equity = float(balance_info.get("total", {}).get("USDT", 0))
                            balance = equity
                        elif broker_id == "alpaca":
                            equity = float(getattr(balance_info, "equity", 0))
                            balance = float(getattr(balance_info, "balance", 0))
                        elif broker_id == "okx":
                            # OKX balance structure via CCXT
                            equity = float(balance_info.get("total", {}).get("USDT", 0))
                            balance = equity

                        # Calculate PnL: Use equity-balance for MT5, or sum active trades PnL for others
                        if broker_id == "mt5":
                            broker_pnl = equity - balance
                        else:
                            # Fallback: Sum PnL of active trades assigned to this broker or matching its assets
                            # For simplicity, we sum all if this is the primary or it's crypto
                            broker_pnl = sum(t.get("pnl", 0) for t in state.SHARED_DATA.get("active_trades", []))
                        
                        state.SHARED_DATA["broker_stats"][broker_id] = {
                            "equity": round(equity, 2),
                            "balance": round(balance, 2),
                            "pnl": round(broker_pnl, 2),
                            "last_update": datetime.now().strftime("%H:%M:%S")
                        }
                        
                        # Sync main display if this is the default broker
                        if broker_id == os.getenv("DEFAULT_BROKER", "mt5").lower():
                            state.SHARED_DATA["balance"] = balance
                            state.SHARED_DATA["equity"] = equity
                except Exception as ex:
                    log.error(f"Error fetching balance for {broker_id}: {ex}")

            # 3. Sync MT5 Specific Positions (Special trailing logic)
            adapter = executor.adapters.get("mt5")
            if adapter:
                positions = mt5.positions_get()
                if positions:
                    current_active = []
                    history = state.SHARED_DATA.get("trade_history", [])
                    existing_active = {str(t.get("ticket")): t for t in state.SHARED_DATA.get("active_trades", [])}

                    for p in positions:
                        ticket_id = str(p.ticket)
                        pnl = p.profit + p.swap
                        
                        # --- [SMART TRAILING MONITOR (1:1 BE+ Logic)] ---
                        if executor.risk_engine.config.enable_trailing_stop:
                            is_long = p.type == mt5.POSITION_TYPE_BUY
                            curr = p.price_current
                            current_sl = p.sl
                            
                            # Get original entry/sl from state to calculate 1:1 RR distance
                            orig_trade = existing_active.get(ticket_id)
                            if orig_trade:
                                orig_entry = float(orig_trade.get("entry", p.price_open))
                                orig_sl = float(orig_trade.get("sl", current_sl))
                                
                                risk_dist = abs(orig_entry - orig_sl)
                                prog_dist = abs(curr - orig_entry)
                                
                                # Check if 1:1 RR is reached (prog_dist >= risk_dist)
                                in_profit = (curr > orig_entry) if is_long else (curr < orig_entry)
                                if in_profit and prog_dist >= risk_dist and risk_dist > 0:
                                    # Lock in 10% of risk distance as profit (dynamically scales to asset pip size)
                                    lock_in_dist = risk_dist * 0.1
                                    be_level = orig_entry + lock_in_dist if is_long else orig_entry - lock_in_dist
                                    
                                    # Only move SL if it's an improvement
                                    if (is_long and current_sl < be_level) or (not is_long and (current_sl > be_level or current_sl == 0)):
                                        log.info("🛡️ TRAILING STOP: Locking in BE+ for %s ticket %s", p.symbol, ticket_id)
                                        adapter.modify_order(p.ticket, be_level, p.tp)
                        
                        if ticket_id in existing_active:
                            trade = existing_active[ticket_id]
                            trade["pnl"] = round(pnl, 2)
                        else:
                            trade = {
                                "ticket": p.ticket, "symbol": p.symbol, "direction": "LONG" if p.type == mt5.POSITION_TYPE_BUY else "SHORT",
                                "entry": p.price_open, "tp": p.tp, "sl": p.sl, "qty": p.volume, "pnl": round(pnl, 2),
                                "status": "ACTIVE", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            }
                        current_active.append(trade)
                    state.SHARED_DATA["active_trades"] = current_active

            # 5. Periodically Save Equity Snapshot
            if not hasattr(pnl_update_loop, "counter"): pnl_update_loop.counter = 0
            pnl_update_loop.counter += 1
            if pnl_update_loop.counter >= 100:
                pnl_update_loop.counter = 0
                equity = state.SHARED_DATA.get("equity", 0)
                try:
                    from db_utils import get_db_connection
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO equity_history (total_equity) VALUES (?)", (equity,))
                        conn.commit()
                        conn.close()
                except: pass

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

    # Launch Web Dashboard Server (Internal API)
    log.info("🌐 Launching Internal API on http://0.0.0.0:8000")
    
    # Pre-sync state
    state.SHARED_DATA["auto_trade"] = os.getenv("AUTO_TRADE_ENABLED", "false").lower() == "true"
    state.SHARED_DATA["demo_mode"] = os.getenv("DEMO_MODE", "true").lower() == "true"
    state.SHARED_DATA["active_profile"] = os.getenv("ACTIVE_PROFILE", "CONSERVATIVE")
    state.SHARED_DATA["risk_config"] = get_executor().risk_engine.config.dict()
    
    import web_server
    web_thread = threading.Thread(target=web_server.run_server, args=("0.0.0.0", 8000), daemon=True)
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
