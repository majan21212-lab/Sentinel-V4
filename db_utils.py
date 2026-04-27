import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()

# The database file will be created in the current working directory of the executable
DB_FILE = os.getenv('DB_NAME', 'trading_bot.db')
if not DB_FILE.endswith('.db'):
    DB_FILE += '.db'

def get_db_connection(database=None):
    """
    Establishes a connection to the local SQLite database.
    If database parameter is provided, it's ignored since SQLite uses the file local to the bot.
    """
    try:
        connection = sqlite3.connect(DB_FILE)
        return connection
    except sqlite3.Error as e:
        print(f"Error connecting to SQLite: {e}")
        return None

def setup_database():
    """
    Creates the database file and tables if they do not exist.
    """
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            
            # Create Table (SQLite syntax)
            create_table_query = """
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL,
                take_profit REAL,
                stop_loss REAL,
                timeframe TEXT,
                pattern TEXT,
                score REAL,
                outcome INTEGER DEFAULT 0, -- 1=Win, -1=Loss, 0=Pending
                ml_confidence REAL,
                indicators_meta TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            # Create Equity History Table (For Charting)
            create_history_query = """
            CREATE TABLE IF NOT EXISTS equity_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                total_equity REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            # Create Transactions Table (For Audit Trail)
            create_transactions_query = """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL, -- 'deposit', 'withdraw', 'reset'
                amount REAL,
                balance_before REAL,
                balance_after REAL,
                status TEXT DEFAULT 'success',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            cursor.execute(create_table_query)
            cursor.execute(create_history_query)
            cursor.execute(create_transactions_query)
            conn.commit()
            print("Database tables check/creation successful using SQLite.")
            
            cursor.close()
            conn.close()
            print("Database setup completed (Serverless portable DB).")
        else:
            print("Failed to connect to the portable SQLite database.")

    except sqlite3.Error as e:
        print(f"Error during SQLite database setup: {e}")

def log_transaction(tx_type, amount, balance_before, balance_after, status='success'):
    """Logs a funding transaction to the database."""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transactions (type, amount, balance_before, balance_after, status)
                VALUES (?, ?, ?, ?, ?)
            """, (tx_type, amount, balance_before, balance_after, status))
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        print(f"Error logging transaction: {e}")
    return False

if __name__ == "__main__":
    setup_database()
