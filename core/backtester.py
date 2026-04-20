import pandas as pd
import pandas_ta as ta
import numpy as np
import logging
from datetime import datetime
from patterns_engine import PatternsEngine
from risk_management import RiskEngine, RiskConfig

log = logging.getLogger(__name__)

class SMCBacktester:
    def __init__(self, m5_df, m15_df, h1_df, initial_equity=10000.0, commission=0.0006, spread_pct=0.0001):
        self.m5 = m5_df.sort_values('timestamp').reset_index(drop=True)
        self.m15 = m15_df.sort_values('timestamp').reset_index(drop=True)
        self.h1 = h1_df.sort_values('timestamp').reset_index(drop=True)
        
        self.initial_equity = initial_equity
        self.commission = commission 
        self.spread_pct = spread_pct
        
        self.signals = []
        self.results = []
        self.equity_curve = []

    def _detect_pivots(self, series, left, right, is_high=True):
        pivots = [np.nan] * len(series)
        for i in range(left, len(series) - right):
            window = series.iloc[i-left : i+right+1]
            if is_high:
                if series.iloc[i] == window.max(): pivots[i] = series.iloc[i]
            else:
                if series.iloc[i] == window.min(): pivots[i] = series.iloc[i]
        return pivots

    def precalculate_signals(self):
        """Runs the PatternsEngine over the entire dataset ONCE to find all potential trade entries."""
        log.info("🔍 Pre-calculating all possible signals (this takes a moment)...")
        
        # 1. Indicators
        self.m5['ema200'] = ta.ema(self.m5['close'], length=200)
        self.m5['rsi'] = ta.rsi(self.m5['close'], length=14)
        self.m5['vol_avg'] = ta.sma(self.m5['volume'], length=20)
        self.m5['atr'] = ta.atr(self.m5['high'], self.m5['low'], self.m5['close'], length=14)
        self.m5['ph'] = self._detect_pivots(self.m5['high'], left=5, right=5)
        self.m5['pl'] = self._detect_pivots(self.m5['low'], left=5, right=5, is_high=False)
        self.m15['ema200'] = ta.ema(self.m15['close'], length=200)
        self.h1['ema200'] = ta.ema(self.h1['close'], length=200)

        # 2. MTF Sync
        m15_indices = np.searchsorted(self.m15['timestamp'].values, self.m5['timestamp'].values, side='right') - 1
        h1_indices = np.searchsorted(self.h1['timestamp'].values, self.m5['timestamp'].values, side='right') - 1
        
        self.signals = []
        warmup = 300
        for i in range(warmup, len(self.m5)):
            if i % 500 == 0: log.info(f"   Scanning progress: {i}/{len(self.m5)}")
            
            idx_m15 = m15_indices[i]
            idx_h1 = h1_indices[i]
            
            slice_m5 = self.m5.iloc[max(0, i-500) : i+1]
            slice_m15 = self.m15.iloc[max(0, idx_m15-200) : idx_m15+1]
            slice_h1 = self.h1.iloc[max(0, idx_h1-200) : idx_h1+1]
            
            engine = PatternsEngine(m5_df=slice_m5, m15_df=slice_m15, h1_df=slice_h1)
            sig = engine.detect_patterns()
            if sig:
                self.signals.append({**sig, 'idx': i, 'timestamp': self.m5.iloc[i]['timestamp']})
        
        log.info(f"✅ Found {len(self.signals)} potential signals.")

    def run(self, min_multiplier=0.5, max_multiplier=1.5):
        """Runs a lightning-fast equity simulation using pre-calculated signals."""
        if not self.signals:
            log.warning("No signals to simulate. Did you call precalculate_signals()?")
            return self.calculate_metrics()
            
        equity = self.initial_equity
        active_trade = None
        self.results = []
        self.equity_curve = []
        
        # Risk logic
        config = RiskConfig(min_multiplier=min_multiplier, max_multiplier=max_multiplier)
        risk_engine = RiskEngine(config=config)
        
        current_sig_idx = 0
        
        for i in range(0, len(self.m5)):
            current_bar = self.m5.iloc[i]
            
            # 1. Manage Trade
            if active_trade:
                hit_sl = False
                hit_tp = False
                if active_trade['direction'] == 'LONG':
                    if current_bar['low'] <= active_trade['sl']: hit_sl = True
                    elif current_bar['high'] >= active_trade['tp']: hit_tp = True
                else: 
                    if current_bar['high'] >= active_trade['sl']: hit_sl = True
                    elif current_bar['low'] <= active_trade['tp']: hit_tp = True
                
                if hit_sl or hit_tp:
                    exit_price = active_trade['sl'] if hit_sl else active_trade['tp']
                    pnl_raw = (exit_price - active_trade['entry']) / active_trade['entry']
                    if active_trade['direction'] == 'SHORT': pnl_raw = -pnl_raw
                    pnl_net = (pnl_raw * active_trade['qty_value']) - (active_trade['qty_value'] * self.commission * 2)
                    equity += pnl_net
                    self.results.append({'pnl': pnl_net, 'score': active_trade['score']})
                    active_trade = None

            # 2. Open Trade
            if not active_trade and current_sig_idx < len(self.signals):
                signal = self.signals[current_sig_idx]
                if signal['idx'] == i:
                    multiplier = risk_engine._calculate_multiplier(signal['score'])
                    qty_value = equity * (1.0 / 100.0) * multiplier
                    entry_price = signal['entry'] * (1 + self.spread_pct) if signal['direction'] == 'LONG' else signal['entry'] * (1 - self.spread_pct)
                    
                    active_trade = {
                        'direction': signal['direction'], 'entry': entry_price,
                        'sl': signal['sl'], 'tp': signal['tp1'], 'score': signal['score'],
                        'qty_value': qty_value
                    }
                    current_sig_idx += 1
                elif signal['idx'] < i:
                    current_sig_idx += 1 # Catch up

            self.equity_curve.append({'time': current_bar['timestamp'], 'equity': equity})

        return self.calculate_metrics()

    def calculate_metrics(self):
        if not self.results: return {"sharpe": 0, "profit": 0, "drawdown": 0, "win_rate": 0, "trades": 0}
        df = pd.DataFrame(self.results)
        eq_df = pd.DataFrame(self.equity_curve)
        total_p = eq_df['equity'].iloc[-1] - self.initial_equity
        rets = eq_df['equity'].pct_change().dropna()
        sharpe = (rets.mean() / rets.std() * np.sqrt(252*24*12)) if rets.std() != 0 else 0
        mx = eq_df['equity'].cummax()
        dd = (eq_df['equity'] - mx) / mx
        return {"profit": total_p, "sharpe": sharpe, "max_drawdown": dd.min(), "win_rate": len(df[df['pnl']>0])/len(df), "trades": len(df)}
