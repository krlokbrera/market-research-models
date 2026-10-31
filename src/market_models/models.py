"""Causal signals, a close-to-close ledger and conditional risk scenarios."""
from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

@dataclass
class Costs:
    commission_eur: float = 1.0
    spread_bps: float = 4.0
    slippage_bps: float = 3.0
    fx_bps: float = 10.0
    fee_bps: float = 0.0

    def __post_init__(self):
        for value in vars(self).values():
            if isinstance(value, bool) or not np.isfinite(value) or value < 0:
                raise ValueError("Costs must be finite and nonnegative.")

    @property
    def variable(self):
        return (self.spread_bps / 2 + self.slippage_bps +
                self.fx_bps + self.fee_bps) / 10000

def validate_prices(prices):
    if not isinstance(prices.index, pd.DatetimeIndex) or prices.index.tz is not None:
        raise ValueError("Use a timezone-naive daily DatetimeIndex.")
    if prices.index.hasnans or prices.columns.has_duplicates:
        raise ValueError("Invalid dates or duplicate asset names.")
    if prices.empty or not prices.index.is_monotonic_increasing:
        raise ValueError("Prices must be nonempty and ordered.")
    if prices.index.has_duplicates or prices.isna().any().any():
        raise ValueError("Duplicate dates or missing prices; repair source data.")
    if not np.isfinite(prices.to_numpy()).all() or (prices <= 0).any().any():
        raise ValueError("Nonpositive or nonfinite prices.")
    return prices.astype(float)

def features(p):
    r = p.pct_change(fill_method=None)
    return pd.DataFrame({
        "mom21": p.pct_change(21, fill_method=None),
        "mom63": p.pct_change(63, fill_method=None),
        "mom126": p.pct_change(126, fill_method=None),
        "vol21": r.rolling(21).std(),
        "trend200": p / p.rolling(200).mean() - 1
    })

def rebalance_positions(index, frequency):
    # Calendar boundaries are known before execution. No return data are used.
    key = index.to_period("M" if frequency == "monthly" else "W-SUN")
    return np.flatnonzero(np.asarray(key[:-1] != key[1:]))

def signals(prices, kind="momentum", annualization=252, target_vol=.10,
            cap=.35, top_n=3, rebalance="monthly"):
    if annualization not in (252, 365) or rebalance not in ("monthly", "weekly"):
        raise ValueError("Invalid calendar or rebalance setting.")
    if not np.isfinite(target_vol) or target_vol <= 0 or not 0 < cap <= 1:
        raise ValueError("Positive finite target volatility and cap in (0,1] required.")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or top_n < 1:
        raise ValueError("top_n must be a positive integer.")
    p = validate_prices(prices)
    r = p.pct_change(fill_method=None)
    vol = r.rolling(63).std() * np.sqrt(annualization)
    lookback, skip = (365, 30) if annualization == 365 else (252, 21)
    momentum = p.shift(skip) / p.shift(lookback) - 1
    trend = p > p.rolling(200).mean()
    out = pd.DataFrame(np.nan, index=p.index, columns=p.columns)
    predictions = pd.DataFrame(np.nan, index=p.index, columns=p.columns)
    fs = {s: features(p[s]) for s in p}
    for t in rebalance_positions(p.index, rebalance):
        if t < lookback:
            continue
        if kind == "ridge":
            for s in p:
                # y_i uses prices at i+21. Last training label ends strictly before t.
                x = fs[s]
                y = p[s].shift(-21) / p[s] - 1
                cutoff = t - 21
                train = x.iloc[max(0, t-1260):cutoff].copy()
                target = y.reindex(train.index)
                ok = train.notna().all(axis=1) & target.notna()
                if ok.sum() < 252 or x.iloc[t].isna().any():
                    continue
                model = make_pipeline(StandardScaler(), Ridge(alpha=10.0))
                model.fit(train.loc[ok], target.loc[ok])
                predictions.loc[p.index[t], s] = model.predict(x.iloc[[t]])[0]
            if predictions.iloc[t].isna().all():
                continue
            score = predictions.iloc[t].copy()
            eligible = (score > .003) & trend.iloc[t]
        elif kind == "momentum":
            score = momentum.iloc[t].copy()
            eligible = (score > 0) & trend.iloc[t]
        else:
            raise ValueError("Unknown model")
        eligible &= vol.iloc[t].notna() & (vol.iloc[t] > 1e-8)
        chosen = score[eligible].nlargest(top_n).index
        w = pd.Series(0.0, index=p.columns)
        if len(chosen):
            inv = 1 / vol.iloc[t][chosen]
            w.loc[chosen] = (inv / inv.sum()).clip(upper=cap)
            cov = r.iloc[t-62:t+1].cov().to_numpy() * annualization
            risk = np.sqrt(max(0.0, float(w.to_numpy() @ cov @ w.to_numpy())))
            if risk > target_vol:
                w *= target_vol / risk
        out.iloc[t] = w
    return out, predictions

