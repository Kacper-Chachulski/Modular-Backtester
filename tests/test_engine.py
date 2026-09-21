import pytest
from tempfile import TemporaryDirectory

native = pytest.importorskip("backtester._native")

from backtester.technicals import ema, rsi
from backtester.engine import run_ema200_trend_strategy


def test_ema_has_warmup_and_expected_seed():
    values = ema([1, 2, 3, 4, 5], 3)
    assert values[0] != values[0]  # NaN warmup
    assert values[2] == 2.0
    assert values[3] == 3.0


def test_rsi_is_bounded():
    values = rsi([float(i) for i in range(1, 30)], 14)
    assert values[-1] == 100.0


def test_buy_and_hold_exposes_performance_metrics():
    result = native.buy_and_hold([100.0, 105.0, 110.0, 115.0], 10_000.0, 0.0)
    assert result["final_equity"] == 11_500.0
    assert result["total_return"] == pytest.approx(0.15)
    assert "sharpe_ratio" in result


def test_ema200_trend_strategy_enters_an_established_uptrend():
    result = run_ema200_trend_strategy([float(i) for i in range(1, 251)], fee_rate=0.0)
    assert result.trades == 1
    assert result.total_return > 0


def test_divergence_engine_returns_a_complete_result():
    closes = [100.0 + (i % 7) - i * 0.05 for i in range(80)]
    result = native.run_divergence(closes, rsi_period=14, lookback=20)
    assert len(result["equity_curve"]) == len(closes)
    assert "sharpe_ratio" in result


def test_rolling_vwap_and_vwap200_strategy():
    values = [1.0, 2.0, 3.0, 4.0]
    vwap = native.rolling_vwap(values, values, values, [1.0] * 4, 3)
    assert vwap[2:] == pytest.approx([2.0, 3.0])

    closes = [100.0] * 200 + [90.0, 110.0]
    result = native.run_vwap_mean_reversion(closes, closes, closes, [1.0] * len(closes), 200, 10_000.0, 0.0)
    assert result["trades"] == 5
    assert result["final_equity"] > 10_000.0


def test_inverse_signal_execution_reverses_without_going_to_cash():
    result = native.run_long_short_signals(
        [100.0, 110.0, 99.0], [True, False, False], [False, True, True], 10_000.0, 0.0
    )
    assert result["trades"] == 3  # long entry, long close, short entry
    assert result["final_equity"] == pytest.approx(12_100.0)


def test_downloaded_ranges_only_cover_contiguous_intervals():
    from backtester.data.storage import SQLiteBarStore

    with TemporaryDirectory() as directory:
        store = SQLiteBarStore(f"{directory}/prices.db")
        store.record_download("yahoo_finance", "SPY", "2020-01-01", "2021-01-01")
        store.record_download("yahoo_finance", "SPY", "2021-01-01", "2022-01-01")
        assert store.covers("yahoo_finance", "SPY", "2020-06-01", "2021-06-01")
        assert not store.covers("yahoo_finance", "SPY", "2019-01-01", "2021-06-01")
