import alpaca_trade_api as tradeapi
import pandas as pd
import pandas_ta as ta
import time
import os
from dotenv import load_dotenv

# Load credentials
load_dotenv(".env.trading") # Separated env file for trading keys

API_KEY = os.getenv("ALPACA_API_KEY", "YOUR_PAPER_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "YOUR_PAPER_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

# Connect to Alpaca
api = tradeapi.REST(API_KEY, SECRET_KEY, BASE_URL, api_version='v2')

# Configuration
SYMBOL = "TSLA"  # Example stock
TIMEFRAME = "5Min"
RSI_PERIOD = 14
SMA_FAST = 9
SMA_SLOW = 21
CAPITAL = 200.0
RISK_PER_TRADE = 4.0 # $4 (2% of $200)
TP_PERC = 0.02 # 2%
SL_PERC = 0.01 # 1%

def get_data(symbol):
    try:
        # Get last 100 bars
        bars = api.get_bars(symbol, TIMEFRAME, limit=100).df
        return bars
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def check_signal(df):
    # Indicators
    df['rsi'] = ta.rsi(df['close'], length=RSI_PERIOD)
    df['sma_fast'] = ta.sma(df['close'], length=SMA_FAST)
    df['sma_slow'] = ta.sma(df['close'], length=SMA_SLOW)
    
    # Conditions (Crossover/Crossunder)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Long: Fast crosses above Slow and RSI < 70
    long_signal = (prev['sma_fast'] <= prev['sma_slow'] and last['sma_fast'] > last['sma_slow'] and last['rsi'] < 70)
    # Short: Fast crosses below Slow and RSI > 30
    short_signal = (prev['sma_fast'] >= prev['sma_slow'] and last['sma_fast'] < last['sma_slow'] and last['rsi'] > 30)
    
    if long_signal: return "LONG"
    if short_signal: return "SHORT"
    return None

def calculate_quantity(price):
    # Rule: 1% drop = $4 loss
    # SL_amount = Quantity * Price * SL_perc
    # Quantity = SL_amount / (Price * SL_perc)
    qty = RISK_PER_TRADE / (price * SL_PERC)
    return round(qty, 2)

def execute_trade(side, price):
    qty = calculate_quantity(price)
    tp_price = price * (1 + TP_PERC) if side == "buy" else price * (1 - TP_PERC)
    sl_price = price * (1 - SL_PERC) if side == "buy" else price * (1 + SL_PERC)
    
    print(f"Executing {side.upper()} order for {qty} shares of {SYMBOL}")
    print(f"Entry: {price}, TP: {tp_price}, SL: {sl_price}")
    
    try:
        api.submit_order(
            symbol=SYMBOL,
            qty=qty,
            side=side,
            type='market',
            time_in_force='gtc',
            order_class='bracket',
            take_profit={'limit_price': round(tp_price, 2)},
            stop_loss={'stop_price': round(sl_price, 2)}
        )
        print("Success: Order placed with bracket (TP/SL).")
    except Exception as e:
        print(f"Order failed: {e}")

def run_bot():
    print(f"Starting RSI + MA Crossover Bot for {SYMBOL}...")
    print(f"Account Support: $200, Risk: $4/trade")
    
    while True:
        # Check current position
        try:
            positions = api.list_positions()
            active_symbols = [p.symbol for p in positions]
            
            if SYMBOL not in active_symbols:
                df = get_data(SYMBOL)
                if df is not None and not df.empty:
                    signal = check_signal(df)
                    if signal == "LONG":
                        execute_trade("buy", df.iloc[-1]['close'])
                    elif signal == "SHORT":
                        execute_trade("sell", df.iloc[-1]['close'])
            else:
                print(f"Position already open for {SYMBOL}. Waiting...")
                
        except Exception as e:
            print(f"Loop error: {e}")
            
        time.sleep(300) # Check every 5 minutes

if __name__ == "__main__":
    run_bot()
