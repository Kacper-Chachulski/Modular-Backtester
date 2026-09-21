import sqlite3
from datetime import date, timedelta
from pathlib import Path


class SQLiteBarStore:
    def __init__(self, path: str | Path = "data/backtester.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS daily_bars (
                symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL NOT NULL, high REAL NOT NULL,
                low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL,
                PRIMARY KEY (symbol, date))""")

    def _connect(self): return sqlite3.connect(self.path)

    def upsert(self, symbol: str, bars: list[dict]) -> None:
        with self._connect() as conn:
            conn.executemany("INSERT OR REPLACE INTO daily_bars VALUES (?, ?, ?, ?, ?, ?, ?)", [
                (symbol.upper(), b["date"], b["open"], b["high"], b["low"], b["close"], b["volume"]) for b in bars])

    def load(self, symbol: str, start: str, end: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT date, open, high, low, close, volume FROM daily_bars WHERE symbol=? AND date BETWEEN ? AND ? ORDER BY date", (symbol.upper(), start, end)).fetchall()
        return [dict(zip(("date", "open", "high", "low", "close", "volume"), row)) for row in rows]

    def covers(self, symbol: str, start: str, end: str) -> bool:
        """Whether the symbol cache spans the requested range (dates are ISO sortable)."""
        with self._connect() as conn:
            first, last = conn.execute(
                "SELECT MIN(date), MAX(date) FROM daily_bars WHERE symbol=?", (symbol.upper(),)
            ).fetchone()
        # Data sources use an exclusive end date, and an end can land on a weekend/holiday.
        required_last = (date.fromisoformat(end) - timedelta(days=4)).isoformat()
        return first is not None and first <= start and last >= required_last
