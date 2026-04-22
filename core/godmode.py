import pandas as pd
import pandas_ta as ta
import numpy as np
import logging

logger = logging.getLogger(__name__)

class GodModeEngine:
    """Python implementation of Ultimate Universal God-Mode Engine (v8.1) - Advanced Mode"""
    
    def __init__(self, df: pd.DataFrame, h1_df: pd.DataFrame = None):
        self.df = df.copy()
        self.h1_df = h1_df.copy() if h1_df is not None else None

    def analyze(self) -> dict:
        """Calculates 14-Factor Heatmap and returns signal if conditions met."""
        df = self.df
        
        # Ensure we have enough data points
        if len(df) < 200:
            logger.warning("GodModeEngine: Not enough data points (need at least 200).")
            return None
            
        # 1. H1 Trend Confluence (MTF)
        h1_trend_bull = True
        h1_trend_bear = True
        if self.h1_df is not None and len(self.h1_df) >= 200:
            h1_df = self.h1_df
            h1_df['ema200'] = ta.ema(h1_df['close'], length=200).fillna(h1_df['close'])
            h1_latest = h1_df.iloc[-1]
            h1_trend_bull = bool(h1_latest['close'] > h1_latest['ema200'])
            h1_trend_bear = bool(h1_latest['close'] < h1_latest['ema200'])

        # 2. Trend Filter (M15)
        df['ema200'] = ta.ema(df['close'], length=200).fillna(df['close'])
        
        # 3. Hull Baseline
        df['hma25'] = ta.hma(df['close'], length=25).fillna(df['close'])
        
        # 4. Volume Spike
        vol_col = 'tick_volume' if 'tick_volume' in df.columns else 'volume'
        df['vol_avg'] = ta.sma(df[vol_col], length=20).fillna(0)
        
        # 5. Momentum
        df['sma7'] = ta.sma(df['close'], length=7).fillna(df['close'])
        
        # 6. Liquidity sweeps (Simplified rolling)
        df['roll_high'] = df['high'].rolling(20).max().fillna(df['high'])
        df['roll_low'] = df['low'].rolling(20).min().fillna(df['low'])
        
        # 7. VWAP
        try:
            df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df[vol_col]).fillna(df['close'])
        except Exception:
            df['vwap'] = df['close'] 
        
        # 8. Bollinger Bands
        df['sma20'] = ta.sma(df['close'], length=20).fillna(df['close'])
        
        # 9. Daily Pivot (Simplified)
        # Using 1-day resample for pivots (Conceptual)
        
        # Indicators calculated. Slice latest.
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        old = df.iloc[-3]

        mtf_bull = bool(latest['close'] > latest['ema200']) and h1_trend_bull
        mtf_bear = bool(latest['close'] < latest['ema200']) and h1_trend_bear
        
        bull_hull = bool(latest['close'] > latest['hma25'])
        bear_hull = bool(latest['close'] < latest['hma25'])
        
        vol_active = bool(latest[vol_col] > latest['vol_avg'])
        
        bull_mom = bool(latest['sma7'] > prev['sma7'])
        bear_mom = bool(latest['sma7'] < prev['sma7'])
        
        bull_sweep = bool(latest['low'] < prev['roll_low'] and latest['close'] > prev['roll_low'])
        bear_sweep = bool(latest['high'] > prev['roll_high'] and latest['close'] < prev['roll_high'])
        
        midpoint = (latest['roll_high'] + latest['roll_low']) / 2
        is_discount = bool(latest['close'] < midpoint)
        is_premium = bool(latest['close'] > midpoint)
        
        bull_vwap = bool(latest['close'] > latest['vwap'])
        bear_vwap = bool(latest['close'] < latest['vwap'])
        
        bull_bb = bool(latest['close'] > latest['sma20'])
        bear_bb = bool(latest['close'] < latest['sma20'])
        
        # 10. Institutional Patterns: FVG
        bull_fvg = bool(latest['low'] > old['high'])
        bear_fvg = bool(latest['high'] < old['low'])
        
        # 11. Institutional Patterns: MSB
        bull_msb = bool(latest['close'] > prev['roll_high'])
        bear_msb = bool(latest['close'] < prev['roll_low'])
        
        # 12. Breaker Block
        bull_breaker = bool(bull_msb and latest['close'] > latest['hma25'])
        bear_breaker = bool(bear_msb and latest['close'] < latest['hma25'])
        
        bull_rsi = bool(latest['rsi'] > 50) if 'rsi' in latest else True
        bear_rsi = bool(latest['rsi'] < 50) if 'rsi' in latest else True
        
        # Factor Scoring (Total 12 active factors)
        long_score = sum([mtf_bull, bull_hull, vol_active, bull_mom, bull_sweep, is_discount, bull_vwap, bull_bb, bull_fvg, bull_msb, bull_breaker, bull_rsi])
        short_score = sum([mtf_bear, bear_hull, vol_active, bear_mom, bear_sweep, is_premium, bear_vwap, bear_bb, bear_fvg, bear_msb, bear_breaker, bear_rsi])
        
        max_possible = 12
        min_score = 1
        
        if long_score >= min_score:
            return self._format_signal("LONG", (long_score/max_possible)*100, latest)
        elif short_score >= min_score:
            return self._format_signal("SHORT", (short_score/max_possible)*100, latest)
            
        return None

    def _format_signal(self, direction: str, score: float, current_bar) -> dict:
        atr_series = ta.atr(self.df['high'], self.df['low'], self.df['close'], length=14)
        atr = atr_series.iloc[-1] if atr_series is not None and not atr_series.empty else 0
        
        if np.isnan(atr) or atr == 0:
            atr = abs(current_bar['high'] - current_bar['low']) * 2

        entry = current_bar['close']
        
        if direction == "LONG":
            sl = current_bar['roll_low'] - (atr * 0.5)
            tp = entry + ((entry - sl) * 2.5) # Increased RR for Advanced Mode
        else:
            sl = current_bar['roll_high'] + (atr * 0.5)
            tp = entry - ((sl - entry) * 2.5)
            
        return {
            "pattern": "GodMode_IPA_v4",
            "direction": direction,
            "score": float(score),
            "entry": float(entry),
            "sl": float(sl),
            "tp1": float(tp)
        }
