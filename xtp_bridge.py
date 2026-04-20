import os
from fastapi import FastAPI, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
import xtp_trade_api  # This would be the XTP SDK

app = FastAPI(title="XTP Broker Bridge for N8N")

# Use environment variables for security
API_KEY = os.getenv("XTP_BRIDGE_KEY", "default_secret")
api_key_header = APIKeyHeader(name="X-API-KEY", auto_error=True)

class TradeRequest(BaseModel):
    symbol: str
    side: str  # "buy" or "sell"
    price: float
    quantity: int
    sl: float
    tp: float

def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

@app.post("/trade", dependencies=[Security(get_api_key)])
async def execute_trade(trade: TradeRequest):
    """
    Translates N8N request to XTP library calls.
    """
    try:
        # 1. Initialize XTP Session (Simplified)
        # xtp = xtp_trade_api.TradeApi(user_id=..., password=...)
        
        # 2. Logic to place order
        side_const = 1 if trade.side == "buy" else 2 # XTP specific mapping
        
        # Example pseudo-call:
        # order_id = xtp.InsertOrder(
        #     symbol=trade.symbol,
        #     side=side_const,
        #     price=trade.price,
        #     quantity=trade.quantity
        # )
        
        print(f"Executing {trade.side} on XTP for {trade.symbol} at {trade.price}")
        
        return {"status": "success", "broker": "XTP", "order_id": "XTP_12345"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
