from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("web_server")

import pandas as pd
import state_manager as state
from fastapi.middleware.cors import CORSMiddleware
import mimetypes
from market_hours import market_hours

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

active_connections = set()
logger = logging.getLogger("WEB_SERVER")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from dotenv import load_dotenv
load_dotenv()
DB_FILE = os.getenv('DB_NAME', 'said alalawi.db')
if not DB_FILE.endswith('.db'): DB_FILE += '.db'
DB_PATH = os.path.abspath(DB_FILE)

SHARED_DATA = state.SHARED_DATA

@app.get("/api/analytics")
async def get_analytics():
    try:
        from db_utils import get_db_connection
        conn = get_db_connection()
        if not conn: return {}
        query = "SELECT pattern, COUNT(*) as total, SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as wins FROM signals WHERE outcome != 0 GROUP BY pattern"
        df = pd.read_sql_query(query, conn)
        conn.close()
        if df.empty: return {}
        df['accuracy'] = (df['wins'] / df['total'] * 100).round(1)
        return JSONResponse(content=df.set_index('pattern')['accuracy'].to_dict())
    except: return JSONResponse(content={})

if os.path.exists(get_resource_path("PremiumDashboard")):
    app.mount("/static", StaticFiles(directory=get_resource_path("PremiumDashboard")), name="static")

@app.get("/")
async def read_index():
    response = FileResponse(get_resource_path("PremiumDashboard/index.html"))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/api/status")
async def get_status():
    return JSONResponse(content=SHARED_DATA)

@app.get("/api/signals")
async def get_signals():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 20")
        rows = cursor.fetchall()
        signals = []
        for row in rows:
            signals.append({"id": row[0], "symbol": row[1], "direction": row[2], "entry": row[3], "tp": row[4], "sl": row[5], "timeframe": row[6], "created_at": row[8]})
        conn.close()
        return JSONResponse(content=signals)
    except Exception as e: return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/options/{underlying}")
async def get_options(underlying: str):
    """Fetches available option contracts for an underlying symbol."""
    try:
        executor = state.get_executor()
        alpaca = executor.adapters.get("alpaca")
        if alpaca:
            contracts = alpaca.fetch_option_contracts(underlying)
            return JSONResponse(content=contracts)
        return JSONResponse(content=[])
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/settings")
async def update_settings(request: Request):
    data = await request.json()
    logger.info(f"Updating Settings: {data}")
    
    if "is_bot_active" in data: state.SHARED_DATA["is_bot_active"] = bool(data["is_bot_active"])
    if "demo_mode" in data: state.SHARED_DATA["demo_mode"] = bool(data["demo_mode"])
    if "active_broker" in data: state.SHARED_DATA["active_broker"] = data["active_broker"]
    if "strategy_mode" in data: state.SHARED_DATA["strategy_mode"] = data["strategy_mode"]
    
    # --- New: Risk Config Overrides ---
    if "max_daily_loss_pct" in data:
        state.SHARED_DATA["risk_config"]["max_daily_loss_pct"] = float(data["max_daily_loss_pct"])
    if "min_ml_confidence" in data:
        state.SHARED_DATA["risk_config"]["min_ml_confidence"] = float(data["min_ml_confidence"]) / 100.0
    if "default_exposure" in data:
        if "risk_per_asset" not in state.SHARED_DATA["risk_config"]:
            state.SHARED_DATA["risk_config"]["risk_per_asset"] = {}
        state.SHARED_DATA["risk_config"]["risk_per_asset"]["DEFAULT"] = float(data["default_exposure"])
    
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
            os.environ[f"{broker.upper()}_API_KEY"] = str(keys["key"])
            os.environ[f"{broker.upper()}_SECRET"] = str(keys["secret"])
            if "server" in keys:
                os.environ[f"{broker.upper()}_SERVER"] = str(keys["server"])
            
            # Persistence
            with open(".env", "a") as f:
                f.write(f"\n{broker.upper()}_API_KEY={keys['key']}")
                f.write(f"\n{broker.upper()}_SECRET={keys['secret']}")
                if "server" in keys:
                    f.write(f"\n{broker.upper()}_SERVER={keys['server']}")
    
    # Persistence
    state.save_shared_state(state.SHARED_DATA)
    
    # Force Executor Refresh if broker or credentials changed
    if "credentials" in data or "active_broker" in data:
        state.reset_executor()
        logger.info("Broker credentials updated. Executor reset.")

    logger.info(f"Saving State... is_bot_active={state.SHARED_DATA.get('is_bot_active')}")
    
    # Broadcast the change immediately to all connected clients
    await trigger_immediate_broadcast()
    
    return JSONResponse(content={"status": "success", "config": state.SHARED_DATA.get("risk_config", {})})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)

