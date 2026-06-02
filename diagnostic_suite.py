import os
import sys
import json
import logging
import asyncio
import pandas as pd
import sqlite3
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("DIAGNOSTIC")

def run_coding_tests():
    log.info("--- [CODING] Verification ---")
    try:
        import app
        import execution_layer
        import state_manager
        import strategy
        import patterns_engine
        import ml_validator
        log.info("Core modules imported successfully.")
        
        # Test models
        from models import Signal
        sig = Signal(symbol="BTCUSDm", direction="LONG", entry=50000, stop_loss=49000, take_profit=52000)
        log.info("Pydantic models validated.")
        
        return True
    except Exception as e:
        log.error(f"❌ Coding test failed: {e}")
        return False

def run_connectivity_tests():
    log.info("--- [CONNECTIVITY] Verification ---")
    success = True
    
    # 1. Database
    try:
        db_name = os.getenv("DB_NAME", "said alalawi.db")
        if not db_name.endswith(".db"): db_name += ".db"
        conn = sqlite3.connect(db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [t[0] for t in cursor.fetchall()]
        log.info(f"Database connected. Tables: {tables}")
        conn.close()
    except Exception as e:
        log.error(f"❌ DB Connectivity failed: {e}")
        success = False

    # 2. MT5
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            log.error(f"❌ MT5 Init failed: {mt5.last_error()}")
            success = False
        else:
            acc = mt5.account_info()
            if acc:
                log.info(f"MT5 Connected. Account: {acc.login}, Balance: {acc.balance}")
            else:
                log.error("❌ MT5 connected but failed to fetch account info.")
                success = False
            # mt5.shutdown() # Keep it open as the bot might be using it
    except Exception as e:
        log.error(f"❌ MT5 connectivity failed: {e}")
        success = False

    return success

async def run_communication_tests():
    log.info("--- [COMMUNICATION] Verification ---")
    import requests
    success = True
    
    # 1. API Status
    try:
        resp = requests.get("http://localhost:8000/api/status")
        if resp.status_code == 200:
            log.info("Dashboard API is responsive.")
        else:
            log.error(f"❌ Dashboard API returned status {resp.status_code}")
            success = False
    except Exception as e:
        log.error(f"❌ Dashboard API communication failed: {e}")
        success = False
        
    return success

def run_synchronization_tests():
    log.info("--- [SYNCHRONIZING] Verification ---")
    import state_manager as state
    success = True
    
    try:
        # Test memory to disk sync
        test_val = f"TEST_{datetime.now().timestamp()}"
        state.SHARED_DATA["status"] = test_val
        state.save_shared_state(state.SHARED_DATA)
        
        with open("shared_state.json", "r") as f:
            disk_data = json.load(f)
            if disk_data.get("status") == test_val:
                log.info("State synchronization (Memory -> Disk) successful.")
            else:
                log.error("❌ State sync failed: Disk does not match Memory.")
                success = False
                
        # Revert status
        state.SHARED_DATA["status"] = "ONLINE"
        state.save_shared_state(state.SHARED_DATA)
        
    except Exception as e:
        log.error(f"❌ Synchronization test failed: {e}")
        success = False
        
    return success

def run_logic_tests():
    log.info("--- [LOGIC] Verification ---")
    success = True
    
    # 1. Pattern Detection Logic
    try:
        from patterns_engine import PatternsEngine
        import numpy as np
        
        # Create dummy bullish engulfing/liquidity sweep data
        dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
        df = pd.DataFrame({
            'open': np.linspace(100, 105, 100),
            'high': np.linspace(101, 106, 100),
            'low': np.linspace(99, 104, 100),
            'close': np.linspace(100.5, 105.5, 100),
            'volume': np.random.randint(100, 1000, 100)
        }, index=dates)
        
        engine = PatternsEngine(m5_df=df)
        patterns = engine.detect_patterns()
        log.info(f"Patterns Engine initialized and ran. Detected: {patterns.get('pattern') if patterns else 'None'}")
    except Exception as e:
        log.error(f"❌ Patterns Logic test failed: {e}")
        success = False

    # 2. ML Validation Logic
    try:
        from ml_validator import MLValidator
        validator = MLValidator()
        # Mock signal
        mock_signal = {"direction": "LONG", "score": 85, "pattern": "BULLISH_ENGULFING"}
        conf = validator.predict_confidence(mock_signal)
        log.info(f"ML Validator running. Confidence score: {conf:.2f}")
    except Exception as e:
        log.error(f"❌ ML Logic test failed: {e}")
        success = False

    return success

async def main():
    log.info("🚀 STARTING SENTINEL V4 DIAGNOSTIC SUITE")
    print("="*50)
    
    results = {
        "Coding": run_coding_tests(),
        "Connectivity": run_connectivity_tests(),
        "Communication": await run_communication_tests(),
        "Synchronization": run_synchronization_tests(),
        "Logic": run_logic_tests()
    }
    
    print("="*50)
    log.info("FINAL DIAGNOSTIC RESULTS:")
    for test, res in results.items():
        status = "[PASS]" if res else "[FAIL]"
        print(f"{test:<15}: {status}")
    
    if all(results.values()):
        log.info("ALL SYSTEMS NOMINAL. BOT IS PRODUCTION-READY.")
    else:
        log.warning("SOME TESTS FAILED. PLEASE REVIEW LOGS ABOVE.")

if __name__ == "__main__":
    asyncio.run(main())
