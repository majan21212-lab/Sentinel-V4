import os
import time
import logging
import asyncio
import sys
from datetime import datetime
from dotenv import load_dotenv

# Ensure the script can find its dependencies when running from MT5 folder
sys.path.append("f:/TradeBot")

# Project Imports
from patterns_engine import PatternsEngine
from strategy import calculate_indicators, check_signals
from execution_layer import ExecutionLayer
from models import Signal
import MetaTrader5 as mt5

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("master_bot_mt5.log", encoding="utf-8")
    ]
)
log = logging.getLogger("JewelMaster")

load_dotenv()

class JewelEliteMasterBot:
    def __init__(self, symbols=["XAUUSD"], mode="HYBRID"):
        self.symbols = symbols
        self.mode = mode.upper() # JEWEL_ELITE, GOD_MODE, or HYBRID
        self.executor = ExecutionLayer()
        self.is_active = True
        
        # Thresholds
        self.min_god_mode_score = 6
        self.min_smc_score = 60
        
    async def run(self):
        log.info("==========================================")
        log.info(f"💎 MASTER BOT - MT5 ({self.mode} MODE)")
        log.info("==========================================")
        
        mt5_adapter = self.executor.adapters.get("mt5")
        if not mt5_adapter:
            log.error("❌ MT5 Adapter not found! Check .env")
            return

        log.info(f"Monitoring: {self.symbols}")
        
        while self.is_active:
            for symbol in self.symbols:
                try:
                    await self.process_symbol(symbol, mt5_adapter)
                except Exception as e:
                    log.error(f"Error processing {symbol}: {e}")
            await asyncio.sleep(60)

    async def process_symbol(self, symbol, adapter):
        # 1. Fetch Data
        h1_df = await asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_H1, 300)
        m15_df = await asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_M15, 300)
        m5_df = await asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_M5, 300)
        
        if m5_df.empty or m15_df.empty or h1_df.empty:
            return

        smc_signal = None
        god_mode_signal = None
        
        # 2. Logic Selection
        if self.mode in ["JEWEL_ELITE", "HYBRID"]:
            engine = PatternsEngine(m5_df=m5_df, m15_df=m15_df, h1_df=h1_df)
            smc_signal = engine.detect_patterns()

        if self.mode in ["GOD_MODE", "HYBRID"]:
            m5_with_inds = calculate_indicators(m5_df, symbol)
            god_mode_signal = check_signals(m5_with_inds, symbol, req_score=self.min_god_mode_score)

        # 3. Decision Logic
        final_signal = None
        
        if self.mode == "HYBRID":
            if smc_signal and god_mode_signal and smc_signal['direction'] == god_mode_signal['type']:
                final_signal = Signal(
                    symbol=symbol,
                    direction=smc_signal['direction'],
                    entry=float(smc_signal['entry']),
                    stop_loss=float(smc_signal['sl']),
                    take_profit=float(smc_signal['tp1']),
                    tp2=float(smc_signal['tp2']),
                    score=float(smc_signal['score']),
                    pattern=smc_signal['pattern'],
                    reason=f"Hybrid Sync: {smc_signal['pattern']} + GodMode"
                )
        
        elif self.mode == "JEWEL_ELITE" and smc_signal:
            final_signal = Signal(
                symbol=symbol,
                direction=smc_signal['direction'],
                entry=float(smc_signal['entry']),
                stop_loss=float(smc_signal['sl']),
                take_profit=float(smc_signal['tp1']),
                tp2=float(smc_signal['tp2']),
                score=float(smc_signal['score']),
                pattern=smc_signal['pattern'],
                reason=f"SMC Pattern: {smc_signal['pattern']}"
            )
            
        elif self.mode == "GOD_MODE" and god_mode_signal:
            final_signal = Signal(
                symbol=symbol,
                direction=god_mode_signal['type'],
                entry=float(god_mode_signal['entry']),
                stop_loss=float(god_mode_signal['stop_loss']),
                take_profit=float(god_mode_signal['take_profit']),
                score=float(god_mode_signal['score']),
                pattern="GodMode",
                reason=f"God-Mode Confluence ({god_mode_signal['score']}/10)"
            )

        # 4. Execution
        if final_signal:
            log.info(f"🔥 Signal found in {self.mode} mode for {symbol} ({final_signal.direction})")
            res = self.executor.place_trade(final_signal, platform="mt5")
            if res.get("status") == "success":
                log.info(f"✅ Trade Executed on {symbol}")

if __name__ == "__main__":
    import sys
    # Settings from .env
    env_symbols = os.getenv("TRADING_SYMBOLS", "XAUUSDm").split(",")
    symbols = [s.strip() for s in env_symbols if s.strip()]
    
    # Selection of Strategy Mode (CLI argument takes precedence over .env)
    mode = os.getenv("STRATEGY_MODE", "HYBRID")
    if len(sys.argv) > 1:
        mode = sys.argv[1].upper()
    
    if mode not in ["JEWEL_ELITE", "GOD_MODE", "HYBRID"]:
        print(f"Invalid mode: {mode}. Use JEWEL_ELITE, GOD_MODE, or HYBRID.")
        sys.exit(1)
        
    bot = JewelEliteMasterBot(symbols=symbols, mode=mode)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        log.info("Bot stopped.")
    finally:
        mt5.shutdown()
