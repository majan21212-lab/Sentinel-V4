import os
import asyncio
import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
import MetaTrader5 as mt5

# Internal imports
from patterns_engine import PatternsEngine
from db_utils import get_db_connection

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("Reconstructor")

load_dotenv()

async def get_historical_data(symbol, timeframe, bars=2000):
    """Fetches historical data from MT5."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    # MT5 uses tick_volume for CFD/Forex
    df['volume'] = df['tick_volume']
    return df

def check_outcome(df, start_idx, entry, tp, sl, direction):
    """Checks the future candles to see if TP or SL was hit first."""
    for i in range(start_idx + 1, len(df)):
        high = df['high'].iloc[i]
        low = df['low'].iloc[i]
        
        if direction == "LONG":
            if high >= tp: return 1  # Win
            if low <= sl: return -1 # Loss
        else:
            if low <= tp: return 1   # Win
            if high >= sl: return -1 # Loss
    return 0 # Still pending/expired

async def reconstruct():
    if not mt5.initialize(
        login=int(os.getenv("EXNESS_ACCOUNT")),
        password=os.getenv("EXNESS_PASSWORD"),
        server=os.getenv("EXNESS_SERVER")
    ):
        log.error("MT5 Initialization failed")
        return

    symbols = ["XAUUSDm", "BTCUSDm"]
    lookback_bars = 5000 # ~30 days of M5 data
    h1_lookback = 1000   # Sufficient for EMA200
    
    conn = get_db_connection()
    cursor = conn.cursor()

    for symbol in symbols:
        log.info(f"⌛ Reconstructing history for {symbol}...")
        signals_found = 0
        
        # Get M5 data for signals
        df_m5 = await get_historical_data(symbol, mt5.TIMEFRAME_M5, lookback_bars)
        # Get H1 data for anchors
        df_h1 = await get_historical_data(symbol, mt5.TIMEFRAME_H1, h1_lookback)
        
        if df_m5.empty: continue

        # We slide a window of 200 bars (PatternsEngine needs EMA200, etc.)
        for i in range(200, len(df_m5) - 50): # Stop 50 bars before end to check outcomes
            window = df_m5.iloc[i-200 : i+1].copy()
            
            # Match H1 data to the current M5 timestamp
            current_time = df_m5['time'].iloc[i]
            h1_window = df_h1[df_h1['time'] <= current_time].tail(200)
            
            engine = PatternsEngine(window, h1_df=h1_window)
            signal = engine.detect_patterns()
            
            if signal:
                # Check what happened next
                outcome = check_outcome(
                    df_m5, i, 
                    signal['entry'], signal['tp1'], signal['sl'], 
                    signal['direction']
                )
                
                if outcome != 0:
                    cursor.execute("""
                        INSERT INTO signals (symbol, direction, entry_price, take_profit, stop_loss, timeframe, pattern, score, outcome, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        symbol, signal['direction'], signal['entry'], 
                        signal['tp1'], signal['sl'], "M5", 
                        signal['pattern'], signal['score'], outcome,
                        current_time.strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    
                    # Periodic commits and logging
                    signals_found += 1
                    if signals_found % 10 == 0:
                        conn.commit()
                        log.info(f"   + Found and committed {signals_found} signals for {symbol} so far...")

        conn.commit()
    
    conn.close()
    mt5.shutdown()
    log.info("✅ Reconstruction Complete. Database seeded with real historical results.")

if __name__ == "__main__":
    asyncio.run(reconstruct())
