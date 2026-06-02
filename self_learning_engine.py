import logging
import pandas as pd
from db_utils import get_db_connection

log = logging.getLogger(__name__)

class SelfLearningEngine:
    def __init__(self):
        self.stats = {}
        self.min_samples = 5 # Minimum trades before we trust the learning
        self.update_learning()

    def update_learning(self):
        """Analyzes historical signals to identify top-performing pattern/asset pairs."""
        try:
            conn = get_db_connection()
            # Query outcomes (1=Win, -1=Loss)
            query = "SELECT symbol, pattern, outcome FROM signals WHERE outcome != 0"
            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                log.info("Self-Learning: No trade history yet. Using default biases.")
                return

            # Group by Symbol & Pattern
            stats = df.groupby(['symbol', 'pattern']).agg(
                wins=('outcome', lambda x: (x == 1).sum()),
                total=('outcome', 'count')
            )
            
            stats['win_rate'] = stats['wins'] / stats['total']
            
            # Convert to a nested dict for fast lookup: {symbol: {pattern: win_rate}}
            self.stats = {}
            for (symbol, pattern), row in stats.iterrows():
                if symbol not in self.stats: self.stats[symbol] = {}
                self.stats[symbol][pattern] = {
                    "win_rate": row['win_rate'],
                    "total": row['total']
                }
            
            log.info(f"🧠 Self-Learning: Analysis complete for {len(self.stats)} assets.")
        except Exception as e:
            log.error(f"Self-Learning Analysis Error: {e}")

    def get_strategy_multiplier(self, symbol: str, pattern: str) -> float:
        """
        Returns a risk multiplier (0.5 to 1.5) based on historical accuracy.
        - High Win Rate (>65%) -> 1.25x Risk
        - Elite Win Rate (>75%) -> 1.5x Risk
        - Poor Win Rate (<45%) -> 0.75x Risk
        - Failing Win Rate (<35%) -> 0.5x Risk
        """
        asset_stats = self.stats.get(symbol, {}).get(pattern)
        
        if not asset_stats or asset_stats['total'] < self.min_samples:
            return 1.0 # Default risk for new strategies

        wr = asset_stats['win_rate']
        
        if wr >= 0.75: return 1.5
        if wr >= 0.65: return 1.25
        if wr <= 0.35: return 0.5
        if wr <= 0.45: return 0.75
        
        return 1.0

# Singleton instance
self_learning = SelfLearningEngine()
