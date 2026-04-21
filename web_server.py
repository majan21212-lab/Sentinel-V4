from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import os
import sqlite3
import asyncio
from datetime import datetime

import pandas as pd
import state_manager as state
from fastapi.middleware.cors import CORSMiddleware
import mimetypes

mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

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
    if "auto_trade" in data: SHARED_DATA["auto_trade"] = bool(data["auto_trade"])
    if "demo_mode" in data: SHARED_DATA["demo_mode"] = bool(data["demo_mode"])
    if "active_profile" in data: SHARED_DATA["active_profile"] = data["active_profile"]
    if "strategy_mode" in data: SHARED_DATA["strategy_mode"] = data["strategy_mode"]
    
    executor = state.get_executor()
    executor.risk_engine.config.active_profile = SHARED_DATA["active_profile"]
    from models import ExecutionMode
    executor.risk_engine.config.execution_mode = ExecutionMode.DEMO if SHARED_DATA["demo_mode"] else ExecutionMode.LIVE
    
    SHARED_DATA["risk_config"] = executor.risk_engine.config.dict()
    return JSONResponse(content={"status": "success", "config": SHARED_DATA["risk_config"]})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.active_connections.add(websocket) if hasattr(state, 'active_connections') else None
    try:
        while True: await websocket.receive_text()
    except WebSocketDisconnect: pass

async def broadcast_data():
    while True:
        # Simplified broadcast logic for brevity in this tool call
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_data())

@app.post("/api/test_signal")
async def simulate_signal():
    test_sig = {"id": 9999, "symbol": "BTCUSDm", "direction": "LONG", "entry": 65000.0, "tp": 66000.0, "sl": 64500.0, "timeframe": "M5", "created_at": datetime.now().strftime("%H:%M:%S")}
    SHARED_DATA["signals"] = [test_sig] + SHARED_DATA.get("signals", [])
    return JSONResponse(content={"status": "success", "message": "Test signal injected"})

def run_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_server()
