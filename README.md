# Modular Backtester (starter)

A compact foundation for a reusable, extensible trading backtester.

```
src/backtester/
  data/        providers and SQLite-backed OHLCV storage
  technicals/  Python-facing indicator API (delegates to C++)
  engine/      Python backtest orchestration and result models
  web/         FastAPI web/API layer
cpp/           C++17 / pybind11 calculation engine
```

## Setup

Create a virtual environment and install the Python dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Build the C++ extension (requires a C++17 compiler: Visual Studio Build Tools on Windows, or GCC/Clang on Linux/macOS):

```powershell
.\scripts\build_native.ps1
```

Run the web application:

```powershell
uvicorn backtester.web.main:app --reload
```

Then open http://127.0.0.1:8000. The API documentation is at `/docs`.

## Run from VS Code

Open this project folder in VS Code and press **F5** (or use **Run and Debug** → **Start Backtester UI**). The project pins VS Code to its local `.venv`, which contains the dependencies. VS Code automatically builds the native C++ module, starts the web server, and opens the UI in your default browser. Stop the server with **Shift+F5**.

## First strategy

The included example is long-only: buy when a fast EMA is above a slow EMA and RSI is below a configurable ceiling; sell when the EMA relationship reverses. Indicator and execution calculations run in `cpp/engine.cpp`; Python owns data acquisition, persistence, strategy composition, and the UI.

`yfinance` is deliberately behind a provider interface, so it can later be replaced by a broker, paid data feed, or local parquet reader without changing the engine.

## Market data and cache

The starter provider is [Yahoo Finance](https://finance.yahoo.com/) through the `yfinance` Python package. It downloads daily adjusted OHLCV bars (`auto_adjust=True`). This is convenient for prototyping, but is not a licensed institutional data feed.

Downloaded bars are stored locally in `data/backtester.db` (SQLite). The cache also records the exact source, symbol, and half-open date ranges (`[start, end)`) that were downloaded. Requests are served from SQLite only when those records form uninterrupted coverage for the complete selected range; otherwise the missing request range is downloaded and merged. This avoids accidentally calculating from a partial, overlapping cache.
