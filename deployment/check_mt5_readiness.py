import MetaTrader5 as mt5
import os
import sys

def check_readiness():
    print("🔍 SENTINEL-V4 MT5 READINESS DIAGNOSTIC")
    print("-" * 40)

    # 1. Initialize
    if not mt5.initialize():
        print("❌ FAILED: Could not initialize MetaTrader 5.")
        print("   Fix: Ensure MT5 is OPEN on your VPS before running this.")
        return

    # 2. Account Check
    acc = mt5.account_info()
    if acc:
        print(f"✅ CONNECTED: Account {acc.login} ({acc.company})")
        print(f"💰 BALANCE: ${acc.balance:,.2f} | EQUITY: ${acc.equity:,.2f}")
    else:
        print("❌ FAILED: Could not fetch account info.")
        return

    # 3. Algo Trading Check
    if not acc.trade_allowed:
        print("❌ FAILED: Algorithmic Trading is DISABLED.")
        print("   Fix: Click the 'Algo Trading' button in the MT5 top toolbar (must be GREEN).")
    else:
        print("✅ ALGO TRADING: Enabled.")

    # 4. Expert Advisor Check
    if not acc.trade_expert:
        print("❌ FAILED: Expert Advisor Trading is DISABLED.")
        print("   Fix: Tools > Options > Expert Advisors > 'Allow Algorithmic Trading' must be CHECKED.")
    else:
        print("✅ EA TRADING: Enabled.")

    # 5. Symbol Visibility Check
    symbols_to_check = ["XAUUSDm", "BTCUSDm", "EURUSDm"]
    for sym in symbols_to_check:
        info = mt5.symbol_info(sym)
        if info:
            if info.visible:
                print(f"✅ SYMBOL: {sym} is visible and ready.")
            else:
                print(f"⚠️  SYMBOL: {sym} exists but is HIDDEN. (Right-click MarketWatch > Show All)")
        else:
            print(f"❌ SYMBOL: {sym} NOT FOUND. Check your broker's naming convention.")

    print("-" * 40)
    if acc.trade_allowed and acc.trade_expert:
        print("🎉 MISSION READY: Your VPS is correctly configured for Sentinel-V4.")
    else:
        print("⚠️  ACTION REQUIRED: Fix the red items above before starting the bot.")

    mt5.shutdown()

if __name__ == "__main__":
    check_readiness()
