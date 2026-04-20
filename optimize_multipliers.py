import os
import asyncio
import pandas as pd
import MetaTrader5 as mt5
import logging
from dotenv import load_dotenv
from core.backtester import SMCBacktester

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("Optimizer")

load_dotenv()

async def fetch_mt5_data(symbol, timeframe, bars=5000):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
    if rates is None:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df['timestamp'] = pd.to_datetime(df['time'], unit='s')
    df['volume'] = df['tick_volume']
    return df

async def optimize():
    if not mt5.initialize(
        login=int(os.getenv("EXNESS_ACCOUNT")),
        password=os.getenv("EXNESS_PASSWORD"),
        server=os.getenv("EXNESS_SERVER")
    ):
        log.error("MT5 Initialization failed")
        return

    symbol = "XAUUSDm"
    log.info(f"💾 Fetching historical data for {symbol} optimization...")
    
    m5_df = await fetch_mt5_data(symbol, mt5.TIMEFRAME_M5, 5000)
    m15_df = await fetch_mt5_data(symbol, mt5.TIMEFRAME_M15, 2000)
    h1_df = await fetch_mt5_data(symbol, mt5.TIMEFRAME_H1, 1000)
    
    mt5.shutdown()

    if m5_df.empty or h1_df.empty:
        log.error("Failed to fetch data for optimization.")
        return

    backtester = SMCBacktester(m5_df, m15_df, h1_df, commission=0.0006, spread_pct=0.0002)
    
    # Pre-detect signals once for the whole dataset
    backtester.precalculate_signals()

    # --- Grid Search ---
    min_options = [0.1, 0.3, 0.5, 0.7, 1.0]
    max_options = [1.0, 1.3, 1.5, 2.0, 2.5]
    
    results = []
    
    log.info(f"📊 Starting Grid Search for {symbol} (Sharpe Ratio Optimization)...")
    
    for min_m in min_options:
        for max_m in max_options:
            log.info(f"   Testing: Min={min_m}x | Max={max_m}x")
            metrics = backtester.run(min_multiplier=min_m, max_multiplier=max_m)
            results.append({
                'min': min_m,
                'max': max_m,
                'sharpe': metrics['sharpe'],
                'profit': metrics['profit'],
                'win_rate': metrics['win_rate'],
                'trades': metrics['trades'],
                'drawdown': metrics['max_drawdown']
            })

    results_df = pd.DataFrame(results)
    best_config = results_df.loc[results_df['sharpe'].idxmax()]
    
    print("\n" + "="*50)
    print(f"💎 OPTIMAL CONFIGURATION FOR {symbol}")
    print("="*50)
    print(f"Optimal Min Multiplier: {best_config['min']}x")
    print(f"Optimal Max Multiplier: {best_config['max']}x")
    print("-" * 30)
    print(f"Resulting Sharpe Ratio: {best_config['sharpe']:.2f}")
    print(f"Estimated Net Profit:   ${best_config['profit']:.2f}")
    print(f"Max Strategy Drawdown:  {best_config['drawdown']*100:.1f}%")
    print(f"Total Trades:           {best_config['trades']}")
    print("="*50)

    # Save summary
    results_df.to_csv("multiplier_optimization_results.csv", index=False)
    log.info("✅ Optimization complete. Results saved to multiplier_optimization_results.csv")

if __name__ == "__main__":
    asyncio.run(optimize())
