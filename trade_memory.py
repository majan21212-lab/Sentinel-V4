"""
trade_memory.py — TradeBot v3.1 Elite
Persistent SQLite memory layer: logs every trade, tracks win/loss per symbol,
and blocks repeat trades on chronically losing pairs.
"""

import os
import sqlite3
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# ── Database path (sits next to this file in VPS_Deployment) ─────────────────
_DB_PATH = Path(__file__).parent / "tradebot_memory.db"
_lock    = threading.Lock()


# ── Schema bootstrap ─────────────────────────────────────────────────────────

def _init_db():
    """Create tables if they don't exist yet."""
    with sqlite3.connect(_DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol      TEXT    NOT NULL,
                direction   TEXT    NOT NULL,
                entry       REAL,
                sl          REAL,
                tp          REAL,
                qty         REAL,
                score       REAL,
                broker      TEXT,
                ticket      TEXT,
                status      TEXT    DEFAULT 'OPEN',   -- OPEN | WIN | LOSS | CANCELLED
                pnl         REAL    DEFAULT 0.0,
                opened_at   TEXT    NOT NULL,
                closed_at   TEXT
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS symbol_stats (
                symbol      TEXT    PRIMARY KEY,
                total       INTEGER DEFAULT 0,
                wins        INTEGER DEFAULT 0,
                losses      INTEGER DEFAULT 0,
                consec_loss INTEGER DEFAULT 0,
                last_updated TEXT
            )
        """)
        con.commit()
    log.info("TradeMemory: database initialised at %s", _DB_PATH)


# ── Public API ────────────────────────────────────────────────────────────────

def log_trade(signal, broker: str = "mt5", ticket: str = "") -> int:
    """
    Record a newly executed trade.
    Returns the new trade's database ID.
    """
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    tp_val  = getattr(signal, "tp1", getattr(signal, "tp", None))
    sl_val  = getattr(signal, "sl", None)

    with _lock, sqlite3.connect(_DB_PATH) as con:
        cur = con.execute("""
            INSERT INTO trades (symbol, direction, entry, sl, tp, qty, score, broker, ticket, opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal.symbol,
            str(signal.direction),
            float(getattr(signal, "entry", 0)),
            float(sl_val)  if sl_val  else None,
            float(tp_val)  if tp_val  else None,
            float(getattr(signal, "qty", 0)),
            float(getattr(signal, "score", 0)),
            broker,
            str(ticket),
            now,
        ))
        trade_id = cur.lastrowid
        con.commit()

    # Update symbol stats — new open trade, no outcome yet
    _upsert_stats(signal.symbol, outcome=None)
    log.info("TradeMemory: logged trade #%d for %s", trade_id, signal.symbol)
    return trade_id


def mark_trade_closed(trade_id: int, status: str, pnl: float = 0.0):
    """
    Mark a trade WIN or LOSS once MT5 closes it.
    status must be 'WIN' or 'LOSS'.
    """
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()

    with _lock, sqlite3.connect(_DB_PATH) as con:
        row = con.execute("SELECT symbol FROM trades WHERE id=?", (trade_id,)).fetchone()
        if not row:
            log.warning("TradeMemory: trade #%d not found to close.", trade_id)
            return
        symbol = row[0]
        con.execute("""
            UPDATE trades SET status=?, pnl=?, closed_at=? WHERE id=?
        """, (status.upper(), pnl, now, trade_id))
        con.commit()

    _upsert_stats(symbol, outcome=status.upper())
    log.info("TradeMemory: trade #%d closed as %s (PnL: %.2f)", trade_id, status, pnl)


def should_skip_symbol(symbol: str) -> tuple[bool, str]:
    """
    Returns (True, reason) if the bot should skip trading this symbol,
    or (False, "") if it is safe to trade.

    Skip conditions:
      1. Win rate < 40% over last 20 completed trades for this symbol.
      2. 3 or more consecutive losses with no win in between.
    """
    _ensure_init()

    with _lock, sqlite3.connect(_DB_PATH) as con:
        row = con.execute("""
            SELECT total, wins, losses, consec_loss FROM symbol_stats WHERE symbol=?
        """, (symbol,)).fetchone()

    if not row:
        return False, ""  # No history → allow trade

    total, wins, losses, consec_loss = row

    # Need at least 5 completed trades before we start blocking
    completed = wins + losses
    if completed < 5:
        return False, ""

    # Rule 1: 3+ consecutive losses
    if consec_loss >= 3:
        reason = f"⚠️ {symbol} has {consec_loss} consecutive losses. Cooling off."
        log.warning("TradeMemory: SKIP %s — %s", symbol, reason)
        return True, reason

    # Rule 2: Win rate below 40% (only checked after 10+ completed trades)
    if completed >= 10:
        win_rate = wins / completed
        if win_rate < 0.40:
            reason = f"⚠️ {symbol} win rate is {win_rate:.0%} over {completed} trades. Too low."
            log.warning("TradeMemory: SKIP %s — %s", symbol, reason)
            return True, reason

    return False, ""


