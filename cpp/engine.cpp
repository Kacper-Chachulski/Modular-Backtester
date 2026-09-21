#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

namespace py = pybind11;
using Series = std::vector<double>;

static void validate_period(const Series& values, int period) {
    if (period <= 0) throw std::invalid_argument("period must be positive");
    if (values.size() < static_cast<size_t>(period))
        throw std::invalid_argument("not enough values for period");
}

Series ema(const Series& values, int period) {
    validate_period(values, period);
    Series result(values.size(), std::numeric_limits<double>::quiet_NaN());
    const double multiplier = 2.0 / (period + 1.0);
    double current = 0.0;
    for (int i = 0; i < period; ++i) current += values[i];
    current /= period;
    result[period - 1] = current;
    for (size_t i = period; i < values.size(); ++i) {
        current = (values[i] - current) * multiplier + current;
        result[i] = current;
    }
    return result;
}

Series rsi(const Series& values, int period) {
    validate_period(values, period + 1);
    Series result(values.size(), std::numeric_limits<double>::quiet_NaN());
    double avg_gain = 0.0, avg_loss = 0.0;
    for (int i = 1; i <= period; ++i) {
        double change = values[i] - values[i - 1];
        avg_gain += std::max(change, 0.0);
        avg_loss += std::max(-change, 0.0);
    }
    avg_gain /= period;
    avg_loss /= period;
    auto value = [](double gain, double loss) {
        if (loss == 0.0) return 100.0;
        return 100.0 - 100.0 / (1.0 + gain / loss);
    };
    result[period] = value(avg_gain, avg_loss);
    for (size_t i = period + 1; i < values.size(); ++i) {
        double change = values[i] - values[i - 1];
        avg_gain = (avg_gain * (period - 1) + std::max(change, 0.0)) / period;
        avg_loss = (avg_loss * (period - 1) + std::max(-change, 0.0)) / period;
        result[i] = value(avg_gain, avg_loss);
    }
    return result;
}

Series rolling_vwap(const Series& highs, const Series& lows, const Series& closes, const Series& volumes, int period) {
    if (highs.size() != lows.size() || highs.size() != closes.size() || closes.size() != volumes.size())
        throw std::invalid_argument("OHLCV series must have equal lengths");
    validate_period(closes, period);
    Series result(closes.size(), std::numeric_limits<double>::quiet_NaN());
    double weighted_prices = 0.0, total_volume = 0.0;
    for (size_t i = 0; i < closes.size(); ++i) {
        if (volumes[i] < 0.0) throw std::invalid_argument("volume cannot be negative");
        const double typical_price = (highs[i] + lows[i] + closes[i]) / 3.0;
        weighted_prices += typical_price * volumes[i];
        total_volume += volumes[i];
        if (i >= static_cast<size_t>(period)) {
            const size_t old = i - period;
            const double old_typical = (highs[old] + lows[old] + closes[old]) / 3.0;
            weighted_prices -= old_typical * volumes[old];
            total_volume -= volumes[old];
        }
        if (i >= static_cast<size_t>(period - 1) && total_volume > 0.0)
            result[i] = weighted_prices / total_volume;
    }
    return result;
}

py::dict run_long_only(const Series& closes, const std::vector<bool>& enter, const std::vector<bool>& exit, double initial_cash, double fee_rate) {
    if (closes.empty() || closes.size() != enter.size() || closes.size() != exit.size())
        throw std::invalid_argument("closes, enter and exit must have equal non-zero length");
    if (initial_cash <= 0 || fee_rate < 0) throw std::invalid_argument("invalid capital or fee rate");
    double cash = initial_cash, units = 0.0;
    int trades = 0;
    Series equity; equity.reserve(closes.size());
    for (size_t i = 0; i < closes.size(); ++i) {
        if (closes[i] <= 0) throw std::invalid_argument("close prices must be positive");
        if (units == 0.0 && enter[i]) { units = cash / (closes[i] * (1.0 + fee_rate)); cash = 0.0; ++trades; }
        else if (units > 0.0 && exit[i]) { cash = units * closes[i] * (1.0 - fee_rate); units = 0.0; ++trades; }
        equity.push_back(cash + units * closes[i]);
    }
    double final_equity = equity.back();
    double peak = equity.front(), max_drawdown = 0.0;
    for (double v : equity) { peak = std::max(peak, v); max_drawdown = std::max(max_drawdown, (peak - v) / peak); }
    py::dict out;
    out["equity_curve"] = equity;
    out["final_equity"] = final_equity;
    out["total_return"] = final_equity / initial_cash - 1.0;
    out["max_drawdown"] = max_drawdown;
    out["trades"] = trades;
    if (equity.size() < 2) { out["sharpe_ratio"] = 0.0; return out; }
    Series returns; returns.reserve(equity.size() - 1);
    for (size_t i = 1; i < equity.size(); ++i) returns.push_back(equity[i] / equity[i - 1] - 1.0);
    double mean = 0.0;
    for (double r : returns) mean += r;
    mean /= returns.size();
    double sum_squared = 0.0;
    for (double r : returns) sum_squared += (r - mean) * (r - mean);
    double deviation = returns.size() > 1 ? std::sqrt(sum_squared / (returns.size() - 1)) : 0.0;
    out["sharpe_ratio"] = deviation == 0.0 ? 0.0 : std::sqrt(252.0) * mean / deviation;
    return out;
}

