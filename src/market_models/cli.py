"""Local-only CLI. Input prices and generated outputs never leave this process."""
import argparse
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from uuid import uuid4
import numpy as np
import pandas as pd
from . import __version__
from .models import (Costs, validate_prices, signals, simulate, metrics,
                     risk_snapshot, block_scenarios, event_study)

REQUIRED = {"benchmark","annualization","target_vol","cap","top_n","rebalance",
    "commission_eur","spread_bps","slippage_bps","fx_bps","fee_bps",
    "min_trade_eur","cash_rate"}
COST_KEYS = set(asdict(Costs()))
MODEL_KEYS = {"annualization","target_vol","cap","top_n","rebalance"}
ASSET = re.compile(r"[A-Za-z0-9^][A-Za-z0-9._^=/\-]{0,39}")

def load_config(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        cfg = json.load(stream)
    if not isinstance(cfg, dict) or set(cfg) != REQUIRED:
        raise ValueError("Configuration keys do not match the documented schema.")
    if not isinstance(cfg["benchmark"],str) or not ASSET.fullmatch(cfg["benchmark"]):
        raise ValueError("Invalid benchmark identifier.")
    if cfg["annualization"] not in (252,365) or isinstance(cfg["annualization"],bool):
        raise ValueError("annualization must be 252 or 365.")
    if cfg["rebalance"] not in ("monthly","weekly"):
        raise ValueError("rebalance must be monthly or weekly.")
    if isinstance(cfg["top_n"],bool) or not isinstance(cfg["top_n"],int) or not 1 <= cfg["top_n"] <= 256:
        raise ValueError("top_n must be an integer between 1 and 256.")
    for key in REQUIRED - {"benchmark","annualization","top_n","rebalance"}:
        v = cfg[key]
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not np.isfinite(v) or v < 0:
            raise ValueError("Configuration numbers must be finite and nonnegative.")
    if not 0 < cfg["cap"] <= 1 or not 0 < cfg["target_vol"] <= 5 or cfg["cash_rate"] > 1:
        raise ValueError("Invalid exposure, volatility or cash-rate range.")
    Costs(**{k:cfg[k] for k in COST_KEYS})
    return cfg

def load_prices(path, asof=None):
    p = Path(path)
    if not p.is_file() or p.stat().st_size > 100*1024*1024:
        raise ValueError("Input must be a CSV file no larger than 100 MiB.")
    with p.open(encoding="utf-8-sig",newline="") as stream:
        header = next(csv.reader(stream),[])
    if len(header) < 2 or len(header) > 257 or header[0] != "date" or len(set(header)) != len(header):
        raise ValueError("CSV needs unique headers: date and 1..256 asset identifiers.")
    if any(not ASSET.fullmatch(name) for name in header[1:]):
        raise ValueError("Use safe ticker identifiers, not formula-like or personal column names.")
    f = pd.read_csv(p,encoding="utf-8-sig",dtype={"date":str})
    if not f.date.str.fullmatch(r"\d{4}-\d{2}-\d{2}",na=False).all():
        raise ValueError("Dates must be YYYY-MM-DD without time or timezone suffixes.")
    f["date"] = pd.to_datetime(f.date,format="%Y-%m-%d",errors="raise")
    f = f.set_index("date").apply(pd.to_numeric,errors="raise")
    f = validate_prices(f)
    if asof:
        cutoff = pd.Timestamp(asof)
        if cutoff.tzinfo is not None:
            raise ValueError("asof must be a daily date without timezone.")
        f = f.loc[f.index < cutoff]
    if len(f) < 2:
        raise ValueError("Need at least two complete observations after the cutoff.")
    return f

def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,ensure_ascii=False,
        default=str,allow_nan=False),encoding="utf-8")

def new_run_dir(root):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    p = Path(root) / (stamp+"_"+uuid4().hex[:8])
    p.mkdir(parents=True,exist_ok=False)
    return p

def save_csv(path,frame):
    frame.to_csv(path,index=True,index_label="date")

