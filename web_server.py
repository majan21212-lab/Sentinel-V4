from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import os
import sqlite3
import asyncio
from datetime import datetime
import logging
import random
import time

import pandas as pd
import state_manager as state
from fastapi.middleware.cors import CORSMiddleware
import mimetypes

mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    import sys
    try:
        base_path = sys._MEIPASS
    except Exception:
        # Use the directory containing this script as the base path
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

FLEET_SUBSCRIBERS = set()
logger = logging.getLogger("WEB_SERVER")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware to handle the /web-api prefix from the frontend build
@app.middleware("http")
async def strip_web_api_prefix(request: Request, call_next):
    if request.url.path.startswith("/web-api"):
        new_scope = request.scope.copy()
        new_scope['path'] = request.scope['path'].replace("/web-api", "", 1)
        # Create a new request with the modified scope
        from starlette.requests import Request as StarletteRequest
        new_request = StarletteRequest(new_scope)
        return await call_next(new_request)
    return await call_next(request)

from dotenv import load_dotenv
load_dotenv()
DB_FILE = os.getenv('DB_NAME', 'trading_bot.db')
if not DB_FILE.endswith('.db'): DB_FILE += '.db'
DB_PATH = os.path.abspath(DB_FILE)

SHARED_DATA = state.SHARED_DATA

@app.get("/api/performance")
async def get_performance():
    """Returns rich performance data: equity curve, live PnL, per-asset breakdown, and session stats."""
    try:
        from db_utils import get_db_connection
        conn = get_db_connection()
        if not conn: return JSONResponse(content={"error": "DB Connection Failed"})

        # 1. Equity Curve (last 100 points, chronological)
        query_equity = "SELECT total_equity as equity, timestamp as time FROM equity_history ORDER BY id DESC LIMIT 100"
        df_equity = pd.read_sql_query(query_equity, conn).iloc[::-1]

        # 2. Closed trade metrics
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM signals WHERE outcome != 0")
        total_trades = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM signals WHERE outcome = 1")
        wins = cursor.fetchone()[0]
        losses = total_trades - wins
        win_rate = round((wins / total_trades * 100), 1) if total_trades > 0 else 0

        # Calculate Profit Factor
        cursor.execute("SELECT SUM(CASE WHEN outcome = 1 THEN 1.0 ELSE 0.0 END), SUM(CASE WHEN outcome = -1 THEN 1.0 ELSE 0.0 END) FROM signals")
        pf_row = cursor.fetchone()
        gross_profit = pf_row[0] or 0
        gross_loss = pf_row[1] or 0
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0)

        # Simplified Sharpe Ratio from Equity History
        sharpe = 0
        if not df_equity.empty and len(df_equity) > 1:
            returns = df_equity['equity'].pct_change().dropna()
            if not returns.empty and returns.std() > 0:
                sharpe = round((returns.mean() / returns.std()) * (252**0.5), 2) # Annualized

        # 3. Total open signals
        cursor.execute("SELECT COUNT(*) FROM signals WHERE outcome = 0")
        open_signals = cursor.fetchone()[0]

        # 4. All signals count + avg confidence
        cursor.execute("SELECT COUNT(*), AVG(ml_confidence) FROM signals")
        row = cursor.fetchone()
        total_signals = row[0] or 0
        avg_confidence = round((row[1] or 0) * 100, 1)

        # 5. Per-asset breakdown
        cursor.execute("""
            SELECT symbol,
                   COUNT(*) as total,
                   SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN outcome = -1 THEN 1 ELSE 0 END) as losses,
                   SUM(CASE WHEN outcome = 0 THEN 1 ELSE 0 END) as open,
                   AVG(ml_confidence) as avg_conf
            FROM signals
            GROUP BY symbol
            ORDER BY total DESC
        """)
        asset_rows = cursor.fetchall()
        asset_breakdown = [
            {
                "symbol": r[0], "total": r[1], "wins": r[2] or 0,
                "losses": r[3] or 0, "open": r[4] or 0,
                "avg_conf": round((r[5] or 0) * 100, 1)
            }
            for r in asset_rows
        ]

        # 6. Best performing asset
        cursor.execute("SELECT symbol, COUNT(*) as c FROM signals WHERE outcome = 1 GROUP BY symbol ORDER BY c DESC LIMIT 1")
        best_row = cursor.fetchone()
        best_symbol = best_row[0] if best_row else "XAUUSDm"

        conn.close()

        # 7. Live data from shared state
        live_equity   = SHARED_DATA.get("equity", SHARED_DATA.get("balance", 0))
        active_trades = SHARED_DATA.get("active_trades", [])
        live_pnl      = sum(t.get("pnl", 0) for t in active_trades)
        active_count  = len(active_trades)

        # 8. Historical profit from equity curve
        if len(df_equity) > 1:
            hist_profit = round(df_equity['equity'].iloc[-1] - df_equity['equity'].iloc[0], 2)
        else:
            hist_profit = 0.0

        # 9. Daily goal tracking ($50 target)
        daily_goal    = 50.0
        daily_progress = min(round((live_pnl / daily_goal) * 100, 1), 100) if daily_goal > 0 else 0

        return JSONResponse(content={
            "chart_data": df_equity.to_dict(orient='records'),
            "metrics": {
                "win_rate":       win_rate,
                "total_profit":   round(hist_profit + live_pnl, 2),
                "total_trades":   total_trades,
                "best_asset":     best_symbol,
                "wins":           wins,
                "losses":         losses,
                "open_signals":   open_signals,
                "total_signals":  total_signals,
                "avg_confidence": avg_confidence,
                "profit_factor":  profit_factor,
                "sharpe_ratio":   sharpe
            },
            "live": {
                "equity":         round(live_equity, 2),
                "open_pnl":       round(live_pnl, 2),
                "active_trades":  active_count,
                "daily_goal":     daily_goal,
                "daily_progress": daily_progress,
            },
            "asset_breakdown": asset_breakdown,
        })
    except Exception as e:
        logger.error(f"Performance API Error: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/analytics")
