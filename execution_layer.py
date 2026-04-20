"""
execution_layer.py — TradeBot v3.1 Elite
Broker adapters + ExecutionLayer with risk gate and dynamic position sizing.
"""

import os
import logging
from abc import ABC, abstractmethod

import ccxt
import alpaca_trade_api as tradeapi
import pandas as pd
import MetaTrader5 as mt5
from dotenv import load_dotenv

# Models are defined in models.py — import once here, never re-import below.
from models import Signal, AccountStatus, RiskConfig
from risk_management import RiskEngine
from core.notifier import notifier

load_dotenv()

log = logging.getLogger(__name__)

# ── Abstract Base ─────────────────────────────────────────────────────────────

class BaseExchangeAdapter(ABC):
    """Unified interface for all exchange/broker adapters."""

    @abstractmethod
    def place_order(self, signal: dict) -> dict:
        pass

    @abstractmethod
    def get_balance(self):
        pass

    @abstractmethod
    def get_active_symbols(self) -> list[str]:
        pass

    @abstractmethod
    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int) -> pd.DataFrame:
        pass

    @abstractmethod
    def close_all_positions(self) -> dict:
        pass


# ── Binance Adapter ───────────────────────────────────────────────────────────

class BinanceAdapter(BaseExchangeAdapter):
    def __init__(self):
        self.exchange = ccxt.binance({
            "apiKey":          os.getenv("BINANCE_API_KEY"),
            "secret":          os.getenv("BINANCE_SECRET_KEY"),
            "enableRateLimit": True,
            "options":         {"defaultType": "future"},
        })
        log.info("BinanceAdapter initialised (futures mode).")

    def place_order(self, signal: dict) -> dict:
        try:
            side   = "buy" if signal["direction"] == "LONG" else "sell"
            symbol = signal["symbol"]
            qty    = float(signal.get("qty", 0.001))
            
            # 1. Place Main Market Order
            order  = self.exchange.create_order(
                symbol=symbol,
                type="market",
                side=side,
                amount=qty,
            )
            log.info("Binance Market Order placed: %s", order.get("id"))

            # 2. Add TP/SL Protection Orders (Binance Futures)
            # Use 'stop' and 'take_profit' or limit-based closes
            try:
                opp_side = "sell" if side == "buy" else "buy"
                # Place SL
                self.exchange.create_order(
                    symbol=symbol, type="STOP_MARKET", side=opp_side, amount=qty,
                    params={"stopPrice": signal["sl"]}
                )
                # Place TP1 (50%)
                self.exchange.create_order(
                    symbol=symbol, type="TAKE_PROFIT_MARKET", side=opp_side, amount=qty/2,
                    params={"stopPrice": signal["tp1"]}
                )
                # Place TP2 (50%)
                if signal.get("tp2"):
                    self.exchange.create_order(
                        symbol=symbol, type="TAKE_PROFIT_MARKET", side=opp_side, amount=qty/2,
                        params={"stopPrice": signal["tp2"]}
                    )
            except Exception as e:
                log.warning("Binance TP/SL attachment failed: %s", e)

            return {"status": "success", "exchange": "binance", "order_id": order["id"]}
        except Exception as exc:
            log.error("Binance primary order error: %s", exc)
            return {"status": "error", "message": str(exc)}

    def get_balance(self):
        return self.exchange.fetch_balance()

    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int) -> pd.DataFrame:
        # Placeholder for Binance if ever needed in a polling context
        return pd.DataFrame()

    def get_active_symbols(self) -> list[str]:
        try:
            positions = self.exchange.fetch_positions()
            return [p['symbol'] for p in positions if float(p.get('positionAmt', p.get('contracts', 0))) != 0]
        except Exception as exc:
            log.error("Binance fetch_positions error: %s", exc)
            return []

    def close_all_positions(self) -> dict:
        try:
            positions = self.exchange.fetch_positions()
            count = 0
            for p in positions:
                amt = float(p.get('positionAmt', p.get('contracts', 0)))
                if amt != 0:
                    side = "sell" if amt > 0 else "buy"
                    self.exchange.create_order(
                        symbol=p['symbol'],
                        type="market",
                        side=side,
                        amount=abs(amt)
                    )
                    count += 1
            log.warning("Binance: Panic Close All triggered. %d positions closed.", count)
            return {"status": "success", "closed": count}
        except Exception as exc:
            log.error("Binance close_all error: %s", exc)
            return {"status": "error", "message": str(exc)}