def run_backtest(p,cfg,capital,out):
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be positive and finite.")
    if len(p) < 600 or cfg["benchmark"] not in p.columns:
        raise ValueError("Backtest needs >=600 common observations and its benchmark.")
    specs = {k:cfg[k] for k in MODEL_KEYS}
    strategies, predictions = {}, {}
    for name in ("momentum","ridge"):
        strategies[name],predictions[name] = signals(p,kind=name,**specs)
    firsts = [s.dropna().index.min() for s in strategies.values()]
    if any(pd.isna(t) for t in firsts):
        raise ValueError("Insufficient complete training history for the models.")
    start = max(firsts)
    q = p.loc[start:]
    cost = Costs(**{k:cfg[k] for k in COST_KEYS})
    results = {}
    for name in ("momentum","ridge","buy_hold","equal_weight"):
        if name in strategies:
            targets = strategies[name].loc[start:]
        else:
            targets = pd.DataFrame(np.nan,index=q.index,columns=q.columns)
            targets.iloc[0] = 0.
            if name == "buy_hold":
                targets.loc[q.index[0],cfg["benchmark"]] = 1.
            else:
                targets.iloc[0] = 1/len(q.columns)
        ledger,trades = simulate(q,targets,capital,cost,cfg["cash_rate"],
                                  cfg["annualization"],cfg["min_trade_eur"])
        results[name] = metrics(ledger,capital,cfg["annualization"],cfg["cash_rate"])
        save_csv(out/(name+"_ledger.csv"),ledger)
        trades.to_csv(out/(name+"_trades.csv"),index=False)
        if name in strategies:
            save_csv(out/(name+"_targets.csv"),targets)
            save_csv(out/(name+"_predictions.csv"),predictions[name].loc[start:])
        if name == "momentum" and len(ledger) >= 102:
            results[name]["conditional_scenarios"] = block_scenarios(
                ledger.equity.pct_change(),capital,cfg["annualization"])
    doubled = Costs(**{k:v*2 for k,v in asdict(cost).items()})
    for name in ("momentum","ridge"):
        ledger,_ = simulate(q,strategies[name].loc[start:],capital,doubled,
                            cfg["cash_rate"],cfg["annualization"],cfg["min_trade_eur"])
        results[name]["double_costs"] = metrics(ledger,capital,cfg["annualization"],cfg["cash_rate"])
    dump(out/"metrics.json",{"first_signal":str(start),"last_data":str(q.index.max()),
        "capital_eur":capital,"results":results,
        "limits":["Before personal tax; fractional total-return units.",
            "Current chosen universe introduces selection bias.",
            "Bootstrap is conditional on historical observations, not a forecast.",
            "No custody losses, financing, withdrawals, order execution or guarantees."]})

def example(path,market):
    """Generate a labelled demonstration only; never replace an existing file."""
    rng = np.random.default_rng(48)
    idx = pd.bdate_range("2018-01-01",periods=1200) if market=="traditional" else pd.date_range("2021-01-01",periods=1200)
    names = ["SPY","SYNTH_B","SYNTH_C"] if market=="traditional" else ["BTC-USD","SYNTH_B","SYNTH_C"]
    values = 100*np.exp(np.cumsum(rng.normal(.0002,.012,(len(idx),3)),axis=0))
    frame = pd.DataFrame(values,index=idx,columns=names)
    target = Path(path)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("x",encoding="utf-8",newline="") as stream:
        frame.to_csv(stream,index_label="date")
    print("Synthetic demonstration generated; not real market prices.")

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command",required=True)
    sample = sub.add_parser("example",help="Generate synthetic demonstration prices.")
    sample.add_argument("--output",required=True)
    sample.add_argument("--market",choices=["traditional","crypto"],default="traditional")
    for name in ("backtest","risk","event"):
        p = sub.add_parser(name)
        p.add_argument("--prices",required=True)
        p.add_argument("--config",required=True)
        p.add_argument("--output",default="outputs")
        p.add_argument("--asof",default=datetime.now(timezone.utc).date().isoformat())
        p.add_argument("--data-label",choices=["research","synthetic"],default="research")
        if name=="backtest":
            p.add_argument("--capital",type=float,default=3000.)
        if name=="event":
            p.add_argument("--event-date",required=True)
    args = parser.parse_args(argv)
    try:
        if args.command=="example":
            example(args.output,args.market)
            return 0
        cfg = load_config(args.config)
        prices = load_prices(args.prices,args.asof)
        if args.command=="event" and cfg["annualization"] != 365:
            raise ValueError("Event study requires a 365-day crypto calendar.")
        out = new_run_dir(args.output)
        if args.command=="backtest":
            run_backtest(prices,cfg,args.capital,out)
        elif args.command=="risk":
            risk_snapshot(prices,cfg["annualization"]).to_csv(out/"risk.csv",index=False)
        else:
            event_study(prices,args.event_date,benchmark=cfg["benchmark"]).to_csv(out/"event.csv",index=False)
        dump(out/"run_manifest.json",{"package_version":__version__,"data_label":args.data_label,
            "input_sha256":hashlib.sha256(Path(args.prices).read_bytes()).hexdigest(),
            "observations":len(prices),"first_date":str(prices.index.min()),
            "last_date":str(prices.index.max()),"asof_exclusive":args.asof,
            "config":cfg,"synthetic_is_not_market_evidence":args.data_label=="synthetic"})
        print("Local results written to",out)
        return 0
    except (ValueError,TypeError,OSError,KeyError) as exc:
        print("Input or computation error: "+str(exc),file=sys.stderr)
        return 2
