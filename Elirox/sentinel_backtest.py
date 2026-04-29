import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv
from patterns_engine import PatternsEngine
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Load .env from parent dir
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

def fetch_historical_mtf(symbol, days=30):
    if not mt5.initialize():
        log.error(f"MT5 Init Failed: {mt5.last_error()}")
        return None

    utc_to = datetime.now()
    utc_from = utc_to - timedelta(days=days)
    log.info(f"Fetching data from {utc_from} to {utc_to}")

    rates_m5 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M5, utc_from, utc_to)
    if rates_m5 is None or len(rates_m5) == 0:
        log.error(f"No M5 data for {symbol}. Error: {mt5.last_error()}")
        return None
    
    df_m5 = pd.DataFrame(rates_m5)
    df_m5['timestamp'] = pd.to_datetime(df_m5['time'], unit='s')
    df_m5.rename(columns={'tick_volume': 'volume'}, inplace=True)

    rates_m15 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, utc_from, utc_to)
    df_m15 = pd.DataFrame(rates_m15)
    df_m15['timestamp'] = pd.to_datetime(df_m15['time'], unit='s')
    df_m15.rename(columns={'tick_volume': 'volume'}, inplace=True)

    rates_h1 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, utc_from, utc_to)
    df_h1 = pd.DataFrame(rates_h1)
    df_h1['timestamp'] = pd.to_datetime(df_h1['time'], unit='s')
    df_h1.rename(columns={'tick_volume': 'volume'}, inplace=True)

    return {'m5': df_m5, 'm15': df_m15, 'h1': df_h1}

def run_sentinel_backtest(symbol="XAUUSDm", days=30):
    log.info(f"--- Sentinel-V4 Backtest: {symbol} ({days} Days) ---")
    data = fetch_historical_mtf(symbol, days)
    if not data: return

    m5 = data['m5']
    m15 = data['m15']
    h1 = data['h1']

    trades = []
    log.info(f"Processing {len(m5)} candles...")
    
    for i in range(200, len(m5), 20): # Step 20 to be faster
        current_time = m5.iloc[i]['timestamp']
        sub_m5 = m5.iloc[:i+1]
        sub_m15 = m15[m15['timestamp'] <= current_time]
        sub_h1 = h1[h1['timestamp'] <= current_time]

        engine = PatternsEngine(m5_df=sub_m5, m15_df=sub_m15, h1_df=sub_h1)
        signal = engine.detect_patterns()

        if signal:
            entry_price = signal['entry']
            tp = signal['tp1']
            sl = signal['sl']
            direction = signal['direction']
            
            result = None
            exit_time = None
            exit_price = None
            
            for j in range(i+1, len(m5)):
                future_bar = m5.iloc[j]
                if direction == "LONG":
                    if future_bar['low'] <= sl: result, exit_price = "SL", sl
                    elif future_bar['high'] >= tp: result, exit_price = "TP", tp
                else:
                    if future_bar['high'] >= sl: result, exit_price = "SL", sl
                    elif future_bar['low'] <= tp: result, exit_price = "TP", tp
                
                if result:
                    exit_time = future_bar['timestamp']
                    break
            
            if result:
                pnl = (exit_price - entry_price) if direction == "LONG" else (entry_price - exit_price)
                if "XAU" in symbol: pnl *= 100 
                
                trades.append({
                    'time': current_time,
                    'pattern': signal['pattern'],
                    'direction': direction,
                    'entry': entry_price,
                    'result': result,
                    'pnl': round(pnl, 2),
                    'exit_time': exit_time
                })
    
    if not trades:
        log.info("No trades generated.")
        return None

    df_results = pd.DataFrame(trades)
    win_rate = len(df_results[df_results['result'] == 'TP']) / len(df_results)
    total_pnl = df_results['pnl'].sum()
    
    print("\n" + "="*40)
    print(f"BACKTEST RESULTS: {symbol}")
    print("="*40)
    print(f"Total Trades:  {len(df_results)}")
    print(f"Win Rate:      {win_rate*100:.1f}%")
    print(f"Total PnL:     ${total_pnl:,.2f}")
    print("="*40)
    
    return df_results

if __name__ == "__main__":
    run_sentinel_backtest("XAUUSDm", days=30)
