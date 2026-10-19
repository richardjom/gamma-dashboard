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

ET = gm.ET
NOW = datetime(2026, 10, 19, 10, 30, tzinfo=ET)  # Monday, mid session


def _synthetic_chain(spot, expirations, underlying="QQQ", root="QQQ", step=1.0, seed=7):
    """A QQQ like chain: put OI heavy below spot, call OI heavy above."""
    rng = np.random.default_rng(seed)
    rows = []
    strikes = np.arange(round(spot * 0.85 / step) * step, spot * 1.15, step)
    for exp in expirations:
        for k in strikes:
            m = (k - spot) / spot
            iv = 0.18 + 0.6 * m * m - 0.10 * m
            call_oi = max(0.0, 4000 * np.exp(-((m - 0.015) / 0.03) ** 2) + rng.uniform(0, 200))
            put_oi = max(0.0, 5000 * np.exp(-((m + 0.02) / 0.035) ** 2) + rng.uniform(0, 200))
            for typ, oi in (("call", call_oi), ("put", put_oi)):
                rows.append(
                    {
                        "option": f"{root}{exp:%y%m%d}{typ[0].upper()}{int(k * 1000):08d}",
                        "type": typ,
                        "strike": float(k),
                        "expiration": exp,
                        "open_interest": float(oi),
                        "volume": float(oi * 0.3),
                        "iv": float(iv),
                        "bid": 1.00,
                        "ask": 1.10,
                        "gamma": 0.0,
                        "delta": 0.0,
                        "root": root,
                        "underlying": underlying,
                    }
                )
    return pd.DataFrame(rows)


class _FakeSessionState(dict):
    pass


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            mock.patch.object(gm, "now_et", return_value=NOW),
            mock.patch.object(fd.st, "session_state", _FakeSessionState()),
        ]
        for p in self.patches:
            p.start()
        self.spot = 600.0
        self.exps = [datetime(2026, 10, 19), datetime(2026, 10, 23), datetime(2026, 11, 20)]
        self.chain = _synthetic_chain(self.spot, self.exps)

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def test_expirations_use_eastern_time(self):
        exp0, wk, mo = fd.get_expirations_by_type(self.chain)
        self.assertEqual(exp0.date(), datetime(2026, 10, 19).date())
        # After the 16:00 ET close the same day, today's contracts are gone.
        with mock.patch.object(gm, "now_et", return_value=datetime(2026, 10, 19, 17, 0, tzinfo=ET)):
            exp0_late, _, _ = fd.get_expirations_by_type(self.chain)
        self.assertEqual(exp0_late.date(), datetime(2026, 10, 23).date())

    def test_process_expiration_uses_full_chain_and_reprices(self):
        ratio = 41.0
        out = fd.process_expiration(self.chain, self.exps[1], self.spot, ratio, self.spot * ratio)
        self.assertIsNotNone(out)
        full = self.chain[(self.chain["expiration"] == self.exps[1]) & (self.chain["open_interest"] > 0)]
        self.assertEqual(len(out["df"]), len(full))
        self.assertLess(len(out["df_levels"]), len(out["df"]))
        self.assertAlmostEqual(out["g_flip_nq"], out["g_flip_strike"] * ratio)
        # The flip matches an independent solve on the same full chain.
        prepared = gm.prepare_chain(full, self.spot, now=NOW, q=0.006)
        expect = gm.solve_level(prepared, self.spot, "gamma", q=0.006)["level"]
        self.assertAlmostEqual(out["g_flip_strike"], expect, places=6)
        self.assertTrue(out["g_flip_in_range"])
        self.assertIn("gamma_profile", out)
        self.assertEqual(len(out["gamma_profile"]["nq"]), len(out["gamma_profile"]["gex_oi"]))
        self.assertEqual(out["data_meta"]["flip_model"], "bs_reprice_profile_v1")
        # Floor below wall, both mapped into NQ.
        self.assertLess(out["p_floor"], out["p_wall"])

    def test_all_expirations_view(self):
        out = fd.process_expiration(self.chain, fd.ALL_EXPIRATIONS, self.spot, 41.0, self.spot * 41.0)
        self.assertIsNotNone(out)
        self.assertEqual(out["df"]["expiration"].nunique(), 3)
        self.assertIn("All expirations", out["expiration_label"])

    def test_combined_chain_adds_ndx_with_preserved_exposure(self):
        ndx_spot = 24600.0
        ndx = _synthetic_chain(ndx_spot, [self.exps[1]], underlying="NDX", root="NDXP", step=10.0, seed=11)
        combined, info = fd.build_combined_chain(self.chain, self.spot, ndx, ndx_spot)
        self.assertEqual(info["underlyings"], ["QQQ", "NDX"])
        self.assertAlmostEqual(info["k"], self.spot / ndx_spot)
        ndx_native = gm.prepare_chain(ndx, ndx_spot, now=NOW)
        ndx_scaled = gm.prepare_chain(combined[combined["underlying"] == "NDX"], self.spot, now=NOW)
        self.assertAlmostEqual(ndx_native["GEX"].sum() / ndx_scaled["GEX"].sum(), 1.0, places=9)
        out = fd.process_expiration(combined, self.exps[1], self.spot, 41.0, self.spot * 41.0)
        self.assertEqual(out["underlyings"], ["NDX", "QQQ"])

    def test_combined_chain_rejects_bad_spot_ratio(self):
        combined, info = fd.build_combined_chain(self.chain, self.spot, self.chain, self.spot)
        self.assertEqual(info["underlyings"], ["QQQ"])
        self.assertIn("out of bounds", info["note"])

    def test_cboe_freshness_accounts_for_known_delay(self):
        now_ms = int(NOW.timestamp() * 1000)
        with mock.patch.object(fd.time, "time", return_value=NOW.timestamp()):
            fd._set_dataset_meta("options:QQQ", "CBOE", timestamp_ms=now_ms - 16 * 60 * 1000,
                                 max_age_sec=180, expected_delay_sec=15 * 60)
            fresh = fd.get_dataset_freshness("options:QQQ", max_age_sec=150)
            self.assertEqual(fresh["status"], "delayed")
            fd._set_dataset_meta("options:QQQ", "CBOE", timestamp_ms=now_ms - 40 * 60 * 1000,
                                 max_age_sec=180, expected_delay_sec=15 * 60)
            self.assertEqual(fd.get_dataset_freshness("options:QQQ", max_age_sec=150)["status"], "stale_hard")

    def test_closed_session_snapshot_is_not_stale(self):
        evening = datetime(2026, 10, 19, 21, 0, tzinfo=ET)
        close_ms = int(datetime(2026, 10, 19, 16, 15, tzinfo=ET).timestamp() * 1000)
        with mock.patch.object(gm, "now_et", return_value=evening), \
                mock.patch.object(fd.time, "time", return_value=evening.timestamp()):
            fd._set_dataset_meta("options:QQQ", "CBOE", timestamp_ms=close_ms, expected_delay_sec=900)
            self.assertEqual(fd.get_dataset_freshness("options:QQQ", max_age_sec=150)["status"], "session_closed")

    def test_cboe_timestamp_parsed_as_eastern(self):
        ms = fd._cboe_timestamp_ms({"timestamp": "2026-10-19 10:15:00", "data": {}})
        self.assertEqual(ms, int(datetime(2026, 10, 19, 10, 15, tzinfo=ET).timestamp() * 1000))


