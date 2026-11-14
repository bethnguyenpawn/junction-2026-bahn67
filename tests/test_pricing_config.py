"""Offline tests (no server, no key): pricing rules, fee schedules and config parsing.

    python -m unittest discover -s tests
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import pricing  # noqa: E402
from config import DEFAULT, PRESETS, Params, from_overrides  # noqa: E402
from dispatch import fee_schedule, steep_schedule  # noqa: E402

NOON = 12 * 60  # Monday 12:00


def request(options, respond_by=NOON):
    return {"id": "R1", "respondBy": respond_by, "legs": [{}], "referenceFeeCents": 5000,
            "options": [{"kind": k, "deadline": d, "listPriceCents": p} for k, d, p in options]}


SAME = ("same_day", 20 * 60, 10000)            # Monday 20:00
NEXT = ("next_day", 24 * 60 + 20 * 60, 12000)  # Tuesday 20:00


class Pricing(unittest.TestCase):
    def test_levels_1_to_3_quote_list_price_of_first_option(self):
        p = PRESETS["l8"]  # even with tuned params, levels 1-3 must stay at list price
        for level in (1, 2, 3):
            self.assertEqual(pricing.quote(request([SAME, NEXT]), level, p, km=900, backlog=50), {"same_day": 10000})

    def test_default_is_starter_at_level_8(self):
        self.assertEqual(pricing.quote(request([SAME, NEXT]), 8, DEFAULT), {"same_day": 10000})

    def test_quote_mult_and_backlog(self):
        p = Params(quote_mult=1.6, backlog_k=0.01)
        self.assertEqual(pricing.quote(request([SAME]), 8, p), {"same_day": 16000})
        self.assertEqual(pricing.quote(request([SAME]), 8, p, backlog=10), {"same_day": 17000})

    def test_long_trip_is_declined_far_above_list(self):
        p = Params(quote_mult=1.6, decline_km=500)
        self.assertEqual(pricing.quote(request([SAME]), 8, p, km=501), {"same_day": 100000})
        self.assertEqual(pricing.quote(request([SAME]), 8, p, km=500), {"same_day": 16000})

    def test_slack_filter_drops_options_without_time(self):
        p = Params(quote_mult=1.5, min_slack_h=8)
        # same_day: 20:00 - 12:00 - 2h drive = 6h < 8h -> dropped; next_day kept
        self.assertEqual(pricing.quote(request([SAME, NEXT]), 8, p, drive_min=120), {"next_day": 18000})
        # nothing left -> decline at 10x list
        self.assertEqual(pricing.quote(request([SAME]), 8, p, drive_min=120), {"same_day": 100000})

    def test_later_mult_only_changes_later_options(self):
        p = Params(quote_mult=1.5, min_slack_h=1, later_mult=1.1)
        self.assertEqual(pricing.quote(request([SAME, NEXT]), 8, p), {"same_day": 15000, "next_day": 19800})

    def test_dealer_trust_only_at_level_8_and_capped(self):
        p = Params(quote_mult=1.0, trust_w=1.0)
        self.assertEqual(pricing.quote(request([SAME]), 7, p, trust=10), {"same_day": 10000})
        self.assertEqual(pricing.quote(request([SAME]), 8, p, trust=10), {"same_day": 11000})
        self.assertEqual(pricing.quote(request([SAME]), 8, p, trust=99), {"same_day": 12500})

    def test_prices_are_whole_cents(self):
        q = pricing.quote(request([("same_day", 20 * 60, 3333)]), 8, Params(quote_mult=1.37))
        self.assertIsInstance(q["same_day"], int)


class Fees(unittest.TestCase):
    def test_level_1_has_one_step(self):
        self.assertEqual(fee_schedule(100, 5000, 1, DEFAULT), [{"at": 100, "feeCents": 5000}])
        self.assertEqual(steep_schedule(100, 5000, 1, DEFAULT), [{"at": 100, "feeCents": 7500}])

    def test_starter_schedule_rises_and_never_falls(self):
        steps = fee_schedule(0, 5000, 8, PRESETS["l8"])
        self.assertEqual(steps[0]["feeCents"], 4000)  # opens at 0.8x
        fees = [s["feeCents"] for s in steps]
        self.assertEqual(fees, sorted(fees))
        self.assertTrue(all(isinstance(f, int) for f in fees))


class Config(unittest.TestCase):
    def test_overrides_use_field_types_not_preset_values(self):
        p = from_overrides(["decline_km=450.5", "raise_steps=4"], PRESETS["l8"])
        self.assertEqual(p.decline_km, 450.5)
        self.assertEqual(p.raise_steps, 4)
        self.assertEqual(p.quote_mult, PRESETS["l8"].quote_mult)  # rest of the preset kept

    def test_unknown_parameter_fails(self):
        with self.assertRaises(SystemExit):
            from_overrides(["nope=1"])

    def test_presets_exist(self):
        self.assertEqual(set(config.PRESETS), {"starter", "l1", "l8", "l8_v1"})
        self.assertIs(PRESETS["starter"], DEFAULT)


if __name__ == "__main__":
    unittest.main()
