"""Descriptive weekly sector research on adjusted EUR closes. No network or orders."""
import argparse
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
from .cli import ASSET, load_prices
from .models import validate_prices


def validate_rotation(entry=60, exit_score=40, limit=3):
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v)
           for v in (entry, exit_score)):
        raise ValueError("Thresholds must be finite numbers")
    if not 0 <= exit_score <= entry <= 100 or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 3:
        raise ValueError("Require 0 <= exit <= entry <= 100 and 1..3 candidates")


def load_sector_config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(cfg, dict) or cfg.get("currency") != "EUR":
        raise ValueError("Sector configuration must declare EUR")
    sectors = cfg.get("sectors")
    if not isinstance(sectors, dict) or not 2 <= len(sectors) <= 64:
        raise ValueError("Configure 2..64 sector representatives")
    for ticker, info in sectors.items():
        if not ASSET.fullmatch(ticker) or not isinstance(info, dict):
            raise ValueError("Invalid sector ticker or metadata")
        if not isinstance(info.get("name"), str) or not 1 <= len(info["name"]) <= 100:
            raise ValueError("Sector names must contain 1..100 characters")
        if not isinstance(info.get("baseline", False), bool):
            raise ValueError("baseline must be boolean")
    if not isinstance(cfg.get("benchmark"), str) or not ASSET.fullmatch(cfg["benchmark"]) or cfg["benchmark"] in sectors:
        raise ValueError("Benchmark must be separate from sector representatives")
    rotation = cfg.get("rotation", {})
    if not isinstance(rotation, dict) or set(rotation) - {"entry", "exit_score", "limit"}:
        raise ValueError("Unknown rotation settings")
    validate_rotation(**rotation)
    return cfg


def screen(prices, benchmark, asof):
    """Use only observations before the cutoff; never fill ETF prices."""
    cutoff = pd.Timestamp(asof)
    if pd.isna(cutoff) or cutoff.tzinfo is not None or cutoff != cutoff.normalize():
        raise ValueError("asof must be a daily date without timezone")
    prices = validate_prices(prices)
    if benchmark not in prices or prices.shape[1] < 3:
        raise ValueError("Need a benchmark and at least two sector ETFs")
    common = prices.loc[prices.index < cutoff].copy()
    if common.empty or (cutoff-common.index[-1]).days > 7:
        raise ValueError("Missing or stale prices")
    if len(common) < 253:
        raise ValueError("Need at least 253 complete common closes")
    if common.index.to_series().diff().dropna().max() > pd.Timedelta(days=7):
        raise ValueError("Unexpected gap in common observation calendar")
    r3 = common.iloc[-1]/common.iloc[-64]-1
    r6 = common.iloc[-1]/common.iloc[-127]-1
    vol = common.pct_change(fill_method=None).iloc[-63:].std()*np.sqrt(252)
    year = common.iloc[-253:]
    dd = (year/year.cummax()-1).min()
    table = pd.DataFrame({
        "return_3m": r3, "return_6m": r6,
        "relative_3m": r3-r3[benchmark], "relative_6m": r6-r6[benchmark],
        "volatility": vol, "drawdown_1y": dd,
        "above_ma200": common.iloc[-1] > common.iloc[-200:].mean()
    }).drop(index=benchmark)
    def rank01(series):
        return (series.rank(method="average")-1)/(len(series)-1)
    table["score"] = 100*(.35*rank01(table.relative_3m)+.25*rank01(table.relative_6m)
                           +.20*rank01(-table.volatility)+.20*rank01(table.drawdown_1y))
    table["eligible"] = (table.return_3m > 0) & (table.relative_3m > 0) & table.above_ma200
    return table.sort_values("score", ascending=False), common


