import os
import sqlite3
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from execution_layer import ExecutionLayer
from db_utils import DB_FILE

app = FastAPI(title="Sentinel OS UI")

# Mount the static directory
app.mount("/static", StaticFiles(directory="dashboard"), name="static")

@app.get("/")
def read_index():
    return FileResponse("dashboard/index.html")

_executor = None

def safe_get_executor():
    global _executor
    if _executor is None:
        try:
            _executor = ExecutionLayer()
        except Exception as e:
            print(f"Cannot initialize executor in dashboard: {e}")
            return None
    return _executor

@app.get("/api/stats")
def get_stats():
    executor = safe_get_executor()
    target = os.getenv("DEFAULT_BROKER", "binance").lower()
    
    if executor and target in executor.adapters:
        try:
            raw_balance = executor.adapters[target].get_balance()
            if target == "binance":
                equity = float(raw_balance.get("total", {}).get("USDT", 0))
            elif target == "alpaca":
                equity = float(getattr(raw_balance, "equity", 0))
            elif target == "mt5":
                equity = float(raw_balance.get("equity", 0))
            else:
                equity = 0.0
                
            active_symbols = executor.adapters[target].get_active_symbols()
            
            return {
                "status": "connected",
                "target_broker": target.upper(),
                "equity": equity,
                "active_symbols": active_symbols
            }
        except Exception as e:
            return {"status": "error", "message": str(e), "equity": 0.0, "active_symbols": []}
            
    return {"status": "disconnected", "target_broker": target.upper(), "equity": 0.0, "active_symbols": []}

@app.get("/api/signals")
def get_signals():
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 15")
        rows = cursor.fetchall()
        
        signals = [dict(r) for r in rows]
        return {"signals": signals}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    uvicorn.run("dashboard_app:app", host="0.0.0.0", port=8000, reload=True)