async def get_analytics():
    """Returns win-rate analytics grouped by pattern."""
    try:
        from db_utils import get_db_connection
        conn = get_db_connection()
        if not conn: return JSONResponse(content={})
        query = "SELECT pattern, COUNT(*) as total, SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as wins FROM signals WHERE outcome != 0 GROUP BY pattern"
        df = pd.read_sql_query(query, conn)
        conn.close()
        if df.empty: return JSONResponse(content={})
        df['accuracy'] = (df['wins'] / df['total'] * 100).round(1)
        return JSONResponse(content=df.set_index('pattern')['accuracy'].to_dict())
    except:
        return JSONResponse(content={})

@app.get("/")
async def get_index():
    response = FileResponse(get_resource_path("Elirox/index.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/api/status")
async def get_status():
    return JSONResponse(content=SHARED_DATA)

@app.get("/api/signals")
async def get_signals():
    """Returns historical signals with full trade intelligence data including calculated P&L."""
    try:
        from db_utils import get_db_connection
        conn = get_db_connection()
        if not conn: return JSONResponse(content=[])
        
        query = """
            SELECT id, symbol, direction, entry_price as entry, take_profit as tp, 
                   stop_loss as sl, pattern, score, ml_confidence as confidence, 
                   created_at as time, outcome, ai_rationale
            FROM signals 
            ORDER BY id DESC 
            LIMIT 50
        """
        df = pd.read_sql_query(query, conn)
        conn.close()

        # Replace ALL NaN values — string NaN columns also break JSON serialization
        df = df.where(pd.notna(df), None)
        df['score']      = pd.to_numeric(df['score'],      errors='coerce').fillna(0)
        df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce').fillna(0)
        df['entry']      = pd.to_numeric(df['entry'],      errors='coerce').fillna(0)
        df['tp']         = pd.to_numeric(df['tp'],         errors='coerce').fillna(0)
        df['sl']         = pd.to_numeric(df['sl'],         errors='coerce').fillna(0)
        df['outcome']    = pd.to_numeric(df['outcome'],    errors='coerce').fillna(0).astype(int)
        df['pattern']    = df['pattern'].fillna('Unknown Pattern')
        df['time']       = df['time'].fillna('N/A')

        if df.empty:
            return JSONResponse(content=SHARED_DATA.get("signals", []))


        # Build a lookup of live trade PnL from active_trades and trade_history
        live_pnl_lookup = {}
        for t in SHARED_DATA.get("active_trades", []):
            live_pnl_lookup[t.get("symbol", "")] = t.get("pnl", 0)

        def estimate_profit(row):
            """Estimate dollar profit for a signal based on outcome, TP/SL, and contract rules."""
            entry = row.get('entry') or 0
            tp = row.get('tp') or 0
            sl = row.get('sl') or 0
            outcome = row.get('outcome', 0)
            symbol = row.get('symbol', '')
            direction = (row.get('direction') or '').upper()
            lot = 0.01  # default minimum lot

            if outcome == 0:
                # Still running — check live PnL from MT5
                live = live_pnl_lookup.get(symbol)
                if live is not None:
                    return round(live, 2), True
                return None, True  # running but no data yet

            # Calculate pip distance
            if outcome == 1:   # Win — hit TP
                diff = (tp - entry) if direction in ('LONG', 'BUY') else (entry - tp)
            else:              # Loss — hit SL
                diff = (sl - entry) if direction in ('LONG', 'BUY') else (entry - sl)

            # Contract size by instrument type
            if 'XAU' in symbol or 'GOLD' in symbol:
                pnl = diff * 100 * lot
            elif 'BTC' in symbol:
                pnl = diff * lot
            elif 'ETH' in symbol:
                pnl = diff * lot
            elif 'XRP' in symbol:
                pnl = diff * lot
            elif 'US30' in symbol or 'DJ' in symbol:
                pnl = diff * 1 * lot
            elif 'JPY' in symbol:
                pnl = (diff * 100000 * lot) / max(entry, 1)
            else:  # Standard forex
                pnl = diff * 100000 * lot

            return round(pnl, 2), False

        results = []
        for _, row in df.iterrows():
            pnl_value, is_running = estimate_profit(row)

            if is_running:
                if pnl_value is not None:
                    pnl_display = f"{'+' if pnl_value >= 0 else ''}${pnl_value:.2f}"
                    pnl_status = "running"
                else:
                    pnl_display = "LIVE"
                    pnl_status = "running"
            elif pnl_value is not None:
                pnl_display = f"{'+' if pnl_value >= 0 else ''}${pnl_value:.2f}"
                pnl_status = "win" if pnl_value >= 0 else "loss"
            else:
                pnl_display = "-"
                pnl_status = "none"

            results.append({
                "id": f"SIG-{row['id']}",
                "symbol": row['symbol'],
                "action": row['direction'],
                "price": row['entry'],
                "tp": row['tp'],
                "sl": row['sl'],
                "pattern": row['pattern'],
                "score": f"{int(float(row['score'] or 0))}/100",
                "confidence": f"{int(float(row['confidence'] or 0)*100)}%",
                "status": "Closed" if row['outcome'] != 0 else "Open",
                "timestamp": row['time'],
                "profit": pnl_display,
                "pnl_status": pnl_status,
                "ai_rationale": row.get('ai_rationale')
            })
        return JSONResponse(content=results)
    except Exception as e:
        logger.error(f"Signal Intel Error: {e}")
        return JSONResponse(content=SHARED_DATA.get("signals", []))

# --- AUTH SYSTEM ---
SECRET_KEY = "fleet_command_secure_key_2026"
USERS = {"admin": "admin"} # Default credentials

@app.post("/api/auth/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username")
    password = data.get("password")
    
    if USERS.get(username) == password:
        # Simple token for local demo
        token = f"fleet_{username}_{int(time.time())}"
        return JSONResponse(content={"token": token, "user": {"username": username, "role": "Commander"}})
    
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/auth/me")
async def get_me(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer fleet_"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    username = auth_header.split("_")[1]
    return JSONResponse(content={"username": username, "role": "Commander"})

# --- LOG STREAMING ---
@app.get("/api/logs")
async def get_logs():
    """Returns the last 50 lines of the sentinel log for the dashboard terminal."""
    log_file = "sentinel.log"
    if not os.path.exists(log_file):
        # Create it if it doesn't exist
        with open(log_file, "w", encoding="utf-8") as f: f.write("--- Fleet Command Log Initialised ---\n")
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return JSONResponse(content=lines[-50:])
    except Exception as e:
        return JSONResponse(content=[f"Error reading logs: {str(e)}"])

@app.post("/api/settings")
async def update_settings(request: Request):
    data = await request.json()
    logger.info(f"Updating Settings: {data}")
    
    if "is_bot_active" in data: state.SHARED_DATA["is_bot_active"] = bool(data["is_bot_active"])
    if "demo_mode" in data: state.SHARED_DATA["demo_mode"] = bool(data["demo_mode"])
    if "auto_trade" in data: state.SHARED_DATA["auto_trade"] = bool(data["auto_trade"])
    if "active_broker" in data: state.SHARED_DATA["active_broker"] = data["active_broker"]
    if "strategy_mode" in data: state.SHARED_DATA["strategy_mode"] = data["strategy_mode"]
    if "kill_switch" in data: state.SHARED_DATA["kill_switch"] = bool(data["kill_switch"])
    if "status" in data: state.SHARED_DATA["status"] = data["status"]
    
    # Advanced Risk Config
    if "risk_config" in data:
        if "risk_config" not in state.SHARED_DATA: state.SHARED_DATA["risk_config"] = {}
        state.SHARED_DATA["risk_config"].update(data["risk_config"])
        
    # Identity & Notifications
    if "telegram_token" in data: state.SHARED_DATA["telegram_token"] = data["telegram_token"]
    if "telegram_chat_id" in data: state.SHARED_DATA["telegram_chat_id"] = data["telegram_chat_id"]
    
    if "active_markets" in data:
        state.SHARED_DATA["active_markets"] = data["active_markets"]
        
    if "fund_action" in data:
        action = data["fund_action"]
        try:
            amt = float(data.get("amount", 0))
            if amt <= 0 and action != "reset":
                return JSONResponse(status_code=400, content={"status": "error", "message": "Amount must be positive"})
                
            is_demo = state.SHARED_DATA.get("active_broker", "DEMO") == "DEMO"
            bal_key = "demo_balance" if is_demo else "balance"
            current_bal = state.SHARED_DATA.get(bal_key, 0.0)
            
            from db_utils import log_transaction
            
            if action == "deposit":
                new_bal = current_bal + amt
                state.SHARED_DATA[bal_key] = new_bal
                log_transaction("deposit", amt, current_bal, new_bal)
            elif action == "withdraw":
                if current_bal < amt:
                    log_transaction("withdraw", amt, current_bal, current_bal, status='failed: insufficient funds')
                    return JSONResponse(status_code=400, content={"status": "error", "message": "Insufficient funds for withdrawal"})
                new_bal = current_bal - amt
                state.SHARED_DATA[bal_key] = new_bal
                log_transaction("withdraw", amt, current_bal, new_bal)
            elif action == "reset":
                state.SHARED_DATA[bal_key] = 0.0
                log_transaction("reset", current_bal, current_bal, 0.0)
                
        except Exception as e:
            logger.error(f"Funding Error: {e}")
            return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    
    if "credentials" in data:
        creds = data["credentials"]
        for broker, keys in creds.items():
            os.environ[f"{broker.upper()}_API_KEY"] = keys["key"]
            os.environ[f"{broker.upper()}_SECRET"] = keys["secret"]
            # Persistence
            with open(".env", "a") as f:
                f.write(f"\n{broker.upper()}_API_KEY={keys['key']}")
                f.write(f"\n{broker.upper()}_SECRET={keys['secret']}")
    
    # Update Engine State
    executor = state.get_executor()
    if executor:
        from models import ExecutionMode
        executor.risk_engine.config.execution_mode = ExecutionMode.DEMO if state.SHARED_DATA["demo_mode"] else ExecutionMode.LIVE
        state.SHARED_DATA["risk_config"] = executor.risk_engine.config.dict()
    
    state.save_shared_state(state.SHARED_DATA)
    logger.info(f"Saving State... is_bot_active={state.SHARED_DATA.get('is_bot_active')}")
    return JSONResponse(content={"status": "success", "config": state.SHARED_DATA.get("risk_config", {})})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    FLEET_SUBSCRIBERS.add(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        FLEET_SUBSCRIBERS.remove(websocket)
    except Exception:
        if websocket in FLEET_SUBSCRIBERS:
            FLEET_SUBSCRIBERS.remove(websocket)

async def broadcast_data():
    """Background task to push SHARED_DATA to all connected dashboard clients."""
    while True:
        try:
            # Sync from disk and update the in-memory state dictionary
            saved_state = state.load_shared_state()
            state.SHARED_DATA.update(saved_state)
            
            if FLEET_SUBSCRIBERS:
                payload = {
                    "type": "FLEET_UPDATE",
                    "timestamp": datetime.now().strftime("%H:%M:%S"),
                    "data": state.SHARED_DATA
                }
                payload_json = json.dumps(payload)
                disconnected = set()
                for ws in list(FLEET_SUBSCRIBERS):
                    try:
                        await ws.send_text(payload_json)
                    except:
                        disconnected.add(ws)
                for ws in disconnected:
                    if ws in FLEET_SUBSCRIBERS:
                        FLEET_SUBSCRIBERS.remove(ws)
        except Exception as e:
            print(f"Broadcast Error: {e}")
        await asyncio.sleep(1.0) # Sync every second

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_data())

@app.post("/api/test_jewel_elite")
async def simulate_jewel_elite():
    test_sig = {
        "id": 8888, 
        "symbol": "XAUUSDm", 
        "direction": "LONG", 
        "entry": 2350.50, 
        "tp": 2380.00, 
        "sl": 2335.00, 
        "timeframe": "M15", 
        "pattern": "Institutional Liquidity Sweep (G.A.B v1.0)",
        "created_at": datetime.now().strftime("%H:%M:%S")
    }
    SHARED_DATA["signals"] = [test_sig] + SHARED_DATA.get("signals", [])
    state.save_shared_state(SHARED_DATA)
    return JSONResponse(content={"status": "success", "message": "Jewel Elite Institutional Signal Injected"})

@app.post("/api/connect_broker")
async def connect_broker(request: Request):
    """Securely links a new broker account."""
    try:
        data = await request.json()
        broker = data.get("broker")
        api_key = data.get("api_key")
        
        logger.info(f"Establishing link with {broker} using key: {api_key[:5]}***")
        
        # In a real scenario, initialize the adapter here
        # For this demo, we simulate success
        return JSONResponse(content={"status": "success", "message": f"{broker} connected successfully"})
    except Exception as e:
        logger.error(f"Connection Error: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.post("/api/action")
async def trigger_action(request: Request):
    """Executes a system action like testing connection or re-syncing data."""
    try:
        data = await request.json()
        action = data.get("action")
        broker = data.get("broker", "General")
        
        logger.info(f"⚡ ACTION TRIGGERED: {action} on {broker}")
        
        if action == "test_connection":
            # Simulate a real broker ping
            import random
            success = random.random() > 0.1 # 90% success rate for demo
            if success:
                return JSONResponse(content={"status": "success", "message": f"Connection to {broker} is STABLE."})
            else:
                return JSONResponse(status_code=500, content={"status": "error", "message": f"Connection to {broker} FAILED. Check API keys."})
        
        elif action == "resync":
            # Force refresh of shared data
            state.save_shared_state(SHARED_DATA)
            return JSONResponse(content={"status": "success", "message": f"Data Resynchronization for {broker} complete."})
            
        elif action == "disconnect_broker":
            # Remove from active markets and clear session
            if broker in SHARED_DATA.get("active_markets", []):
                SHARED_DATA["active_markets"].remove(broker)
            state.save_shared_state(SHARED_DATA)
            return JSONResponse(content={"status": "success", "message": f"{broker} has been disconnected."})
            
        elif action == "close_trade":
            trade_id = data.get("trade_id")
            logger.warning(f"Closing trade {trade_id} manually from dashboard")
            return JSONResponse(content={"status": "success", "message": f"Closed trade {trade_id}"})
            
        elif action == "approve_signal":
            signal_id = data.get("signal_id")
            logger.info(f"Manually approved signal {signal_id}")
            return JSONResponse(content={"status": "success", "message": f"Signal {signal_id} approved for execution"})

        return JSONResponse(status_code=400, content={"status": "error", "message": "Unknown action"})
    except Exception as e:
        logger.error(f"Action Error: {e}")
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/close_position")
async def close_position(request: Request):
    """Closes a specific active position."""
    try:
        data = await request.json()
        symbol = data.get("symbol")
        logger.info(f"🛑 Manual Close Requested for {symbol}")
        
        active_trades = SHARED_DATA.get("active_trades", [])
        
        # Trigger actual broker close
        executor = state.get_executor()
        res = executor.close_symbol(symbol)
        
        if res.get("status") == "success":
            closed_trade = next((t for t in active_trades if t["symbol"] == symbol), None)
            if closed_trade:
                closed_trade["status"] = "CLOSED"
                closed_trade["closed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                history = SHARED_DATA.get("trade_history", [])
                history.insert(0, closed_trade) # Add to start
                SHARED_DATA["trade_history"] = history[:50] # Keep last 50
                
            new_trades = [t for t in active_trades if t["symbol"] != symbol]
            SHARED_DATA["active_trades"] = new_trades
            state.save_shared_state(SHARED_DATA)
            return JSONResponse(content={"status": "success", "message": f"Position {symbol} closed"})
        else:
            return JSONResponse(status_code=500, content={"status": "error", "message": res.get("message", "Broker rejection")})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/panic_close")
async def panic_close():
    """Liquidates all positions across all brokers."""
    try:
        logger.warning("🚨 PANIC CLOSE TRIGGERED FROM DASHBOARD")
        executor = state.get_executor()
        res = executor.close_all()
        
        SHARED_DATA["active_trades"] = []
        state.save_shared_state(SHARED_DATA)
        return JSONResponse(content={"status": "success", "results": res})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    """Entry point for Sovereign Institutional signals."""
    try:
        data = await request.json()
        logger.info(f"🏛️ RECEIVED SOVEREIGN WEBHOOK: {data}")

        # ── Secret Key Validation ──────────────────────────────────────
        expected_secret = os.getenv("WEBHOOK_SECRET", "SENTINEL_V4_SECRET")
        if data.get("secret") != expected_secret:
            logger.warning(f"🚫 Rejected webhook — invalid secret from {request.client.host}")
            from fastapi.responses import JSONResponse as _JSONResponse
            return _JSONResponse(status_code=401, content={"status": "error", "message": "Unauthorized"})
        
        # 1. Identify Action
        action = data.get("action", "buy").lower()
        symbol = data.get("ticker", "UNKNOWN")
        
        # 2. Map to standardized Signal for Dashboard visibility
        signal_summary = {
            "id": random.randint(1000, 9999),
            "symbol": symbol,
            "direction": "LONG" if action == "buy" else "SHORT" if action == "sell" else action.upper(),
            "entry": float(data.get("price", 0)),
            "tp": float(data.get("tp", 0)),
            "sl": float(data.get("sl", 0)),
            "pattern": data.get("pattern", f"Sovereign {action.capitalize()}"),
            "score": float(data.get("score", 0)),
            "timeframe": data.get("timeframe", ""),
            "created_at": datetime.now().strftime("%H:%M:%S")
        }
        
        # 3. Inject into shared state for dashboard visibility
        SHARED_DATA["signals"] = [signal_summary] + SHARED_DATA.get("signals", [])
        # Keep only the last 15 signals
        SHARED_DATA["signals"] = SHARED_DATA["signals"][:15]
        
        # 4. Trigger execution gateway if bot is active
        res = {"status": "accepted", "message": "Signal received"}
        if SHARED_DATA.get("is_bot_active"):
            executor = state.get_executor()
            # Run execution in a separate thread/task if it's blocking
            res = executor.handle_webhook_action(data)
            logger.info(f"🚀 Execution Result: {res}")

        return JSONResponse(content={"status": "success", "signal_id": signal_summary["id"], "execution": res})
    except Exception as e:
        logger.error(f"❌ Webhook Error: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

@app.post("/api/market/toggle")
async def toggle_market(request: Request):
    data = await request.json()
    symbol = data.get("symbol")
    if symbol in SHARED_DATA["market_configs"]:
        current = SHARED_DATA["market_configs"][symbol]["enabled"]
        SHARED_DATA["market_configs"][symbol]["enabled"] = not current
        
        # Update active_markets list
        SHARED_DATA["active_markets"] = [s for s, c in SHARED_DATA["market_configs"].items() if c["enabled"]]
        
        state.save_shared_state(SHARED_DATA)
        return JSONResponse(content={"status": "success", "enabled": not current})
    return JSONResponse(status_code=404, content={"status": "error", "message": "Symbol not found"})

@app.post("/api/market/add")
async def add_market(request: Request):
    data = await request.json()
    symbol = data.get("symbol").strip()
    if symbol:
        if symbol not in SHARED_DATA["market_configs"]:
            SHARED_DATA["market_configs"][symbol] = {"enabled": True, "strategy": "JEWEL_ELITE"}
            SHARED_DATA["active_markets"] = [s for s, c in SHARED_DATA["market_configs"].items() if c["enabled"]]
            state.save_shared_state(SHARED_DATA)
            return JSONResponse(content={"status": "success"})
        return JSONResponse(content={"status": "exists"})
    return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid symbol"})

@app.post("/api/market/remove")
async def remove_market(request: Request):
    data = await request.json()
    symbol = data.get("symbol")
    if symbol in SHARED_DATA["market_configs"]:
        del SHARED_DATA["market_configs"][symbol]
        SHARED_DATA["active_markets"] = [s for s, c in SHARED_DATA["market_configs"].items() if c["enabled"]]
        state.save_shared_state(SHARED_DATA)
        return JSONResponse(content={"status": "success"})
    return JSONResponse(status_code=404, content={"status": "error", "message": "Symbol not found"})

# Catch-all: serve index.html for any unmatched GET (React Router SPA support)
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # Don't intercept /api/*, /web-api/* or /ws routes
    if full_path.startswith("api/") or full_path.startswith("web-api/") or full_path == "ws":
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    # Serve static assets directly if they exist
    asset_path = get_resource_path(f"Elirox/{full_path}")
    if os.path.isfile(asset_path):
        return FileResponse(asset_path)
    # Otherwise fall back to index.html for React routing
    return FileResponse(get_resource_path("Elirox/index.html"))

def run_server(host="0.0.0.0", port=8000):
    # Start the broadcast task within the event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(broadcast_data())
    
    config = uvicorn.Config(app, host=host, port=port, log_level="info", loop=loop)
    server = uvicorn.Server(config)
    loop.run_until_complete(server.serve())

if __name__ == "__main__":
    run_server()
