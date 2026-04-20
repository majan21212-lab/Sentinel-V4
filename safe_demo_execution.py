import os
import time
import logging
from dotenv import load_dotenv

# Load credentials securely
load_dotenv()

# --- 1. CONFIGURATION ---
TRADING_ENV = os.getenv("TRADING_ENV", "SIMULATION") # SIMULATION or SANDBOX
DEMO_API_KEY = os.getenv("DEMO_API_KEY")
DEMO_SECRET = os.getenv("DEMO_SECRET")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class MockBroker:
    """
    Simulates order execution without API calls.
    """
    def __init__(self):
        logging.info("Initialized MOCK BROKER for Dry Run.")

    def place_order(self, symbol, side, qty, price, sl, tp):
        # Add simulated slippage (e.g., 0.1%)
        fill_price = price * 1.0001 if side == 'buy' else price * 0.9999
        logging.info(f"[MOCK] Order Placed: {side} {qty} {symbol} @ {fill_price}")
        return {"order_id": f"MOCK_{int(time.time())}", "status": "FILLED", "fill_price": fill_price}

class DemoBroker:
    """
    Connects to actual Demo/Sandbox API (e.g., Exness/CCXT).
    """
    def __init__(self, key, secret):
        self.key = key
        self.secret = secret
        # self.exchange = ccxt.exness({'apiKey': key, 'secret': secret, 'test': True})
        logging.info("Connected to SANCTIONED DEMO API.")

    def place_order(self, symbol, side, qty, price, sl, tp):
        logging.info(f"[DEMO API] Executing real Demo Trade: {side} {qty} {symbol}")
        # Placeholder for real API call:
        # return self.exchange.create_order(symbol, 'limit', side, qty, price, {'stopLoss': sl, 'takeProfit': tp})
        return {"order_id": "DEMO_12345", "status": "PENDING"}

# --- 2. EXECUTION LOGIC ---
def process_signal(signal):
    """
    Main entry point for processing a strategy signal safely.
    """
    print("\n" + "="*40)
    print(f"NEW SIGNAL: {signal['type']} {signal['symbol']} at {signal['entry']}")
    
    # SAFETY CHECK
    if TRADING_ENV not in ['SIMULATION', 'SANDBOX']:
         logging.error("SECURITY ALERT: LIVE ENVIRONMENT DETECTED! ABORTING.")
         return

    # Choose Broker Interface
    broker = MockBroker() if TRADING_ENV == "SIMULATION" else DemoBroker(DEMO_API_KEY, DEMO_SECRET)

    # Risk Management Calculation
    qty = calculate_position_size(signal['entry'], signal['stop_loss'])
    
    # Execute Order
    order_result = broker.place_order(
        symbol=signal['symbol'],
        side=signal['type'].lower(),
        qty=qty,
        price=signal['entry'],
        sl=signal['stop_loss'],
        tp=signal['take_profit']
    )
    
    return order_result

def calculate_position_size(entry, sl):
    # Logic to risk 1% of equity per trade
    return 0.01

# --- 3. TEST RUN ---
if __name__ == "__main__":
    # Simulated Signal from Strategy
    sample_signal = {
        'type': 'LONG',
        'symbol': 'BTC/USDT',
        'entry': 65000.0,
        'stop_loss': 64500.0,
        'take_profit': 66500.0
    }
    
    result = process_signal(sample_signal)
    print(f"Final Result: {result}")
