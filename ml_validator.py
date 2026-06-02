import logging
import numpy as np
from sklearn.ensemble import RandomForestClassifier

log = logging.getLogger(__name__)

import logging
import sqlite3
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from db_utils import get_db_connection

log = logging.getLogger(__name__)

class MLValidator:
    def __init__(self):
        self.is_trained = False
        self.total_samples = 0
        self.model = RandomForestClassifier(n_estimators=50, random_state=42)
        log.info("🤖 MLValidator initializing...")
        self.retrain_model()

    def _prepare_features(self, df):
        """Standardizes feature engineering for both training and prediction."""
        # Encode Pattern types (simple mapping or categorical)
        pattern_map = {"SMC_STRUCTURE": 1, "FVG_BULL": 2, "FVG_BEAR": 3, "OB_BULL": 4, "OB_BEAR": 5, "LIQUIDITY_DEMAND": 6, "LIQUIDITY_SUPPLY": 7, "WATERFALL_BULL": 8, "WATERFALL_BEAR": 9}
        
        df['pattern_encoded'] = df['pattern'].map(pattern_map).fillna(0)
        df['direction_encoded'] = df['direction'].apply(lambda x: 1 if x == "LONG" else 0)
        
        return df[['score', 'pattern_encoded', 'direction_encoded']]

    def retrain_model(self):
        """Fetches real historical results from DB and trains the model."""
        try:
            conn = get_db_connection()
            # Only train on resolved trades (outcome 1 or -1)
            query = "SELECT score, pattern, direction, outcome FROM signals WHERE outcome != 0"
            df = pd.read_sql_query(query, conn)
            conn.close()

            if len(df) < 10:
                log.info(f"ML: Not enough data ({len(df)}/10). Using bootstrap mode.")
                self._fit_synthetic_model()
                return

            X = self._prepare_features(df)
            y = df['outcome'].apply(lambda x: 1 if x == 1 else 0) # 1=Good, 0=Bad

            self.model.fit(X, y)
            self.is_trained = True
            self.total_samples = len(df)
            log.info(f"✅ MLValidator trained on {len(df)} REAL historical results.")
        except Exception as e:
            log.error(f"Error training ML model: {e}")
            self._fit_synthetic_model()

    def _fit_synthetic_model(self):
        """Fallback: Trains on a synthetic dataset."""
        np.random.seed(42)
        n_samples = 100
        X = pd.DataFrame({
            'score': np.random.uniform(40, 100, n_samples),
            'pattern': ['SMC_STRUCTURE'] * n_samples,
            'direction': np.random.choice(['LONG', 'SHORT'], n_samples)
        })
        X_encoded = self._prepare_features(X)
        y = np.where(X['score'] > 75, 1, 0)
        
        self.model.fit(X_encoded, y)
        self.is_trained = True
        log.info("ML: Synthetic bootstrap model trained.")

    def predict_confidence(self, signal_dict: dict) -> float:
        """Predicts confidence for a new signal based on real history."""
        if not self.is_trained: return 0.5
            
        try:
            # Create a single-row dataframe for the features
            df = pd.DataFrame([signal_dict])
            X = self._prepare_features(df)
            
            probabilities = self.model.predict_proba(X)
            confidence = probabilities[0][1]
            
            log.info(f"🤖 ML Confidence for {signal_dict.get('pattern')}: {confidence*100:.1f}%")
            return confidence
        except Exception as e:
            log.warning(f"ML Prediction failed: {e}")
            return 0.5

    def record_outcome(self, ticket: int, outcome: int):
        """
        Updates the outcome of a signal in the DB and triggers a model refresh.
        Outcome: 1 (Win), -1 (Loss)
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE signals SET outcome = ? WHERE ticket = ? OR id = (SELECT id FROM signals WHERE symbol = ? AND outcome = 0 ORDER BY id DESC LIMIT 1)", (outcome, ticket, ticket))
            conn.commit()
            conn.close()
            
            # Retrain if we have enough new samples
            log.info(f"ML: Recorded outcome {outcome} for trade {ticket}. Refreshing Intelligence...")
            self.retrain_model()
        except Exception as e:
            log.error(f"Error recording ML outcome: {e}")