# ── Alpaca Adapter ────────────────────────────────────────────────────────────

class AlpacaAdapter(BaseExchangeAdapter):
    def __init__(self):
        self.api = tradeapi.REST(
            os.getenv("ALPACA_API_KEY"),
            os.getenv("ALPACA_SECRET_KEY"),
            os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
            api_version="v2",
        )
        log.info("AlpacaAdapter initialised.")

    def place_order(self, signal: dict) -> dict:
        try:
            side = "buy" if signal["direction"] == "LONG" else "sell"
            symbol = signal["symbol"]
            total_qty = int(signal.get("qty", 1))
            
            # Support for Split TP
            qty1 = total_qty // 2 if signal.get("tp2") else total_qty
            qty2 = total_qty - qty1
            
            # Order 1 (TP1)
            self.api.submit_order(
                symbol=symbol,
                qty=qty1,
                side=side,
                type="market",
                time_in_force="gtc",
                order_class="bracket",
                take_profit={"limit_price": round(signal["tp1"], 2)},
                stop_loss={"stop_price": round(signal["sl"], 2)},
            )
            
            # Order 2 (TP2)
            if signal.get("tp2") and qty2 > 0:
                self.api.submit_order(
                    symbol=symbol,
                    qty=qty2,
                    side=side,
                    type="market",
                    time_in_force="gtc",
                    order_class="bracket",
                    take_profit={"limit_price": round(signal["tp2"], 2)},
                    stop_loss={"stop_price": round(signal["sl"], 2)},
                )

            log.info("Alpaca Split Orders submitted for %s.", symbol)
            return {"status": "success", "exchange": "alpaca"}
        except Exception as exc:
            log.error("Alpaca order error: %s", exc)
            return {"status": "error", "message": str(exc)}

    def get_balance(self):
        return self.api.get_account()

    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int) -> pd.DataFrame:
        # Placeholder for Alpaca
        return pd.DataFrame()

    def get_active_symbols(self) -> list[str]:
        try:
            positions = self.api.list_positions()
            return [p.symbol for p in positions]
        except Exception as exc:
            log.error("Alpaca list_positions error: %s", exc)
            return []


# ── MT5 Adapter ───────────────────────────────────────────────────────────────

