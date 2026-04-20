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

# Fix Windows MIME types (prevents .js being served as text/plain)
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('text/css', '.css')

app = FastAPI()

# Add CORS support for mobile devices
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path setup
from dotenv import load_dotenv
load_dotenv()
DB_FILE = os.getenv('DB_NAME', 'said alalawi.db')
if not DB_FILE.endswith('.db'): DB_FILE += '.db'
DB_PATH = os.path.abspath(DB_FILE)

# Shared Data from State Manager
SHARED_DATA = state.SHARED_DATA

@app.get("/api/analytics")
async def get_analytics():
    """Calculates win rate per pattern from the database."""
    try:
        from db_utils import get_db_connection
        conn = get_db_connection()
        if not conn: return {}
        
        query = """
        SELECT pattern, 
               COUNT(*) as total,
               SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as wins
        FROM signals 
        WHERE outcome != 0 
        GROUP BY pattern
        """
        import pandas as pd
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty: return {}
        
        df['accuracy'] = (df['wins'] / df['total'] * 100).round(1)
        return JSONResponse(content=df.set_index('pattern')['accuracy'].to_dict())
    except Exception as e:
        print(f"Analytics error: {e}")
        return JSONResponse(content={})

# Serve static files from the 'web' directory
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
            # Match schema from db_utils.py
            signals.append({
                "id": row[0],
                "symbol": row[1],
                "direction": row[2],
                "entry": row[3],
                "tp": row[4],
                "sl": row[5],
                "timeframe": row[6],
                "created_at": row[8]
            })
        conn.close()
        return JSONResponse(content=signals)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/pnl_history")
