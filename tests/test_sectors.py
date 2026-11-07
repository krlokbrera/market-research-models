import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
import pandas as pd
from market_models.sectors import screen, select_sectors, explain_changes


class SectorTests(unittest.TestCase):
    def setUp(self):
        self.index = pd.bdate_range("2023-01-02", periods=320)
        t = np.arange(320)
        self.prices = pd.DataFrame({"WORLD":100*np.exp(.0002*t),
                                    "A":100*np.exp(.001*t),
                                    "B":100*np.exp(-.0002*t)}, index=self.index)
        self.cutoff = self.index[-1]+pd.Timedelta(days=1)

    def test_returns_and_trend_filter(self):
        table, _ = screen(self.prices, "WORLD", self.cutoff)
        self.assertTrue(table.loc["A", "eligible"])
        self.assertFalse(table.loc["B", "eligible"])
        self.assertAlmostEqual(table.loc["A", "return_3m"], np.exp(.063)-1)

    def test_future_data_cannot_change_screen(self):
        cutoff = self.index[290]
        first, _ = screen(self.prices, "WORLD", cutoff)
        changed = self.prices.copy()
        changed.loc[cutoff:, "A"] *= 3
        second, _ = screen(changed, "WORLD", cutoff)
        pd.testing.assert_frame_equal(first, second)

    def test_stale_and_short_history_fail(self):
        with self.assertRaises(ValueError):
            screen(self.prices, "WORLD", self.cutoff+pd.Timedelta(days=20))
        with self.assertRaises(ValueError):
            screen(self.prices.iloc[-100:], "WORLD", self.cutoff)

    def test_missing_latest_price_fails(self):
        self.prices.iloc[-1, 1] = np.nan
        with self.assertRaises(ValueError):
            screen(self.prices, "WORLD", self.cutoff)

    def test_hysteresis_and_broken_trend_exit(self):
        table = pd.DataFrame({"score":[55,80,30], "eligible":[True,True,True]}, index=["A","B","C"])
        self.assertEqual(select_sectors(table, ["A","C"], limit=2), ["A","B"])
        table.loc["A", "eligible"] = False
        self.assertEqual(select_sectors(table, ["A"], limit=2), ["B"])

    def test_new_sector_can_replace_failed_incumbent(self):
        table = pd.DataFrame({"score":[65.,85.,20.], "eligible":[True,True,False]},
                             index=["BASE","NEW","OLD"])
        selected = select_sectors(table, ["OLD"], limit=2)
        self.assertEqual(selected, ["NEW","BASE"])
        changes = {x["ticker"]:x for x in explain_changes(table, selected, ["OLD"])}
        self.assertEqual(changes["OLD"]["reason"], "trend_filter_failed")
        self.assertEqual(changes["NEW"]["status"], "entered")

    def test_weak_market_does_not_force_selection(self):
        table = pd.DataFrame({"score":[90.,50.], "eligible":[False,False]}, index=["A","B"])
        self.assertEqual(select_sectors(table, ["A"]), [])

    def test_invalid_settings_and_duplicate_dates_fail(self):
        table, _ = screen(self.prices, "WORLD", self.cutoff)
        for kwargs in ({"entry":float("nan")}, {"entry":30,"exit_score":60}, {"limit":True}):
            with self.assertRaises(ValueError):
                select_sectors(table, **kwargs)
        duplicate = pd.concat([self.prices.iloc[:2], self.prices.iloc[1:]])
        with self.assertRaises(ValueError):
            screen(duplicate, "WORLD", self.cutoff)

    def test_cli_records_state_and_partial_coverage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cfg = {"benchmark":"WORLD","currency":"EUR","rotation":{},
                   "sectors":{t:{"name":t,"baseline":t=="A"} for t in ["A","B","MISSING"]}}
            (root/"cfg.json").write_text(json.dumps(cfg), encoding="utf-8")
            self.prices.to_csv(root/"prices.csv", index_label="date")
            run = subprocess.run([sys.executable,"-m","market_models.sectors",
                                  "--prices",str(root/"prices.csv"),"--config",str(root/"cfg.json"),
                                  "--asof",str(self.cutoff.date()),"--output",str(root/"out")],
                                  capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            out = Path(run.stdout.strip())
            meta = json.loads((out/"metadata.json").read_text())
            self.assertEqual(meta["excluded_missing_columns"], ["MISSING"])
            self.assertEqual(meta["configured_sectors"], 3)
            state = json.loads((out/"selection.json").read_text())
            self.assertEqual(state["last_close"], str(self.index[-1].date()))
            self.assertEqual(state["universe"], ["A","B"])


if __name__ == "__main__":
    unittest.main()
