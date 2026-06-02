import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")
BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

headers = {
    "APCA-API-KEY-ID": API_KEY,
    "APCA-API-SECRET-KEY": SECRET_KEY
}

# Use the V2 Broker API or Trading API for options
# The options contracts endpoint is usually /v2/options/contracts
print(f"Fetching option contracts for AAPL via REST...")
url = f"{BASE_URL}/v2/options/contracts?underlying_symbol=AAPL&limit=5"

try:
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        contracts = data.get("option_contracts", [])
        for contract in contracts:
            print(f"Symbol: {contract['symbol']}, Expiry: {contract['expiration_date']}, Strike: {contract['strike_price']}, Type: {contract['type']}")
    else:
        print(f"Failed: {response.text}")
except Exception as e:
    print(f"Error: {e}")
