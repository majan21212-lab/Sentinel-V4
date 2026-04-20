# Sentinel V4: Trading Bot Skills & DNA

This document defines the core capabilities, goals, and operational constraints of the Sentinel V4 Trading Bot System.

## 1. Core Goals
- **Multi-Platform Execution**: Seamless trade routing between Binance (Crypto), XTP (Quant), and MetaTrader (Forex/Gold).
- **AI-Enhanced Precision**: Mandatory consultation with DeepSeek Reasoner for every generated signal.
- **Risk First architecture**: No trade is executed without passing three levels of risk checks (Account, Symbol, and Correlation).
- **Sub-100ms Latency**: Internal processing time from signal reception to platform dispatch must be under 100ms.

## 2. Platform Capabilities
- **Binance**: Futures trading with support for USDT/COIN-M contracts.
- **XTP**: High-frequency order execution for Equities and Futures.
- **MT5/MT4**: Specialist adapters for Forex pairs and Gold (XAUUSD) using the institutional pattern engine.

## 3. Order Types & Risk Skills
- **Skill: Dynamic Sizing**: Calculate lot size based on % of equity and ATR-adjusted SL.
- **Skill: Multi-TP Scaling**: Automatic management of TP1 (partial close) and TP2 (trailing stop).
- **Skill: Sentiment Filtering**: Using DeepSeek to weigh Fear & Greed vs. Technical signals.

## 4. Safety Constraints
- **Kill-Switch**: Immediate closure of all open positions if account drawdown exceeds 5% in 24h.
- **Connectivity Failsafe**: Stop order placement if connection to the platform heart-beat fails.
- **Sanity check**: Maximum position size cannot exceed 10 lots (adjust based on asset).
