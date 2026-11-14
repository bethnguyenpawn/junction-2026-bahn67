"""Offline tests (no server, no key): pricing rules, fee schedules and config parsing.

python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import pricing  # noqa: E402
from config import DAY, DEFAULT, HOUR, PRESETS, Params, from_overrides  # noqa: E402
from dispatch import Desk, fee_schedule, next_plan_at, steep_schedule  # noqa: E402

NOON = 12 * 60  # Monday 12:00


def quote(req, level, params, **situation):
    return pricing.quote(req, level, params, pricing.Situation(**situation))


def request(options, respond_by=NOON):
    return {
        "id": "R1",
        "respondBy": respond_by,
        "legs": [{}],
        "referenceFeeCents": 5000,
        "options": [{"kind": k, "deadline": d, "listPriceCents": p} for k, d, p in options],
    }


SAME = ("same_day", 20 * 60, 10000)  # Monday 20:00
NEXT = ("next_day", 24 * 60 + 20 * 60, 12000)  # Tuesday 20:00


class Pricing(unittest.TestCase):
    def test_levels_1_to_3_quote_list_price_of_first_option(self):
        p = PRESETS["l8"]  # even with tuned params, levels 1-3 must stay at list price
        for level in (1, 2, 3):
            self.assertEqual(quote(request([SAME, NEXT]), level, p, km=900, backlog=50), {"same_day": 10000})

    def test_default_is_starter_at_level_8(self):
        self.assertEqual(quote(request([SAME, NEXT]), 8, DEFAULT), {"same_day": 10000})

    def test_quote_mult_and_backlog(self):
        p = Params(quote_mult=1.6, backlog_k=0.01)
        self.assertEqual(quote(request([SAME]), 8, p), {"same_day": 16000})
        self.assertEqual(quote(request([SAME]), 8, p, backlog=10), {"same_day": 17000})

    def test_long_trip_is_declined_far_above_list(self):
        p = Params(quote_mult=1.6, decline_km=500)
        self.assertEqual(quote(request([SAME]), 8, p, km=501), {"same_day": 100000})
        self.assertEqual(quote(request([SAME]), 8, p, km=500), {"same_day": 16000})

    def test_slack_filter_drops_options_without_time(self):
        p = Params(quote_mult=1.5, min_slack_h=8)
        # same_day: 20:00 - 12:00 - 2h drive = 6h < 8h -> dropped; next_day kept
        self.assertEqual(quote(request([SAME, NEXT]), 8, p, drive_min=120), {"next_day": 18000})
        # nothing left -> decline at 10x list
        self.assertEqual(quote(request([SAME]), 8, p, drive_min=120), {"same_day": 100000})

    def test_later_mult_only_changes_later_options(self):
        p = Params(quote_mult=1.5, min_slack_h=1, later_mult=1.1)
        self.assertEqual(quote(request([SAME, NEXT]), 8, p), {"same_day": 15000, "next_day": 19800})

    def test_dealer_trust_only_at_level_8_and_capped(self):
        p = Params(quote_mult=1.0, trust_w=1.0)
        self.assertEqual(quote(request([SAME]), 7, p, trust=10), {"same_day": 10000})
        self.assertEqual(quote(request([SAME]), 8, p, trust=10), {"same_day": 11000})
        self.assertEqual(quote(request([SAME]), 8, p, trust=99), {"same_day": 12500})

    def test_drivers_near_pickup_move_the_price(self):
        p = Params(quote_mult=1.5, dense_n=40, dense_cut=0.2, sparse_n=5, sparse_add=0.1)
        self.assertEqual(quote(request([SAME]), 8, p, near=40), {"same_day": 13000})
        self.assertEqual(quote(request([SAME]), 8, p, near=10), {"same_day": 15000})
        self.assertEqual(quote(request([SAME]), 8, p, near=4), {"same_day": 16000})
        self.assertEqual(quote(request([SAME]), 8, p), {"same_day": 15000})  # unknown: no change

    def test_private_address_surcharge_and_decline(self):
        r = request([SAME])
        r["legs"] = [{"pickup": {"privateAddress": True}, "delivery": {"privateAddress": False}}]
        self.assertEqual(quote(r, 8, Params(quote_mult=1.5, private_add=0.2)), {"same_day": 17000})
        self.assertEqual(quote(r, 8, Params(quote_mult=1.5, private_add=9)), {"same_day": 100000})

    def test_delivery_place_offset(self):
        r = request([SAME])
        r["legs"] = [{"delivery": {"placeId": "vantaa"}}]
        offset = pricing.DEST_OFFSET["vantaa"]  # competitor cheap there: we quote lower
        self.assertLess(offset, 0)
        self.assertEqual(
            quote(r, 8, Params(quote_mult=1.5, dest_k=1.0)), {"same_day": int(10000 * (1.5 + offset) + 0.5)}
        )
        r["legs"] = [{"delivery": {"placeId": "nowhere"}}]  # unknown place: no offset
        self.assertEqual(quote(r, 8, Params(quote_mult=1.5, dest_k=1.0)), {"same_day": 15000})

    def test_expected_profit_price_accounts_for_delivery_place_offset(self):
        r = request([SAME])
        r["arrivedAt"] = NOON
        r["legs"] = [{"pickup": {"privateAddress": False}, "delivery": {"privateAddress": False, "placeId": "vantaa"}}]
        p = Params(opt=1)
        s = pricing.Situation(km=30, near=80, near_delivery=80)
        vantaa = pricing.best_price(r, r["options"][0], p, s)
        r["legs"][0]["delivery"]["placeId"] = "joensuu"
        joensuu = pricing.best_price(r, r["options"][0], p, s)
        self.assertLess(vantaa, joensuu)

    def test_win_rate_adjustment_moves_the_price(self):
        p = Params(quote_mult=1.5)
        self.assertEqual(quote(request([SAME]), 8, p, adapt=-0.1), {"same_day": 14000})
        self.assertEqual(quote(request([SAME]), 3, p, adapt=-0.1), {"same_day": 10000})  # levels 1-3: list

    def test_is_decline(self):
        r = request([SAME, NEXT])
        self.assertTrue(pricing.is_decline(r, {"same_day": 100000}))
        self.assertFalse(pricing.is_decline(r, {"same_day": 14500, "next_day": 13050}))

    def test_prices_are_whole_cents(self):
        q = quote(request([("same_day", 20 * 60, 3333)]), 8, Params(quote_mult=1.37))
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


class Plan(unittest.TestCase):
    def test_plans_from_07_to_19_every_n_hours(self):
        self.assertEqual(next_plan_at(0, 3), 7 * HOUR)  # Monday 00:00 -> 07:00
        self.assertEqual(next_plan_at(7 * HOUR, 3), 10 * HOUR)  # strictly after now
        self.assertEqual(next_plan_at(18 * HOUR, 3), 19 * HOUR)
        self.assertEqual(next_plan_at(19 * HOUR, 3), DAY + 7 * HOUR)  # after 19:00 -> next day 07:00


class PairChange(unittest.TestCase):
    """Test final (Sat 14:00): a dealer changed one car of a two-car gig; we withdrew the gig and reposted only that
    car, so the other car never got a driver."""

    def order(self, oid):
        window = {"from": 0, "to": DAY}
        place = {"placeId": "a", "privateAddress": False, "window": window}
        car = {"premium": False, "electric": False, "chargePercent": None}
        return {
            "id": oid,
            "legs": [{"car": car, "pickup": place, "delivery": {**place, "placeId": "b"}}],
            "deadline": DAY,
            "deliveredAt": [None],
        }

    def test_changed_car_reposts_its_partner(self):
        desk = Desk(None, 8, 10 * HOUR, PRESETS["l8_plan"])
        for oid in ("A", "B"):
            desk.orders[oid] = self.order(oid)
            desk.requests[oid] = {"referenceFeeCents": 5000, "note": None, "legs": [{}]}
        stops = [{"orderId": oid, "leg": 0, "kind": kind} for oid in ("A", "B") for kind in ("pickup", "delivery")]
        desk.carry({"type": "post", "stops": stops, "audience": {}, "schedule": []}, "g1")
        desk.change(self.order("A"))
        posted = sorted(a["stops"][0]["orderId"] for a in desk.outbox if a["type"] == "post")
        self.assertIn({"type": "withdraw", "gigId": "g1"}, desk.outbox)
        self.assertEqual(posted, ["A", "B"])


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
        self.assertEqual(
            set(config.PRESETS), {"starter", "l1", "l8", "l8_plan", "l8_guarded", "l8_v3", "l8_v2", "l8_v1"}
        )
        self.assertIs(PRESETS["starter"], DEFAULT)

    def test_l8_guarded_keeps_lane_price_and_reliability_filters(self):
        p = PRESETS["l8_guarded"]
        self.assertEqual((p.dest_k, p.opt, p.opt_backlog), (1.0, 1, 0.04))
        self.assertEqual((p.decline_km, p.min_slack_h), (550, 8))
        self.assertEqual((p.opt_guard_late, p.opt_guard_backlog, p.opt_delta_cap), (0.08, 3, 0.06))

    def test_l8_guarded_falls_back_to_flat_price_on_high_late_risk_or_backlog(self):
        r = request([SAME])
        r["arrivedAt"] = NOON
        r["legs"] = [{"pickup": {"privateAddress": False}, "delivery": {"privateAddress": False, "placeId": "vantaa"}}]
        p = PRESETS["l8_guarded"]
        flat = quote(r, 8, PRESETS["l8"], near=0)
        self.assertEqual(quote(r, 8, p, near=0), flat)
        self.assertEqual(
            quote(r, 8, p, km=30, near=80, near_delivery=80, backlog=3),
            quote(r, 8, PRESETS["l8"], km=30, near=80, near_delivery=80, backlog=3),
        )

    def test_l8_guarded_caps_low_risk_price_change(self):
        r = request([SAME])
        r["arrivedAt"] = NOON
        r["legs"] = [{"pickup": {"privateAddress": False}, "delivery": {"privateAddress": False, "placeId": "vantaa"}}]
        p = PRESETS["l8_guarded"]
        guarded = quote(r, 8, p, km=30, near=80, near_delivery=80)
        flat = quote(r, 8, PRESETS["l8"], km=30, near=80, near_delivery=80)
        self.assertLessEqual(abs(guarded["same_day"] - flat["same_day"]), int(SAME[2] * p.opt_delta_cap + 0.5))


class Outage(unittest.TestCase):
    """The desk calls it an outage when it wins most of today's quotes near the pickup (Params.outage_*)."""

    def setUp(self):
        roads = {("a", "a"): {"km": 0}, ("a", "b"): {"km": 50}, ("a", "c"): {"km": 300}}
        self.desk = Desk(None, 8, 0, Params(outage_add=0.3, outage_n=4, outage_rate=0.75), roads)
        self.tuesday_10 = DAY + 10 * HOUR

    def request(self, at):
        return {"arrivedAt": at, "legs": [{"pickup": {"placeId": "a"}}]}

    def test_won_most_quotes_nearby(self):
        self.desk.answers = [(self.tuesday_10 - 60, "b", True)] * 3 + [(self.tuesday_10 - 60, "a", False)]
        self.assertTrue(self.desk.outage_near(self.request(self.tuesday_10)))

    def test_not_enough_answers_far_away_or_other_day(self):
        self.desk.answers = [(self.tuesday_10 - 60, "b", True)] * 3 + [(self.tuesday_10 - 60, "c", True)]
        self.assertFalse(self.desk.outage_near(self.request(self.tuesday_10)))  # c is 300 km away
        self.desk.answers = [(self.tuesday_10 - DAY, "b", True)] * 4  # yesterday
        self.assertFalse(self.desk.outage_near(self.request(self.tuesday_10)))
        self.desk.answers = [(self.tuesday_10 - 60, "b", True)] * 4
        self.assertFalse(self.desk.outage_near(self.request(DAY + 19 * HOUR)))  # outages end at 18:00


if __name__ == "__main__":
    unittest.main()