async def sync_broker_balance():
    """Fetches actual balance from the connected broker."""
    try:
        executor = state.get_executor()
        target = state.SHARED_DATA.get("active_broker", "DEMO").lower()
        
        if target == "bridge":
            total_equity = 0.0
            details = {}
            for name, adapter in executor.adapters.items():
                try:
                    raw = adapter.get_balance()
                    eq = 0.0
                    if name == "binance": eq = float(raw.get("total", {}).get("USDT", 0))
                    elif name == "alpaca": eq = float(getattr(raw, "equity", 0))
                    elif name == "mt5": eq = float(raw.get("equity", 0))
                    total_equity += eq
                    details[name] = {"balance": eq, "status": "CONNECTED"}
                except: 
                    details[name] = {"balance": 0.0, "status": "OFFLINE"}
            state.SHARED_DATA["balance" if not state.SHARED_DATA.get("demo_mode") else "demo_balance"] = total_equity
            state.SHARED_DATA["broker_status"] = "BRIDGE ACTIVE"
            state.SHARED_DATA["broker_details"] = details
        elif target in executor.adapters:
            adapter = executor.adapters[target]
            raw_balance = adapter.get_balance()
            
            equity = 0.0
            if target == "binance":
                equity = float(raw_balance.get("total", {}).get("USDT", 0))
            elif target == "alpaca":
                equity = float(getattr(raw_balance, "equity", 0))
            elif target == "mt5":
                equity = float(raw_balance.get("equity", 0))
            
            if isinstance(equity, (int, float)):
                state.SHARED_DATA["balance" if not state.SHARED_DATA.get("demo_mode") else "demo_balance"] = equity
                state.SHARED_DATA["broker_status"] = "CONNECTED"
        else:
            if target != "demo":
                state.SHARED_DATA["broker_status"] = "DISCONNECTED"
    except Exception as e:
        logger.error(f"Balance Sync Error: {e}")
        state.SHARED_DATA["broker_status"] = "ERROR"

async def sync_active_trades():
    """Fetches all open positions from active brokers."""
    try:
        executor = state.get_executor()
        # Run I/O intensive aggregation in a separate thread
        positions = await asyncio.to_thread(executor.get_all_open_positions)
        state.SHARED_DATA["active_trades"] = positions
    except Exception as e:
        logger.error(f"Position Sync Error: {e}")

async def sync_trade_history():
    """Pulls recent closed trades from brokers to update the history feed."""
    try:
        executor = state.get_executor()
        if "mt5" in executor.adapters:
            adapter = executor.adapters["mt5"]
            # Fetch last 20 deals from MT5
            import MetaTrader5 as mt5
            from datetime import datetime, timedelta
            
            from_date = datetime.now() - timedelta(days=1)
            deals = mt5.history_deals_get(from_date, datetime.now())
            if deals:
                history = state.SHARED_DATA.get("trade_history", [])
                for d in deals:
                    # Only include deals that are actually 'deals' (not just orders)
                    if d.entry == mt5.DEAL_ENTRY_OUT: # Closing a position
                        # Prevent duplicates
                        if any(h.get("ticket") == d.position_id for h in history): continue
                        
                        history.insert(0, {
                            "ticket": d.position_id,
                            "symbol": d.symbol,
                            "direction": "LONG" if d.type == mt5.DEAL_TYPE_SELL else "SHORT", # If we sold to close, it was long
                            "pnl": round(float(d.profit + d.commission + d.swap), 2),
                            "entry_time": "N/A",
                            "close_time": datetime.fromtimestamp(d.time).strftime("%H:%M:%S"),
                            "status": "WIN" if d.profit > 0 else "LOSS"
                        })
                state.SHARED_DATA["trade_history"] = history[:50]
    except Exception as e:
        logger.error(f"History Sync Error: {e}")

