from datetime import date
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from backtester.data import SQLiteBarStore, YahooFinanceProvider
from backtester.engine import (
    run_buy_and_hold,
    run_divergence_strategy,
    run_ema200_trend_strategy,
    run_ema_rsi_strategy,
    run_vwap200_strategy,
)

DATA_SOURCE = "yahoo_finance"
app = FastAPI(title="Modular Backtester", version="0.1.0")
store = SQLiteBarStore()
provider = YahooFinanceProvider()


class BacktestRequest(BaseModel):
    strategy: Literal["ema_rsi", "ema200_trend", "divergence", "vwap200"] = "ema_rsi"
    symbol: str = Field(examples=["SPY"])
    start: date = Field(examples=["2022-01-01"])
    end: date = Field(examples=["2024-01-01"])
    fast_period: int = Field(default=12, ge=2)
    slow_period: int = Field(default=26, ge=3)
    rsi_period: int = Field(default=14, ge=2)
    initial_cash: float = Field(default=10_000, gt=0)


@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html><html><head><title>Modular Backtester</title><script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.8"></script><style>
body{font:16px system-ui;background:#f5f7fb;color:#172033;max-width:1100px;margin:2.5rem auto;padding:0 1rem}h1{margin-bottom:.25rem}.sub{color:#61708b}form,.card{background:white;border:1px solid #e2e8f0;border-radius:10px;padding:1rem;box-shadow:0 2px 8px #18233a0a}input,select,button{padding:.6rem .7rem;margin:.2rem;border:1px solid #cbd5e1;border-radius:6px}button{background:#2563eb;color:white;border:0;font-weight:600;cursor:pointer}button.secondary{background:#475569}.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem;margin:1rem 0}.metric{display:grid;grid-template-columns:1fr 1fr;gap:.5rem}.metric b{font-size:1.2rem}#message{min-height:1.5rem;color:#b91c1c;margin:.6rem 0}canvas{max-height:460px}@media(max-width:650px){.cards{grid-template-columns:1fr}.metric{grid-template-columns:1fr}}</style></head><body>
<h1>Modular Backtester</h1><p class=sub>Compare C++-calculated trading strategies and buy &amp; hold on the same historical price series.</p>
<form id=form><label>Strategy <select name=strategy><option value=ema_rsi>EMA / RSI crossover</option><option value=ema200_trend>Price vs 200 EMA</option><option value=divergence>RSI divergence (long / short)</option><option value=vwap200>Price vs 200 VWAP</option></select></label><label>Symbol <input name=symbol value=SPY required></label><label>Start <input type=date name=start value=2022-01-01 required></label><label>End <input type=date name=end value=2024-01-01 required></label><button>Run backtest</button><button id=add type=button class=secondary>Add to comparison</button></form><div id=message></div>
<section id=cards class=cards></section><article class=card><canvas id=chart></canvas></article>
<script>
const form=document.querySelector('#form'),add=document.querySelector('#add'),message=document.querySelector('#message'),cards=document.querySelector('#cards');let chart,signature='',labels=[],comparisons=new Map();const colors={ema_rsi:'#2563eb',ema200_trend:'#7c3aed',divergence:'#dc2626',vwap200:'#0891b2',buy_and_hold:'#f97316'};
const money=n=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(n),pct=n=>(n*100).toFixed(2)+'%',num=n=>Number(n).toFixed(2);function metrics(x){return `<span>Final equity<b>${money(x.final_equity)}</b></span><span>Total return<b>${pct(x.total_return)}</b></span><span>Max drawdown<b>${pct(x.max_drawdown)}</b></span><span>Annualized Sharpe<b>${num(x.sharpe_ratio)}</b></span><span>Executions<b>${x.trades}</b></span>`}function requestData(){let d=Object.fromEntries(new FormData(form));Object.assign(d,{fast_period:12,slow_period:26,rsi_period:14,initial_cash:10000});return d}function key(d){return `${d.symbol}|${d.start}|${d.end}|${d.initial_cash}`}function draw(){cards.innerHTML=[...comparisons.values()].map(x=>`<article class=card><h2 style="color:${x.color}">${x.label}</h2><div class=metric>${metrics(x.result)}</div></article>`).join('');if(chart)chart.destroy();chart=new Chart(document.querySelector('#chart'),{type:'line',data:{labels,datasets:[...comparisons.values()].map(x=>({label:x.label,data:x.result.equity_curve,borderColor:x.color,borderWidth:2,pointRadius:0}))},options:{responsive:true,interaction:{mode:'index',intersect:false},plugins:{tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${money(c.raw)}`}}},scales:{y:{ticks:{callback:v=>money(v)}}}}})}async function run(reset){let d=requestData(),next=key(d);if(!reset&&next!==signature){message.textContent='Dates, symbol, or capital changed. Run a new backtest before adding a comparison.';return}message.textContent='Loading market data and calculating...';try{let r=await fetch('/api/backtests',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(d)}),body=await r.json();if(!r.ok)throw Error(body.detail||'Backtest failed');if(reset){signature=next;labels=body.dates;comparisons=new Map();comparisons.set('buy_and_hold',{label:'Buy & hold',result:body.buy_and_hold,color:colors.buy_and_hold})}comparisons.set(body.strategy_key,{label:body.strategy_name,result:body.strategy,color:colors[body.strategy_key]});draw();message.textContent=`${body.symbol}: ${body.bars} daily bars | ${comparisons.size-1} strategy comparison(s)`}catch(err){message.textContent=err.message}}form.addEventListener('submit',e=>{e.preventDefault();run(true)});add.addEventListener('click',()=>run(false));
</script></body></html>"""


@app.post("/api/backtests")
def backtest(request: BacktestRequest):
    try:
        start, end = request.start.isoformat(), request.end.isoformat()
        if not store.covers(DATA_SOURCE, request.symbol, start, end):
            store.upsert(request.symbol, provider.fetch_daily(request.symbol, request.start, request.end))
            store.record_download(DATA_SOURCE, request.symbol, start, end)
        bars = store.load(request.symbol, start, end)
        closes = [bar["close"] for bar in bars]
        if request.strategy == "ema200_trend":
            strategy = run_ema200_trend_strategy(closes, initial_cash=request.initial_cash)
            strategy_name = "Price vs 200 EMA"
        elif request.strategy == "divergence":
            strategy = run_divergence_strategy(closes, initial_cash=request.initial_cash)
            strategy_name = "RSI divergence (long / short)"
        elif request.strategy == "vwap200":
            strategy = run_vwap200_strategy(
                [bar["high"] for bar in bars], [bar["low"] for bar in bars], closes,
                [bar["volume"] for bar in bars], initial_cash=request.initial_cash,
            )
            strategy_name = "Price vs 200 VWAP"
        else:
            strategy = run_ema_rsi_strategy(
                closes, request.fast_period, request.slow_period, request.rsi_period,
                initial_cash=request.initial_cash,
            )
            strategy_name = "EMA / RSI strategy"
        buy_and_hold = run_buy_and_hold(closes, initial_cash=request.initial_cash)
        return {
            "symbol": request.symbol.upper(), "bars": len(bars), "dates": [b["date"] for b in bars],
            "strategy_key": request.strategy, "strategy_name": strategy_name,
            "strategy": strategy.__dict__, "buy_and_hold": buy_and_hold.__dict__,
        }
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
