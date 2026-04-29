import MetaTrader5 as mt5
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def run_diagnostic():
    print("--- MT5 Connection Diagnostic ---")
    
    # 1. Basic Init
    if not mt5.initialize():
        print(f"FAILED: mt5.initialize() failed: {mt5.last_error()}")
        return
    
    print("SUCCESS: MT5 Library Initialized.")
    
    # 2. Get Terminal Info
    terminal_info = mt5.terminal_info()
    if terminal_info:
        print(f"Terminal Path: {terminal_info.path}")
        print(f"Terminal Name: {terminal_info.name}")
        print(f"Terminal Connected: {terminal_info.connected}")
    else:
        print("WARNING: Could not get terminal_info()")

    # 3. Try Login
    account = int(os.getenv("EXNESS_ACCOUNT", 0))
    password = os.getenv("EXNESS_PASSWORD", "")
    server = os.getenv("EXNESS_SERVER", "")
    
    print(f"\nAttempting login to Account: {account} on Server: {server}...")
    
    authorized = mt5.login(account, password=password, server=server)
    if authorized:
        print(f"SUCCESS: Logged in to {account}")
        
        # 4. Check Account Details
        acc_info = mt5.account_info()
        if acc_info:
            print(f"   Name: {acc_info.name}")
            print(f"   Balance: {acc_info.balance}")
            print(f"   Equity: {acc_info.equity}")
            print(f"   Currency: {acc_info.currency}")
            print(f"   Broker: {acc_info.company}")
            print(f"   Server: {acc_info.server}")
        else:
            print("   ERROR: Could not get account_info after login.")
    else:
        print(f"FAILED: Login failed for {account}. Error: {mt5.last_error()}")

    mt5.shutdown()
    print("\n--- Diagnostic Complete ---")

if __name__ == "__main__":
    run_diagnostic()
