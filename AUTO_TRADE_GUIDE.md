# 🛡️ TradeBot v3.1 Elite — Auto-Trading Guide

Welcome to the **Jewel Elite** automated trading system. This bot is now equipped with the **Waterfall Signal Engine** and can trade across **Binance**, **Alpaca**, and **Exness (MT5)**.

## 🛠️ 1. Setup Your Environment
Open your `.env` file (copy from `.env.example`) and configure the following:

### Core Settings
```env
STRATEGY_MODE=JEWEL_ELITE            # JEWEL_ELITE or GOD_MODE
CHECK_INTERVAL_MINS=5                # Time between scans
TRADING_SYMBOLS=BTC/USDT,ETH/USDT    # Comma separated
AUTO_TRADE_ENABLED=true              # Set to true to execute trades!
BROKER_TYPE=BINANCE                  # BINANCE, ALPACA, or MT5
```

### 🔑 Broker Credentials

#### Binance (Futures)
- `BINANCE_API_KEY`: Your API Key
- `BINANCE_SECRET_KEY`: Your Secret Key

#### Alpaca (Stocks / Crypto)
- `ALPACA_API_KEY`: Your Key ID
- `ALPACA_SECRET_KEY`: Your Secret Key
- `ALPACA_BASE_URL`: https://paper-api.alpaca.markets (for demo)

#### Exness (MetaTrader 5)
- `EXNESS_ACCOUNT`: Your MT5 Account Number
- `EXNESS_PASSWORD`: Your Trading Password
- `EXNESS_SERVER`: E.g., Exness-MT5Trial6

---

## 🚀 2. Launching the Bot
To activate the bot, run the following command in your terminal:

```powershell
python app.py
```

### 🌊 Monitoring Waterfall Signals
The bot will output high-velocity "Waterfall" detections directly to the console:
`🔥 PATTERN DETECTED: WATERFALL_BULL | Score: 85.0`
`✅ Trade Executed Successfully on BINANCE`

---

## 📊 3. Verifying Performance
1. **Local Database**: All signals (even if auto-trade is off) are saved to `trading_bot.db`.
2. **Logs**: Check the console for execution confirmation.
3. **Broker App**: Verify that Market/Bracket orders appear in your Binance/Alpaca/MT5 terminal.

> [!CAUTION]
> **Risk Management**: The bot currently defaults to a 0.01 lot (MT5) or minimum quantity for safety. Ensure you test in **Demo/Paper** accounts before using real capital.