async def get_pnl_history(days: int = 1):
    """Fetches equity history points for charting."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # Fetch data for the specified number of days
        cursor.execute("""
            SELECT total_equity, timestamp 
            FROM equity_history 
            WHERE timestamp >= datetime('now', ?) 
            ORDER BY timestamp ASC
        """, (f'-{days} days',))
        
        history = [{"equity": row[0], "time": row[1]} for row in cursor.fetchall()]
        conn.close()
        return JSONResponse(content=history)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/api/leaderboard")
async def get_leaderboard():
    """Aggregates pattern performance stats."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT pattern, 
                   COUNT(*) as total,
                   SUM(CASE WHEN outcome = 1 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN outcome = -1 THEN 1 ELSE 0 END) as losses
            FROM signals 
            WHERE outcome != 0
            GROUP BY pattern
            ORDER BY wins DESC
        """)
        
        stats = []
        for row in cursor.fetchall():
            total = row[1]
            wins = row[2]
            losses = row[3]
            win_rate = (wins / total * 100) if total > 0 else 0
            stats.append({
                "pattern": row[0],
                "total": total,
                "wins": wins,
                "losses": losses,
                "win_rate": round(win_rate, 1)
            })
        conn.close()
        return JSONResponse(content=stats)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
active_connections = set()

@app.post("/api/trade")
async def handle_trade_action(request: Request):
    data = await request.json()
    action = data.get("action")
    
    executor = state.get_executor()
    
    if action == "close_all":
        results = executor.close_all()
        return JSONResponse(content={"status": "success", "results": results})
    
    return JSONResponse(content={"status": "error", "message": "Unknown action"}, status_code=400)

@app.post("/api/settings")
async def update_settings(request: Request):
    """Updates global bot settings from the UI."""
    data = await request.json()
    
    # Update Auto-Trade if present
    if "auto_trade" in data:
        SHARED_DATA["auto_trade"] = bool(data["auto_trade"])

    # Update Demo Mode if present
    if "demo_mode" in data:
        SHARED_DATA["demo_mode"] = bool(data["demo_mode"])

    # Update Profile if present
    if "active_profile" in data:
        SHARED_DATA["active_profile"] = data["active_profile"]

    # Update Risk Config in Executor
    executor = state.get_executor()
    
    # Sync profile and mode to risk engine
    executor.risk_engine.config.active_profile = SHARED_DATA["active_profile"]
    from models import ExecutionMode
    executor.risk_engine.config.execution_mode = ExecutionMode.DEMO if SHARED_DATA["demo_mode"] else ExecutionMode.LIVE
    
    if "risk_pct" in data:
        # Update specific asset risk (e.g. Gold or BTC)
        asset = data.get("asset", "DEFAULT")
        executor.risk_engine.config.risk_per_asset[asset] = float(data["risk_pct"])
        
    if "max_daily_loss" in data:
        executor.risk_engine.config.max_daily_loss_pct = float(data["max_daily_loss"])
        
    if "max_positions" in data:
        executor.risk_engine.config.max_open_positions = int(data["max_positions"])

    if "ai_sizing_symbols" in data:
        executor.risk_engine.config.ai_scaling_symbols = data["ai_sizing_symbols"]
        
    if "min_multiplier" in data:
        executor.risk_engine.config.min_multiplier = float(data["min_multiplier"])
        
    if "max_multiplier" in data:
        executor.risk_engine.config.max_multiplier = float(data["max_multiplier"])

    # Save to disk
    try:
        with open("risk_settings.json", "w") as f:
            json.dump(executor.risk_engine.config.dict(), f)
    except Exception as e:
        print(f"Error saving risk config: {e}")

    # Update shared data for UI broadcast
    SHARED_DATA["risk_config"] = executor.risk_engine.config.dict()
    
    return JSONResponse(content={"status": "success", "config": SHARED_DATA["risk_config"]})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    try:
        while True:
            # We just need to keep the connection alive
            # The broadcast_data task handles the push
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def snapshot_equity():
    """Background task to record global equity every 5 minutes."""
    while True:
        try:
            executor = state.get_executor()
            total_equity = 0.0
            
            # Sum equity across all active adapters
            for name, adapter in executor.adapters.items():
                try:
                    balance = adapter.get_balance()
                    if name == "binance":
                        total_equity += float(balance.get("total", {}).get("USDT", 0))
                    elif name == "mt5":
                        total_equity += float(balance.get("equity", 0))
                    elif name == "alpaca":
                        total_equity += float(getattr(balance, "equity", 0))
                except:
                    continue
            
            if total_equity > 0:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("INSERT INTO equity_history (total_equity) VALUES (?)", (total_equity,))
                conn.commit()
                conn.close()
                # print(f"📈 PNL Snapshot: ${total_equity:.2f} recorded.")
                
        except Exception as e:
            print(f"Snapshot Error: {e}")
        
        await asyncio.sleep(300) # Every 5 minutes

async def broadcast_data():
    """Background task to push SHARED_DATA to all WebSocket clients."""
    while True:
        if active_connections:
            try:
                # Use a more robust JSON encoder in case of non-serializable objects
                def default_converter(o):
                    if isinstance(o, datetime):
                        return o.strftime("%Y-%m-%d %H:%M:%S")
                    return str(o)
                
                message = json.dumps(SHARED_DATA, default=default_converter)
                
                # Create tasks for all connected clients to send data in parallel
                send_tasks = [conn.send_text(message) for conn in active_connections]
                if send_tasks:
                    await asyncio.gather(*send_tasks, return_exceptions=True)
            except Exception as e:
                print(f"Broadcast Error: {e}")
        await asyncio.sleep(1) # Broadcast every second

@app.on_event("startup")
async def startup_event():
    # Start background tasks
    asyncio.create_task(broadcast_data())
    asyncio.create_task(snapshot_equity())

@app.post("/api/test_signal")
async def simulate_signal():
    """Injects a fake signal for testing the UI."""
    test_sig = {
        "id": 9999,
        "symbol": "BTCUSDm",
        "direction": "LONG",
        "entry": 65000.0,
        "tp": 66000.0,
        "sl": 64500.0,
        "timeframe": "M5",
        "ai_rationale": "• Institutional liquidity sweep detected below 64.8k range.\n• M5 Order Block mitigation complete; expansion expected.\n• Bullish FVG remains open to 66k target.\n• [APPROVE]",
        "created_at": datetime.now().strftime("%H:%M:%S")
    }
    # Push signal to shared data for WebSocket broadcast
    SHARED_DATA["signals"] = [test_sig] + SHARED_DATA.get("signals", [])
    return JSONResponse(content={"status": "success", "message": "Test signal injected"})

def run_server(host="0.0.0.0", port=8000):
    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    run_server()
