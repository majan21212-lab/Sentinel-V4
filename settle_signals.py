import sqlite3
import os
import random

db_path = r"c:\Users\OTTSF\OneDrive\Documents\Fleet Dashboard Overview\backend\Sentinel-V4\trading_bot.db"

def settle_signals():
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Settle 30 signals: 25 wins, 5 losses
    print("Settling signals for testing...")
    
    # Get IDs of open signals
    cursor.execute("SELECT id FROM signals WHERE outcome = 0 LIMIT 30")
    ids = [row[0] for row in cursor.fetchall()]
    
    for i, sig_id in enumerate(ids):
        outcome = 1 if i < 25 else -1
        profit = random.uniform(50, 150) if outcome == 1 else random.uniform(-100, -30)
        
        cursor.execute("""
            UPDATE signals 
            SET outcome = ?, profit = ?
            WHERE id = ?
        """, (outcome, round(profit, 2), sig_id))
    
    conn.commit()
    print(f"Settled {len(ids)} signals.")
    
    # Verify
    cursor.execute("SELECT outcome, COUNT(*) FROM signals GROUP BY outcome")
    for row in cursor.fetchall():
        print(f"Outcome {row[0]}: {row[1]}")
        
    conn.close()

if __name__ == "__main__":
    settle_signals()
