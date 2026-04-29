import ccxt.async_support as ccxt
import logging
import os
from typing import Dict, Any
from platforms.base import BasePlatformAdapter
from core.signals import Signal
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("CCXT_Adapter")

class CCXTAdapter(BasePlatformAdapter):
    """Universal Crypto Adapter using CCXT (supports Binance, OKX, etc.)."""

    def __init__(self, exchange_id: str = "binance"):
        self.exchange_id = exchange_id
        self.exchange = None
        self.connected = False
        
        # Load credentials from .env or config
        self.api_key = os.getenv(f"{exchange_id.upper()}_API_KEY")
        self.secret = os.getenv(f"{exchange_id.upper()}_SECRET")
        self.password = os.getenv(f"{exchange_id.upper()}_PASSWORD") # Some exchanges like OKX need this

    async def connect(self) -> bool:
        try:
            if not self.api_key or not self.secret:
                logger.warning(f"{self.exchange_id} API keys not found in .env. Running in read-only/public mode.")
            
            exchange_class = getattr(ccxt, self.exchange_id)
            self.exchange = exchange_class({
                'apiKey': self.api_key,
                'secret': self.secret,
                'password': self.password,
                'enableRateLimit': True,
                'options': {'defaultType': 'spot'} # Can be 'future', 'margin', etc.
            })
            
            if self.api_key:
                await self.exchange.load_markets()
                logger.info(f"Connected to {self.exchange_id} (Authenticated)")
            else:
                logger.info(f"Connected to {self.exchange_id} (Public Only)")
                
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.exchange_id}: {e}")
            return False

    async def get_balance(self) -> Dict[str, float]:
        if not self.connected or not self.api_key: return {"USDT": 0.0}
        try:
            balance = await self.exchange.fetch_balance()
            return {curr: info['total'] for curr, info in balance['total'].items() if info['total'] > 0}
        except Exception as e:
            logger.error(f"Error fetching balance from {self.exchange_id}: {e}")
            return {}

    async def place_order(self, signal: Signal) -> Dict[str, Any]:
        if not self.connected or not self.api_key:
            return {"status": "error", "message": "Exchange not connected or read-only"}
            
        try:
            symbol = signal.symbol.replace("m", "") # Handle symbol mapping if needed
            # Common mapping: BTCUSDm -> BTC/USDT
            if "BTC" in symbol: symbol = "BTC/USDT"
            if "XAU" in symbol: symbol = "XAU/USDT" # Binance has PAXG/USDT for Gold

            side = "buy" if signal.direction == "LONG" else "sell"
            amount = float(signal.quantity)
            
            logger.info(f"Placing {side} order for {symbol} on {self.exchange_id}...")
            order = await self.exchange.create_order(symbol, 'market', side, amount)
            
            return {
                "status": "success",
                "order_id": order['id'],
                "price": order['price'],
                "amount": order['amount']
            }
        except Exception as e:
            logger.error(f"Order failed on {self.exchange_id}: {e}")
            return {"status": "error", "message": str(e)}

    async def get_open_positions_count(self) -> int:
        if not self.connected or not self.api_key: return 0
        try:
            # For spot, "positions" are just assets. For futures:
            if self.exchange.has['fetchPositions']:
                positions = await self.exchange.fetch_positions()
                return len([p for p in positions if float(p['contracts']) > 0])
            return 0
        except Exception as e:
            logger.error(f"Error fetching positions from {self.exchange_id}: {e}")
            return 0

    async def disconnect(self):
        if self.exchange:
            await self.exchange.close()
            self.connected = False
            logger.info(f"Disconnected from {self.exchange_id}")
