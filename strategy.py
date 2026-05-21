import ccxt
import pandas as pd
import numpy as np
from datetime import datetime
from db_utils import get_db_connection

# ── TA helper functions (replaces pandas_ta) ─────────────────────────────────
def _ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def _sma(series, length):
    return series.rolling(window=length).mean()

def _hma(series, length):
    import math
    half = int(length / 2)
    sqrt_len = int(math.sqrt(length))
    wmah = series.ewm(span=half, adjust=False).mean()
    wmal = series.ewm(span=length, adjust=False).mean()
    diff = 2 * wmah - wmal
    return diff.ewm(span=sqrt_len, adjust=False).mean()

def _rsi(series, length=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1/length, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1/length, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def _atr(high, low, close, length=14):
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=length).mean()

def _mom(series, length):
    return series - series.shift(length)

def _vwap(high, low, close, volume):
    tp = (high + low + close) / 3
    cum_tp_vol = (tp * volume).cumsum()
    cum_vol = volume.cumsum()
    return cum_tp_vol / cum_vol

def _bbands(close, length=20, std=2):
    mid = close.rolling(window=length).mean()
    band_std = close.rolling(window=length).std()
    upper = mid + (band_std * std)
    lower = mid - (band_std * std)
    return pd.DataFrame({'BBM': mid, 'BBU': upper, 'BBL': lower})

def _adx_full(high, low, close, length=14):
    """Returns (adx, plus_di, minus_di) for directional scoring."""
    up = high - high.shift(1)
    down = low.shift(1) - low

    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=high.index)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1/length, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1/length, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1/length, adjust=False).mean() / atr)

    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-9)) * 100
    adx = dx.ewm(alpha=1/length, adjust=False).mean()
    return adx, plus_di, minus_di

# ── Data Fetching ─────────────────────────────────────────────────────────────

def fetch_data(symbol, timeframe='5m', limit=500):
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
    df['ema200'] = _ema(df['close'], 200)
    df['mtf_bull'] = df['close'] > df['ema200']
    df['mtf_bear'] = df['close'] < df['ema200']

    # 2. Hull Baseline (25)
    df['baseline'] = _hma(df['close'], 25)
    df['bull_hull'] = df['close'] > df['baseline']
    df['bear_hull'] = df['close'] < df['baseline']

    # 3. Volume Spike (Z-Score) — directional: bull if price rising, bear if falling
    vol_avg = df['volume'].rolling(20).mean()
    vol_std = df['volume'].rolling(20).std().replace(0, np.nan)
    df['vol_z'] = (df['volume'] - vol_avg) / vol_std
    vol_strong = _ema(df['vol_z'].fillna(0), 3) > 1.2
    price_rising = df['close'] > df['close'].shift(1)
    df['bull_vol_spike'] = vol_strong & price_rising
    df['bear_vol_spike'] = vol_strong & ~price_rising

    # 4. Momentum (TMO-style simplified)
    osc = _mom(_sma(_sma(df['close'], 7), 7), 7)
    df['bull_mom'] = osc.diff() > 0
    df['bear_mom'] = osc.diff() < 0

    # 5. RSI (14)
    df['rsi'] = _rsi(df['close'], 14)
    df['bull_rsi'] = df['rsi'] > 50
    df['bear_rsi'] = df['rsi'] < 50

    # 6. VWAP — session-anchored: reset at 00:00 UTC each day
    try:
        idx = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df['timestamp'])
        df['_date'] = idx.date if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df['timestamp']).dt.date
        tp = (df['high'] + df['low'] + df['close']) / 3
        df['_tp_vol'] = tp * df['volume']
        df['vwap'] = (
            df.groupby('_date')['_tp_vol'].cumsum() /
            df.groupby('_date')['volume'].cumsum()
        )
        df.drop(columns=['_date', '_tp_vol'], inplace=True)
    except Exception as e:
        print(f"VWAP Error: {e}")
        df['vwap'] = df['close']  # Fallback

    df['bull_vwap'] = df['close'] > df['vwap']
    df['bear_vwap'] = df['close'] < df['vwap']

    # 7. Bollinger Bands (20, 2)
    bbands = _bbands(df['close'], length=20, std=2)
    if bbands is not None:
        df['bb_mid'] = bbands['BBM']
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

    # 11. Trend Strength & Direction (ADX + DI)
    # FIX: use directional DI values — +DI > -DI = bullish momentum, vice versa
    adx_vals, plus_di, minus_di = _adx_full(df['high'], df['low'], df['close'], 14)
    df['adx'] = adx_vals
    df['plus_di'] = plus_di
    df['minus_di'] = minus_di
    df['adx_strong'] = df['adx'] > 25
    df['bull_di'] = (df['plus_di'] > df['minus_di']) & df['adx_strong']   # bullish DI alignment
    df['bear_di'] = (df['minus_di'] > df['plus_di']) & df['adx_strong']   # bearish DI alignment

    # Reset index back for subsequent processing if needed
    df.reset_index(inplace=True)
    return df

