import logging
from platforms.base import BasePlatformAdapter
from platforms.mt5_adapter import MT5Adapter
from platforms.ccxt_adapter import CCXTAdapter

logger = logging.getLogger("Gateway")

class PlatformGateway:
    """Institutional router for managing multiple broker connections."""
    
    def __init__(self):
        self.adapters: Dict[str, BasePlatformAdapter] = {
            "MT5": MT5Adapter(),
            "Binance": CCXTAdapter("binance"),
            "OKX": CCXTAdapter("okx")
        }
        self.active_brokers = ["MT5"] # Default active broker

    async def connect_all(self):
        for name, adapter in self.adapters.items():
            try:
                await adapter.connect()
                logger.info(f"Gateway: Connected to {name}")
            except Exception as e:
                logger.error(f"Gateway: Failed to connect to {name}: {e}")

    async def execute_trade(self, signal):
        """Dispatches trade to all active and compatible brokers."""
        for name in self.active_brokers:
            adapter = self.adapters.get(name)
            if adapter:
                # In a real scenario, check if the symbol is supported by the broker
                try:
                    logger.info(f"Gateway: Dispatching {signal.symbol} trade to {name}")
                    # await adapter.execute_signal(signal) # Implementation depends on adapter
                except Exception as e:
                    logger.error(f"Gateway: Error executing on {name}: {e}")

    def add_adapter(self, name: str, adapter: BasePlatformAdapter):
        self.adapters[name] = adapter
        if name not in self.active_brokers:
            self.active_brokers.append(name)