def select_sectors(table, previous=(), entry=60, exit_score=40, limit=3):
    """Retain qualifying incumbents, then admit strong entrants."""
    validate_rotation(entry, exit_score, limit)
    previous = set(previous)
    retained = table.index[table.eligible & (table.score >= exit_score) & table.index.isin(previous)].tolist()
    retained = sorted(retained, key=lambda t: (-table.loc[t, "score"], t))[:limit]
    entrants = table.index[table.eligible & (table.score >= entry) & ~table.index.isin(retained)]
    entrants = sorted(entrants, key=lambda t: (-table.loc[t, "score"], t))
    return retained+entrants[:limit-len(retained)]


def explain_changes(table, selected, previous=(), exit_score=40, initial=False):
    previous = set(previous)
    changes = []
    for ticker in sorted(previous | set(selected)):
        if ticker in selected:
            status = "retained" if ticker in previous else "initial" if initial else "entered"
            reason = "qualifying_previous_selection" if ticker in previous else "entry_score_and_trend"
        else:
            status = "exited"
            reason = ("outside_current_data_universe" if ticker not in table.index else
                      "trend_filter_failed" if not table.loc[ticker, "eligible"] else
                      "score_below_exit" if table.loc[ticker, "score"] < exit_score else "capacity_limit")
        changes.append({"ticker": ticker, "status": status, "reason": reason})
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", required=True, help="Adjusted EUR CSV: date,tickers")
    parser.add_argument("--config", required=True)
    parser.add_argument("--asof", required=True, help="Exclusive cutoff YYYY-MM-DD")
    parser.add_argument("--previous", help="Private previous weekly selection.json")
    parser.add_argument("--output", default="outputs")
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--georgia-dir", help="Local directory with licensed Georgia TTFs")
    args = parser.parse_args()
    cfg = load_sector_config(args.config)
    prices = load_prices(args.prices)
    expected = {cfg["benchmark"], *cfg["sectors"]}
    if not set(prices.columns) <= expected or cfg["benchmark"] not in prices:
        raise ValueError("CSV must contain benchmark and only configured ETFs")
    table, common = screen(prices, cfg["benchmark"], args.asof)
    old = json.loads(Path(args.previous).read_text(encoding="utf-8")) if args.previous else {}
    previous = old.get("selected", []) if isinstance(old, dict) else old
    if not isinstance(previous, list) or not all(isinstance(t, str) and ASSET.fullmatch(t) for t in previous):
        raise ValueError("Previous selection must contain safe ticker strings")
    if isinstance(old, dict) and args.previous:
        previous_close = pd.Timestamp(old.get("last_close"))
        if pd.isna(previous_close) or previous_close.tzinfo is not None or previous_close >= common.index[-1]:
            raise ValueError("Previous state must precede current last close")
    rotation = cfg.get("rotation", {})
    selected = select_sectors(table, previous, **rotation)
    table["selected"] = table.index.isin(selected)
    table["baseline"] = [cfg["sectors"][t].get("baseline", False) for t in table.index]
    changes = explain_changes(table, selected, previous, rotation.get("exit_score", 40), not args.previous)
    output = Path(args.output)/("sectors_"+uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    table.to_csv(output/"screen.csv")
    state = {"selected": selected, "last_close": str(common.index[-1].date()),
             "universe": sorted(table.index), "cutoff_exclusive": args.asof}
    metadata = {
        "cutoff_exclusive": args.asof, "last_close": state["last_close"],
        "first_close": str(common.index[0].date()), "observations": len(common),
        "currency": "EUR", "benchmark": cfg["benchmark"],
        "configured_sectors": len(cfg["sectors"]), "ranked_sectors": len(table),
        "excluded_missing_columns": sorted(expected-set(prices.columns)),
        "universe_changed": bool(isinstance(old, dict) and args.previous and old.get("universe") != sorted(table.index)),
        "input_sha256": hashlib.sha256(Path(args.prices).read_bytes()).hexdigest()
    }
    for name, value in (("selection", state), ("changes", changes), ("metadata", metadata)):
        (output/(name+".json")).write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    if args.pdf:
        from .reporting import render_report
        render_report(table, common, cfg, output, args.georgia_dir)
    print(output)


if __name__ == "__main__":
    main()
