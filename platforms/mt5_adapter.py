import os
import asyncio
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except (ImportError, OSError):
    mt5 = None
    MT5_AVAILABLE = False

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from typing import Dict, Any
from .base import BasePlatformAdapter
from core.signals import Signal

logger = logging.getLogger(__name__)

class MT5Adapter(BasePlatformAdapter):
    def __init__(self):
        self.magic = int(os.getenv("MT5_MAGIC", "20260415"))
        self.connected = False

    async def connect(self) -> bool:
        """Initialises MT5 connection."""
        if not MT5_AVAILABLE:
            logger.warning("MT5 library not available on this platform.")
            return False
        
        login = os.getenv("MT5_LOGIN") or os.getenv("EXNESS_ACCOUNT")
        password = os.getenv("MT5_PASSWORD") or os.getenv("EXNESS_PASSWORD")
        server = os.getenv("MT5_SERVER") or os.getenv("EXNESS_SERVER")
        
        # If credentials provided, use them. Otherwise, initialize without args.
        if login and password and server:
            try:
                login_int = int(login)
            except ValueError:
                logger.error(f"MT5 Initialisation Failed: Account Login ({login}) must be an integer, not a string/username!")
                return False

            if not mt5.initialize(login=login_int, password=password, server=server, path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
                logger.error(f"MT5 Initialisation Failed with credentials: {mt5.last_error()}")
                return False
        else:
            if not mt5.initialize(path=r"C:\Program Files\MetaTrader 5\terminal64.exe"):
                logger.error(f"MT5 Initialisation Failed (no credentials): {mt5.last_error()}")
                return False
        
        self.connected = True
        logger.info("MT5 Adapter Connected.")
        return True

    async def get_balance(self) -> Dict[str, float]:
        if not MT5_AVAILABLE: return {"equity": 0.0, "balance": 0.0}
        if not self.connected: await self.connect()
        acc = mt5.account_info()
        if acc:
            return {"equity": acc.equity, "balance": acc.balance}
        return {"equity": 0.0, "balance": 0.0}

    async def get_open_positions_count(self) -> int:
        if not MT5_AVAILABLE: return 0
        if not self.connected: await self.connect()
        positions = mt5.positions_get()
        return len(positions) if positions else 0

    async def place_order(self, signal: Signal) -> Dict[str, Any]:
        if not MT5_AVAILABLE: return {"status": "error", "message": "MT5 not available"}
        if not self.connected: await self.connect()
        
        symbol = signal.symbol
        is_long = signal.direction == "LONG"
        order_type = mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL
        
        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            return {"status": "error", "message": f"Symbol {symbol} not found"}

        price = tick.ask if is_long else tick.bid
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(signal.quantity),
            "type": order_type,
            "price": price,
            "sl": float(signal.stop_loss),
            "tp": float(signal.take_profit_1),
            "deviation": 20,
            "magic": self.magic,
            "comment": "Sentinel V4",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Run order_send in a thread to keep asyncio loop alive if it blocks
        result = await asyncio.to_thread(mt5.order_send, request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"MT5 Order Failed: {result.comment}")
            return {"status": "error", "message": result.comment}
        
        logger.info(f"MT5 Order Placed: {result.order}")
        return {"status": "success", "ticket": result.order}

    async def disconnect(self):
        if MT5_AVAILABLE:
            mt5.shutdown()
        self.connected = False
        logger.info("MT5 Adapter Disconnected.")

    def get_balance(self):
        """Alias for get_account_info to match ExecutionLayer interface."""
        return self.get_account_info()

    def get_account_info(self):
        """Fetches account balance and equity for risk management."""
        if not MT5_AVAILABLE: return {"balance": 0.0, "equity": 0.0}
        acc_info = mt5.account_info()
        if acc_info is None:
            logger.error("Failed to fetch MT5 account info")
            return {"balance": 0.0, "equity": 0.0}
        return {
            "balance": acc_info.balance,
            "equity": acc_info.equity,
            "currency": acc_info.currency,
            "leverage": acc_info.leverage
        }

    def close_all_positions(self):
        """Emergency panic button to close all trades."""
        if not MT5_AVAILABLE: return {"status": "error", "message": "MT5 not available"}
        positions = mt5.positions_get()
        if not positions:
            return {"status": "success", "closed": 0}
        
        count = 0
        for pos in positions:
            # Simple close logic for MT5
            tick = mt5.symbol_info_tick(pos.symbol)
            type_close = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price_close = tick.bid if type_close == mt5.ORDER_TYPE_SELL else tick.ask
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "position": pos.ticket,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": type_close,
                "price": price_close,
                "deviation": 20,
                "magic": pos.magic,
                "comment": "Dashboard Panic Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            res = mt5.order_send(request)
            if res.retcode == mt5.TRADE_RETCODE_DONE:
                count += 1
                
        return {"status": "success", "closed": count}

    def get_active_symbols(self):
        if not MT5_AVAILABLE: return []
        positions = mt5.positions_get()
        if not positions: return []
        return list(set([p.symbol for p in positions]))

    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int) -> pd.DataFrame:
        """Fetches historical data. Returns SIMULATED data if MT5 is not available."""
        if not MT5_AVAILABLE or not self.connected:
            logger.info(f"MT5: Generating SIMULATED data for {symbol} ({lookback} bars)")

            # Generate realistic-ish price action
            np.random.seed(int(datetime.now().timestamp()) % 1000)
            base_price = 2350.0 if "XAU" in symbol else 65000.0
            
            # Simple random walk for simulation
            prices = [base_price]
            for _ in range(lookback - 1):
                prices.append(prices[-1] * (1 + np.random.normal(0, 0.0005)))
            
            df = pd.DataFrame({
                'time': [datetime.now() - timedelta(minutes=15*i) for i in range(lookback)][::-1],
                'open': prices,
                'high': [p * 1.002 for p in prices],
                'low': [p * 0.998 for p in prices],
                'close': [p * (1 + np.random.normal(0, 0.0002)) for p in prices],
                'tick_volume': [np.random.randint(100, 1000) for _ in range(lookback)]
            })
            df['volume'] = df['tick_volume']
            df.set_index('time', inplace=True)
            return df
            
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        
        if rates is None or len(rates) == 0:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df['volume'] = df['tick_volume']
        df.set_index('time', inplace=True)
        return df
