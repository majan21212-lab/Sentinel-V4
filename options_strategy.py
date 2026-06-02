import logging
from typing import Optional
from models import Signal, OptionSignal, OptionType, Direction
from execution_layer import AlpacaAdapter

log = logging.getLogger(__name__)

class OptionsOrchestrator:
    def __init__(self, adapter: AlpacaAdapter):
        self.adapter = adapter

    def convert_to_option_signal(self, signal: Signal) -> Optional[OptionSignal]:
        """
        Translates a standard spot/forex signal into an Alpaca Option signal.
        """
        try:
            underlying = self.adapter._map_symbol(signal.symbol)
            # Fetch active contracts
            contracts = self.adapter.fetch_option_contracts(underlying, limit=50)
            if not contracts:
                log.warning("No option contracts found for %s", underlying)
                return None

            # Filter by direction
            target_type = "call" if signal.direction == Direction.LONG else "put"
            
            # Simple Selection Logic:
            # 1. Matches type (Call/Put)
            # 2. Closest strike to entry price (ATM)
            # 3. Soonest expiry but at least 3 days away
            
            valid_contracts = [c for c in contracts if c['type'] == target_type]
            if not valid_contracts:
                return None

            # Sort by strike distance and expiry
            # We want strike near signal.entry
            valid_contracts.sort(key=lambda x: (abs(float(x['strike_price']) - signal.entry), x['expiration_date']))

            best_contract = valid_contracts[0]
            
            log.info("💎 Best Option for %s: %s (Strike: %s, Expiry: %s)", 
                     underlying, best_contract['symbol'], best_contract['strike_price'], best_contract['expiration_date'])

            return OptionSignal(
                symbol=signal.symbol,
                direction=signal.direction,
                entry=signal.entry,
                stop_loss=signal.sl,
                take_profit=signal.tp1,
                qty=1, # 1 contract = 100 shares usually
                contract_symbol=best_contract['symbol'],
                strike=float(best_contract['strike_price']),
                expiry=best_contract['expiration_date'],
                option_type=OptionType.CALL if target_type == "call" else OptionType.PUT,
                pattern=f"OPT_{signal.pattern}",
                reason=f"Option hedge/play for {signal.symbol}"
            )
        except Exception as e:
            log.error("Error converting to option signal: %s", e)
            return None