class MT5Adapter(BaseExchangeAdapter):
    """
    MetaTrader 5 adapter.
    FIX #4 – Magic number and filling mode are read from the .env file so they
    can be tuned without changing code. Many brokers reject ORDER_FILLING_IOC;
    set MT5_FILLING_MODE=FOK or MT5_FILLING_MODE=RETURN in your .env as needed.
    """

    _FILLING_MAP = {
        "FOK":    None,   # resolved after mt5 is initialised
        "RETURN": None,
        "IOC":    None,
    }

    def __init__(self):
        if not mt5.initialize():
            error = mt5.last_error()
            raise RuntimeError(f"MT5 initialisation failed: {error}")

        # Resolve filling constants now that mt5 is live
        self._FILLING_MAP = {
            "FOK":    mt5.ORDER_FILLING_FOK,
            "RETURN": mt5.ORDER_FILLING_RETURN,
            "IOC":    mt5.ORDER_FILLING_IOC,
        }

        self.magic   = int(os.getenv("MT5_MAGIC_NUMBER", "20260415"))
        filling_str  = os.getenv("MT5_FILLING_MODE", "IOC").upper()
        self.filling = self._FILLING_MAP.get(filling_str, mt5.ORDER_FILLING_IOC)

        log.info(
            "MT5Adapter initialised. Magic=%d, Filling=%s",
            self.magic,
            filling_str,
        )

    def place_order(self, signal: dict) -> dict:
        symbol     = signal["symbol"]
        is_long    = signal["direction"] == "LONG"
        order_type = mt5.ORDER_TYPE_BUY if is_long else mt5.ORDER_TYPE_SELL

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            msg = f"MT5: Cannot get tick for {symbol}. Is the symbol visible in MarketWatch?"
            log.error(msg)
            return {"status": "error", "message": msg}

        price = tick.ask if is_long else tick.bid
        total_qty = float(signal.get("qty", 0.01))
        
        # Trade Scaling Logic: If tp2 is provided, split into two orders
        targets = [signal.get("tp1")]
        if signal.get("tp2"):
            targets.append(signal.get("tp2"))
            qty_per_order = total_qty / 2.0
            # Ensure minimum lot size (0.01)
            if qty_per_order < 0.01:
                qty_per_order = 0.01
                targets = [signal.get("tp2")] # Just take the final target if too small to split
        else:
            qty_per_order = total_qty

        results = []
        for target_price in targets:
            request = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       symbol,
                "volume":       qty_per_order,
                "type":         order_type,
                "price":        price,
                "sl":           float(signal["sl"]),
                "tp":           float(target_price),
                "deviation":    20,
                "magic":        self.magic,
                "comment":      f"Jewel Elite {'TP'+str(targets.index(target_price)+1)}",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": self.filling,
            }

            result = mt5.order_send(request)
            if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
                code = result.retcode if result else "N/A"
                msg  = result.comment if result else "No response from MT5"
                log.error("MT5 order failed for target %s. Retcode=%s, Comment=%s", target_price, code, msg)
                results.append({"status": "error", "message": msg, "retcode": code})
            else:
                log.info("MT5 order placed for target %s. Ticket=%s", target_price, result.order)
                results.append({"status": "success", "exchange": "mt5", "ticket": result.order})

        # Return the last result or a summary
        return results[0] if len(results) == 1 else {"status": "success", "details": results}

    def get_balance(self) -> dict:
        info = mt5.account_info()
        return info._asdict() if info else {}

    def get_active_symbols(self) -> list[str]:
        positions = mt5.positions_get()
        if positions is None:
            return []
        return list(set(p.symbol for p in positions))

    def shutdown(self):
        mt5.shutdown()
        log.info("MT5 connection closed.")

    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int) -> pd.DataFrame:
        """Fetch historical candles from MT5 and return as a DataFrame."""
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) == 0:
            log.warning("MT5: No data returned for %s", symbol)
            return pd.DataFrame()
        
        df = pd.DataFrame(rates)
        df['timestamp'] = pd.to_datetime(df['time'], unit='s')
        # Map MT5 specific columns to standard names
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        return df

    def close_all_positions(self) -> dict:
        positions = mt5.positions_get()
        if not positions:
            return {"status": "success", "closed": 0}
        
        count = 0
        for p in positions:
            order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(p.symbol).bid if p.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(p.symbol).ask
            
            request = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       p.symbol,
                "volume":       p.volume,
                "type":         order_type,
                "position":     p.ticket,
                "price":        price,
                "deviation":    20,
                "magic":        self.magic,
                "comment":      "PANIC CLOSE",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": self.filling,
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                count += 1
        
        log.warning("MT5: Panic Close All triggered. %d positions closed.", count)
        return {"status": "success", "closed": count}


# ── Execution Layer ───────────────────────────────────────────────────────────

