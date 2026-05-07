import asyncio
import os
import json
from datetime import datetime
from models import Signal, ExplainabilityReport
from db_utils import setup_database, get_db_connection

async def test_injection():
    print("Initializing Test Database...")
    setup_database()
    
    # Create a mock explainability report
    report = ExplainabilityReport(
        summary="Bullish SMC setup confirmed by liquidity sweep at 2345.50.",
        key_factors=[
            "Institutional order block mitigation",
            "RSI Bullish Divergence on M15",
            "Liquidity sweep of previous day low"
        ],
        liquidity_analysis="Sell-side liquidity cleared below 2340.00 level.",
        market_structure="BOS (Break of Structure) confirmed on M5 timeframe.",
        ai_confidence_score=0.92
    )
    
    # Create a signal with this report
    signal = Signal(
        symbol="XAUUSDm",
        direction="LONG",
        entry=2350.75,
        stop_loss=2335.00,
        take_profit=2385.00,
        pattern="Institutional Sweep",
        score=92.0,
        explainability=report
    )
    
    print(f"Injecting Signal for {signal.symbol} with AI Rationale...")
    
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO signals (symbol, direction, entry_price, take_profit, stop_loss, timeframe, pattern, score, ml_confidence, indicators_meta, ai_rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal.symbol, signal.direction, signal.entry,
            signal.tp1, signal.sl, "M5",
            signal.pattern, signal.score, 0.92,
            "Test Injection", signal.explainability.json()
        ))
        conn.commit()
        conn.close()
    print("Signal Injected successfully!")

    # Also update shared_state.json to show an active trade with P&L
    script_dir = os.path.dirname(os.path.abspath(__file__))
    state_file = os.path.join(script_dir, "shared_state.json")
    try:
        with open(state_file, "r") as f:
            state_data = json.load(f)
        
        active_trade = {
            "ticket": 123456,
            "symbol": "XAUUSDm",
            "direction": "LONG",
            "entry": 2350.75,
            "tp": 2385.00,
            "sl": 2335.00,
            "qty": 0.1,
            "pnl": 125.50,
            "status": "ACTIVE",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        state_data["active_trades"] = [active_trade]
        with open(state_file, "w") as f:
            json.dump(state_data, f, indent=4)
        print("Updated shared_state.json with active trade.")
    except Exception as e:
        print(f"Failed to update shared_state.json: {e}")

if __name__ == "__main__":
    asyncio.run(test_injection())
