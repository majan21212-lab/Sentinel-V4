import os
import asyncio
import MetaTrader5 as mt5
import logging
import pandas as pd
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

            if not mt5.initialize(login=login_int, password=password, server=server):
                logger.error(f"MT5 Initialisation Failed with credentials: {mt5.last_error()}")
                return False
        else:
            if not mt5.initialize():
                logger.error(f"MT5 Initialisation Failed (no credentials): {mt5.last_error()}")
                return False
        
        self.connected = True
        logger.info("MT5 Adapter Connected.")
        return True

    async def get_balance(self) -> Dict[str, float]:
        if not self.connected: await self.connect()
        acc = mt5.account_info()
        if acc:
            return {"equity": acc.equity, "balance": acc.balance}
        return {"equity": 0.0, "balance": 0.0}

    async def get_open_positions_count(self) -> int:
        if not self.connected: await self.connect()
        positions = mt5.positions_get()
        return len(positions) if positions else 0

    async def place_order(self, signal: Signal) -> Dict[str, Any]:
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
        mt5.shutdown()
        self.connected = False
        logger.info("MT5 Adapter Disconnected.")

    def get_balance(self):
        """Alias for get_account_info to match ExecutionLayer interface."""
        return self.get_account_info()

    def get_account_info(self):
        """Fetches account balance and equity for risk management."""
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
        positions = mt5.positions_get()
        if not positions: return []
        return list(set([p.symbol for p in positions]))

    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int) -> pd.DataFrame:
        """Fetches historical data synchronously (intended for use with to_thread)."""
        if not self.connected:
            # Synchronous initialize
            if not mt5.initialize():
                logger.error("MT5 initialization failed inside fetch_historical_data")
                return pd.DataFrame()
            self.connected = True
            
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        
        if rates is None or len(rates) == 0:
            logger.warning(f"No data returned for {symbol}")
            return pd.DataFrame()
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        # Map tick_volume to volume for strategy consistency
        df['volume'] = df['tick_volume']
        return df
