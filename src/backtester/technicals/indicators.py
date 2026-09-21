from collections.abc import Sequence


def _native():
    try:
        from backtester import _native
        return _native
    except ImportError as exc:
        raise RuntimeError(
            "Native engine is not built. Install a C++17 compiler, then run: python setup.py build_ext --inplace"
        ) from exc


def ema(closes: Sequence[float], period: int) -> list[float]:
    """Exponential moving average, calculated in C++."""
    return _native().ema(list(map(float, closes)), period)


def rsi(closes: Sequence[float], period: int = 14) -> list[float]:
    """Wilder RSI, calculated in C++."""
    return _native().rsi(list(map(float, closes)), period)


def rolling_vwap(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], volumes: Sequence[float], period: int = 200) -> list[float]:
    """Rolling typical-price VWAP, calculated in C++."""
    return _native().rolling_vwap(list(map(float, highs)), list(map(float, lows)), list(map(float, closes)), list(map(float, volumes)), period)
