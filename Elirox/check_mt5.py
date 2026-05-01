import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

load_dotenv()

def check_mt5():
    if not mt5.initialize(path="C:/Program Files/MetaTrader 5/terminal64.exe"):
        print(f"MT5 Initialize Failed: {mt5.last_error()}")
        return

    account = int(os.getenv("EXNESS_ACCOUNT"))
    password = os.getenv("EXNESS_PASSWORD")
    server = os.getenv("EXNESS_SERVER")

    authorized = mt5.login(account, password=password, server=server)
    if authorized:
        print(f"SUCCESS: Logged in to Exness Account: {account}")
        account_info = mt5.account_info()
        if account_info:
            print(f"Balance: {account_info.balance}")
            print(f"Equity: {account_info.equity}")
            print(f"Broker: {account_info.company}")
    else:
        print(f"FAILED: Failed to login to {account}: {mt5.last_error()}")

    mt5.shutdown()

if __name__ == "__main__":
    check_mt5()
