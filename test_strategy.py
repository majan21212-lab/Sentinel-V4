import pandas as pd
import numpy as np
from strategy import calculate_indicators, check_signals

def generate_synthetic_data(length=300):
    """
    Generates a DataFrame with sufficient history for calculations.
    """
    dates = pd.date_range(end=pd.Timestamp.now(), periods=length, freq='1h')
    # Generate some slightly trending data
    close = np.linspace(100, 150, length) + np.random.randn(length)
    df = pd.DataFrame({
        'timestamp': dates,
        'open': close - 1,
        'high': close + 2,
        'low': close - 2,
        'close': close,
        'volume': np.random.randint(100, 1000, length)
    })
    return df

def test_indicators():
    print("Testing Indicators Calculation...")
    df = generate_synthetic_data()
    df = calculate_indicators(df, 'TEST/USD')
    
    required_cols = [
        'ema200', 'baseline', 'vol_spike', 'rsi', 'vwap', 
        'mtf_bull', 'bull_hull', 'bull_rsi', 'bull_vwap', 
        'bull_fvg', 'is_discount'
    ]
    
    missing = [col for col in required_cols if col not in df.columns]
    
    if not missing:
        print("PASS: All indicator columns calculated.")
    else:
        print(f"FAIL: Missing columns: {missing}")

def test_god_mode_long():
    print("\nTesting God-Mode Long Signal...")
    df = generate_synthetic_data()
    
    # Manually set confluence factors at the end
    last_idx = df.index[-1]
    prev_idx = df.index[-2]
    
    # 1. Confluence factors (Let's set 8/10)
    confluence_cols = [
        'mtf_bull', 'bull_hull', 'bull_mom', 'bull_rsi', 
        'bull_vwap', 'bull_bb', 'bull_fvg', 'is_discount'
    ]
    for col in confluence_cols:
        df.loc[last_idx, col] = True
        
    # 2. Baseline Crossover
    df.loc[last_idx, 'baseline'] = 100.0
    df.loc[prev_idx, 'baseline'] = 100.0
    
    df.loc[last_idx, 'close'] = 105.0 # Above baseline
    df.loc[prev_idx, 'close'] = 98.0  # Below baseline
    
    # Add high/low for ATR calculation (required by check_signals)
    df.loc[last_idx, 'high'] = 106.0
    df.loc[last_idx, 'low'] = 104.0
    
    signal = check_signals(df, 'TEST/USD', req_score=7)
    
    if signal and signal['type'] == 'LONG' and signal['score'] >= 7:
        print(f"PASS: Long Signal Detected with score {signal['score']}")
    else:
        print(f"FAIL: Expected Long Signal, got {signal}")

def test_god_mode_low_score():
    print("\nTesting Low Score Filter...")
    df = generate_synthetic_data()
    
    last_idx = df.index[-1]
    prev_idx = df.index[-2]
    
    # Only 3 factors (threshold is 7)
    df.loc[last_idx, 'mtf_bull'] = True
    df.loc[last_idx, 'bull_rsi'] = True
    df.loc[last_idx, 'bull_fvg'] = True
    
    # Crossover exists
    df.loc[last_idx, 'baseline'] = 100.0
    df.loc[last_idx, 'close'] = 105.0
    df.loc[prev_idx, 'close'] = 98.0
    
    signal = check_signals(df, 'TEST/USD', req_score=7)
    
    if signal is None:
        print("PASS: No signal generated for low confluence score.")
    else:
        print(f"FAIL: Signal generated with low score: {signal['score']}")

if __name__ == "__main__":
    try:
        test_indicators()
        test_god_mode_long()
        test_god_mode_low_score()
    except Exception as e:
        print(f"An error occurred during testing: {e}")
        import traceback
        traceback.print_exc()
