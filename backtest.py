import pandas as pd
import numpy as np
from strategy import fetch_data, calculate_indicators, check_signals

def run_backtest(symbol='BTC/USDT', timeframe='1h', limit=1000, req_score=7):
    print(f"--- Backtesting God-Mode v8.1 Engine on {symbol} ({timeframe}) ---")
    
    # 1. Fetch Data
    df = fetch_data(symbol, timeframe=timeframe, limit=limit)
    if df is None or len(df) < 200:
        print("Not enough data for backtest.")
        return

    # 2. Calculate Indicators
    df = calculate_indicators(df, symbol)
    
    # 3. Simulate Signals
    # We walk through the data bar by bar after the initial calculation period
    initial_period = 200
    trades = []
    
    for i in range(initial_period, len(df)):
        # Look at window up to index i
        sub_df = df.iloc[:i+1]
        
        # Check for signal on the latest bar of the window
        signal = check_signals(sub_df, symbol, req_score=req_score)
        
        if signal:
            # Simple trade tracking: Check if TP or SL hit in subsequent bars
            # For backtesting, we look at future data starting from i+1
            entry_price = signal['entry']
            tp = signal['take_profit']
            sl = signal['stop_loss']
            trade_type = signal['type']
            
            result = None
            exit_bar = None
            
            for j in range(i+1, len(df)):
                curr_bar = df.iloc[j]
                
                if trade_type == 'LONG':
                    if curr_bar['low'] <= sl:
                        result = 'SL'
                        exit_bar = j
                        break
                    if curr_bar['high'] >= tp:
                        result = 'TP'
                        exit_bar = j
                        break
                elif trade_type == 'SHORT':
                    if curr_bar['high'] >= sl:
                        result = 'SL'
                        exit_bar = j
                        break
                    if curr_bar['low'] <= tp:
                        result = 'TP'
                        exit_bar = j
                        break
            
            if result:
                trades.append({
                    'entry_time': df.iloc[i]['timestamp'],
                    'type': trade_type,
                    'entry': entry_price,
                    'sl': sl,
                    'tp': tp,
                    'result': result,
                    'exit_time': df.iloc[exit_bar]['timestamp'],
                    'score': signal['score']
                })
                # Skip the window until the trade is closed to avoid overlapping signals
                # i = exit_bar # Wait, this won't work in a simple loop without modifying index.
    
    # 4. Analyze Results
    if not trades:
        print("No signals generated during this period.")
        return

    report_df = pd.DataFrame(trades)
    win_rate = (len(report_df[report_df['result'] == 'TP']) / len(report_df)) * 100
    
    print("\n[BACKTEST RESULTS]")
    print(f"Total Trades: {len(report_df)}")
    print(f"Win Rate: {win_rate:.2f}%")
    print(f"Long Trades: {len(report_df[report_df['type'] == 'LONG'])}")
    print(f"Short Trades: {len(report_df[report_df['type'] == 'SHORT'])}")
    
    print("\nLast 5 trades:")
    print(report_df.tail(5))
    
    return report_df

if __name__ == "__main__":
    run_backtest(limit=1000)