class LevelLogTests(unittest.TestCase):
    def test_snapshot_and_scoring(self):
        data = {
            "results": [("Gamma Flip", 24600.0, 10.0, ""), ("Primary Wall", 24700.0, 5.0, ""), ("Upper 0.50σ", 1.0, 1.0, "")],
            "underlyings": ["NDX", "QQQ"],
            "data_meta": {"options_source": "test", "flip_model": "bs_reprice_profile_v1"},
        }
        saved_at = datetime(2026, 10, 19, 9, 50, tzinfo=ET)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "log.csv")
            self.assertEqual(level_log.maybe_auto_snapshot(data, "0DTE", 24550.0, 41.0, path=path, now=saved_at), 2)
            # Second call the same day does nothing.
            self.assertEqual(level_log.maybe_auto_snapshot(data, "0DTE", 24550.0, 41.0, path=path, now=saved_at), 0)
            log = level_log.read_log(path)
        self.assertEqual(sorted(log["level_name"]), ["Gamma Flip", "Primary Wall"])

        # Price rallies into 24700, rejects 40 pts. 24600 gets sliced through.
        idx = pd.date_range("2026-10-19 09:55", periods=10, freq="5min", tz=ET)
        closes = [24560, 24590, 24625, 24660, 24690, 24680, 24655, 24640, 24630, 24620]
        bars = pd.DataFrame({"Open": closes, "High": [c + 12 for c in closes], "Low": [c - 12 for c in closes], "Close": closes}, index=idx)
        scored = level_log.score_levels(log, bars, tolerance_pts=8, reaction_pts=25, break_pts=15, lookahead_bars=6)
        outcomes = dict(zip(scored["level_name"], scored["outcome"]))
        self.assertEqual(outcomes["Primary Wall"], "held")
        self.assertEqual(outcomes["Gamma Flip"], "broke")
        summary = level_log.summarize_scores(scored)
        self.assertEqual(set(summary["level_name"]), {"Gamma Flip", "Primary Wall"})


if __name__ == "__main__":
    unittest.main()