def simulate(prices, targets, capital=3000.0, costs=None,
             cash_rate=0.0, annualization=252, min_trade=25.0):
    """Targets formed at t close execute at t+1 close, after that day's return.
    Amounts are fractional total-return units, not broker share quantities.
    Costs reduce cash. Positive cash accrues a fixed user-specified scenario rate.
    """
    p = validate_prices(prices)
    costs = costs or Costs()
    if not np.isfinite([capital,cash_rate,min_trade]).all() or annualization not in (252,365) or min_trade < 0:
        raise ValueError("Invalid finite cash, trade or calendar setting.")
    if capital <= 0 or cash_rate < 0:
        raise ValueError("Positive capital and nonnegative cash rate required.")
    if set(targets.columns) != set(p.columns):
        raise ValueError("Target assets must match prices.")
    mixed = targets.notna().any(axis=1) & ~targets.notna().all(axis=1)
    if mixed.any():
        raise ValueError("Partial target rows are not allowed.")
    targets = targets.reindex(index=p.index, columns=p.columns)
    v = np.zeros(p.shape[1])
    cash = float(capital)
    records, trades = [], []
    daily_cash = (1 + cash_rate) ** (1 / annualization) - 1
    returns = p.pct_change(fill_method=None).fillna(0.0).to_numpy()
    for t, date in enumerate(p.index):
        v *= 1 + returns[t]
        cash *= 1 + daily_cash
        cost_today, turnover = 0.0, 0.0
        # Yesterday's signal; current close is never used to form this order.
        if t and targets.iloc[t-1].notna().all():
            w = targets.iloc[t-1].to_numpy(dtype=float)
            if (w < 0).any() or w.sum() > 1 + 1e-9:
                raise ValueError("Long-only unlevered weights required.")
            wealth = cash + v.sum()
            delta = wealth * w - v
            delta[np.abs(delta) < min_trade] = 0.0
            # Sell first, then scale buys for cash, variable and fixed costs.
            for j in np.flatnonzero(delta < 0):
                amount = -delta[j]
                fee = costs.commission_eur + amount * costs.variable
                if fee >= amount:
                    continue
                v[j] -= amount
                cash += amount - fee
                cost_today += fee
                turnover += amount
                trades.append((date, p.columns[j], -amount, fee))
            buys = np.flatnonzero(delta > 0)
            if len(buys):
                budget = max(0.0, cash - len(buys) * costs.commission_eur)
                scale = min(1.0, budget / (delta[buys].sum() * (1+costs.variable)))
                for j in buys:
                    amount = delta[j] * scale
                    fee = costs.commission_eur + amount * costs.variable
                    if amount < min_trade or amount + fee > cash + 1e-8:
                        continue
                    v[j] += amount
                    cash -= amount + fee
                    cost_today += fee
                    turnover += amount
                    trades.append((date, p.columns[j], amount, fee))
        wealth = cash + v.sum()
        records.append((date, wealth, cash, cost_today, turnover))
    ledger = pd.DataFrame(records, columns=["date","equity","cash","cost_eur","traded_eur"]).set_index("date")
    tr = pd.DataFrame(trades, columns=["date","asset","signed_eur","cost_eur"])
    return ledger, tr

def metrics(ledger, initial, annualization=252, cash_rate=0.0):
    eq = ledger.equity
    rr = pd.Series(np.r_[eq.iloc[0]/initial-1, eq.to_numpy()[1:]/eq.to_numpy()[:-1]-1],
                   index=eq.index)
    peak = np.maximum.accumulate(np.r_[initial, eq.to_numpy()])[1:]
    sd = rr.std(ddof=1)
    tail = rr[rr <= rr.quantile(.05)]
    return {"observations":len(rr), "final_eur":float(eq.iloc[-1]),
        "total_return":float(eq.iloc[-1]/initial-1),
        "cagr":float((eq.iloc[-1]/initial)**(annualization/len(rr))-1),
        "volatility":float(sd*np.sqrt(annualization)),
        "sharpe_vs_cash":float((rr.mean()-((1+cash_rate)**(1/annualization)-1))/sd*np.sqrt(annualization)) if sd > 0 else None,
        "max_drawdown":float((eq.to_numpy()/peak-1).min()),
        "daily_expected_shortfall_95":float(tail.mean()),
        "total_cost_eur":float(ledger.cost_eur.sum()),
        "annual_traded_over_average_equity":float(ledger.traded_eur.sum()/eq.mean()*annualization/len(eq))}

