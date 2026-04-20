from abc import ABC, abstractmethod
from typing import Dict, Any
from core.signals import Signal

class BasePlatformAdapter(ABC):
    """Abstract base class for all exchange/broker adapters."""

    @abstractmethod
    async def connect(self) -> bool:
        """Initialises connection to the platform."""
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        """Returns account balance/equity."""
        pass

    @abstractmethod
    async def place_order(self, signal: Signal) -> Dict[str, Any]:
        """Executes a trade on the platform."""
        pass

    @abstractmethod
    async def get_open_positions_count(self) -> int:
        """Returns the number of currently open trades."""
        pass

    @abstractmethod
    async def disconnect(self):
        """Cleanly closes connections."""
        pass
stone_adapter = BasePlatformAdapter # Alias for transition
