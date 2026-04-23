import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

load_dotenv()

def test_mt5():
    login = int(os.getenv("EXNESS_ACCOUNT"))
    password = os.getenv("EXNESS_PASSWORD")
    server = os.getenv("EXNESS_SERVER")
    
    print(f"Attempting to initialize MT5 with account {login} on server {server}...")
    mt5_path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    if not mt5.initialize(login=login, password=password, server=server, path=mt5_path):
        print(f"MT5 initialization failed: {mt5.last_error()}")
        return
    
    print("MT5 initialized successfully!")
    acc_info = mt5.account_info()
    if acc_info:
        print(f"Account Balance: {acc_info.balance}")
        print(f"Account Equity: {acc_info.equity}")
    else:
        print("Failed to get account info.")
    
    mt5.shutdown()

if __name__ == "__main__":
    test_mt5()
