import os
import json
import logging
import pandas as pd
from datetime import datetime, timedelta

class CortexOptimizer:
    """
    Cortex: The Self-Evolving Brain of Jewel Elite.
    This prototype analyzes trade history and dynamically optimizes risk multipliers.
    """
    def __init__(self, history_path="trade_history.json"):
        self.history_path = history_path
        self.config_path = "config.json"
        logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | CORTEX | %(message)s')
        self.logger = logging.getLogger("Cortex")

    def analyze_performance(self):
        """Analyze the last 24 hours of trading to find the ideal risk profile."""
        if not os.path.exists(self.history_path):
            self.logger.warning("No trade history found. Using default multipliers.")
            return 1.0  # Default multiplier

        try:
            with open(self.history_path, 'r') as f:
                history = json.load(f)
            
            df = pd.DataFrame(history)
            if df.empty: return 1.0

            # Filter for last 24 hours
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            last_24h = df[df['timestamp'] > (datetime.now() - timedelta(days=1))]
            
            if last_24h.empty:
                self.logger.info("Insufficient data for 24h optimization. Checking all-time.")
                last_24h = df

            win_rate = len(last_24h[last_24h['pnl'] > 0]) / len(last_24h)
            avg_pnl = last_24h['pnl'].mean()

            self.logger.info(f"Performance Analysis: Win Rate: {win_rate:.2%}, Avg PnL: {avg_pnl:.2f}")

            # Calculate Sharpe Ratio (Simplified)
            if len(last_24h) > 5:
                # Assume 'pnl' is the absolute return; convert to percentage if equity is known
                # For this simplified model, we use the volatility of PnL
                pnl_std = last_24h['pnl'].std()
                if pnl_std > 0:
                    sharpe = (avg_pnl / pnl_std) * (252 ** 0.5) # Annualized approximation
                else:
                    sharpe = 0
            else:
                sharpe = 0

            self.logger.info(f"Performance Analysis: Win Rate: {win_rate:.2%}, Avg PnL: {avg_pnl:.2f}, Sharpe: {sharpe:.2f}")

            # Self-Evolving Logic:
            # If Win Rate > 60% AND Sharpe > 1.5, increase risk.
            # If Win Rate < 40% OR Sharpe < 0.5, decrease risk.
            if win_rate > 0.6 and sharpe > 1.5:
                new_multiplier = 1.25  # Aggressive growth
            elif win_rate < 0.4 or sharpe < 0.5:
                new_multiplier = 0.50  # Defensive mode
            else:
                new_multiplier = 1.0    # Neutral stability

            return new_multiplier

        except Exception as e:
            self.logger.error(f"Analysis Failed: {e}")
            return 1.0

    def evolve_config(self, multiplier):
        """Rewrite the bot's configuration with the optimized multiplier."""
        try:
            config = {}
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    config = json.load(f)

            config['risk_multiplier'] = multiplier
            config['last_evolution'] = datetime.now().isoformat()
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            self.logger.info(f"Evolution Complete. Risk Multiplier set to: {multiplier}x")
            return True
        except Exception as e:
            self.logger.error(f"Evolution Failed: {e}")
            return False

    def run_cycle(self):
        """One full cycle of the Cortex brain."""
        self.logger.info("Initializing Evolution Cycle...")
        multiplier = self.analyze_performance()
        success = self.evolve_config(multiplier)
        return success

if __name__ == "__main__":
    cortex = CortexOptimizer()
    cortex.run_cycle()
