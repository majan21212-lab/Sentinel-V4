import ccxt
import pandas as pd
import pandas_ta as ta
import numpy as np
from datetime import datetime
from db_utils import get_db_connection

def fetch_data(symbol, timeframe='1h', limit=500):
    """
    Fetches OHLCV data from Binance using CCXT.
    Returns a DataFrame with OHLCV data.
    """
    try:
        exchange = ccxt.binance()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return None

def _atr(high, low, close, length=14):
    """Internal helper for ATR calculation."""
    return ta.atr(high, low, close, length=length)

def calculate_indicators(df, symbol):
    """
    Calculates the 14-Factor God-Mode Indicators.
    """
    if df is None or len(df) < 200:
        return df

    # Prepare index for VWAP and other time-based indicators
    df = df.copy()
    df.set_index('timestamp', inplace=True)
    df.sort_index(inplace=True)

    # 1. MTF Trend (Using EMA 200 as Proxy)
    df['ema200'] = ta.ema(df['close'], length=200)
    df['mtf_bull'] = df['close'] > df['ema200']
    df['mtf_bear'] = df['close'] < df['ema200']

    # 2. Hull Baseline (25)
    df['baseline'] = ta.hma(df['close'], length=25)
    df['bull_hull'] = df['close'] > df['baseline']
    df['bear_hull'] = df['close'] < df['baseline']

    # 3. Volume Spike (Z-Score)
    vol_avg = df['volume'].rolling(20).mean()
    vol_std = df['volume'].rolling(20).std().replace(0, np.nan)
    df['vol_z'] = (df['volume'] - vol_avg) / vol_std
    df['vol_spike'] = ta.ema(df['vol_z'].fillna(0), length=3) > 1.2

    # 4. Momentum (TMO-style simplified)
    osc = ta.mom(ta.sma(ta.sma(df['close'], 7), 7), 7)
    df['bull_mom'] = osc.diff() > 0
    df['bear_mom'] = osc.diff() < 0

    # 5. RSI (14)
    df['rsi'] = ta.rsi(df['close'], length=14)
    df['bull_rsi'] = df['rsi'] > 50
    df['bear_rsi'] = df['rsi'] < 50

    # 6. VWAP (Requires timestamp index)
    try:
        df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    except Exception as e:
        print(f"VWAP Error: {e}")
        df['vwap'] = df['close'] # Fallback
    
    df['bull_vwap'] = df['close'] > df['vwap']
    df['bear_vwap'] = df['close'] < df['vwap']

    # 7. Bollinger Bands (20, 2)
    bbands = ta.bbands(df['close'], length=20, std=2)
    if bbands is not None:
        # Use more robust way to find BBM/BBU/BBL columns
        bbm_col = [c for c in bbands.columns if 'BBM' in c]
        if bbm_col:
            df['bb_mid'] = bbands[bbm_col[0]]
            df['bull_bb'] = df['close'] > df['bb_mid']
            df['bear_bb'] = df['close'] < df['bb_mid']

    # 8. Liquidity Sweeps
    df['sw_high'] = df['high'].rolling(window=10, center=True).max()
    df['sw_low'] = df['low'].rolling(window=10, center=True).min()
    df['bull_sweep'] = (df['low'] < df['sw_low'].shift(1)) & (df['close'] > df['sw_low'].shift(1))
    df['bear_sweep'] = (df['high'] > df['sw_high'].shift(1)) & (df['close'] < df['sw_high'].shift(1))

    # 9. FVG
    df['bull_fvg'] = (df['low'] > df['high'].shift(2)) & (df['close'].shift(1) > df['open'].shift(1))
    df['bear_fvg'] = (df['high'] < df['low'].shift(2)) & (df['close'].shift(1) < df['open'].shift(1))

    # 10. Discount/Premium
    range_high = df['high'].rolling(50).max()
    range_low = df['low'].rolling(50).min()
    midpoint = (range_high + range_low) / 2
    df['is_discount'] = df['close'] < midpoint
    df['is_premium'] = df['close'] > midpoint

    # Reset index back for subsequent processing if needed
    df.reset_index(inplace=True)
    return df

