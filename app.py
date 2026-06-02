from db_utils import setup_database
from strategy import run_strategy
import schedule
import time

def main():
    print("Starting TradeBot...")
    
    # Initialize Database
    print("Initializing Database...")
    setup_database()
    
    # Schedule the strategy to run periodically (e.g., every 1 hour)
    # For testing purposes or depending on requirements, this can be adjusted.
    # The user asked for "Exness Ichimoku Pro", which often runs on 4H or 1D, but logic handles any timeframe.
    # Let's default to running the check every 5 minutes to catch 1H candle closes or similar.
    # CAUTION: CCXT fetch_ohlcv with '1h' will get the latest closed bars.
    
    schedule.every(5).minutes.do(run_strategy, symbol='BTC/USDT')
    print("Strategy scheduled to run every 5 minutes for BTC/USDT.")
    
    # Run once immediately on startup
    run_strategy('BTC/USDT')

    print("TradeBot is running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