def get_summary() -> list[dict]:
    """Return a list of dicts with per-symbol performance stats for the dashboard."""
    _ensure_init()

    with _lock, sqlite3.connect(_DB_PATH) as con:
        rows = con.execute("""
            SELECT symbol, total, wins, losses, consec_loss, last_updated
            FROM symbol_stats ORDER BY losses DESC
        """).fetchall()

    results = []
    for r in rows:
        symbol, total, wins, losses, consec_loss, updated = r
        completed = wins + losses
        win_rate = (wins / completed * 100) if completed > 0 else 0
        results.append({
            "symbol":      symbol,
            "total":       total,
            "wins":        wins,
            "losses":      losses,
            "win_rate":    f"{win_rate:.1f}%",
            "consec_loss": consec_loss,
            "last_updated": updated,
        })
    return results


def get_recent_trades(limit: int = 20) -> list[dict]:
    """Return the most recent N trades for dashboard display."""
    _ensure_init()

    with _lock, sqlite3.connect(_DB_PATH) as con:
        rows = con.execute("""
            SELECT id, symbol, direction, entry, sl, tp, qty, status, pnl, opened_at, closed_at
            FROM trades ORDER BY opened_at DESC LIMIT ?
        """, (limit,)).fetchall()

    keys = ["id", "symbol", "direction", "entry", "sl", "tp", "qty", "status", "pnl", "opened_at", "closed_at"]
    return [dict(zip(keys, r)) for r in rows]


# ── MT5 Position Reconciler ───────────────────────────────────────────────────

def reconcile_with_mt5():
    """
    Scan MT5 closed deals and mark matching open trades as WIN or LOSS.
    Call this once per CHECK_INTERVAL from your main loop.
    """
    _ensure_init()
    try:
        import MetaTrader5 as mt5
        import math

        # Pull deals from the last 30 days
        from datetime import timedelta
        date_from = datetime.now(timezone.utc) - timedelta(days=30)
        deals = mt5.history_deals_get(date_from, datetime.now(timezone.utc))
        if deals is None:
            return

        # Build a map of ticket → (profit, symbol)
        deal_map: dict[int, tuple[float, str]] = {}
        for d in deals:
            if d.entry == 1:  # 1 = exit deal
                deal_map[d.position_id] = (d.profit, d.symbol)

        with _lock, sqlite3.connect(_DB_PATH) as con:
            open_trades = con.execute("""
                SELECT id, ticket, symbol FROM trades WHERE status='OPEN'
            """).fetchall()

            for trade_id, ticket, symbol in open_trades:
                if not ticket:
                    continue
                try:
                    pos_id = int(ticket)
                except ValueError:
                    continue

                if pos_id in deal_map:
                    pnl, _ = deal_map[pos_id]
                    status = "WIN" if pnl >= 0 else "LOSS"
                    now    = datetime.now(timezone.utc).isoformat()
                    con.execute("""
                        UPDATE trades SET status=?, pnl=?, closed_at=? WHERE id=?
                    """, (status, pnl, now, trade_id))
                    con.commit()
                    _upsert_stats(symbol, outcome=status)
                    log.info(
                        "TradeMemory: reconciled trade #%d (ticket %s) → %s (PnL: %.2f)",
                        trade_id, ticket, status, pnl
                    )

    except Exception as exc:
        log.warning("TradeMemory: MT5 reconcile failed: %s", exc)


# ── Internal helpers ──────────────────────────────────────────────────────────

_initialised = False

def _ensure_init():
    global _initialised
    if not _initialised:
        _init_db()
        _initialised = True


def _upsert_stats(symbol: str, outcome: str | None):
    """Update the per-symbol stats table after a trade event."""
    now = datetime.now(timezone.utc).isoformat()

    with _lock, sqlite3.connect(_DB_PATH) as con:
        existing = con.execute(
            "SELECT total, wins, losses, consec_loss FROM symbol_stats WHERE symbol=?",
            (symbol,)
        ).fetchone()

        if existing:
            total, wins, losses, consec_loss = existing
        else:
            total, wins, losses, consec_loss = 0, 0, 0, 0

        total += 1

        if outcome == "WIN":
            wins       += 1
            consec_loss = 0   # reset streak on a win
        elif outcome == "LOSS":
            losses     += 1
            consec_loss += 1
        # outcome=None means just opened, no change to win/loss

        con.execute("""
            INSERT INTO symbol_stats (symbol, total, wins, losses, consec_loss, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                total       = excluded.total,
                wins        = excluded.wins,
                losses      = excluded.losses,
                consec_loss = excluded.consec_loss,
                last_updated= excluded.last_updated
        """, (symbol, total, wins, losses, consec_loss, now))
        con.commit()


# ── Module self-test ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _init_db()
    print("TradeMemory database created at:", _DB_PATH)
    print("Summary:", get_summary())