def check_signals(df, symbol, req_score=7):
    """
    Checks for Buy/Sell signals based on a 14-Factor scoring engine (simplified).
    """
    if df is None or len(df) < 200:
        return None

    current = df.iloc[-1]
    prev = df.iloc[-2]

    # Calculate Score
    long_pts = 0
    short_pts = 0
    
    # Simple scoring based on the indicators calculated
    factors = [
        ('mtf_bull', 'mtf_bear'),
        ('bull_hull', 'bear_hull'),
        ('vol_spike', 'vol_spike'), # Volume spike counts for both usually or just strength
        ('bull_mom', 'bear_mom'),
        ('bull_rsi', 'bear_rsi'),
        ('bull_vwap', 'bear_vwap'),
        ('bull_bb', 'bear_bb'),
        ('bull_sweep', 'bear_sweep'),
        ('bull_fvg', 'bear_fvg'),
        ('is_discount', 'is_premium')
    ]

    for bull_f, bear_f in factors:
        if current.get(bull_f): long_pts += 1
        if current.get(bear_f): short_pts += 1

    # Signal Logic: Score >= threshold AND price crossover baseline
    baseline_curr = current.get('baseline')
    baseline_prev = prev.get('baseline')
    
    if baseline_curr is None or pd.isna(baseline_curr) or baseline_prev is None or pd.isna(baseline_prev):
        return None

    long_cond = (long_pts >= req_score) and (current['close'] > baseline_curr) and (prev['close'] <= baseline_prev)
    short_cond = (short_pts >= req_score) and (current['close'] < baseline_curr) and (prev['close'] >= baseline_prev)

    signal = None
    try:
        atr_series = ta.atr(df['high'], df['low'], df['close'], length=14)
        if atr_series is None or (isinstance(atr_series, pd.Series) and atr_series.empty):
            atr = (current['high'] - current['low']) if 'high' in current else 0.01
        else:
            atr = atr_series.iloc[-1]
            if pd.isna(atr):
                atr = (current['high'] - current['low']) if 'high' in current else 0.01
    except Exception:
        atr = (current['high'] - current['low']) if 'high' in current else 0.01

    if long_cond:
        sl = current['close'] - (atr * 1.5)
        tp = current['close'] + (current['close'] - sl) * 2.0
        signal = {
            'type': 'LONG',
            'symbol': symbol,
            'entry': current['close'],
            'stop_loss': sl,
            'take_profit': tp,
            'score': long_pts,
            'reason': f'God-Mode Score: {long_pts}/10'
        }

    elif short_cond:
        sl = current['close'] + (atr * 1.5)
        tp = current['close'] - (sl - current['close']) * 2.0
        signal = {
            'type': 'SHORT',
            'symbol': symbol,
            'entry': current['close'],
            'stop_loss': sl,
            'take_profit': tp,
            'score': short_pts,
            'reason': f'God-Mode Score: {short_pts}/10'
        }

    return signal

def save_signal(signal):
    """
    Saves the signal to the database.
    """
    if not signal:
        return

    try:
        conn = get_db_connection(database='trading_bot')
        if conn:
            cursor = conn.cursor()
            query = """
            INSERT INTO signals (symbol, direction, entry_price, take_profit, stop_loss, timeframe, indicators_meta)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            val = (
                signal['symbol'], 
                signal['type'], 
                signal['entry'], 
                signal['take_profit'], 
                signal['stop_loss'], 
                '1h', 
                signal['reason']
            )
            cursor.execute(query, val)
            conn.commit()
            print(f"Signal saved: {signal}")
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Error saving signal: {e}")

def calculate_grid_params(df, symbol, levels=10, spacing_atr_mult=1.5):
    """
    Calculates Grid Strategy parameters based on current volatility.
    Returns a dict with grid levels.
    """
    if df is None or len(df) < 20:
        return None
        
    current_price = df.iloc[-1]['close']
    atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
    
    if pd.isna(atr):
        atr = current_price * 0.005 # Fallback 0.5%
        
    step = atr * spacing_atr_mult
    
    grid = {
        "symbol": symbol,
        "base_price": current_price,
        "step": step,
        "buy_levels": [current_price - (i * step) for i in range(1, levels + 1)],
        "sell_levels": [current_price + (i * step) for i in range(1, levels + 1)],
        "tp_pct": (step / current_price) * 0.8 # Target 80% of step as profit
    }
    return grid

if __name__ == "__main__":
    run_strategy()
