import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

import numpy as np
import pandas as pd

from nq_precision import gamma_math as gm
from nq_precision import full_data as fd
from nq_precision import level_log
from test_levels_pipeline import NOW, _synthetic_chain

ET = gm.ET


class SessionAndRatioTests(unittest.TestCase):
    def test_equity_session_states(self):
        cases = {
            datetime(2026, 10, 19, 10, 0, tzinfo=ET): "regular",
            datetime(2026, 10, 19, 17, 30, tzinfo=ET): "extended",
            datetime(2026, 10, 19, 6, 0, tzinfo=ET): "extended",
            datetime(2026, 10, 19, 20, 43, tzinfo=ET): "closed",
            datetime(2026, 10, 18, 12, 0, tzinfo=ET): "closed",  # Sunday
        }
        for when, expect in cases.items():
            self.assertEqual(fd.equity_session_state(when), expect, when)

    def test_held_ratio_uses_nq_at_last_qqq_print(self):
        hold = fd.held_closed_ratio(24700.0, 600.0, 1_700_000_000_000, nq_at_fn=lambda ts: 24600.0)
        self.assertAlmostEqual(hold["ratio"], 41.0)
        # NQ moved 100 points since QQQ's last print, so implied QQQ moves too.
        self.assertAlmostEqual(hold["implied_qqq"], 24700.0 / 41.0)

    def test_held_ratio_rejects_bad_inputs(self):
        self.assertIsNone(fd.held_closed_ratio(24700.0, 600.0, None, nq_at_fn=lambda ts: 24600.0))
        self.assertIsNone(fd.held_closed_ratio(24700.0, 600.0, 1, nq_at_fn=lambda ts: None))
        self.assertIsNone(fd.held_closed_ratio(24700.0, 6000.0, 1, nq_at_fn=lambda ts: 24600.0))

    def test_closed_market_accepts_last_schwab_print(self):
        evening = datetime(2026, 10, 19, 20, 43, tzinfo=ET)
        last_print_ms = int(datetime(2026, 10, 19, 19, 59, tzinfo=ET).timestamp() * 1000)
        with mock.patch.object(gm, "now_et", return_value=evening), \
                mock.patch.object(fd.time, "time", return_value=evening.timestamp()), \
                mock.patch.object(fd, "_get_schwab_quotes", return_value={"QQQ": {}}), \
                mock.patch.object(fd, "_extract_quote_price", return_value=601.25), \
                mock.patch.object(fd, "_extract_quote_timestamp_ms", return_value=last_print_ms), \
                mock.patch.object(fd, "_set_quote_meta") as meta:
            fd.get_qqq_price_with_source.clear()
            price, source = fd.get_qqq_price_with_source("key")
        self.assertEqual(price, 601.25)
        self.assertEqual(source, "Schwab (last print)")
        meta.assert_called_with("QQQ", "Schwab (last print)", last_print_ms)


class IvSmoothingTests(unittest.TestCase):
    def _group(self, spot=600.0, T=3 / 365):
        strikes = np.arange(570, 631, 2.0)
        rows = []
        for k in strikes:
            z = np.log(k / spot) / (0.20 * np.sqrt(T))
            true_iv = 0.20 + 0.01 * z * z - 0.02 * z
            typ = "call" if k >= spot else "put"
            rows.append({"strike": k, "type": typ, "iv": true_iv, "true": true_iv, "T": T,
                         "expiration": "2026-10-22", "bid": 1.0})
        return pd.DataFrame(rows)

    def test_outliers_replaced_and_clean_points_kept(self):
        df = self._group()
        bad_idx = [3, 10, 25]
        df.loc[bad_idx, "iv"] = [1.9, 0.02, np.nan]
        out = gm.smooth_iv(df, 600.0)
        for i in bad_idx:
            self.assertTrue(bool(out.loc[i, "iv_smoothed"]))
            self.assertAlmostEqual(float(out.loc[i, "iv"]), float(out.loc[i, "true"]), delta=0.01)
        clean = [i for i in range(len(df)) if i not in bad_idx]
        np.testing.assert_allclose(out.loc[clean, "iv"], df.loc[clean, "iv"])

    def test_too_few_points_leaves_chain_alone(self):
        df = self._group().head(4)
        out = gm.smooth_iv(df, 600.0)
        self.assertFalse(out["iv_smoothed"].any())


