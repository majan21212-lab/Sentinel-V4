import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

load_dotenv()

def probe_mt5_price():
    if not mt5.initialize(
        login=int(os.getenv("EXNESS_ACCOUNT")),
        password=os.getenv("EXNESS_PASSWORD"),
        server=os.getenv("EXNESS_SERVER")
    ):
        print(f"Failed to initialize MT5: {mt5.last_error()}")
        return

    symbol = "XAUUSDm"
    # Check if symbol exists
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Symbol {symbol} not found.")
        mt5.shutdown()
        return

    # Fetch last tick
    tick = mt5.symbol_info_tick(symbol)
    print(f"--- MT5 RAW TICK DATA for {symbol} ---")
    print(f"Bid: {tick.bid}")
    print(f"Ask: {tick.ask}")
    print(f"Last: {tick.last}")
    
    # Fetch last candle
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 1)
    if rates is not None and len(rates) > 0:
        print(f"--- MT5 RAW CANDLE DATA for {symbol} ---")
        print(f"Close: {rates[0]['close']}")
    
    mt5.shutdown()

if __name__ == "__main__":
    probe_mt5_price()
