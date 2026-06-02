import sqlite3
import pandas as pd
from datetime import datetime
import os
from db_utils import get_db_connection

def generate_institutional_report():
    print("Generating Sentinel V4 Performance Report...")
    print("--------------------------------------------")
    
    conn = get_db_connection()
    if not conn:
        print("Error: Could not connect to database.")
        return

    # 1. Overall Stats
    query = "SELECT * FROM signals WHERE outcome != 0"
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        print("No resolved trades found in the database yet.")
        conn.close()
        return

    total_trades = len(df)
    wins = len(df[df['outcome'] == 1])
    losses = len(df[df['outcome'] == -1])
    win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
    
    # 2. Pattern Performance
    pattern_stats = df.groupby('pattern').agg(
        trades=('outcome', 'count'),
        wins=('outcome', lambda x: (x == 1).sum())
    )
    pattern_stats['win_rate'] = (pattern_stats['wins'] / pattern_stats['trades']) * 100

    # 3. Asset Performance
    asset_stats = df.groupby('symbol').agg(
        trades=('outcome', 'count'),
        wins=('outcome', lambda x: (x == 1).sum())
    )
    asset_stats['win_rate'] = (asset_stats['wins'] / asset_stats['trades']) * 100

    # 4. Recent Equity Trend
    equity_query = "SELECT total_equity, timestamp FROM equity_history ORDER BY id DESC LIMIT 20"
    equity_df = pd.read_sql_query(equity_query, conn)
    
    conn.close()

    # --- Print Report ---
    print(f"Total Resolved Trades: {total_trades}")
    print(f"Overall Win Rate:     {win_rate:.1f}%")
    print(f"Net Outcome:          {wins} Wins / {losses} Losses")
    print("--------------------------------------------")
    
    print("Top Performing Patterns:")
    for pattern, row in pattern_stats.sort_values(by='win_rate', ascending=False).iterrows():
        print(f" * {pattern:15}: {row['win_rate']:>5.1f}% ({int(row['trades'])} trades)")
    
    print("\nTop Performing Assets:")
    for asset, row in asset_stats.sort_values(by='win_rate', ascending=False).iterrows():
        print(f" * {asset:15}: {row['win_rate']:>5.1f}% ({int(row['trades'])} trades)")
    
    print("--------------------------------------------")
    if not equity_df.empty:
        start_equity = equity_df['total_equity'].iloc[-1]
        curr_equity = equity_df['total_equity'].iloc[0]
        change = ((curr_equity - start_equity) / start_equity) * 100
        print(f"Recent Equity Drift:   {change:+.2f}% (${curr_equity:.2f})")
    
    print(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    generate_institutional_report()
