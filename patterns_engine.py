import pandas as pd
import numpy as np
import logging

log = logging.getLogger(__name__)

# ── TA helper functions (replaces pandas_ta) ─────────────────────────────────
def _ema(series, length):
    return series.ewm(span=length, adjust=False).mean()

def _sma(series, length):
    return series.rolling(window=length).mean()

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

class PatternsEngine:
    def __init__(self, m5_df, m15_df=None, h1_df=None):
        self.df = m5_df
        self.m15 = m15_df
        self.h1 = h1_df
        self.indicators = {} # Registry for custom indicator results
        self._prepare_indicators()

    def add_custom_indicator(self, name: str, weight: float, condition_func):
        """
        Allows users to add any indicator.
        condition_func should take the dataframe and return a boolean (Signal).
        """
        try:
            is_active = condition_func(self.df)
            self.indicators[name] = {"active": is_active, "weight": weight}
        except Exception as e:
            log.error(f"Error adding custom indicator {name}: {e}")

    def _prepare_indicators(self):
        """Prepare core indicators for the main timeframe."""
        df = self.df
        if 'ema200' not in df.columns:
            df['ema200'] = _ema(df['close'], length=200)
        if 'rsi' not in df.columns:
            df['rsi'] = _rsi(df['close'], length=14)
        if 'vol_avg' not in df.columns:
            df['vol_avg'] = _sma(df['volume'], length=20)
        if 'atr' not in df.columns:
            df['atr'] = _atr(df['high'], df['low'], df['close'], length=14)
        
        # Helper for pivot detection
        if 'ph' not in df.columns:
            df['ph'] = self._detect_pivots(df['high'], left=5, right=5)
        if 'pl' not in df.columns:
            df['pl'] = self._detect_pivots(df['low'], left=5, right=5, is_high=False)
            
        # NR7 Helper (Narrow Range 7)
        if 'tr' not in df.columns:
            df['tr'] = df['high'] - df['low']
        if 'nr7' not in df.columns:
            df['nr7'] = df['tr'] < df['tr'].shift(1).rolling(6).min()

    def _detect_pivots(self, series, left, right, is_high=True):
        """Python implementation of ta.pivothigh / ta.pivotlow."""
        pivots = [np.nan] * len(series)
        for i in range(left, len(series) - right):
            window = series.iloc[i-left : i+right+1]
            if is_high:
                if series.iloc[i] == window.max():
                    pivots[i] = series.iloc[i]
            else:
                if series.iloc[i] == window.min():
                    pivots[i] = series.iloc[i]
        return pivots

    def calculate_confluence_score(self, is_bull: bool) -> float:
        """
        Calculates the Jewel Confluence Score (0-100%).
        Now includes dynamic custom indicators.
        """
        df = self.df
        latest = df.iloc[-1]
        score = 0.0

        # 1. Trend Filter (EMA 200)
        trend_ok = latest['close'] > latest['ema200'] if is_bull else latest['close'] < latest['ema200']
        if trend_ok: score += 20

        # 2. MTF Alignment (M15 & H1)
        mtf_score = 0
        if self.m15 is not None:
            m15_ema = _ema(self.m15['close'], length=200).iloc[-1]
            if (is_bull and self.m15['close'].iloc[-1] > m15_ema) or (not is_bull and self.m15['close'].iloc[-1] < m15_ema):
                mtf_score += 10
        if self.h1 is not None and len(self.h1) > 200:
            h1_series = _ema(self.h1['close'], length=200)
            if h1_series is not None and not h1_series.empty:
                 h1_ema = h1_series.iloc[-1]
                 if (is_bull and self.h1['close'].iloc[-1] > h1_ema) or (not is_bull and self.h1['close'].iloc[-1] < h1_ema):
                    mtf_score += 10
        score += mtf_score

        # 3. RSI Momentum
        rsi_ok = (latest['rsi'] > 40 and latest['rsi'] < 75) if is_bull else (latest['rsi'] < 60 and latest['rsi'] > 25)
        if rsi_ok: score += 15

        # 4. Volume Filter
        vol_ok = latest['volume'] > latest['vol_avg'] * 1.2
        if vol_ok: score += 15

        # 5. DYNAMIC CUSTOM INDICATORS
        for name, data in self.indicators.items():
            if data["active"]:
                score += data["weight"]
                log.info(f"💎 Indicator '{name}' added {data['weight']} to score.")

        return min(100, score)

    # ── Pattern Detection Algorithms ──────────────────────────────────────────

    def detect_waterfall(self):
        """Enhanced Waterfall Detection (5 consecutive candles + Surge)."""
        df = self.df
        if len(df) < 6: return None
        
        subset = df.iloc[-5:]
        all_bull = all(subset['close'] > subset['open'])
        all_bear = all(subset['close'] < subset['open'])
        
        vol_ratio = subset['volume'].mean() / df['vol_avg'].iloc[-1]
        
        if all_bull and vol_ratio > 1.5:
            return {"type": "WATERFALL_BULL", "direction": "LONG", "score_bonus": 20}
        elif all_bear and vol_ratio > 1.5:
            return {"type": "WATERFALL_BEAR", "direction": "SHORT", "score_bonus": 20}
        return None

    def detect_cup_and_handle(self):
        """Cup & Handle Breakout logic."""
        df = self.df
        # Simplified: Look for a major pivot high, a consolidation, and a breakout
        pivots = df['ph'].dropna()
        if len(pivots) < 2: return None
        
        last_ph = pivots.iloc[-1]
        last_ph_idx = pivots.index[-1]
        
        # Check if we just broke above the last major pivot high
        if df['close'].iloc[-2] <= last_ph and df['close'].iloc[-1] > last_ph:
            # Validate 'cup' depth (must have dipped between pivots)
            mid_low = df['low'].iloc[last_ph_idx:-1].min()
            if mid_low < last_ph - (df['atr'].iloc[-1] * 3):
                return {"type": "CUP_AND_HANDLE", "direction": "LONG", "score_bonus": 25}
        return None

    def detect_head_and_shoulders(self):
        """3-Pivot structure detection."""
        df = self.df
        pivots = df['ph'].dropna()
        if len(pivots) < 3: return None
        
        l_sh, head, r_sh = pivots.iloc[-3], pivots.iloc[-2], pivots.iloc[-1]
        
        # Logic: Head > Shoulders and Shoulders roughly equal
        if head > l_sh and head > r_sh and abs(l_sh - r_sh) < (df['atr'].iloc[-1] * 2):
            # Check for neckline breakout (bearish)
            neckline = df['low'].iloc[pivots.index[-3]:pivots.index[-1]].min()
            if df['close'].iloc[-1] < neckline:
                return {"type": "HEAD_AND_SHOULDERS", "direction": "SHORT", "score_bonus": 30}
        return None

    def detect_double_top_bottom(self):
        """Detection of price rejections at similar levels."""
        df = self.df
        latest_atr = df['atr'].iloc[-1]
        
        # Double Top
        ph_pivots = df['ph'].dropna()
        if len(ph_pivots) >= 2:
            p1, p2 = ph_pivots.iloc[-2], ph_pivots.iloc[-1]
            if abs(p1 - p2) < (latest_atr * 0.5):
                if df['close'].iloc[-1] < df['low'].iloc[ph_pivots.index[-1]-1]: # Neckline break
                    return {"type": "DOUBLE_TOP", "direction": "SHORT", "score_bonus": 15}

        # Double Bottom
        pl_pivots = df['pl'].dropna()
        if len(pl_pivots) >= 2:
            p1, p2 = pl_pivots.iloc[-2], pl_pivots.iloc[-1]
            if abs(p1 - p2) < (latest_atr * 0.5):
                if df['close'].iloc[-1] > df['high'].iloc[pl_pivots.index[-1]-1]:
                    return {"type": "DOUBLE_BOTTOM", "direction": "LONG", "score_bonus": 15}
        return None

    def detect_liquidity_zones(self):
        """Retest of Supply/Demand areas."""
        df = self.df
        atr = df['atr'].iloc[-1]
        
        # Demand Zone Check (recent pivot lows)
        pl_pivots = df['pl'].dropna()
        if not pl_pivots.empty:
            last_pl = pl_pivots.iloc[-1]
            # If price just touched the pivot area and bounced
            if df['low'].iloc[-1] <= last_pl + (atr * 0.2) and df['close'].iloc[-1] > last_pl:
                return {"type": "LIQUIDITY_DEMAND", "direction": "LONG", "score_bonus": 25}

        # Supply Zone Check
        ph_pivots = df['ph'].dropna()
        if not ph_pivots.empty:
            last_ph = ph_pivots.iloc[-1]
            if df['high'].iloc[-1] >= last_ph - (atr * 0.2) and df['close'].iloc[-1] < last_ph:
                return {"type": "LIQUIDITY_SUPPLY", "direction": "SHORT", "score_bonus": 25}
                
        return None

    def detect_triangles(self):
        """Detect Sym/Asc/Desc Triangles based on pivot slopes."""
        df = self.df
        ph = df['ph'].dropna().tail(2)
        pl = df['pl'].dropna().tail(2)
        
        if len(ph) < 2 or len(pl) < 2: return None
        
        h1, h2 = ph.iloc[-2], ph.iloc[-1]
        l1, l2 = pl.iloc[-2], pl.iloc[-1]
        atr = df['atr'].iloc[-1]
        
        is_sym = h2 < h1 and l2 > l1
        is_asc = abs(h2 - h1) < (atr * 0.5) and l2 > l1
        is_desc = h2 < h1 and abs(l2 - l1) < (atr * 0.5)
        
        if (is_sym or is_asc or is_desc):
            # Breakout logic
            if df['close'].iloc[-1] > h2:
                return {"type": "TRIANGLE_BO", "direction": "LONG", "score_bonus": 20}
            elif df['close'].iloc[-1] < l2:
                return {"type": "TRIANGLE_BD", "direction": "SHORT", "score_bonus": 20}
        return None

    def detect_rectangles(self):
        """Detect Horizontal Congestion (Rectangle) breakouts."""
        df = self.df
        ph = df['ph'].dropna().tail(2)
        pl = df['pl'].dropna().tail(2)
        
        if len(ph) < 2 or len(pl) < 2: return None
        
        h_avg = ph.mean()
        l_avg = pl.mean()
        atr = df['atr'].iloc[-1]
        
        # Check if pivots are roughly at the same horizontal level
        is_rect = abs(ph.iloc[0] - ph.iloc[1]) < (atr * 0.8) and abs(pl.iloc[0] - pl.iloc[1]) < (atr * 0.8)
        
        if is_rect:
            if df['close'].iloc[-1] > h_avg + (atr * 0.2):
                return {"type": "RECTANGLE_BO", "direction": "LONG", "score_bonus": 20}
            elif df['close'].iloc[-1] < l_avg - (atr * 0.2):
                return {"type": "RECTANGLE_BD", "direction": "SHORT", "score_bonus": 20}
        return None

    def detect_gaps(self):
        """Identify Institutional Open Gaps."""
        df = self.df
        if len(df) < 2: return None
        
        # Bullish Gap
        if df['low'].iloc[-1] > df['high'].iloc[-2]:
            return {"type": "INST_GAP_UP", "direction": "LONG", "score_bonus": 15}
        # Bearish Gap
        elif df['high'].iloc[-1] < df['low'].iloc[-2]:
            return {"type": "INST_GAP_DN", "direction": "SHORT", "score_bonus": 15}
        return None
    
    def detect_fvg(self, df):
        """Detect Fair Value Gaps (FVG) / Imbalances in a dataframe."""
        if len(df) < 3: return []
        gaps = []
        for i in range(2, len(df)):
            # Bullish FVG (Low of candle 3 is above high of candle 1)
            if df['low'].iloc[i] > df['high'].iloc[i-2]:
                gaps.append({"type": "FVG_BULL", "top": df['low'].iloc[i], "bottom": df['high'].iloc[i-2], "index": i})
            # Bearish FVG (High of candle 3 is below low of candle 1)
            elif df['high'].iloc[i] < df['low'].iloc[i-2]:
                gaps.append({"type": "FVG_BEAR", "top": df['low'].iloc[i-2], "bottom": df['high'].iloc[i], "index": i})
        return gaps

    def detect_order_blocks(self, df):
        """Detect Institutional Order Blocks (OB)."""
        if len(df) < 10: return []
        obs = []
        # Simplified: Look for a strong move (3+ candles) and identify the preceding 'base' candle
        for i in range(5, len(df) - 3):
            # Bullish Move Check
            if all(df['close'].iloc[i+1 : i+4] > df['open'].iloc[i+1 : i+4]):
                # The 'Order Block' is the last bearish candle before the move
                if df['close'].iloc[i] < df['open'].iloc[i]:
                    obs.append({"type": "OB_BULL", "high": df['high'].iloc[i], "low": df['low'].iloc[i], "index": i})
            # Bearish Move Check
            elif all(df['close'].iloc[i+1 : i+4] < df['open'].iloc[i+1 : i+4]):
                 if df['close'].iloc[i] > df['open'].iloc[i]:
                    obs.append({"type": "OB_BEAR", "high": df['high'].iloc[i], "low": df['low'].iloc[i], "index": i})
        return obs

    def detect_patterns(self):
        """
        Top-Down SMC Strategy:
        1. Identify H1 Order Blocks (Anchors).
        2. Verify Price is in H1 OB or hitting an FVG.
        3. Enter on M5 internal Order Blocks or Liquidity Sweeps.
        """
        df = self.df
        h1_df = self.h1
        atr = df['atr'].iloc[-1]
        entry = df['close'].iloc[-1]
        
        # --- 1. Higher Timeframe Analysis (H1 Anchors) ---
        h1_bias = "NEUTRAL"
        if h1_df is not None:
            h1_obs = self.detect_order_blocks(h1_df)
            for ob in h1_obs:
                if entry >= ob['low'] and entry <= ob['high']:
                    h1_bias = "LONG" if ob['type'] == "OB_BULL" else "SHORT"
                    break

        # --- 2. Lower Timeframe Pattern Scan (M5 Entries) ---
        m5_results = [
            self.detect_waterfall(),
            self.detect_order_blocks(df),
            self.detect_fvg(df),
            self.detect_liquidity_zones(),
            self.detect_triangles(),
            self.detect_rectangles(),
            self.detect_gaps()
        ]
        
        # Dynamic NR7 weighting
        nr7_boost = 10 if df['nr7'].iloc[-1] else 0
        
        # Flatten and filter results
        signals = []
        for r in m5_results:
            if isinstance(r, list): signals.extend(r)
            elif r is not None: signals.append(r)

        if not signals: return None
        
        # Filter signals based on H1 Bias (Top-Down Alignment)
        valid_signals = []
        for sig in signals:
            sig_type = sig.get('type', '')
            is_bull = "BULL" in sig_type or sig.get('direction') == "LONG" or "DEMAND" in sig_type
            
            # Confluence check: Must align with H1 or be a strong solo reversal
            if h1_bias == "LONG" and is_bull:
                valid_signals.append(sig)
            elif h1_bias == "SHORT" and not is_bull:
                valid_signals.append(sig)
            elif h1_bias == "NEUTRAL":
                # Only take very high scoring signals if no HTF anchor
                valid_signals.append(sig)

        if not valid_signals: return None
        
        # Pick the most recent/relevant signal
        primary = valid_signals[-1]
        is_bull = "BULL" in primary.get('type', '') or primary.get('direction') == "LONG" or "DEMAND" in primary.get('type', '')
        
        base_score = self.calculate_confluence_score(is_bull)
        total_score = min(100, base_score + 25 + nr7_boost) # SMC signals get a high bonus
        
        if total_score >= 60:
            sl_dist = atr * 2
            sl = entry - sl_dist if is_bull else entry + sl_dist
            tp1 = entry + sl_dist if is_bull else entry - sl_dist
            tp2 = entry + (sl_dist * 3) if is_bull else entry - (sl_dist * 3)
            
            return {
                "pattern": primary.get('type', 'SMC_STRUCTURE'),
                "direction": "LONG" if is_bull else "SHORT",
                "score": total_score,
                "entry": entry,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "reason": f"H1 Anchor: {h1_bias} + M5 SMC Entry"
            }
        
        return None