def block_scenarios(returns, initial, annualization=252, paths=1000, seed=81):
    """Empirical block bootstrap, conditional scenario, not a forecast."""
    a = np.asarray(returns.dropna(), float)
    if len(a) < 100:
        raise ValueError("Insufficient history for scenarios.")
    block = 7 if annualization == 365 else 21
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, len(a)-block+1, size=(paths, int(np.ceil(annualization/block))))
    samples = np.concatenate([a[z[:,None]+np.arange(block)] for z in starts.T], axis=1)[:, :annualization]
    ends = initial * np.prod(1+samples, axis=1)
    return {"label":"conditional historical bootstrap; not expected returns",
        "p05_eur":float(np.quantile(ends,.05)), "p50_eur":float(np.quantile(ends,.5)),
        "p95_eur":float(np.quantile(ends,.95)), "prob_loss_in_resample":float((ends<initial).mean())}

def event_study(prices, event_date, benchmark="BTC-USD",
                estimation=120, gap=10, windows=(0,1,3,7)):
    """Daily UTC close model; window 0 includes incident day; no causal claim.
    Regression is estimated before event-gap. Incomplete event windows are NA.
    BTC uses a constant pre-event mean, other assets use a BTC market model.
    """
    if benchmark not in prices.columns:
        raise ValueError("Event benchmark is absent.")
    if len(pd.date_range(prices.index.min(),prices.index.max())) != len(prices):
        raise ValueError("Event study requires complete daily calendar prices.")
    r = np.log(validate_prices(prices)).diff()
    event = pd.Timestamp(event_date)
    train = r[(r.index < event-pd.Timedelta(days=gap)) &
              (r.index >= event-pd.Timedelta(days=estimation))].dropna()
    if len(train) < 60:
        raise ValueError("Need at least 60 complete pre-event days.")
    rows = []
    for s in r:
        x = np.ones((len(train),1)) if s == benchmark else np.column_stack([np.ones(len(train)),train[benchmark]])
        b = np.linalg.lstsq(x, train[s].to_numpy(), rcond=None)[0]
        for h in windows:
            end = event + pd.Timedelta(days=h)
            obs = r.loc[event:end]
            complete = len(obs) == h+1 and obs.index.max() == end
            car = None
            if complete:
                xp = np.ones((len(obs),1)) if s == benchmark else np.column_stack([np.ones(len(obs)),obs[benchmark]])
                car = float(np.expm1((obs[s].to_numpy()-xp@b).sum()))
            rows.append({"asset":s,"window_end":h,"complete":complete,
                         "abnormal_compounded_return":car,"alpha":float(b[0]),
                         "beta_btc":None if s == benchmark else float(b[1]),
                         "note":"Descriptive association; daily bars mix pre/post incident."})
    return pd.DataFrame(rows)


def risk_snapshot(prices,annualization=252):
    p=validate_prices(prices)
    r=p.pct_change(fill_method=None)
    rows=[]
    for s in p:
        z=r[s].dropna()
        last=p[s].iloc[-1]
        tail=z.tail(annualization)
        q=tail.quantile(.05)
        row={"asset":s,"last_date":p.index[-1],"last_price":last,
             "vol63":float(z.tail(63).std()*np.sqrt(annualization)),
             "ewma_vol":float(np.sqrt(z.pow(2).ewm(alpha=.06,adjust=False).mean().iloc[-1]*annualization)),
             "es95_daily":float(tail[tail<=q].mean()),
             "distance_sma200":float(last/p[s].tail(200).mean()-1)}
        for n,name in [(21,"return_21obs"),(63,"return_63obs"),(annualization,"return_1year")]:
            row[name]=float(last/p[s].iloc[-n-1]-1) if len(p)>n else None
        rows.append(row)
    return pd.DataFrame(rows)

def robust_flow_z(series,window=52,min_obs=26):
    """Compare current observation with an exclusively past robust baseline."""
    if min_obs < 10 or min_obs > window:
        raise ValueError("Insufficient minimum sample or invalid window.")
    past=series.shift(1).rolling(window,min_periods=min_obs)
    median=past.median()
    mad=past.apply(lambda x: np.median(np.abs(x-np.median(x))),raw=True)
    return (series-median)/(1.4826*mad.replace(0,np.nan))

