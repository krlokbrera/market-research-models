import contextlib
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
from market_models.cli import main, load_config, load_prices, example
from market_models.models import Costs, simulate, signals, metrics, event_study, robust_flow_z

ROOT = Path(__file__).resolve().parents[1]

def synthetic(n=850, crypto=False):
    rng = np.random.default_rng(81)
    idx = pd.date_range("2021-01-01",periods=n) if crypto else pd.bdate_range("2015-01-01",periods=n)
    return pd.DataFrame(100*np.exp(np.cumsum(rng.normal(.0002,.01,(n,3)),axis=0)),
                        index=idx,columns=["BTC-USD" if crypto else "SPY","SYNTH_B","SYNTH_C"])

class ModelTests(unittest.TestCase):
    def test_execution_after_signal_day_return(self):
        idx = pd.date_range("2020-01-01",periods=4)
        p = pd.DataFrame({"A":[100,200,200,400]},index=idx)
        t = pd.DataFrame({"A":[1,np.nan,np.nan,np.nan]},index=idx)
        ledger,trades = simulate(p,t,1000,Costs(0,0,0,0,0),min_trade=0)
        np.testing.assert_allclose(ledger.equity,[1000,1000,1000,2000])
        self.assertEqual(trades.iloc[0]["date"],idx[1])

    def test_costs_never_financed_with_negative_cash(self):
        p = synthetic(5)[["SPY"]]
        t = pd.DataFrame(np.nan,index=p.index,columns=p.columns)
        t.iloc[0] = 1.
        ledger,trades = simulate(p,t,1000,Costs())
        self.assertTrue((ledger.cash >= -1e-8).all())
        self.assertEqual(len(trades),1)

    def test_unchanged_holdings_have_no_phantom_fees(self):
        idx = pd.date_range("2020-01-01",periods=4)
        p = pd.DataFrame({"A":[100]*4},index=idx)
        t = pd.DataFrame({"A":[.5,np.nan,np.nan,np.nan]},index=idx)
        ledger,trades = simulate(p,t,1000,Costs(1,0,0,0,0))
        self.assertEqual(len(trades),1)
        self.assertAlmostEqual(ledger.equity.iloc[-1],999)

    def test_initial_commission_in_drawdown(self):
        idx = pd.date_range("2020-01-01",periods=2)
        p = pd.DataFrame({"A":[100,100]},index=idx)
        t = pd.DataFrame({"A":[1,np.nan]},index=idx)
        ledger,_ = simulate(p,t,1000,Costs(1,0,0,0,0))
        self.assertAlmostEqual(metrics(ledger,1000)["max_drawdown"],-.001)

    def test_future_prices_do_not_change_past_signals(self):
        p = synthetic()
        changed = p.copy()
        changed.iloc[710:] *= np.linspace(1,100,len(p)-710)[:,None]
        for kind in ("momentum","ridge"):
            a,_ = signals(p,kind=kind)
            b,_ = signals(changed,kind=kind)
            pd.testing.assert_frame_equal(a.iloc[:710],b.iloc[:710])
            valid = a.dropna()
            self.assertFalse(valid.empty)
            self.assertTrue((valid >= 0).all().all())
            self.assertTrue((valid.sum(axis=1) <= 1+1e-9).all())

    def test_partial_targets_rejected(self):
        p = synthetic(5)
        t = pd.DataFrame(np.nan,index=p.index,columns=p.columns)
        t.iloc[0,0] = .5
        with self.assertRaises(ValueError):
            simulate(p,t)

    def test_incomplete_event_window_stays_missing(self):
        p = synthetic(183,crypto=True)
        event = p.index[-2].strftime("%Y-%m-%d")
        f = event_study(p,event_date=event)
        self.assertTrue(f[f.window_end<=1].complete.all())
        self.assertFalse(f[f.window_end>=3].complete.any())
        self.assertTrue(f[f.window_end>=3].abnormal_compounded_return.isna().all())

    def test_flows_need_history_and_only_use_past(self):
        self.assertTrue(robust_flow_z(pd.Series([1.,2.,3.,4.,5.])).isna().all())
        z = pd.Series(np.arange(60,dtype=float))
        changed = z.copy()
        changed.iloc[50:] = 9999.
        pd.testing.assert_series_equal(robust_flow_z(z).iloc[:50],robust_flow_z(changed).iloc[:50])

class InputAndDataTests(unittest.TestCase):
    def test_config_rejects_unknown_or_nonfinite_values(self):
        cfg = load_config(ROOT/"config/traditional.json")
        for key,value in (("unknown",1),("cap",float("nan")),("top_n",True),("fee_bps",-1)):
            altered = dict(cfg)
            altered[key] = value
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)/"cfg.json"
                p.write_text(json.dumps(altered),encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_config(p)

    def test_unsafe_or_duplicate_headers_are_rejected(self):
        for header in ("date,=FORMULA","date,SPY,SPY"):
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp)/"input.csv"
                p.write_text(header+"\n2020-01-01,100,100\n",encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_prices(p)

    def test_bad_prices_and_dates_are_rejected(self):
        p = synthetic(5)
        cases=[]
        bad=p.copy();bad.iloc[0,0]=np.inf;cases.append(bad)
        bad=p.copy();bad.iloc[0,0]=0;cases.append(bad)
        bad=p.copy();bad.index=[p.index[0]]*len(p);cases.append(bad)
        for case in cases:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/"input.csv"
                case.to_csv(path,index_label="date")
                with self.assertRaises(ValueError):
                    load_prices(path)

    def test_cutoff_excludes_day_and_later(self):
        p = synthetic(5)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"prices.csv"
            p.to_csv(path,index_label="date")
            result = load_prices(path,p.index[3].strftime("%Y-%m-%d"))
            self.assertEqual(len(result),3)
            self.assertTrue((result.index < p.index[3]).all())

    def test_examples_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/"synthetic.csv"
            with contextlib.redirect_stdout(io.StringIO()):
                example(p,"traditional")
            before = p.read_bytes()
            with self.assertRaises(FileExistsError):
                example(p,"traditional")
            self.assertEqual(before,p.read_bytes())

    def test_cli_both_calendars_and_local_manifests(self):
        for market in ("traditional","crypto"):
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                prices = folder/"private_source_name.csv"
                with contextlib.redirect_stdout(io.StringIO()):
                    example(prices,market)
                    status=main(["backtest","--prices",str(prices),"--config",str(ROOT/"config"/(market+".json")),
                         "--output",str(folder/"outputs"),"--data-label","synthetic","--asof","2026-01-01"])
                self.assertEqual(status,0)
                runs=list((folder/"outputs").iterdir())
                self.assertEqual(len(runs),1)
                manifest=json.loads((runs[0]/"run_manifest.json").read_text())
                self.assertEqual(manifest["data_label"],"synthetic")
                self.assertEqual(manifest["input_sha256"],hashlib.sha256(prices.read_bytes()).hexdigest())
                self.assertNotIn("private_source_name",json.dumps(manifest))
                result=json.loads((runs[0]/"metrics.json").read_text())
                self.assertEqual(set(result["results"]),{"momentum","ridge","buy_hold","equal_weight"})
                self.assertTrue((runs[0]/"momentum_ledger.csv").is_file())

if __name__=="__main__":
    unittest.main()