def check_signals(df, symbol, req_score=8):
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
    
    # Scoring — all factors are now directional (no factor applies to both sides)
    factors = [
        ('mtf_bull',       'mtf_bear'),       # 1. EMA 200 trend filter
        ('bull_hull',      'bear_hull'),       # 2. Hull MA baseline
        ('bull_vol_spike', 'bear_vol_spike'),  # 3. FIX: directional volume spike
        ('bull_mom',       'bear_mom'),        # 4. Momentum
        ('bull_rsi',       'bear_rsi'),        # 5. RSI 50 filter
        ('bull_vwap',      'bear_vwap'),       # 6. Session-anchored VWAP
        ('bull_bb',        'bear_bb'),         # 7. Bollinger Band midline
        ('bull_sweep',     'bear_sweep'),      # 8. Liquidity sweep
        ('bull_fvg',       'bear_fvg'),        # 9. Fair value gap
        ('is_discount',    'is_premium'),      # 10. Price zone
        ('bull_di',        'bear_di'),         # 11. FIX: directional DI alignment
    ]

    for bull_f, bear_f in factors:
        if current.get(bull_f): long_pts += 1
        if current.get(bear_f): short_pts += 1

    # Signal Logic: Score >= threshold AND price crossover baseline
    long_cond = (long_pts >= req_score) and (current['close'] > current['baseline']) and (prev['close'] <= prev['baseline'])
    short_cond = (short_pts >= req_score) and (current['close'] < current['baseline']) and (prev['close'] >= prev['baseline'])

    signal = None
    atr = _atr(df['high'], df['low'], df['close'], length=14).iloc[-1]

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
        import os
        broker = os.getenv("BROKER_TYPE", "BINANCE")
        conn = get_db_connection(database='trading_bot')
        if conn:
            cursor = conn.cursor()
            query = """
            INSERT INTO signals (symbol, direction, entry_price, take_profit, stop_loss, timeframe, indicators_meta, broker)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            val = (
                signal['symbol'],
                signal['type'],
                signal['entry'],
                signal['take_profit'],
                signal['stop_loss'],
                '5m',   # FIX: was hardcoded '1h' — data is fetched on 5m timeframe
                signal['reason'],
                broker
            )
            cursor.execute(query, val)
            conn.commit()
            print(f"Signal saved: {signal}")
            cursor.close()
            conn.close()
    except Exception as e:
        print(f"Error saving signal: {e}")

def run_strategy(symbol='BTC/USDT', df=None):
    print(f"Running God-Mode Strategy for {symbol}...")
    if df is None:
        df = fetch_data(symbol)
    if df is not None:
        df = calculate_indicators(df, symbol)
        signal = check_signals(df, symbol)
        if signal:
            print(f"SIGNAL FOUND: {signal}")
            save_signal(signal)
        else:
            # For debugging, show score
            last = df.iloc[-1]
            # print(f"Current Market Context: RSI: {last['rsi']:.2f} | Score: ? (Not calculated if no cross)")
            print("No signal found (requires baseline crossover and confluence).")

if __name__ == "__main__":
    run_strategy()
