import os
import json
from models import RiskConfig, AccountStatus, Signal

class RiskEngine:
    def __init__(self, config: RiskConfig = RiskConfig()):
        self.config = config
        self.peak_equity = 0.0
        self.base_equity = 0.0
        self.locked_profit = 0.0
        self.load_config()

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

    def validate_trade(self, signal, account: AccountStatus):
        """Validates whether a new trade is allowed given current risk constraints."""
        profile = self.config.active_profile

        # 1. Check Max Open Positions
        if account.open_positions >= self.config.max_open_positions:
            return False, f"Max {profile} open positions reached ({self.config.max_open_positions})."

        # 2. Prevent Duplicate Trades on same symbol
        if signal.symbol in account.active_symbols:
            return False, f"Duplicate Trade: Position for {signal.symbol} already open."

        # 3. Check Daily Drawdown (Passive Stop)
        # If daily pnl is below the max allowed loss %, stop taking NEW trades
        max_loss_usd = account.equity * (self.config.max_daily_loss_pct / 100)
        if account.daily_pnl < -max_loss_usd and max_loss_usd > 0:
            return False, f"Passive Stop: Daily loss limit reached (${max_loss_usd:.2f})."

        # 3b. Dynamic Profit Lock Check (Trailing Floor)
        # We don't block trades here, but we ensure the floor is respected.
        # Logic is handled in validate_drawdown() which is called by the failsafe loop.

        # 4. Check Minimum Order Value
        # For MT5, we must multiply by contract size to get real face value.
        multiplier = 1.0
        if account.platform == "mt5":
            if "XAU" in signal.symbol or "XAG" in signal.symbol:
                multiplier = 100.0
            elif "BTC" in signal.symbol or "ETH" in signal.symbol:
                multiplier = 1.0 # Crypto usually 1 coin per lot
            elif "AAPL" in signal.symbol or "TSLA" in signal.symbol:
                multiplier = 1.0 # Stocks usually 1 share per lot
            else:
                multiplier = 100000.0 # Standard Forex Lot size
                
        order_value = signal.entry * signal.qty * multiplier
        if order_value < self.config.min_order_value_usd:
            return False, f"Order value ${order_value:.2f} too low (Min ${self.config.min_order_value_usd})."

        # 5. Check Correlation Risk
        correlation_groups = [
            {"BTC/USDT", "ETH/USDT", "SOL/USDT"},
            {"XAUUSD", "EURUSD"}
        ]
        
        for group in correlation_groups:
            if signal.symbol in group:
                active_correlated = group.intersection(set(account.active_symbols))
                # Block if we try to open a new correlated asset
                if active_correlated and signal.symbol not in active_correlated:
                    return False, f"Correlation Risk: Highly correlated asset(s) {list(active_correlated)} already open."

        return True, "Risk validation passed."

    def validate_drawdown(self, current_equity: float) -> tuple[bool, str]:
        """Checks for account-level hard stop based on peak drawdown AND Trailing Profit Lock."""
        
        # Initialize base equity if not set
        if self.base_equity <= 0:
            self.base_equity = current_equity
            self.peak_equity = current_equity
            return True, "Initial baseline established."

        # 1. Update Peak for standard % drawdown checks
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity

        # 2. Dynamic Profit Lock (Fortress Scale System)
        if self.config.enable_profit_lock:
            current_profit = current_equity - self.base_equity
            new_lock_level = 0
            
            # --- Tiered Milestone Logic ---
            if current_profit >= 1000:
                # 1k+ Tier: Lock in blocks of $1000
                new_lock_level = (current_profit // 1000) * 1000
            elif current_profit >= 800:
                new_lock_level = 800
            elif current_profit >= 500:
                new_lock_level = 500
            elif current_profit >= 200:
                new_lock_level = 200
            else:
                # Early Tier: Lock in blocks of $50
                new_lock_level = (current_profit // self.config.profit_lock_step_usd) * self.config.profit_lock_step_usd
            
            # Ensure we only move the lock UPWARD
            if new_lock_level > self.locked_profit:
                self.locked_profit = new_lock_level
                import logging
                logging.warning(f"🏦 FORTRESS MILESTONE REACHED: Profit locked at +${self.locked_profit:.2f}. This is now your permanent floor.")
            
            # Check against the Hard Floor
            hard_floor = self.base_equity + self.locked_profit
            
            if current_equity < hard_floor:
                return False, f"HARD STOP: Fortress Floor Violation. Equity ${current_equity:.2f} fell below locked floor ${hard_floor:.2f}."

        # 3. Standard Percentage Drawdown from Peak (Secondary Safety)
        drawdown_pct = ((self.peak_equity - current_equity) / self.peak_equity) * 100
        if drawdown_pct >= self.config.max_account_drawdown_pct:
            return False, f"HARD STOP: Max Peak Drawdown reached ({drawdown_pct:.1f}%)."
            
        return True, f"Risk Nominal. Floor: +${self.locked_profit:.2f} | Max DD: {drawdown_pct:.1f}%"

    def _calculate_multiplier(self, score: float) -> float:
        """Calculates risk multiplier based on score (70-100)."""
        if score <= 0: return 1.0
        min_s, max_s = 70.0, 100.0
        clipped_score = max(min_s, min(max_s, score))
        ratio = (clipped_score - min_s) / (max_s - min_s)
        return self.config.min_multiplier + (self.config.max_multiplier - self.config.min_multiplier) * ratio

    def calculate_position_size(self, symbol: str, account_equity: float, entry: float, stop_loss: float, score: float = 0.0) -> float:
        """
        Calculates qty based on asset-specific % risk, SL distance, and optional AI scaling.
        """
        # 1. Base Risk Calculation
        risk_pct = self.config.risk_per_asset.get(symbol, self.config.risk_per_asset.get("DEFAULT", 1.0))
        
        # Profile Multiplier
        profile = self.config.active_profile
        if profile == "CONSERVATIVE":
            risk_pct *= 0.5
        elif profile == "AGGRESSIVE":
            risk_pct *= 2.0
        
        # 2. Dynamic Scaling based on AI Confidence
        if symbol in self.config.ai_scaling_symbols and score > 0:
            multiplier = self._calculate_multiplier(score)
            risk_pct *= multiplier
            print(f"AI Profile ({profile}) Auto-Sizing: {symbol} score={score} | Multiplier={multiplier:.2f}x | Final Risk={risk_pct:.2f}%")
        
        risk_amt = account_equity * (risk_pct / 100)
        risk_per_unit = abs(entry - stop_loss)
        
        if risk_per_unit == 0:
            return 0.01
            
        qty = risk_amt / risk_per_unit

        # Convert from raw units to MT5 Lots (1 Lot = 100,000 units for Forex)
        # We use a simplified contract size detection
        contract_size = 100000.0
        if "XAU" in symbol or "XAG" in symbol: contract_size = 100.0
        elif "BTC" in symbol or "ETH" in symbol: contract_size = 1.0
        elif "AAPL" in symbol or "TSLA" in symbol: contract_size = 1.0

        lots = qty / contract_size
        
        # Adjust for typical lot increments (min 0.01)
        return max(0.01, round(lots, 2))