class FlowTests(unittest.TestCase):
    def test_classify_trade_side(self):
        last = [1.10, 1.00, 1.05, 1.05, 0.0]
        bid = [1.00, 1.00, 1.00, 1.00, 1.00]
        ask = [1.10, 1.10, 1.10, 1.10, 1.10]
        tick = ["up", "down", "up", "no_change", "up"]
        np.testing.assert_array_equal(fd.classify_trade_side(last, bid, ask, tick), [1, -1, 1, 0, 0])

    def _snap(self, vol, last):
        return pd.DataFrame({"option": ["QQQ261019C00600000"], "type": ["call"], "volume": [vol],
                             "bid": [1.00], "ask": [1.10], "last": [last]})

    def test_flow_counts_only_new_volume_with_side(self):
        store = {}
        t = NOW
        first = fd.update_flow(self._snap(500, 1.10), "QQQ", store=store, now_et=t, persist=False)
        self.assertEqual(float(first["flow_net"].iloc[0]), 0.0)  # earlier volume is unknown
        second = fd.update_flow(self._snap(800, 1.10), "QQQ", store=store, now_et=t, persist=False)
        self.assertEqual(float(second["flow_net"].iloc[0]), 300.0)
        third = fd.update_flow(self._snap(900, 1.00), "QQQ", store=store, now_et=t, persist=False)
        self.assertEqual(float(third["flow_net"].iloc[0]), 200.0)
        self.assertAlmostEqual(float(third["flow_tracked"].iloc[0]), 400.0)
        # New trading day starts clean.
        nxt = fd.update_flow(self._snap(50, 1.10), "QQQ", store=store, now_et=t + timedelta(days=1), persist=False)
        self.assertEqual(float(nxt["flow_net"].iloc[0]), 0.0)

    def test_flow_adjusted_open_interest_signs(self):
        df = pd.DataFrame({"type": ["call", "put"], "open_interest": [1000.0, 1000.0], "flow_net": [300.0, 300.0]})
        np.testing.assert_allclose(gm.flow_adjusted_open_interest(df), [700.0, 1300.0])

    def test_flow_view_lowers_gamma_when_customers_buy_calls(self):
        exp = datetime(2026, 10, 19)
        chain = _synthetic_chain(600.0, [exp])
        chain["flow_net"] = np.where(chain["type"] == "call", chain["open_interest"] * 0.5, 0.0)
        chain["flow_tracked"] = chain["volume"]
        with mock.patch.object(gm, "now_et", return_value=NOW), mock.patch.object(fd.st, "session_state", {}):
            base = fd.process_expiration(chain, exp, 600.0, 41.0, 24600.0)
            flow = fd.process_expiration(chain, exp, 600.0, 41.0, 24600.0, weight_mode="flow")
        self.assertEqual(flow["weight_mode"], "flow")
        self.assertLess(flow["total_gex"], base["total_gex"])
        self.assertGreater(flow["flow_coverage"], 0.0)


class ProjectionTests(unittest.TestCase):
    def test_projection_reprices_and_expires(self):
        exp = datetime(2026, 10, 19)
        at_3pm = datetime(2026, 10, 19, 15, 0, tzinfo=ET)
        df = gm.prepare_chain(_synthetic_chain(600.0, [exp]), 600.0, now=at_3pm)
        proj = gm.project_levels(df, 600.0, (30, 60))
        self.assertEqual([p["minutes"] for p in proj], [30, 60])
        self.assertGreater(proj[0]["contracts"], 0)
        self.assertNotEqual(proj[0]["gex_at_spot"], 0.0)
        # Everything settles at 16:00, so nothing is left an hour ahead.
        self.assertEqual(proj[1]["contracts"], 0)
        self.assertIsNone(proj[1]["flip"])

    def test_process_expiration_adds_projections_during_session(self):
        exp = datetime(2026, 10, 19)
        with mock.patch.object(gm, "now_et", return_value=NOW), mock.patch.object(fd.st, "session_state", {}):
            out = fd.process_expiration(_synthetic_chain(600.0, [exp]), exp, 600.0, 41.0, 24600.0)
        self.assertEqual(len(out["projections"]), 2)
        self.assertAlmostEqual(out["projections"][0]["flip_nq"], out["projections"][0]["flip"] * 41.0)


