import yfinance as yf
import pandas as pd
import pandas_ta as ta
import numpy as np

def run_backtest(symbol, interval, period="60d"):
    print(f"Testing {interval} timeframe...")
    try:
        # Fetch data
        df = yf.download(symbol, period=period, interval=interval, progress=False)
        if df.empty: return None
        
        # Flatten columns if multi-index (yfinance sometimes does this)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Indicators
        df['rsi'] = ta.rsi(df['Close'], length=14)
        df['sma_fast'] = ta.sma(df['Close'], length=9)
        df['sma_slow'] = ta.sma(df['Close'], length=21)
        
        # Signals
        # Long: Fast > Slow and RSI < 70
        # Short: Fast < Slow and RSI > 30
        df['long_signal'] = (df['sma_fast'] > df['sma_slow']) & (df['sma_fast'].shift(1) <= df['sma_slow'].shift(1)) & (df['rsi'] < 70)
        df['short_signal'] = (df['sma_fast'] < df['sma_slow']) & (df['sma_fast'].shift(1) >= df['sma_slow'].shift(1)) & (df['rsi'] > 30)

        # Backtest Logic (Simplified)
        capital = 200.0
        position = 0
        entry_price = 0
        trades = []
        
        tp_perc = 0.02
        sl_perc = 0.01

        for i in range(len(df)):
            if position == 0:
                if df['long_signal'].iloc[i]:
                    position = 1
                    entry_price = df['Close'].iloc[i]
                elif df['short_signal'].iloc[i]:
                    position = -1
                    entry_price = df['Close'].iloc[i]
            
            elif position == 1: # Long
                curr_price = df['Close'].iloc[i]
                if curr_price >= entry_price * (1 + tp_perc) or curr_price <= entry_price * (1 - sl_perc):
                    pnl = (curr_price - entry_price) / entry_price
                    trades.append(pnl)
                    position = 0
            
            elif position == -1: # Short
                curr_price = df['Close'].iloc[i]
                if curr_price <= entry_price * (1 - tp_perc) or curr_price >= entry_price * (1 + sl_perc):
                    pnl = (entry_price - curr_price) / entry_price
                    trades.append(pnl)
                    position = 0

        # Metrics
        if not trades: return {"Win Rate": 0, "Total Profit %": 0, "Trade Count": 0}
        
        win_rate = len([t for t in trades if t > 0]) / len(trades) * 100
        total_pnl = sum(trades) * 100
        return {
            "Timeframe": interval,
            "Trade Count": len(trades),
            "Win Rate": f"{win_rate:.1f}%",
            "Total Profit %": f"{total_pnl:.2f}%"
        }
    except Exception as e:
        return f"Error: {e}"

# Gold Symbol in yfinance: GC=F (Futures) or GOLD (though GOLD is Barrick Gold stock)
# Most brokers use XAUUSD, yfinance uses GC=F for Gold prices.
SYMBOL = "GC=F" 
timeframes = ["1m", "5m", "15m", "30m", "60m", "3h", "1d"] # Adjusting to yfinance available intervals

# yfinance intervals: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
results = []
# 1h = 60m, 4h is not directly available in standard yf download for small ranges, but we can resample.
# We'll test what's available easily first.

intervals_to_test = {
    "1m": "7d",
    "5m": "30d",
    "15m": "60d",
    "30m": "60d",
    "60m": "60d", # 1h
    "1d": "max" # Using Daily as proxy for high TF
}

print(f"--- GOLD (XAUUSD) STRATEGY TEST ---")
for tf, prd in intervals_to_test.items():
    res = run_backtest(SYMBOL, tf, prd)
    if res: results.append(res)

import json
print(json.dumps(results, indent=2))