py::dict run_long_short_signals(const Series& closes, const std::vector<bool>& long_signals, const std::vector<bool>& short_signals, double initial_cash, double fee_rate) {
    if (closes.empty() || closes.size() != long_signals.size() || closes.size() != short_signals.size())
        throw std::invalid_argument("closes and signals must have equal non-zero length");
    if (initial_cash <= 0 || fee_rate < 0) throw std::invalid_argument("invalid capital or fee rate");
    double cash = initial_cash, units = 0.0;
    int trades = 0;
    Series equity; equity.reserve(closes.size());
    for (size_t i = 0; i < closes.size(); ++i) {
        if (closes[i] <= 0) throw std::invalid_argument("close prices must be positive");
        if (units > 0.0 && short_signals[i]) { cash = units * closes[i] * (1.0 - fee_rate); units = 0.0; ++trades; }
        if (units < 0.0 && long_signals[i]) { cash += units * closes[i] * (1.0 + fee_rate); units = 0.0; ++trades; }
        if (units == 0.0 && long_signals[i]) { units = cash / (closes[i] * (1.0 + fee_rate)); cash = 0.0; ++trades; }
        else if (units == 0.0 && short_signals[i]) {
            units = -cash / (closes[i] * (1.0 + fee_rate));
            cash += -units * closes[i] * (1.0 - fee_rate);
            ++trades;
        }
        equity.push_back(cash + units * closes[i]);
    }
    double final_equity = equity.back();
    double peak = equity.front(), max_drawdown = 0.0;
    for (double v : equity) { peak = std::max(peak, v); max_drawdown = std::max(max_drawdown, (peak - v) / peak); }
    double sharpe = 0.0;
    if (equity.size() > 2) {
        Series returns; returns.reserve(equity.size() - 1);
        for (size_t i = 1; i < equity.size(); ++i) returns.push_back(equity[i] / equity[i - 1] - 1.0);
        double mean = 0.0; for (double value : returns) mean += value; mean /= returns.size();
        double sum_squared = 0.0; for (double value : returns) sum_squared += (value - mean) * (value - mean);
        double deviation = std::sqrt(sum_squared / (returns.size() - 1));
        sharpe = deviation == 0.0 ? 0.0 : std::sqrt(252.0) * mean / deviation;
    }
    py::dict out;
    out["equity_curve"] = equity;
    out["final_equity"] = final_equity;
    out["total_return"] = final_equity / initial_cash - 1.0;
    out["max_drawdown"] = max_drawdown;
    out["trades"] = trades;
    out["sharpe_ratio"] = sharpe;
    return out;
}

py::dict buy_and_hold(const Series& closes, double initial_cash, double fee_rate) {
    if (closes.empty()) throw std::invalid_argument("closes must not be empty");
    std::vector<bool> enter(closes.size(), false), exit(closes.size(), false);
    enter[0] = true;
    // Final liquidation makes the comparison use the same fee model as the strategy.
    exit.back() = true;
    return run_long_only(closes, enter, exit, initial_cash, fee_rate);
}