class ExecutionLayer:
    """
    Orchestrates adapter selection, risk validation, and order dispatch.
    FIX #2/#5 – Instantiate this ONCE in main(); do not create inside a loop.
    """

    def __init__(self):
        self.adapters:     dict[str, BaseExchangeAdapter] = {}
        self.risk_engine = RiskEngine()
        self._init_adapters()

    def _init_adapters(self):
        """Dynamically load only the adapters whose credentials are set."""
        if os.getenv("BINANCE_API_KEY"):
            try:
                self.adapters["binance"] = BinanceAdapter()
            except Exception as exc:
                log.warning("BinanceAdapter failed to initialise: %s", exc)

        if os.getenv("ALPACA_API_KEY"):
            try:
                self.adapters["alpaca"] = AlpacaAdapter()
            except Exception as exc:
                log.warning("AlpacaAdapter failed to initialise: %s", exc)

        if os.getenv("EXNESS_ACCOUNT"):
            try:
                self.adapters["mt5"] = MT5Adapter()
            except Exception as exc:
                log.warning("MT5Adapter failed to initialise: %s", exc)

    def place_trade(self, signal: Signal, platform: str = None) -> dict:
        """
        Validate risk, size the position, then route to the correct adapter.

        Parameters
        ----------
        signal   : Signal  — Pydantic model (not a raw dict).
        platform : str     — 'BINANCE', 'ALPACA', or 'MT5'. Falls back to
                             DEFAULT_BROKER env var, then 'binance'.
        """
        target = (platform or os.getenv("DEFAULT_BROKER", "binance")).lower()

        if target not in self.adapters:
            msg = f"Adapter '{target}' not initialised. Check credentials in .env."
            log.error(msg)
            return {"status": "error", "message": msg}

        try:
            # ── 1. Fetch live account equity ──────────────────────────────
            raw_balance = self.adapters[target].get_balance()

            if target == "binance":
                equity = float(raw_balance.get("total", {}).get("USDT", 0))
            elif target == "alpaca":
                equity = float(getattr(raw_balance, "equity", 0))
            elif target == "mt5":
                equity = float(raw_balance.get("equity", 0))
            else:
                equity = 0.0

            account = AccountStatus(
                platform=target,
                equity=equity,
                balance=equity,
                open_positions=(
                    getattr(raw_balance, "open_positions", 0)
                    if target == "alpaca"
                    else raw_balance.get("positions", 0)
                    if target == "mt5"
                    else 0
                ),
                active_symbols=self.adapters[target].get_active_symbols(),
                daily_pnl=0.0,
            )

            # ── 2. Risk gate ──────────────────────────────────────────────
            is_safe, reason = self.risk_engine.validate_trade(signal, account)
            if not is_safe:
                log.warning("🛑 RISK REJECTED: %s", reason)
                return {"status": "rejected", "message": reason}

            # ── 3. Dynamic position sizing ────────────────────────────────
            if signal.qty == 0.01:   # still at default — calculate proper size
                signal.qty = self.risk_engine.calculate_position_size(
                    signal.symbol, account.equity, signal.entry, signal.sl, signal.score
                )

            log.info(
                "🚀 Executing %s on %s for %s | Qty: %s",
                signal.direction,
                target.upper(),
                signal.symbol,
                signal.qty,
            )

            # ── 4. Dispatch (INTERCEPT IF IN DEMO MODE) ───────────────────
            mode = self.risk_engine.config.execution_mode
            if mode == "DEMO":
                log.info("🧪 [DEMO MODE] Skip execution for %s @ %s", signal.symbol, signal.entry)
                res = {"status": "success", "message": "Demo execution simulated", "demo": True}
            else:
                res = self.adapters[target].place_order(signal.dict(by_alias=True))
            
            if res.get("status") == "success":
                notifier.send_message(
                    f"🚀 *Executed: {signal.symbol}*\n"
                    f"• {signal.direction} @ {signal.entry}\n"
                    f"• Size: {signal.qty}"
                )
            return res

        except Exception as exc:
            log.exception("Unexpected error during trade execution: %s", exc)
            return {"status": "error", "message": str(exc)}

    def close_all(self) -> dict:
        results = {}
        for name, adapter in self.adapters.items():
            results[name] = adapter.close_all_positions()
        
        notifier.send_message("🚨 *GLOBAL PANIC CLOSE TRIGGERED*\nAll active positions have been liquidated across all brokers.")
        return results
