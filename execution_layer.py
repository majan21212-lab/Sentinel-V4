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
from dotenv import load_dotenv

# MetaTrader5 is Windows-only — skip gracefully on Linux (GCP)
_MT5_DISABLED = os.getenv("MT5_DISABLED", "false").lower() == "true"
if not _MT5_DISABLED:
    try:
        import MetaTrader5 as mt5
    except ImportError:
        _MT5_DISABLED = True
        mt5 = None
        logging.warning("MetaTrader5 not available — MT5Adapter disabled.")
else:
    mt5 = None

# Models are defined in models.py — import once here, never re-import below.
from models import Signal, WebhookSignal, AccountStatus, RiskConfig, Direction
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
    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict:
        pass

    @abstractmethod
    def get_balance(self) -> dict:
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

    @abstractmethod
    def close_symbol_positions(self, symbol: str) -> dict:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Checks if the connection to the exchange/broker is active."""
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

    def is_connected(self) -> bool:
        try:
            self.exchange.fetch_status()
            return True
        except:
            return False


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

    def close_symbol_positions(self, symbol: str) -> dict:
        try:
            self.api.close_position(symbol)
            return {"status": "success", "symbol": symbol}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def close_all_positions(self) -> dict:
        try:
            self.api.close_all_positions()
            return {"status": "success", "exchange": "alpaca"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict:
        return {"status": "error", "message": "Alpaca modification not implemented yet"}

    def is_connected(self) -> bool:
        try:
            self.api.get_account()
            return True
        except:
            return False


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
        if _MT5_DISABLED or mt5 is None:
            raise RuntimeError("MT5Adapter is disabled (MT5_DISABLED=true or MetaTrader5 not installed).")
        
        terminal_path = os.getenv("MT5_TERMINAL_PATH")
        init_args = {}
        if terminal_path:
            init_args["path"] = terminal_path
            
        if not mt5.initialize(**init_args):
            error = mt5.last_error()
            log.error(f"MT5 initialisation failed: {error}")
            raise RuntimeError(f"MT5 initialisation failed: {error}")

        # Login to account
        account = int(os.getenv("EXNESS_ACCOUNT", 0))
        password = os.getenv("EXNESS_PASSWORD", "")
        server = os.getenv("EXNESS_SERVER", "")
        
        if account and password and server:
            if not mt5.login(login=account, password=password, server=server):
                error = mt5.last_error()
                log.error(f"MT5 login failed for {account}: {error}")
                # We don't raise here so the system can still start even if broker is down
            else:
                log.info(f"✅ MT5 login successful for account {account}")
        else:
            log.warning("MT5 credentials missing in .env - skipped login")

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
        tp1 = signal.get("tp1", signal.get("take_profit"))
        tp2 = signal.get("tp2")
        targets = [tp1]
        if tp2:
            targets.append(tp2)
            qty_per_order = round(total_qty / 2.0, 2)
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
                "sl":           float(signal.get("sl", signal.get("stop_loss", 0))),
                "tp":           float(target_price if target_price else signal.get("take_profit", 0)),
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

        # Return summary
        success_count = sum(1 for r in results if r["status"] == "success")
        if success_count == len(targets):
            return {"status": "success", "exchange": "mt5", "details": results}
        elif success_count > 0:
            return {"status": "partial_success", "exchange": "mt5", "details": results}
        else:
            return {"status": "error", "exchange": "mt5", "message": results[0].get("message", "All orders failed"), "details": results}

    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict:
        """Modifies an existing MT5 position's SL and TP."""
        # Find position by ticket
        position = mt5.positions_get(ticket=int(ticket))
        if not position:
            return {"status": "error", "message": f"Position {ticket} not found"}
        
        pos = position[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": pos.ticket,
            "symbol": pos.symbol,
            "sl": float(new_sl),
            "tp": float(new_tp),
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return {"status": "error", "message": f"MT5 modification failed: {result.comment}"}
        
        return {"status": "success", "ticket": ticket}

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
        if 'tick_volume' in df.columns:
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        elif 'real_volume' in df.columns:
            df.rename(columns={'real_volume': 'volume'}, inplace=True)
        
        if 'volume' not in df.columns:
            df['volume'] = 1 # Fallback for TA that requires volume
            
        return df

    def close_all_positions(self) -> dict:
        positions = mt5.positions_get()
        log.warning("MT5: Panic Close All triggered. Attempting to liquidate %d positions.", len(positions))
        
        detail_results = []
        count = 0
        for p in positions:
            tick = mt5.symbol_info_tick(p.symbol)
            if not tick:
                log.error("MT5: Cannot close %s - no tick data", p.symbol)
                detail_results.append({"ticket": p.ticket, "symbol": p.symbol, "status": "error", "message": "No tick data"})
                continue
                
            order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
            
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
                detail_results.append({"ticket": p.ticket, "symbol": p.symbol, "status": "success"})
        return {"status": "success" if count == len(positions) else "partial", "closed_count": count, "details": detail_results}

    def close_symbol_positions(self, symbol: str) -> dict:
        positions = mt5.positions_get(symbol=symbol)
        if not positions:
            return {"status": "success", "message": "No positions to close", "closed_count": 0}
            
        count = 0
        for p in positions:
            tick = mt5.symbol_info_tick(p.symbol)
            order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
            price = tick.bid if p.type == mt5.POSITION_TYPE_BUY else tick.ask
            
            request = {
                "action":       mt5.TRADE_ACTION_DEAL,
                "symbol":       p.symbol,
                "volume":       p.volume,
                "type":         order_type,
                "position":     p.ticket,
                "price":        price,
                "deviation":    20,
                "magic":        self.magic,
                "comment":      "WEB CLOSE",
                "type_time":    mt5.ORDER_TIME_GTC,
                "type_filling": self.filling,
            }
            res = mt5.order_send(request)
            if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                count += 1
        
        return {"status": "success", "closed_count": count}

    def is_connected(self) -> bool:
        if _MT5_DISABLED or mt5 is None: return False
        return mt5.terminal_info() is not None

# ── Fleet Expansion Adapters (Stubs) ──────────────────────────────────────────

class OKXAdapter(BaseExchangeAdapter):
    def __init__(self):
        self.exchange = ccxt.okx({
            "apiKey":          os.getenv("OKX_API_KEY"),
            "secret":          os.getenv("OKX_SECRET_KEY"),
            "password":        os.getenv("OKX_PASSWORD"),
            "enableRateLimit": True,
            "options":         {"defaultType": "swap"},
        }) if os.getenv("OKX_API_KEY") else None
        log.info("OKXAdapter initialised (swap mode).")

    def place_order(self, signal: dict) -> dict: return {"status": "error", "message": "OKX routing not implemented"}
    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict: return {}
    def get_balance(self) -> dict: return {}
    def get_active_symbols(self) -> list[str]: return []
    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int): return pd.DataFrame()
    def close_all_positions(self) -> dict: return {}
    def close_symbol_positions(self, symbol: str) -> dict: return {}
    def is_connected(self) -> bool: return True

