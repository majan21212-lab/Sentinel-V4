import os
import sqlite3
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional, List
from dotenv import load_dotenv

from models import Signal, AccountStatus, RiskConfig
from execution_layer import ExecutionLayer
from db_utils import setup_database
import state_manager as state

load_dotenv()

app = FastAPI(title="Sentinel TradeBot API")
executor = ExecutionLayer()

# Serve static dashboard files
app.mount("/static", StaticFiles(directory="dashboard"), name="static")

@app.get("/")
async def root():
    return FileResponse("dashboard/index.html")

@app.get("/manifest.json")
async def get_manifest():
    return FileResponse("dashboard/manifest.json")

@app.get("/styles.css")
async def get_styles():
    return FileResponse("dashboard/styles.css")

@app.get("/app.js")
async def get_js():
    return FileResponse("dashboard/app.js")

# Simple shared-secret authentication for the iOS app
SENTINEL_TOKEN = os.getenv("SENTINEL_API_KEY", "sentinel_debug_key")

async def verify_token(x_token: str = Header(...)):
    if x_token != SENTINEL_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid Sentinel Token")

@app.get("/")
async def root():
    return {"status": "online", "message": "Sentinel TradeBot API v1.0"}

@app.get("/status", dependencies=[Depends(verify_token)])
async def get_status():
    """Returns the operational status of the bot and configured brokers."""
    current_state = state.load_shared_state()
    return {
        "strategy": current_state.get("strategy_mode") or os.getenv("STRATEGY_MODE"),
        "active_adapters": list(executor.adapters.keys()),
        "auto_trade": current_state.get("is_bot_active", False) or current_state.get("auto_trade", False)
    }

@app.get("/account", dependencies=[Depends(verify_token)])
async def get_account_summary():
    """Fetches balance/account info from all active platforms."""
    summary = {}
    for name, adapter in executor.adapters.items():
        try:
            # Handle different adapter return types
            balance = adapter.get_balance()
            if hasattr(balance, '_asdict'): balance = balance._asdict() # MT5
            elif hasattr(balance, 'dict'): balance = balance.dict() # Pydantic
            summary[name] = balance
        except Exception as e:
            summary[name] = {"error": str(e)}
    return summary

@app.get("/positions", dependencies=[Depends(verify_token)])
async def get_active_positions():
    """Fetches all open positions across all platforms."""
    all_positions = []
    for name, adapter in executor.adapters.items():
        try:
            # This requires adding get_positions() to adapters, 
            # or using a helper if exists. For now, we'll try to get symbols.
            symbols = adapter.get_active_symbols()
            for symbol in symbols:
                all_positions.append({
                    "symbol": symbol,
                    "broker": name,
                    # We would ideally fetch full position details here
                })
        except Exception as e:
            print(f"Error fetching positions for {name}: {e}")
    return all_positions

@app.get("/history", response_model=List[dict], dependencies=[Depends(verify_token)])
async def get_trade_history(limit: int = 20):
    """Retrieves recent signal/trade history from the local database."""
    try:
        conn = sqlite3.connect(os.getenv("DB_NAME", "trading_bot.db"))
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM signals ORDER BY timestamp DESC LIMIT ?", (limit,))
        columns = [column[0] for column in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/trade", dependencies=[Depends(verify_token)])
async def manual_trade(signal: Signal, platform: Optional[str] = None):
    """Allows manual trade execution or approval from the iOS app Sentinel."""
    result = executor.place_trade(signal, platform=platform)
    if result and result.get('status') in ['success', 'executed']:
        return {"status": "executed", "details": result}
    else:
        raise HTTPException(status_code=400, detail=result.get('message') if result else "Execution failed")

if __name__ == "__main__":
    import uvicorn
    setup_database()
    uvicorn.run(app, host="0.0.0.0", port=8001)
