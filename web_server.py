from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import os
import sqlite3
import asyncio
from datetime import datetime
import logging
import random

import pandas as pd
import state_manager as state
from fastapi.middleware.cors import CORSMiddleware
import mimetypes

mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

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

if os.path.exists("web"):
    app.mount("/static", StaticFiles(directory="web"), name="static")

@app.get("/")
async def get_index():
    with open("web/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

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

@app.post("/api/settings")
async def update_settings(request: Request):
    data = await request.json()
    logger.info(f"Updating Settings: {data}")
    if "auto_trade" in data: SHARED_DATA["auto_trade"] = bool(data["auto_trade"])
    if "demo_mode" in data: SHARED_DATA["demo_mode"] = bool(data["demo_mode"])
    if "active_profile" in data: SHARED_DATA["active_profile"] = data["active_profile"]
    if "strategy_mode" in data: SHARED_DATA["strategy_mode"] = data["strategy_mode"]
    if "is_bot_active" in data: SHARED_DATA["is_bot_active"] = bool(data["is_bot_active"])
    if "kill_switch" in data: SHARED_DATA["kill_switch"] = bool(data["kill_switch"])
    if "execution_bias" in data: SHARED_DATA["execution_bias"] = data["execution_bias"]
    if "active_markets" in data: SHARED_DATA["active_markets"] = data["active_markets"]
    
    executor = state.get_executor()
    executor.risk_engine.config.active_profile = SHARED_DATA["active_profile"]
    from models import ExecutionMode
    executor.risk_engine.config.execution_mode = ExecutionMode.DEMO if SHARED_DATA["demo_mode"] else ExecutionMode.LIVE
    
    SHARED_DATA["risk_config"] = executor.risk_engine.config.dict()
    logger.info(f"Saving State... is_bot_active={SHARED_DATA['is_bot_active']}")
    state.save_shared_state(SHARED_DATA)
    return JSONResponse(content={"status": "success", "config": SHARED_DATA["risk_config"]})

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

async def broadcast_data():
    while True:
        try:
            if active_connections:
                payload = json.dumps(SHARED_DATA)
                disconnected = set()
                for ws in active_connections:
                    try:
                        await ws.send_text(payload)
                    except:
                        disconnected.add(ws)
                for ws in disconnected:
                    active_connections.remove(ws)
        except Exception as e:
            print(f"Broadcast Error: {e}")
        await asyncio.sleep(0.1)

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

@app.post("/api/webhook/tradingview")
async def tradingview_webhook(request: Request):
    """Entry point for TradingView Alert signals."""
    try:
        data = await request.json()
        logger.info(f"Received TradingView Webhook: {data}")
        
        # 1. Map to standardized Signal
        from core.signals import Signal
        signal = {
            "id": random.randint(1000, 9999),
            "symbol": data.get("symbol", "UNKNOWN"),
            "direction": data.get("action", "LONG").upper(),
            "entry": float(data.get("price", 0)),
            "tp": float(data.get("tp", 0)),
            "sl": float(data.get("sl", 0)),
            "pattern": "TradingView External Alert",
            "created_at": datetime.now().strftime("%H:%M:%S")
        }
        
        # 2. Inject into shared state for dashboard visibility
        SHARED_DATA["signals"] = [signal] + SHARED_DATA.get("signals", [])
        
        # 3. Trigger execution gateway if bot is active
        if SHARED_DATA.get("is_bot_active"):
            # logic to dispatch to gateway
            pass

        return JSONResponse(content={"status": "accepted", "signal_id": signal["id"]})
    except Exception as e:
        logger.error(f"Webhook Error: {e}")
        return JSONResponse(status_code=400, content={"status": "error", "message": str(e)})

def run_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_server()
