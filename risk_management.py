import os
import json
from models import RiskConfig, AccountStatus, Signal
from news_filter import news_filter
from telegram_bot import telegram_bot
from self_learning_engine import self_learning
from sentiment_engine import sentiment_engine
from news_sentiment_engine import news_sentiment
from market_hours import market_hours
class RiskEngine:
    def __init__(self, config: RiskConfig = RiskConfig()):
        self.config = config
        self.load_config()
        self.cooldowns = {} # Stores timestamp of last loss per symbol

    def load_config(self):
        """Loads risk settings from a persistent JSON file if it exists."""
        config_path = "risk_settings.json"
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    data = json.load(f)
                    self.config = RiskConfig(**data)
        except Exception as e:
            print(f"Error loading risk config: {e}")

        # Overlay Profile-specific overrides
        profile = self.config.active_profile
        if profile == "CONSERVATIVE":
            self.config.max_open_positions = 1
            self.config.max_daily_loss_pct = 1.0
        elif profile == "OPTIMAL":
            self.config.max_open_positions = 3
            self.config.max_daily_loss_pct = 3.0
        elif profile == "AGGRESSIVE":
            self.config.max_open_positions = 10
            self.config.max_daily_loss_pct = 10.0

    def validate_trade(self, signal, account: AccountStatus, global_active_symbols: list[str] = None):
        """Validates whether a new trade is allowed given current risk constraints."""
        profile = self.config.active_profile

        # 0. PROP FIRM SHIELD: Check Emergency Stop
        if self.config.emergency_stop_active:
            return False, "🚨 PROP FIRM SHIELD: Emergency Stop Active. Trading Halted."

        # 0. MARKET HOURS SHIELD
        if not market_hours.is_market_open(signal.symbol):
            return False, f"⚠️ MARKET CLOSED: Trading for {signal.symbol} is currently paused."

        # 0.5 NEWS FILTER SHIELD
        if self.config.news_filter_enabled:
            is_news, news_title = news_filter.is_volatile_now(
                signal.symbol, 
                buffer_minutes=self.config.news_buffer_mins,
                min_impact=self.config.news_impact_min
            )
            if is_news:
                telegram_bot.send_security_alert("NEWS ALERT", f"Trading paused for {signal.symbol} due to '{news_title}'")
                return False, f"⚠️ NEWS FILTER: Trading paused for {signal.symbol} due to '{news_title}'"

        # 1. Check Max Open Positions
        if account.open_positions >= self.config.max_open_positions:
            return False, f"Max {profile} open positions reached ({self.config.max_open_positions})."

        if signal.symbol in account.active_symbols:
            return False, f"Duplicate Trade: Position for {signal.symbol} already open."

        # 2.5 Safety Cooldown Check
        import time
        last_loss = self.cooldowns.get(signal.symbol, 0)
        if time.time() - last_loss < 1800: # 30 minute cooldown
            return False, f"🛡️ SAFETY COOLDOWN: {signal.symbol} is on a 30m break after a loss."

        # 3. Check Daily Drawdown (Passive & Hard Stop)
        # We use a safety buffer (4.5% instead of 5%)
        daily_loss_limit = account.balance * (self.config.max_daily_drawdown_pct / 100)
        if account.daily_pnl <= -daily_loss_limit:
            if self.config.prop_firm_mode:
                self.config.emergency_stop_active = True
                self.save_config()
                telegram_bot.send_security_alert("EMERGENCY STOP", f"Daily Loss Limit Reached (-{self.config.max_daily_drawdown_pct}%). Engine Locked.")
                return False, f"🚨 PROP FIRM SHIELD: Daily Loss Limit Reached (-{self.config.max_daily_drawdown_pct}%). Emergency Stop Activated."
            return False, f"Passive Stop: Daily loss limit reached (-${daily_loss_limit:.2f})."

        # 4. Total Drawdown Check (Equity relative to Initial Balance)
        # This is critical for Prop Firms that track 'Max Drawdown'
        if self.config.prop_firm_mode:
            # We assume initial balance is saved or provided. 
            # For now, we check against the current balance to detect rapid drops.
            total_loss_limit = account.balance * (self.config.max_total_drawdown_pct / 100)
            # If current equity is significantly below balance
            unrealized_loss = account.balance - account.equity
            if unrealized_loss > total_loss_limit:
                self.config.emergency_stop_active = True
                self.save_config()
                return False, f"🚨 PROP FIRM SHIELD: Total Drawdown Risk Detected. Emergency Stop Activated."

        # 5. Check Minimum Order Value
        # For MT5, we must multiply by contract size to get real face value.
        multiplier = 1.0
        if account.platform == "mt5":
            if "XAU" in signal.symbol or "XAG" in signal.symbol:
                multiplier = 100.0
            elif "BTC" in signal.symbol or "ETH" in signal.symbol:
                multiplier = 1.0 
            elif "AAPL" in signal.symbol or "TSLA" in signal.symbol:
                multiplier = 1.0 
            elif "USOIL" in signal.symbol or "WTI" in signal.symbol:
                multiplier = 100.0 # Standard Oil contract
            elif "NAS100" in signal.symbol or "US30" in signal.symbol:
                multiplier = 10.0 # Indices often 10x or 1x
            else:
                multiplier = 100000.0 # Standard Forex Lot size
                
        order_value = signal.entry * signal.qty * multiplier
        if order_value < self.config.min_order_value_usd:
            return False, f"Order value ${order_value:.2f} too low (Min ${self.config.min_order_value_usd})."

        # 6. Check Correlation Risk (Global Balancing)
        correlation_groups = [
            {"BTC/USDT", "ETH/USDT", "SOL/USDT", "BTCUSDm", "ETHUSDm"},
            {"XAUUSD", "EURUSD", "XAUUSDm", "EURUSDm", "GBPUSDm"},
            {"US30m", "NAS100m", "DE 40"}
        ]
        
        # Use global symbols if provided (Bridge Mode), otherwise local
        check_list = global_active_symbols if global_active_symbols is not None else account.active_symbols
        
        for group in correlation_groups:
            if signal.symbol in group:
                active_correlated = set(group).intersection(set(check_list))
                if active_correlated:
                    # If this exact symbol is already open, it's a duplicate check (handled above)
                    # If ANOTHER symbol in the group is open, we block to balance the bridge.
                    if signal.symbol not in active_correlated or len(active_correlated) > 0:
                        return False, f"⚖️ Correlation Balance: High exposure to {list(active_correlated)} already exists in the Bridge."

        return True, "Risk validation passed."

    def save_config(self):
        """Persists current risk settings to disk."""
        try:
            with open("risk_settings.json", "w") as f:
                json.dump(self.config.dict(), f, indent=4)
        except Exception as e:
            print(f"Error saving risk config: {e}")

    def _calculate_multiplier(self, score: float) -> float:
        """Calculates risk multiplier based on score (70-100)."""
        if score <= 0: return 1.0
        min_s, max_s = 70.0, 100.0
        clipped_score = max(min_s, min(max_s, score))
        ratio = (clipped_score - min_s) / (max_s - min_s)
        return self.config.min_multiplier + (self.config.max_multiplier - self.config.min_multiplier) * ratio

    def calculate_position_size(self, symbol: str, account_equity: float, entry: float, stop_loss: float, score: float = 0.0, pattern: str = "DEFAULT", weight: float = 1.0) -> float:
        """
        Calculates qty based on asset-specific % risk, SL distance, and optional AI scaling.
        Includes a Fractional Kelly optimization based on score.
        """
        # 1. Base Risk Calculation
        risk_pct = self.config.risk_per_asset.get(symbol, self.config.risk_per_asset.get("DEFAULT", 1.0))
        
        # --- Self-Learning Risk Adjustment ---
        from self_learning_engine import self_learning
        learning_multiplier = self_learning.get_strategy_multiplier(symbol, pattern)
        if learning_multiplier != 1.0:
            risk_pct *= learning_multiplier
            log.info(f"🧠 Self-Learning Adjustment for {pattern} on {symbol}: {learning_multiplier}x (Base Risk: {risk_pct/learning_multiplier:.2f}%)")
        
        # --- Sentiment Overlay Adjustment ---
        sentiment_multiplier = sentiment_engine.get_bias_multiplier("LONG" if "BULL" in pattern.upper() or "LONG" in pattern.upper() else "SHORT")
        if sentiment_multiplier != 1.0:
            risk_pct *= sentiment_multiplier
            log.info(f"📊 Sentiment Adjustment: {sentiment_multiplier}x due to {sentiment_engine.current_sentiment}")
        
        # --- News Headlines Sentiment Adjustment ---
        news_multiplier = news_sentiment.get_news_multiplier("LONG" if "BULL" in pattern.upper() or "LONG" in pattern.upper() else "SHORT", symbol)
        if news_multiplier != 1.0:
            risk_pct *= news_multiplier
            log.info(f"📰 News Sentiment Adjustment: {news_multiplier}x (Bias: {news_sentiment.current_global_bias})")
        
        # Profile Multiplier
        profile = self.config.active_profile
        if profile == "CONSERVATIVE":
            risk_pct *= 0.5
        elif profile == "AGGRESSIVE":
            risk_pct *= 2.0
        
        # 2. Dynamic Scaling based on AI Confidence (Fractional Kelly Concept)
        if symbol in self.config.ai_scaling_symbols and score > 0:
            # We treat score as a proxy for p (probability of success)
            # Normalizing score (70-100) to a conservative p (0.55-0.75)
            p = 0.55 + (0.2 * (max(70, min(100, score)) - 70) / 30)
            # Assuming a standard R:R of 1.5 (b = 1.5)
            b = 1.5
            q = 1 - p
            kelly_f = p - (q / b) # Full Kelly
            fractional_kelly = kelly_f * 0.25 # Use 1/4 Kelly for safety
            
            # Use the higher of standard risk or fractional kelly
            risk_pct = max(risk_pct, fractional_kelly * 100)
            
            log.info(f"KELLY: {symbol} score={score} -> p={p:.2f} | Fractional Kelly Risk={risk_pct:.2f}%")
        
        # Use fixed capital if specified, otherwise use full equity
        calculation_base = self.config.fixed_capital_usd if self.config.fixed_capital_usd > 0 else account_equity
        
        risk_amt = calculation_base * (risk_pct / 100)
        risk_per_unit = abs(entry - stop_loss)
        
        if risk_per_unit == 0:
            return 0.01
            
        qty = risk_amt / risk_per_unit

        # Accurate Contract Size Detection
        contract_size = 100000.0
        if "XAU" in symbol or "XAG" in symbol: contract_size = 100.0
        elif "BTC" in symbol or "ETH" in symbol: contract_size = 1.0
        elif "AAPL" in symbol or "TSLA" in symbol: contract_size = 1.0

        lots = (qty / contract_size) * weight
        
        if weight != 1.0:
            log.info(f"🌉 Bridge Weighting applied: {weight}x (Final Lots: {lots:.4f})")
            
        return max(0.01, round(lots, 2))
    def register_loss(self, symbol: str):
        """Called by execution layer when a trade hits SL."""
        import time
        self.cooldowns[symbol] = time.time()
        log.warning(f"🛡️ SAFETY: Registered loss for {symbol}. Cooldown active.")
