# Walkthrough: Sentinel V4 Modular Trading Bot

I have successfully scaffolded the new modular architecture for the trading bot system. This structure is designed for high-performance background execution, multi-platform support, and AI-driven trade validation.

## 1. Project Structure Overview
The system is now organized as follows:

```
f:/TradeBot/
├── skills.md                 # Bot DNA and operational constraints
├── core/                     # Shared logic (Signals, Risk, Logger)
├── platforms/                # Exchange Adapters (MT5, Binance, etc.)
├── markets/                  # Asset-Specific Bots (e.g., GoldBot)
├── ai/                       # DeepSeek Reasoner Client
├── main.py                   # Async Background Service Entry
└── requirements.txt          # Dependency manifest
```

## 2. Key Components Delivered

### Core Logic (`core/`)
- [signals.py](file:///f:/TradeBot/core/signals.py): Standardized Pydantic models for trade signals and logs.
- [risk.py](file:///f:/TradeBot/core/risk.py): Robust `RiskManager` that handles position sizing and global drawdown gates.
- [logger.py](file:///f:/TradeBot/core/logger.py): Unified logging system with console and file output.

### Platform Adapters (`platforms/`)
- [base.py](file:///f:/TradeBot/platforms/base.py): An Abstract Base Class ensuring all future adapters (Binance, XTP, MT4) follow the same interface.
- [mt5_adapter.py](file:///f:/TradeBot/platforms/mt5_adapter.py): Native MT5 integration using `asyncio.to_thread` to prevent thread blocking.

### AI Integration (`ai/`)
- [deepseek_client.py](file:///f:/TradeBot/ai/deepseek_client.py): Asynchronous client for the `deepseek-reasoner`. It validates every signal before it's allowed to execute.

### Market Execution (`markets/`)
- [gold.py](file:///f:/TradeBot/markets/gold.py): A focused bot instance for Gold (`XAUUSD`) that orchestrates the flow from signal -> risk check -> AI consultation -> execution.

## 3. How to Run & Extend

### Setup
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure your credentials in `.env` (use [.env.example](file:///f:/TradeBot/.env.example) as a template).

### Running the Bot
Launch the background service:
```bash
python main.py
```

### Triggering a Test Signal (MVP)
The `main.py` is configured to listen for a file named `signal_trigger.json`. You can trigger a trade manually for testing:
```json
{
  "symbol": "XAUUSD",
  "direction": "LONG",
  "entry": 2350.50,
  "sl": 2340.00,
  "tp1": 2370.00,
  "pattern": "Institutional Block"
}
```

## 4. Safety & Constraints
> [!IMPORTANT]
> - **Risk Minimums**: The `RiskManager` will reject any signal where SL is invalid relative to entry.
> - **AI Veto**: If DeepSeek returns anything other than `[APPROVE]`, the trade will be logged as `REJECTED` and will not reach the exchange.
> - **Kill Switch**: Monitor `skills.md` for the defined operational limits.

The system is now ready for your specific strategy logic to be plugged into the `markets/` layer.
