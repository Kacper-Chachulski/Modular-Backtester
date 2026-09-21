import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


class SQLiteBarStore:
    """Local OHLCV cache with explicit provider coverage metadata."""

    def __init__(self, path: str | Path = "data/backtester.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS daily_bars (
                symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL NOT NULL, high REAL NOT NULL,
                low REAL NOT NULL, close REAL NOT NULL, volume REAL NOT NULL,
                PRIMARY KEY (symbol, date))""")
            conn.execute("""CREATE TABLE IF NOT EXISTS downloaded_ranges (
                source TEXT NOT NULL, symbol TEXT NOT NULL, start_date TEXT NOT NULL,
                end_date TEXT NOT NULL, downloaded_at TEXT NOT NULL,
                PRIMARY KEY (source, symbol, start_date, end_date))""")
            conn.commit()

    def _connect(self):
        return sqlite3.connect(self.path)

    def upsert(self, symbol: str, bars: list[dict]) -> None:
        with closing(self._connect()) as conn:
            conn.executemany("INSERT OR REPLACE INTO daily_bars VALUES (?, ?, ?, ?, ?, ?, ?)", [
                (symbol.upper(), b["date"], b["open"], b["high"], b["low"], b["close"], b["volume"])
                for b in bars
            ])
            conn.commit()

    def record_download(self, source: str, symbol: str, start: str, end: str) -> None:
        """Record an exact half-open [start, end) interval returned by a provider."""
        with closing(self._connect()) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO downloaded_ranges VALUES (?, ?, ?, ?, ?)",
                (source, symbol.upper(), start, end, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def load(self, symbol: str, start: str, end: str) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT date, open, high, low, close, volume FROM daily_bars "
                "WHERE symbol=? AND date >= ? AND date < ? ORDER BY date",
                (symbol.upper(), start, end),
            ).fetchall()
        return [dict(zip(("date", "open", "high", "low", "close", "volume"), row)) for row in rows]

    def covers(self, source: str, symbol: str, start: str, end: str) -> bool:
        """True only if merged downloaded intervals completely cover [start, end)."""
        with closing(self._connect()) as conn:
            ranges = conn.execute(
                "SELECT start_date, end_date FROM downloaded_ranges "
                "WHERE source=? AND symbol=? AND end_date > ? AND start_date < ? "
                "ORDER BY start_date",
                (source, symbol.upper(), start, end),
            ).fetchall()
        covered_until = start
        for range_start, range_end in ranges:
            if range_start > covered_until:
                return False
            if range_end > covered_until:
                covered_until = range_end
            if covered_until >= end:
                return True
        return False
