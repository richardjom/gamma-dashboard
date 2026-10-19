import math
import unittest
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from nq_precision import gamma_math as gm

ET = gm.ET


def _chain(rows, expiration):
    """rows: list of (type, strike, open_interest[, iv[, volume]])."""
    recs = []
    for r in rows:
        typ, strike, oi = r[0], r[1], r[2]
        iv = r[3] if len(r) > 3 else 0.20
        vol = r[4] if len(r) > 4 else 0.0
        recs.append(
            {
                "type": typ,
                "strike": float(strike),
                "open_interest": float(oi),
                "volume": float(vol),
                "iv": iv,
                "expiration": expiration,
                "bid": 1.0,
                "ask": 1.1,
                "gamma": 0.0,
                "delta": 0.0,
            }
        )
    return pd.DataFrame(recs)


def _closed_form_gamma(S, K, T, sigma, r=gm.DEFAULT_RATE, q=0.0):
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    return math.exp(-q * T) * math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi) / (S * sigma * math.sqrt(T))


def _old_per_strike_flip(df):
    """The previous implementation: first sign change of per strike net GEX."""
    by = df.groupby("strike", as_index=False)["GEX"].sum().sort_values("strike")
    for i in range(1, len(by)):
        a, b = by["GEX"].iloc[i - 1], by["GEX"].iloc[i]
        if a * b < 0:
            x0, x1 = by["strike"].iloc[i - 1], by["strike"].iloc[i]
            return x0 + (0 - a) * (x1 - x0) / (b - a)
    return None


class BlackScholesTests(unittest.TestCase):
    def test_gamma_matches_closed_form(self):
        for S, K, T, sig in [(600, 605, 5 / 365, 0.2), (25000, 24500, 0.002, 0.35), (100, 100, 1.0, 0.15)]:
            self.assertAlmostEqual(float(gm.bs_gamma(S, K, T, sig)), _closed_form_gamma(S, K, T, sig), places=10)

    def test_put_call_delta_parity(self):
        S, K, T, sig = 100.0, 102.0, 0.1, 0.25
        c = float(gm.bs_delta(S, K, T, sig, True, q=0.0))
        p = float(gm.bs_delta(S, K, T, sig, False, q=0.0))
        self.assertAlmostEqual(c - p, 1.0, places=6)

    def test_invalid_inputs_return_zero_gamma(self):
        self.assertEqual(float(gm.bs_gamma(100, 100, 0.0, 0.2)), 0.0)
        self.assertEqual(float(gm.bs_gamma(100, 100, 0.1, 0.0)), 0.0)


class TimeHandlingTests(unittest.TestCase):
    def test_qqq_expires_at_4pm_et(self):
        exp = datetime(2026, 10, 20)
        settle = gm.settlement_time_et(exp, "QQQ")
        self.assertEqual((settle.hour, settle.minute), (16, 0))
        self.assertEqual(settle.tzinfo, ET)

    def test_ndx_monthly_is_am_settled_but_ndxp_is_not(self):
        third_friday = datetime(2026, 10, 16)
        self.assertEqual(gm.settlement_time_et(third_friday, "NDX").hour, 9)
        self.assertEqual(gm.settlement_time_et(third_friday, "NDXP").hour, 16)
        self.assertEqual(gm.settlement_time_et(datetime(2026, 10, 23), "NDX").hour, 16)

    def test_schwab_settlement_flag_wins(self):
        self.assertEqual(gm.settlement_time_et(datetime(2026, 10, 23), "XYZ", "AM").hour, 9)

    def test_zero_dte_time_and_expired_after_close(self):
        exp = datetime(2026, 10, 19)
        df = _chain([("call", 600, 10)], exp)
        at_3pm = datetime(2026, 10, 19, 15, 0, tzinfo=ET)
        t = gm.time_to_expiry_years(df, now=at_3pm)[0]
        self.assertAlmostEqual(t * gm.MINUTES_PER_YEAR, 60.0, places=6)
        # 6pm ET is already past 16:00 ET even though it is the next day in UTC.
        at_6pm = datetime(2026, 10, 19, 18, 0, tzinfo=ET)
        self.assertEqual(gm.time_to_expiry_years(df, now=at_6pm)[0], 0.0)

    def test_minimum_minutes_floor(self):
        exp = datetime(2026, 10, 19)
        df = _chain([("call", 600, 10)], exp)
        t = gm.time_to_expiry_years(df, now=datetime(2026, 10, 19, 15, 59, tzinfo=ET))[0]
        self.assertAlmostEqual(t * gm.MINUTES_PER_YEAR, gm.MIN_MINUTES_TO_EXPIRY, places=6)


class ChainPrepTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 19, 10, 0, tzinfo=ET)
        self.exp = datetime(2026, 10, 23)

    def test_gex_includes_contract_multiplier(self):
        df = gm.prepare_chain(_chain([("call", 100, 10)], self.exp), 100.0, now=self.now, q=0.0)
        g = float(df["gamma"].iloc[0])
        self.assertAlmostEqual(float(df["GEX"].iloc[0]), g * 10 * 100 * 100.0 ** 2 * 0.01, places=6)

    def test_puts_are_negative_gex(self):
        df = gm.prepare_chain(_chain([("put", 100, 10)], self.exp), 100.0, now=self.now)
        self.assertLess(float(df["GEX"].iloc[0]), 0.0)

    def test_expired_rows_dropped(self):
        df = _chain([("call", 100, 10)], datetime(2026, 10, 16))
        self.assertTrue(gm.prepare_chain(df, 100.0, now=self.now).empty)

    def test_missing_iv_is_interpolated_not_dropped(self):
        df = _chain([("call", 95, 5, 0.30), ("call", 100, 5, 0.0), ("call", 105, 5, 0.20)], self.exp)
        out = gm.prepare_chain(df, 100.0, now=self.now)
        self.assertEqual(len(out), 3)
        imputed = out[out["strike"] == 100.0].iloc[0]
        self.assertTrue(bool(imputed["iv_imputed"]))
        self.assertAlmostEqual(float(imputed["iv"]), 0.25, places=6)

    def test_rescale_preserves_dollar_exposure(self):
        ndx_spot, qqq_spot = 25000.0, 610.0
        k = qqq_spot / ndx_spot
        ndx = _chain([("call", 25200, 300, 0.22), ("put", 24800, 450, 0.25), ("call", 25000, 120, 0.21)], self.exp)
        native = gm.prepare_chain(ndx, ndx_spot, now=self.now)
        scaled = gm.prepare_chain(gm.rescale_chain(ndx, k, "NDX"), qqq_spot, now=self.now)
        self.assertAlmostEqual(native["GEX"].sum() / scaled["GEX"].sum(), 1.0, places=9)
        native_dollar_delta = (native["delta"] * native["open_interest"] * 100 * ndx_spot).sum()
        scaled_dollar_delta = (scaled["delta"] * scaled["open_interest"] * 100 * qqq_spot).sum()
        self.assertAlmostEqual(native_dollar_delta / scaled_dollar_delta, 1.0, places=9)
        self.assertTrue((scaled["underlying"] == "NDX").all())


class LevelSolverTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 19, 10, 0, tzinfo=ET)
        self.exp = datetime(2026, 10, 23)

    def test_flip_between_symmetric_put_and_call_walls(self):
        df = gm.prepare_chain(_chain([("call", 110, 1000), ("put", 90, 1000)], self.exp), 100.0, now=self.now, q=0.0)
        sol = gm.solve_level(df, 100.0, "gamma", q=0.0)
        self.assertTrue(sol["in_range"])
        self.assertGreater(sol["level"], 97.0)
        self.assertLess(sol["level"], 102.0)
        # Gamma really is negative below the flip and positive above it.
        below = gm.gamma_profile(df, np.array([sol["level"] - 1.0]), q=0.0)[0]
        above = gm.gamma_profile(df, np.array([sol["level"] + 1.0]), q=0.0)[0]
        self.assertLess(below, 0.0)
        self.assertGreater(above, 0.0)

    def test_old_method_was_fooled_by_far_strikes(self):
        # A small far out of the money call cluster at 80 creates a per strike
        # sign change far below spot. Total gamma does not flip there.
        rows = [("call", 80, 50), ("put", 85, 400), ("put", 90, 1000), ("call", 110, 1000)]
        df = gm.prepare_chain(_chain(rows, self.exp), 100.0, now=self.now, q=0.0)
        old = _old_per_strike_flip(df)
        new = gm.solve_level(df, 100.0, "gamma", q=0.0)["level"]
        self.assertLess(old, 86.0)
        self.assertGreater(new, 95.0)

    def test_no_crossing_reports_out_of_range(self):
        df = gm.prepare_chain(_chain([("call", 100, 1000), ("call", 105, 500)], self.exp), 100.0, now=self.now)
        sol = gm.solve_level(df, 100.0, "gamma")
        self.assertFalse(sol["in_range"])

    def test_delta_neutral_is_where_call_and_put_delta_balance(self):
        df = gm.prepare_chain(_chain([("call", 110, 1000), ("put", 90, 1000)], self.exp), 100.0, now=self.now, q=0.0)
        sol = gm.solve_level(df, 100.0, "delta", q=0.0)
        self.assertTrue(sol["in_range"])
        net = gm.net_delta_profile(df, np.array([sol["level"]]), q=0.0)[0]
        self.assertAlmostEqual(net / 1000.0, 0.0, places=3)
        # Net open interest delta rises with spot, so only one crossing exists.
        self.assertEqual(len(gm.zero_crossings(sol["grid"], sol["values"])), 1)

    def test_zero_crossing_interpolation(self):
        grid = np.array([0.0, 1.0, 2.0, 3.0])
        vals = np.array([-3.0, -1.0, 1.0, 3.0])
        self.assertAlmostEqual(gm.nearest_zero_crossing(grid, vals, 0.0), 1.5)


if __name__ == "__main__":
    unittest.main()
