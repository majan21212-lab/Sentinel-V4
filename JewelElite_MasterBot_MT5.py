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
from execution_layer import ExecutionLayer
from models import Signal, Direction
from strategy import calculate_indicators, check_signals, calculate_grid_params
import MetaTrader5 as mt5
from market_hours import market_hours
from state_manager import update_shared_data

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
    def __init__(self, bot_id="DEBUG", symbols=["XAUUSD"], mode="HYBRID"):
        self.bot_id = bot_id
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
        
        target = os.getenv("DEFAULT_BROKER", "mt5").lower()
        if target == "bridge":
            # For Bridge mode, use the first available adapter to fetch data
            adapter = next(iter(self.executor.adapters.values()), None)
        else:
            adapter = self.executor.adapters.get(target)
        
        if not adapter:
            log.error(f"❌ Adapter for {target} not found or no active adapters! Check .env credentials.")
            return

        log.info(f"Target Broker: {target.upper()}")
        log.info(f"Monitoring: {self.symbols}")
        
        while self.is_active:
            # Refresh Config from Shared State
            try:
                from state_manager import load_shared_state
                state = load_shared_state()
                self.mode = state.get("strategy_mode", self.mode).upper()
                
                # Update symbols from state if they changed
                market_configs = state.get("market_configs", {})
                active_symbols = [s for s, c in market_configs.items() if c.get("enabled")]
                if active_symbols:
                    self.symbols = active_symbols
            except: pass

            for symbol in self.symbols:
                try:
                    await self.process_symbol(symbol, adapter)
                except Exception as e:
                    log.error(f"Error processing {symbol}: {e}")
            await asyncio.sleep(60)

    async def process_symbol(self, symbol, adapter):
        # 0. Check Market Hours
        if not market_hours.is_market_open(symbol):
            log.info(f"⏳ Market for {symbol} is currently CLOSED. Skipping analysis.")
            update_shared_data("broker_status", "MARKET CLOSED")
            return

        # 1. Fetch Data
        h1_df = await asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_H1, 300)
        m15_df = await asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_M15, 300)
        m5_df = await asyncio.to_thread(adapter.fetch_historical_data, symbol, mt5.TIMEFRAME_M5, 300)
        
        if len(m5_df) < 100 or len(m15_df) < 100 or len(h1_df) < 100:
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
                    reason=f"Hybrid Sync: {smc_signal['pattern']} + GodMode",
                    bot_id=self.bot_id
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
                reason=f"SMC Pattern: {smc_signal['pattern']}",
                bot_id=self.bot_id
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
                reason=f"God-Mode Confluence ({god_mode_signal['score']}/10)",
                bot_id=self.bot_id
            )

        elif self.mode == "GRID":
            # Grid doesn't use standard signals, it places limit orders
            grid_params = calculate_grid_params(m5_df, symbol)
            if grid_params:
                log.info(f"🕸️ GRID DEPLOYMENT: {symbol} | Step: {grid_params['step']:.2f}")
                # For Grid, we place the first buy/sell limit orders
                # Buy Limit
                buy_sig = Signal(
                    symbol=symbol,
                    direction=Direction.LONG,
                    entry=grid_params['buy_levels'][0],
                    stop_loss=grid_params['buy_levels'][0] * 0.98,
                    take_profit=grid_params['buy_levels'][0] + (grid_params['step'] * 0.8),
                    pattern="GRID_LEVEL",
                    bot_id=self.bot_id
                )
                self.executor.place_trade(buy_sig, platform=target)
                
                # Sell Limit
                sell_sig = Signal(
                    symbol=symbol,
                    direction=Direction.SHORT,
                    entry=grid_params['sell_levels'][0],
                    stop_loss=grid_params['sell_levels'][0] * 1.02,
                    take_profit=grid_params['sell_levels'][0] - (grid_params['step'] * 0.8),
                    pattern="GRID_LEVEL",
                    bot_id=self.bot_id
                )
                self.executor.place_trade(sell_sig, platform=target)
            return

        # 4. Execution
        if final_signal:
            log.info(f"🔥 Signal found in {self.mode} mode for {symbol} ({final_signal.direction})")
            
            # Use DEFAULT_BROKER instead of hardcoded 'mt5' or 'alpaca'
            broker = os.getenv("DEFAULT_BROKER", "alpaca").lower()
            res = self.executor.place_trade(final_signal, platform=broker)
            
            # --- Alpaca Options Integration ---
            if os.getenv("OPTIONS_TRADING_ENABLED", "false").lower() == "true":
                try:
                    from options_strategy import OptionsOrchestrator
                    from execution_layer import AlpacaAdapter
                    
                    alpaca_adapter = self.executor.adapters.get("alpaca")
                    if isinstance(alpaca_adapter, AlpacaAdapter):
                        orchestrator = OptionsOrchestrator(alpaca_adapter)
                        opt_signal = orchestrator.convert_to_option_signal(final_signal)
                        if opt_signal:
                            log.info(f"💎 Attempting Options Trade for {symbol}...")
                            opt_res = self.executor.place_trade(opt_signal, platform="alpaca")
                            if opt_res.get("status") == "success":
                                log.info(f"✅ Options Trade Executed: {opt_signal.contract_symbol}")
                except Exception as e:
                    log.error(f"Error in Options Integration: {e}")

            if res.get("status") == "success":
                log.info(f"✅ Standard Trade Executed on {symbol}")

if __name__ == "__main__":
    import sys
    # Settings from .env
    env_symbols = os.getenv("TRADING_SYMBOLS", "XAUUSDm").split(",")
    symbols = [s.strip() for s in env_symbols if s.strip()]
    
    # Selection of Strategy Mode (CLI argument takes precedence over .env)
    mode = os.getenv("STRATEGY_MODE", "HYBRID").upper()
    bot_id = "DEBUG"
    
    for i, arg in enumerate(sys.argv):
        if arg == "--id" and i + 1 < len(sys.argv):
            bot_id = sys.argv[i+1].upper()
        if arg in ["JEWEL_ELITE", "GOD_MODE", "HYBRID"]:
            mode = arg

    bot = JewelEliteMasterBot(bot_id=bot_id, symbols=symbols, mode=mode)
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        log.info("Bot stopped.")
    finally:
        mt5.shutdown()