py::dict run_divergence(const Series& closes, int rsi_period, int lookback, double initial_cash, double fee_rate) {
    validate_period(closes, rsi_period + lookback + 1);
    if (lookback <= 0) throw std::invalid_argument("lookback must be positive");
    if (initial_cash <= 0 || fee_rate < 0) throw std::invalid_argument("invalid capital or fee rate");
    Series momentum = rsi(closes, rsi_period);
    double cash = initial_cash, units = 0.0;
    int trades = 0;
    bool previous_bullish = false, previous_bearish = false;
    Series equity; equity.reserve(closes.size());
    for (size_t i = 0; i < closes.size(); ++i) {
        bool ready = i >= static_cast<size_t>(rsi_period + lookback) && !std::isnan(momentum[i]);
        bool bullish = ready && momentum[i] > momentum[i - lookback] && closes[i] < closes[i - lookback];
        bool bearish = ready && closes[i] > closes[i - lookback] && momentum[i] < momentum[i - lookback];
        bool long_signal = bullish && !previous_bullish;
        bool short_signal = bearish && !previous_bearish;

        // An opposite divergence closes the existing position and reverses at this close.
        if (units > 0.0 && short_signal) { cash = units * closes[i] * (1.0 - fee_rate); units = 0.0; ++trades; }
        if (units < 0.0 && long_signal) { cash += units * closes[i] * (1.0 + fee_rate); units = 0.0; ++trades; }
        if (units == 0.0 && long_signal) { units = cash / (closes[i] * (1.0 + fee_rate)); cash = 0.0; ++trades; }
        else if (units == 0.0 && short_signal) {
            units = -cash / (closes[i] * (1.0 + fee_rate));
            cash += -units * closes[i] * (1.0 - fee_rate);
            ++trades;
        }
        equity.push_back(cash + units * closes[i]);
        previous_bullish = bullish;
        previous_bearish = bearish;
    }
    double final_equity = equity.back();
    double peak = equity.front(), max_drawdown = 0.0;
    for (double v : equity) { peak = std::max(peak, v); max_drawdown = std::max(max_drawdown, (peak - v) / peak); }
    double sharpe = 0.0;
    if (equity.size() > 2) {
        Series returns; returns.reserve(equity.size() - 1);
        for (size_t i = 1; i < equity.size(); ++i) returns.push_back(equity[i] / equity[i - 1] - 1.0);
        double mean = 0.0; for (double value : returns) mean += value; mean /= returns.size();
        double sum_squared = 0.0; for (double value : returns) sum_squared += (value - mean) * (value - mean);
        double deviation = std::sqrt(sum_squared / (returns.size() - 1));
        sharpe = deviation == 0.0 ? 0.0 : std::sqrt(252.0) * mean / deviation;
    }
    py::dict out;
    out["equity_curve"] = equity;
    out["final_equity"] = final_equity;
    out["total_return"] = final_equity / initial_cash - 1.0;
    out["max_drawdown"] = max_drawdown;
    out["trades"] = trades;
    out["sharpe_ratio"] = sharpe;
    return out;
}

py::dict run_vwap_mean_reversion(const Series& highs, const Series& lows, const Series& closes, const Series& volumes, int period, double initial_cash, double fee_rate) {
    Series average = rolling_vwap(highs, lows, closes, volumes, period);
    std::vector<bool> enter(closes.size(), false), exit(closes.size(), false);
    for (size_t i = 0; i < closes.size(); ++i) {
        if (std::isnan(average[i])) continue;
        enter[i] = closes[i] < average[i];
        exit[i] = closes[i] >= average[i];
    }
    return run_long_short_signals(closes, enter, exit, initial_cash, fee_rate);
}

PYBIND11_MODULE(_native, m) {
    m.doc() = "C++ numerical core for modular-backtester";
    m.def("ema", &ema);
    m.def("rsi", &rsi);
    m.def("rolling_vwap", &rolling_vwap, py::arg("highs"), py::arg("lows"), py::arg("closes"), py::arg("volumes"), py::arg("period") = 200);
    m.def("run_long_only", &run_long_only, py::arg("closes"), py::arg("enter"), py::arg("exit"), py::arg("initial_cash") = 10000.0, py::arg("fee_rate") = 0.001);
    m.def("run_long_short_signals", &run_long_short_signals, py::arg("closes"), py::arg("long_signals"), py::arg("short_signals"), py::arg("initial_cash") = 10000.0, py::arg("fee_rate") = 0.001);
    m.def("buy_and_hold", &buy_and_hold, py::arg("closes"), py::arg("initial_cash") = 10000.0, py::arg("fee_rate") = 0.001);
    m.def("run_divergence", &run_divergence, py::arg("closes"), py::arg("rsi_period") = 14, py::arg("lookback") = 20, py::arg("initial_cash") = 10000.0, py::arg("fee_rate") = 0.001);
    m.def("run_vwap_mean_reversion", &run_vwap_mean_reversion, py::arg("highs"), py::arg("lows"), py::arg("closes"), py::arg("volumes"), py::arg("period") = 200, py::arg("initial_cash") = 10000.0, py::arg("fee_rate") = 0.001);
}
