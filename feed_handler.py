import asyncio
import logging
import pandas as pd
import ccxt.pro as ccxt

log = logging.getLogger(__name__)

class FeedHandler:
    def __init__(self, callback, timeframe='5m', limit=500):
        """
        Initializes the async data feed handler.
        :param callback: async function to call with (symbol, df)
        :param timeframe: target timeframe ('5m' default)
        :param limit: number of historical candles to maintain
        """
        self.callback = callback
        self.timeframe = timeframe
        self.limit = limit
        # Use Binance via CCXT Pro (WebSockets)
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future', # or spot depending on symbols, assume future for generic
            }
        })
        self.running = False

    async def start(self, symbols: list):
        self.running = True
        log.info(f"💎 Starting WebSockets for {symbols} on {self.timeframe} timeframe")
        # Ensure we have the markets loaded
        while self.running:
            try:
                await self.exchange.load_markets()
                break
            except Exception as e:
                log.warning(f"⚠️ feed_handler fails to load markets (transient network issue?): {e}. Retrying in 5s...")
                await asyncio.sleep(5)
                
        if not self.running:
            return
            
        # We start a concurrent task for each symbol
        tasks = [asyncio.create_task(self.watch_symbol(sym)) for sym in symbols]
        await asyncio.gather(*tasks)

    async def watch_symbol(self, symbol: str):
        while self.running:
            try:
                # CCXT watch_ohlcv returns the latest OHLCV via socket
                ohlcv = await self.exchange.watch_ohlcv(symbol, self.timeframe)
                
                # To maintain a full dataframe of `self.limit` length, 
                # we should fetch initial history if we don't have it, but ccxt watch_ohlcv 
                # actually caches and builds up the limit internally if configured, 
                # or we just fetch full history once and append.
                # Actually, standard CCXT Pro watch_ohlcv handles local cache and returns 
                # up to `limit` candles from its local deque.
                # To be safe and ensure we always have 500 candles for indicators,
                # let's fetch historical once, then watch_ohlcv handles the rest.
                
                # Fetch recent if local cache in ccxt isn't full
                if len(ohlcv) < self.limit:
                     ohlcv = await self.exchange.fetch_ohlcv(symbol, self.timeframe, limit=self.limit)
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                
                # Call strategy callback asynchronously so it doesn't block the socket loop long
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback(symbol, df)
                else:
                    # Run sync callback in an executor to avoid blocking the event loop with Pandas operations
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.callback, symbol, df)
                
            except Exception as e:
                log.error(f"❌ Feed error watching {symbol}: {e}")
                await asyncio.sleep(5)  # Backoff on error
                
    async def close(self):
        self.running = False
        await self.exchange.close()
