"""Locks the levels string pasted into the TradingView "NQ Precision Map" indicator.

The Pine Script reads exactly 24 comma separated numbers by position:
  0DTE   res, wall, floor, supp, swall, sfloor, flip, dn, u50, u25, l25, l50
  Weekly res, wall, floor, supp, swall, sfloor, flip, dn, u50, u25, l25, l50

Never reorder or remove a position. New values may only be appended after
position 24, which older copies of the indicator ignore.
"""

import unittest
from datetime import datetime
from unittest import mock

from nq_precision import gamma_math as gm
from nq_precision import full_data as fd
from nq_precision import full_ui as ui
from test_levels_pipeline import NOW, _synthetic_chain

PINE_ORDER = [
    "Target Resistance", "Primary Wall", "Primary Floor", "Target Support",
    "Secondary Wall", "Secondary Floor", "Gamma Flip", "Delta Neutral",
    "Upper 0.50σ", "Upper 0.25σ", "Lower 0.25σ", "Lower 0.50σ",
]


class TradingViewFormatTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            mock.patch.object(gm, "now_et", return_value=NOW),
            mock.patch.object(fd.st, "session_state", {}),
        ]
        for p in self.patches:
            p.start()
        exps = [datetime(2026, 10, 19), datetime(2026, 10, 23)]
        chain = _synthetic_chain(600.0, exps)
        self.d0 = fd.process_expiration(chain, exps[0], 600.0, 41.0, 24600.0)
        self.wk = fd.process_expiration(chain, exps[1], 600.0, 41.0, 24600.0)

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def _values(self):
        out = ui._build_generated_levels_output_string(self.d0, self.wk)
        self.assertIsNotNone(out)
        return out, [float(x) for x in out.split(",")]

    def test_exactly_24_positive_numbers(self):
        out, vals = self._values()
        self.assertEqual(len(vals), 24)
        self.assertTrue(all(v > 0 for v in vals))
        self.assertNotIn(" ", out)
        # Two decimals each, which is what str.tonumber in the script parses.
        self.assertTrue(all(len(x.split(".")[1]) == 2 for x in out.split(",")))

    def test_positions_match_pine_order(self):
        _, vals = self._values()
        for block, data in ((0, self.d0), (12, self.wk)):
            by_name = {row[0]: float(row[1]) for row in data["results"]}
            for i, name in enumerate(PINE_ORDER):
                self.assertAlmostEqual(vals[block + i], round(by_name[name], 2), places=2, msg=name)

    def test_missing_weekly_gives_no_string(self):
        self.assertIsNone(ui._build_generated_levels_output_string(self.d0, None))


if __name__ == "__main__":
    unittest.main()