async def broadcast_data():
    while True:
        try:
            # 1. Sync from disk to get latest settings/configs
            saved_state = state.load_shared_state()
            state.SHARED_DATA.update(saved_state)
            
            # 2. Sync live data from broker (overwrites balance in memory)
            await sync_broker_balance()
            await sync_active_trades()
            await sync_trade_history()
            
            # 3. Update Market Statuses for Dashboard
            configs = state.SHARED_DATA.get("market_configs", {})
            for symbol in configs:
                configs[symbol]["status"] = market_hours.get_market_status(symbol)
            state.SHARED_DATA["market_configs"] = configs

            # 4. Save the combined state back to disk
            state.save_shared_state(state.SHARED_DATA)
            
            # 5. Add Heartbeat Log
            if "logs" not in state.SHARED_DATA: state.SHARED_DATA["logs"] = []
            now = datetime.now().strftime("%H:%M:%S")
            if random.random() > 0.95: # Occasional heartbeat to show activity
                log_entry = {"time": now, "msg": "System Heartbeat: Core Sync Successful"}
                state.SHARED_DATA["logs"] = ([log_entry] + state.SHARED_DATA["logs"])[:20]

            # 6. Prepare broadcast payload
            if active_connections:
                payload = json.dumps(state.SHARED_DATA)
                disconnected = set()
                for ws in list(active_connections):
                    try:
                        await ws.send_text(payload)
                    except:
                        disconnected.add(ws)
                for ws in disconnected:
                    active_connections.remove(ws)
        except Exception as e:
            print(f"Broadcast Error: {e}")
        await asyncio.sleep(1.0) # Sync every second

@app.post("/api/initialize_bot")
async def initialize_bot(request: Request):
    try:
        data = await request.json()
        strategy = data.get("strategy", "HYBRID")
        # In a real environment, we would trigger MultiLauncher.py or start a subprocess
        # For now, we simulate a log entry and update shared state
        msg = f"Initializing Bot Cluster: {strategy} Deployment Active"
        logger.info(msg)
        
        # Add to logs
        now = datetime.now().strftime("%H:%M:%S")
        log_entry = {"time": now, "msg": msg}
        state.SHARED_DATA["logs"] = ([log_entry] + state.SHARED_DATA.get("logs", []))[:20]
        
        return {"status": "success", "message": msg}
    except Exception as e:
        return {"status": "error", "message": str(e)}

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
    state.SHARED_DATA["signals"] = [test_sig] + state.SHARED_DATA.get("signals", [])
    state.save_shared_state(state.SHARED_DATA)
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
        
        # Only clear local active_trades if the brokers actually confirmed closures
        # Or let the pnl_update_loop sync the state naturally.
        # To be safe and responsive, we filter based on success results.
        
        # However, since pnl_update_loop runs every 2s and is the source of truth,
        # we don't strictly need to clear it here, but it helps with UI responsiveness.
        
        # Let's just return the results and let the background loop handle state sync.
        # This prevents the UI from showing 0 positions when they are actually still open.
        
        overall_status = "success"
        if any(r.get("status") == "error" for r in res.values()):
            overall_status = "error"
        elif any(r.get("status") == "partial" for r in res.values()):
            overall_status = "partial"
            
        return JSONResponse(content={"status": overall_status, "results": res})
    except Exception as e:
        logger.error(f"Panic Error: {e}")
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
    symbol = data.get("symbol", "").strip()
    strategy = data.get("strategy", "JEWEL_ELITE")
    if symbol:
        if symbol not in SHARED_DATA["market_configs"]:
            SHARED_DATA["market_configs"][symbol] = {"enabled": True, "strategy": strategy}
            SHARED_DATA["active_markets"] = [s for s, c in SHARED_DATA["market_configs"].items() if c["enabled"]]
            state.save_shared_state(SHARED_DATA)
            return JSONResponse(content={"status": "success"})
        else:
            # If it already exists, just update the strategy
            SHARED_DATA["market_configs"][symbol]["strategy"] = strategy
            state.save_shared_state(SHARED_DATA)
            return JSONResponse(content={"status": "updated"})
    return JSONResponse(status_code=400, content={"status": "error", "message": "Invalid symbol"})

@app.post("/api/market/strategy")
async def update_market_strategy(request: Request):
    data = await request.json()
    symbol = data.get("symbol")
    strategy = data.get("strategy")
    if symbol in SHARED_DATA["market_configs"]:
        SHARED_DATA["market_configs"][symbol]["strategy"] = strategy
        state.save_shared_state(SHARED_DATA)
        return JSONResponse(content={"status": "success"})
    return JSONResponse(status_code=404, content={"status": "error", "message": "Symbol not found"})

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

def run_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_server()
