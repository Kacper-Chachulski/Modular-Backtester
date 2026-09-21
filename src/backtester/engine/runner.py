from dataclasses import dataclass
from math import isnan
from typing import Any

from backtester.technicals import ema, rsi


@dataclass
class BacktestResult:
    final_equity: float
    total_return: float
    max_drawdown: float
    trades: int
    sharpe_ratio: float
    equity_curve: list[float]

    @classmethod
    def from_native(cls, result: dict[str, Any]) -> "BacktestResult":
        return cls(**result)


def run_ema_rsi_strategy(
    closes: list[float], fast_period: int = 12, slow_period: int = 26, rsi_period: int = 14,
    rsi_entry_ceiling: float = 70.0, initial_cash: float = 10_000, fee_rate: float = 0.001,
) -> BacktestResult:
    """Compose a simple signal in Python and execute it in the C++ engine."""
    if fast_period >= slow_period:
        raise ValueError("fast_period must be smaller than slow_period")
    fast, slow, momentum = ema(closes, fast_period), ema(closes, slow_period), rsi(closes, rsi_period)
    enter, short = [], []
    for f, s, m in zip(fast, slow, momentum):
        ready = not any(isnan(v) for v in (f, s, m))
        long_signal = ready and f > s and m < rsi_entry_ceiling
        enter.append(long_signal)
        short.append(ready and not long_signal)
    from backtester import _native
    return BacktestResult.from_native(_native.run_long_short_signals(closes, enter, short, initial_cash, fee_rate))


def run_ema200_trend_strategy(
    closes: list[float], period: int = 200, initial_cash: float = 10_000, fee_rate: float = 0.001,
) -> BacktestResult:
    """Long-only trend strategy: hold while price closes above its 200-period EMA."""
    trend = ema(closes, period)
    enter, short = [], []
    for close, average in zip(closes, trend):
        ready = not isnan(average)
        enter.append(ready and close > average)
        short.append(ready and close <= average)
    from backtester import _native
    return BacktestResult.from_native(_native.run_long_short_signals(closes, enter, short, initial_cash, fee_rate))


def run_divergence_strategy(
    closes: list[float], rsi_period: int = 14, lookback: int = 20,
    initial_cash: float = 10_000, fee_rate: float = 0.001,
) -> BacktestResult:
    """Long bullish RSI/price divergence and short bearish divergence, calculated in C++."""
    from backtester import _native
    return BacktestResult.from_native(
        _native.run_divergence(closes, rsi_period, lookback, initial_cash, fee_rate)
    )


def run_vwap200_strategy(
    highs: list[float], lows: list[float], closes: list[float], volumes: list[float],
    initial_cash: float = 10_000, fee_rate: float = 0.001,
) -> BacktestResult:
    """Hold long below the 200-period rolling VWAP and short at/above it."""
    from backtester import _native
    return BacktestResult.from_native(
        _native.run_vwap_mean_reversion(highs, lows, closes, volumes, 200, initial_cash, fee_rate)
    )


def run_buy_and_hold(closes: list[float], initial_cash: float = 10_000, fee_rate: float = 0.001) -> BacktestResult:
    """Buy the first close and sell the final close, executed in C++."""
    from backtester import _native
    return BacktestResult.from_native(_native.buy_and_hold(closes, initial_cash, fee_rate))
