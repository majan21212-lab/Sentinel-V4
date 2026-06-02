import os
import sqlite3
import uvicorn
import asyncio
import logging
import json
from datetime import datetime
from typing import List, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from execution_layer import ExecutionLayer
from db_utils import DB_FILE
from state_manager import load_shared_state, update_shared_data

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("SentinelDashboard")

app = FastAPI(title="Sentinel Premium Cockpit")

# Mount PremiumDashboard
app.mount("/static", StaticFiles(directory="PremiumDashboard"), name="static")

@app.get("/")
def read_index():
    return FileResponse("PremiumDashboard/index.html")

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        log.info(f"New client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            log.info(f"Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        # Convert to JSON string for broadcast
        msg_str = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_str)
            except Exception:
                disconnected.append(connection)
        
        for conn in disconnected:
            self.disconnect(conn)

manager = ConnectionManager()

# --- Shared State & Polling ---
_executor = None

def get_executor():
    global _executor
    if _executor is None:
        try:
            _executor = ExecutionLayer()
        except Exception as e:
            log.error(f"Failed to init ExecutionLayer: {e}")
    return _executor

async def telemetry_poller():
    """Background task to poll brokers and broadcast state."""
    log.info("Starting telemetry poller...")
    while True:
        try:
            executor = get_executor()
            if not executor:
                await asyncio.sleep(5)
                continue

            state = load_shared_state()
            
            # Aggregate Broker Details
            broker_details = {}
            for name, adapter in executor.adapters.items():
                try:
                    balance_data = adapter.get_balance()
                    # Unified format for UI
                    balance = 0
                    if name == "binance":
                        balance = float(balance_data.get("total", {}).get("USDT", 0))
                    elif name == "alpaca":
                        balance = float(getattr(balance_data, "equity", 0))
                    elif name == "mt5":
                        balance = float(balance_data.get("equity", 0))
                    
                    broker_details[name] = {
                        "balance": balance,
                        "status": "CONNECTED"
                    }
                except Exception as e:
                    broker_details[name] = {"balance": 0, "status": "ERROR", "error": str(e)}

            # Get Open Positions
            active_trades = executor.get_all_open_positions()
            
            # Get Signals from DB
            signals = []
            try:
                conn = sqlite3.connect(DB_FILE)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 15")
                signals = [dict(r) for r in cursor.fetchall()]
                conn.close()
            except: pass

            # Build Global State
            broadcast_payload = {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "demo_mode": os.getenv("DEMO_MODE", "true").lower() == "true",
                "strategy_mode": state.get("strategy_mode", "HYBRID"),
                "broker_details": broker_details,
                "active_trades": active_trades,
                "signals": signals,
                "market_configs": state.get("market_configs", {}),
                "logs": [{"time": datetime.now().strftime("%H:%M:%S"), "msg": "Telemetry Sync Complete"}]
            }

            await manager.broadcast(broadcast_payload)
            
        except Exception as e:
            log.error(f"Polling Error: {e}")
            
        await asyncio.sleep(5) # Poll every 5 seconds

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telemetry_poller())

# --- API Endpoints ---

class SymbolAction(BaseModel):
    symbol: str

class InitAction(BaseModel):
    strategy: str

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/api/initialize_bot")
async def initialize_bot(data: InitAction):
    """Triggers the Master Bot process."""
    try:
        log.info(f"Received Initialization request for strategy: {data.strategy}")
        # Update shared state
        update_shared_data("strategy_mode", data.strategy)
        
        # Check if bot is already running (simple tasklist check)
        import subprocess
        res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"], capture_output=True, text=True)
        # Note: This is very broad, but better than nothing for a simple UI
        
        # Start bot as subprocess
        # In a real environment, we'd use a process manager like PM2 or Systemd
        cmd = [os.sys.executable, "JewelElite_MasterBot_MT5.py", data.strategy]
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        
        return {"status": "success", "message": f"Deployment signal sent for {data.strategy}"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/close_position")
async def close_position(data: SymbolAction):
    try:
        executor = get_executor()
        if not executor: return {"status": "error", "message": "Executor not ready"}
        
        res = executor.close_symbol(data.symbol, platform="bridge")
        return {"status": "success", "details": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/panic_close")
async def panic_close():
    try:
        executor = get_executor()
        if not executor: return {"status": "error", "message": "Executor not ready"}
        
        res = executor.close_all()
        return {"status": "success", "details": res}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run("dashboard_app:app", host="0.0.0.0", port=8000, reload=True)
