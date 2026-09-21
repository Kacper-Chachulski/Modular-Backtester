from abc import ABC, abstractmethod
from datetime import date


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_daily(self, symbol: str, start: date, end: date) -> list[dict]:
        """Return normalized OHLCV bars."""


class YahooFinanceProvider(MarketDataProvider):
    def fetch_daily(self, symbol: str, start: date, end: date) -> list[dict]:
        import yfinance as yf

        frame = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
        if frame.empty:
            raise ValueError(f"No daily data returned for {symbol}")
        # yfinance may return a single-symbol MultiIndex frame.
        if getattr(frame.columns, "nlevels", 1) > 1:
            frame.columns = frame.columns.get_level_values(0)
        return [
            {"date": index.date().isoformat(), "open": float(row["Open"]), "high": float(row["High"]),
             "low": float(row["Low"]), "close": float(row["Close"]), "volume": float(row["Volume"])}
            for index, row in frame.iterrows()
        ]
