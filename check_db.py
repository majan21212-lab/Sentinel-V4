import sqlite3
import os

db_path = r"c:\Users\OTTSF\OneDrive\Documents\Fleet Dashboard Overview\backend\Sentinel-V4\trading_bot.db"

def check_db():
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("--- Stats ---")
    cursor.execute("SELECT COUNT(*) FROM signals")
    print(f"Total signals: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT outcome, COUNT(*) FROM signals GROUP BY outcome")
    for row in cursor.fetchall():
        print(f"Outcome {row[0]}: {row[1]}")
    
    print("\n--- Recent Signals ---")
    cursor.execute("SELECT id, symbol, outcome, ml_confidence FROM signals ORDER BY id DESC LIMIT 5")
    for row in cursor.fetchall():
        print(row)
    
    conn.close()

if __name__ == "__main__":
    check_db()