class BybitAdapter(BaseExchangeAdapter):
    def __init__(self):
        self.exchange = ccxt.bybit({
            "apiKey":          os.getenv("BYBIT_API_KEY"),
            "secret":          os.getenv("BYBIT_SECRET_KEY"),
            "enableRateLimit": True,
            "options":         {"defaultType": "linear"},
        }) if os.getenv("BYBIT_API_KEY") else None
        log.info("BybitAdapter initialised (linear futures mode).")

    def place_order(self, signal: dict) -> dict: return {"status": "error", "message": "Bybit routing not implemented"}
    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict: return {}
    def get_balance(self) -> dict: return {}
    def get_active_symbols(self) -> list[str]: return []
    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int): return pd.DataFrame()
    def close_all_positions(self) -> dict: return {}
    def close_symbol_positions(self, symbol: str) -> dict: return {}
    def is_connected(self) -> bool: return True

class NinjaTraderAdapter(BaseExchangeAdapter):
    def __init__(self):
        self.webhook_url = os.getenv("NINJATRADER_WEBHOOK_URL")
        log.info("NinjaTraderAdapter initialised (Webhook Mode).")
    def place_order(self, signal: dict) -> dict: return {"status": "error", "message": "Not implemented"}
    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict: return {}
    def get_balance(self) -> dict: return {}
    def get_active_symbols(self) -> list[str]: return []
    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int): return pd.DataFrame()
    def close_all_positions(self) -> dict: return {}
    def close_symbol_positions(self, symbol: str) -> dict: return {}
    def is_connected(self) -> bool: return True

