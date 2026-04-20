import os
import MetaTrader5 as mt5
from fastapi import FastAPI, Request, HTTPException
import uvicorn
from dotenv import load_dotenv

# Load env variables
load_dotenv()
EXNESS_ACCOUNT = os.getenv("EXNESS_ACCOUNT", "YOUR_DEMO_ACCOUNT_NUM")
EXNESS_PASSWORD = os.getenv("EXNESS_PASSWORD", "YOUR_DEMO_PASSWORD")
EXNESS_SERVER = os.getenv("EXNESS_SERVER", "Exness-MT5Trial")

app = FastAPI(title="TradeBot Exness Webhook")

def init_mt5():
    if not mt5.initialize():
        print(f"MT5 Initialize failed, error code = {mt5.last_error()}")
        return False
        
    try:
        account_num = int(EXNESS_ACCOUNT)
    except ValueError:
        print("Invalid account number in .env. Must be an integer.")
        return False

    # Connect to Exness Account
    authorized = mt5.login(account_num, password=EXNESS_PASSWORD, server=EXNESS_SERVER)
    if authorized:
        print(f"Connected to MT5 account #{account_num}")
        return True
    else:
        print(f"MT5 login failed, error code: {mt5.last_error()}")
        return False

def calculate_lot_size(symbol, entry_price, sl_price, risk_usd=10.0):
    """
    Dummy logic for calculate lot size. 
    In pairs like BTCUSD, calculating raw lot is specific to contract sizes.
    For simplicity, returning minimum lot 0.01 as a placeholder for testing.
    You will need exact tick value calculations for a robust deployment.
    """
    return 0.01

def place_order(symbol, side, price, sl, tp, lot_qty):
    order_type = mt5.ORDER_TYPE_BUY if side.lower() == "buy" else mt5.ORDER_TYPE_SELL
    
    # Tick info
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found.")
        return False
        
    if not symbol_info.visible:
        print(f"Symbol {symbol} is not visible. Trying to add it.")
        if not mt5.symbol_select(symbol, True):
            print(f"Symbol {symbol} not found on server.")
            return False
            
    point = mt5.symbol_info(symbol).point

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot_qty,
        "type": order_type,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 20,
        "magic": 2026413, # random ID
        "comment": "TradeBot Webhook",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Order send failed! Retcode: {result.retcode}")
        # Return fallback dictionary to avoid breaking logic
        return {"retcode": result.retcode, "comment": result.comment}
    print(f"Order Placed! Ticket: {result.order}")
    return result

@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request):
    data = await request.json()
    print(f"---- Webhook Received ----")
    print(data)
    
    symbol = data.get("symbol", "").replace("USD", "USDm") # example mapping for Exness
    # Depending on your exness account, gold is XAUUSDm or XAUUSDc etc. 
    # For now we'll assume exact symbol names. Please correct suffix if needed.
    
    if "XAU" in symbol and "m" not in symbol:
        symbol = "XAUUSDm"
    elif "BTC" in symbol and "m" not in symbol:
        symbol = "BTCUSDm"

    side = data.get("side", "buy")
    price = data.get("price")
    sl = data.get("sl")
    tp1 = data.get("tp1")
    tp2 = data.get("tp2")
    
    if not init_mt5():
        raise HTTPException(status_code=500, detail="MT5 connection failed.")
        
    # We are splitting the position into two (one for TP1, one for TP2)
    # E.g. risk $20 total -> $10 per position
    lot_size_per_pos = calculate_lot_size(symbol, price, sl, risk_usd=10.0)
    
    print(f"Placing Position 1 targeting TP1: {tp1}")
    res1 = place_order(symbol, side, price, sl, tp1, lot_size_per_pos)
    
    print(f"Placing Position 2 targeting TP2: {tp2}")
    res2 = place_order(symbol, side, price, sl, tp2, lot_size_per_pos)
    
    mt5.shutdown()
    return {"status": "success", "orders": {"pos1": repr(res1), "pos2": repr(res2)}}

if __name__ == "__main__":
    print("Starting Webhook listener on port 8000...")
    print("If you want to receive webhooks from TradingView, run `ngrok http 8000`")
    uvicorn.run(app, host="0.0.0.0", port=8000)
