import os
import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

load_dotenv()

api = tradeapi.REST(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
    api_version="v2"
)

try:
    print("Fetching option contracts for AAPL...")
    contracts = api.get_option_contracts("AAPL", limit=5)
    for contract in contracts:
        print(f"Symbol: {contract.symbol}, Expiry: {contract.expiration_date}, Strike: {contract.strike_price}, Type: {contract.type}")
except Exception as e:
    print(f"Error: {e}")