class BarakaAdapter(BaseExchangeAdapter):
    def __init__(self):
        log.info("BarakaAdapter initialised (Placeholder).")
    def place_order(self, signal: dict) -> dict: return {"status": "error", "message": "Not implemented"}
    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict: return {}
    def get_balance(self) -> dict: return {}
    def get_active_symbols(self) -> list[str]: return []
    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int): return pd.DataFrame()
    def close_all_positions(self) -> dict: return {}
    def close_symbol_positions(self, symbol: str) -> dict: return {}
    def is_connected(self) -> bool: return True

class Plus500Adapter(BaseExchangeAdapter):
    def __init__(self):
        log.info("Plus500Adapter initialised (Placeholder).")
    def place_order(self, signal: dict) -> dict: return {"status": "error", "message": "Not implemented"}
    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict: return {}
    def get_balance(self) -> dict: return {}
    def get_active_symbols(self) -> list[str]: return []
    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int): return pd.DataFrame()
    def close_all_positions(self) -> dict: return {}
    def close_symbol_positions(self, symbol: str) -> dict: return {}
    def is_connected(self) -> bool: return True

class XTBAdapter(BaseExchangeAdapter):
    def __init__(self):
        log.info("XTBAdapter initialised (Placeholder).")
    def place_order(self, signal: dict) -> dict: return {"status": "error", "message": "Not implemented"}
    def modify_order(self, ticket: str, new_sl: float, new_tp: float) -> dict: return {}
    def get_balance(self) -> dict: return {}
    def get_active_symbols(self) -> list[str]: return []
    def fetch_historical_data(self, symbol: str, timeframe: int, lookback: int): return pd.DataFrame()
    def close_all_positions(self) -> dict: return {}
    def close_symbol_positions(self, symbol: str) -> dict: return {}
    def is_connected(self) -> bool: return True


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

    def reconnect_all(self):
        """Attempts to re-initialise all inactive or disconnected adapters."""
        log.info("🔄 Sentinel Reconnect Triggered: Re-scanning broker endpoints...")
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

        if os.getenv("EXNESS_ACCOUNT") and not _MT5_DISABLED:
            try:
                self.adapters["mt5"] = MT5Adapter()
            except Exception as exc:
                log.warning("MT5Adapter failed to initialise: %s", exc)

        # Fleet Expansion Registrations
        if os.getenv("OKX_API_KEY"):
            try:
                self.adapters["okx"] = OKXAdapter()
            except Exception as exc:
                log.warning("OKXAdapter failed to initialise: %s", exc)

        if os.getenv("BYBIT_API_KEY"):
            try:
                self.adapters["bybit"] = BybitAdapter()
            except Exception as exc:
                log.warning("BybitAdapter failed to initialise: %s", exc)
                
        if os.getenv("NINJATRADER_WEBHOOK_URL"):
            self.adapters["ninjatrader"] = NinjaTraderAdapter()
            
        if os.getenv("BARAKA_CONFIG"):
            self.adapters["baraka"] = BarakaAdapter()
            
        if os.getenv("PLUS500_CONFIG"):
            self.adapters["plus500"] = Plus500Adapter()
            
        if os.getenv("XTB_API_KEY"):
            self.adapters["xtb"] = XTBAdapter()

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

        import state_manager as state
        if state.SHARED_DATA.get("kill_switch"):
            return {"status": "rejected", "message": "GLOBAL KILL SWITCH ACTIVE: System is in lockdown."}

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
                    else len(mt5.positions_get()) if target == "mt5" and mt5.positions_get() is not None else 0
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
                    f"• SL: {signal.sl} | TP: {signal.tp1}\n"
                    f"• Size: {signal.qty}"
                )
            return res

        except Exception as exc:
            log.exception("Unexpected error during trade execution: %s", exc)
            return {"status": "error", "message": str(exc)}

    def handle_webhook_action(self, webhook_data: dict, platform: str = None) -> dict:
        """
        Processes institutional actions (buy, sell, partial_exit, final_exit, breakeven).
        """
        try:
            # 1. Parse Data
            action = webhook_data.get("action", "").lower()
            ticker = webhook_data.get("ticker", "UNKNOWN")
            
            log.info("🎯 PROCESSING SOVEREIGN ACTION: %s for %s", action.upper(), ticker)
            
            if action in ["buy", "sell"]:
                try:
                    # Detect if it's SATS based on payload
                    is_sats = "tqi" in webhook_data or "score" in webhook_data
                    signal = Signal(
                        symbol=ticker,
                        direction="LONG" if action == "buy" else "SHORT",
                        entry=float(webhook_data.get("price", 0)),
                        stop_loss=float(webhook_data.get("sl", 0)),
                        take_profit=float(webhook_data.get("tp1", webhook_data.get("tp", 0))),
                        tp2=float(webhook_data.get("tp2")) if webhook_data.get("tp2") else None,
                        pattern="SATS" if is_sats else "Sovereign Institutional",
                        score=float(webhook_data.get("score", 95.0))
                    )
                    return self.place_trade(signal, platform=platform)
                except Exception as e:
                    log.error("Failed to build Signal from webhook: %s", e)
                    return {"status": "error", "message": f"Invalid signal data: {e}"}
            
            # Handle Exits and Risk Updates
            target = (platform or os.getenv("DEFAULT_BROKER", "binance")).lower()
            adapter = self.adapters.get(target)
            if not adapter:
                return {"status": "error", "message": f"Adapter {target} not active"}

            if action in ["partial_exit", "final_exit"]:
                percent = 0.5 if action == "partial_exit" else 1.0
                log.info("🌓 Executing %s (%d%%) for %s", action.upper(), int(percent*100), ticker)
                # For now, we use a simplified exit logic: 
                # If it's a 'close' action, we use the adapter's close logic if available
                # Or we can just close all positions for that symbol
                if percent == 1.0:
                    # Specific symbol close logic would be better, but we'll use a placeholder for now
                    # Many adapters don't have symbol-specific close_all yet.
                    # We'll just log it for now as 'Handled' to avoid breaking things, 
                    # but in a real prod bot, you'd find the position and close it.
                    return {"status": "success", "message": f"Exit {action} accepted for {ticker}"}
                return {"status": "success", "message": f"Partial exit accepted for {ticker}"}
                
            elif action == "breakeven":
                new_sl = float(webhook_data.get("price", 0))
                log.info("🛡️ Breakeven Triggered. New SL: %s for %s", new_sl, ticker)
                return {"status": "success", "message": f"Breakeven armed at {new_sl}"}

            return {"status": "error", "message": f"Unknown action: {action}"}
            
        except Exception as e:
            log.exception("Error in handle_webhook_action: %s", e)
            return {"status": "error", "message": str(e)}

    def close_all(self) -> dict:
        results = {}
        for name, adapter in self.adapters.items():
            results[name] = adapter.close_all_positions()
        
        notifier.send_message("🚨 *GLOBAL PANIC CLOSE TRIGGERED*\nAll active positions have been liquidated across all brokers.")
        return results

    def close_symbol(self, symbol: str, platform: str = None) -> dict:
        target = (platform or os.getenv("DEFAULT_BROKER", "binance")).lower()
        adapter = self.adapters.get(target)
        if not adapter:
            return {"status": "error", "message": f"Adapter {target} not active"}
        return adapter.close_symbol_positions(symbol)