class SnapshotAndCalibrationTests(unittest.TestCase):
    def test_chain_snapshot_once_per_slot_in_session(self):
        chain = _synthetic_chain(600.0, [datetime(2026, 10, 19), datetime(2026, 11, 20)])
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "level_snapshots.csv")
            level_log._written_slots.clear()
            t = datetime(2026, 10, 19, 10, 37, tzinfo=ET)
            first = level_log.maybe_write_chain_snapshot(chain, 600.0, 24600.0, 41.0, path=log, now=t)
            self.assertTrue(first.endswith(os.path.join("2026-10-19", "1030.csv.gz")))
            self.assertIsNone(level_log.maybe_write_chain_snapshot(chain, 600.0, 24600.0, 41.0, path=log, now=t + timedelta(minutes=3)))
            saved = pd.read_csv(first)
            self.assertEqual(set(pd.to_datetime(saved["expiration"]).dt.date.astype(str)), {"2026-10-19"})
            self.assertTrue(saved["strike"].between(540, 660).all())
            evening = datetime(2026, 10, 19, 18, 0, tzinfo=ET)
            self.assertIsNone(level_log.maybe_write_chain_snapshot(chain, 600.0, 24600.0, 41.0, path=log, now=evening))

    def test_hold_rates_need_enough_sessions(self):
        rows = []
        for day in range(12):
            for outcome in ("held", "held", "broke") if day % 2 else ("held",):
                rows.append({"view": "0DTE", "level_name": "Gamma Flip", "session_date": f"2026-09-{day + 1:02d}", "outcome": outcome})
        rows.append({"view": "0DTE", "level_name": "Primary Wall", "session_date": "2026-09-01", "outcome": "held"})
        rates = level_log.hold_rates_by_level(pd.DataFrame(rows), "0DTE")
        self.assertTrue(rates["Gamma Flip"]["enough"])
        self.assertAlmostEqual(rates["Gamma Flip"]["hold_rate"], round(18 / 24, 3))
        self.assertFalse(rates["Primary Wall"]["enough"])


if __name__ == "__main__":
    unittest.main()


class ReviewFixTests(unittest.TestCase):
    def test_prepare_chain_handles_duplicate_index(self):
        exp = datetime(2026, 10, 23)
        chain = _synthetic_chain(600.0, [exp])
        chain.index = [0] * len(chain)  # every row shares one label
        chain.loc[:, "iv"] = chain["iv"].where(np.arange(len(chain)) % 7 != 0, 0.0)
        out = gm.prepare_chain(chain, 600.0, now=NOW)
        self.assertEqual(len(out), len(chain))
        self.assertTrue((out["iv"] > 0).all())

    def test_nq_price_at_uses_bars_that_closed_by_the_print(self):
        idx = pd.date_range("2026-10-19 19:45", periods=4, freq="5min", tz=ET)
        bars = pd.DataFrame({"Close": [1.0, 2.0, 3.0, 4.0]}, index=idx)
        print_ms = int(datetime(2026, 10, 19, 19, 59, tzinfo=ET).timestamp() * 1000)
        with mock.patch.object(fd, "get_intraday_history", return_value=bars):
            # 19:55 bar ends at 20:00, after the 19:59 print, so 19:50's close is used.
            self.assertEqual(fd.nq_price_at(print_ms), 2.0)

    def test_qqq_quote_function_is_cached_and_session_state_is_not(self):
        self.assertTrue(hasattr(fd.get_qqq_price_with_source, "clear"))
        self.assertFalse(hasattr(fd.equity_session_state, "clear"))

    def test_flow_store_has_lock(self):
        import threading

        store = {"date": None, "contracts": {}, "lock": threading.Lock()}
        snap = pd.DataFrame({"option": ["X"], "type": ["call"], "volume": [10], "bid": [1.0], "ask": [1.1], "last": [1.1]})
        fd.update_flow(snap, "QQQ", store=store, now_et=NOW, persist=False)
        snap["volume"] = 20
        out = fd.update_flow(snap, "QQQ", store=store, now_et=NOW, persist=False)
        self.assertEqual(float(out["flow_net"].iloc[0]), 10.0)
        self.assertFalse(store["lock"].locked())
