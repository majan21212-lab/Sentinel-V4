import os
import ccxt
from dotenv import load_dotenv

load_dotenv()

def test_binance():
    api_key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_SECRET")
    password = os.getenv("BINANCE_PASSWORD")
    
    exchange = ccxt.binance({
        "apiKey":          api_key,
        "secret":          secret,
        "password":        password,
        "enableRateLimit": True,
        "options":         {"defaultType": "future"},
    })
    
    try:
        balance = exchange.fetch_balance()
        print("--- BINANCE BALANCE DATA ---")
        print(f"Total USDT: {balance.get('total', {}).get('USDT')}")
        print(f"Free USDT: {balance.get('free', {}).get('USDT')}")
        # print full keys in total to see what we have
        print(f"Available Assets: {list(balance.get('total', {}).keys())[:10]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_binance()
