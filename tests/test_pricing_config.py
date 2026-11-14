"""Offline tests (no server, no key): pricing rules, fee schedules and config parsing.

python -m unittest discover -s tests
"""

import math
import os
import sys
import unittest
import unittest.mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import dispatch
import notes
import pricing
from config import DAY, DEFAULT, HOUR, PRESETS, Params, from_overrides
from dispatch import Desk, fee_schedule, maximum_cardinality_matching, next_plan_at, steep_schedule

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

    def test_slack_counts_the_deadline_moved_by_a_later_ready_day(self):
        req = request([NEXT])  # Tuesday 20:00
        req["legs"] = [{"pickup": {"window": {"from": NOON}}}]
        option = req["options"][0]
        same_day = notes.Facts(ready=NOON + 4 * HOUR)  # ready Monday 16:00: waits 4 h, the deadline stays
        self.assertEqual(pricing.slack(req, option, pricing.Situation(facts=same_day)), 32 * HOUR - 4 * HOUR)
        next_day = notes.Facts(ready=DAY + 10 * HOUR)  # ready Tuesday 10:00: waits 22 h, the deadline moves a day
        self.assertEqual(pricing.slack(req, option, pricing.Situation(facts=next_day)), 32 * HOUR - 22 * HOUR + DAY)

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

    def test_early_cut_opens_lower_with_the_same_cap(self):
        normal = fee_schedule(0, 5000, 8, PRESETS["l8"])
        early = fee_schedule(0, 5000, 8, PRESETS["l8"], cut=0.2)
        self.assertEqual(early[0]["feeCents"], 3000)  # 0.6x
        self.assertEqual(early[-1]["feeCents"], normal[-1]["feeCents"])
        self.assertEqual(len(early), len(normal) + 2)

    def test_early_cut_only_for_cars_ready_later(self):
        desk = Desk(None, 8, 0, Params(early_cut=0.1, early_h=12))
        for oid, ready in (("now", 0), ("tomorrow", 13 * 60)):
            window = {"from": ready, "to": DAY}
            desk.orders[oid] = {"id": oid, "legs": [{"pickup": {"window": window}}]}
        self.assertEqual(desk.early_cut({"orderId": "now", "leg": 0, "kind": "pickup"}), 0.0)
        self.assertEqual(desk.early_cut({"orderId": "tomorrow", "leg": 0, "kind": "pickup"}), 0.1)


class Plan(unittest.TestCase):
    def test_plans_from_07_to_19_every_n_hours(self):
        self.assertEqual(next_plan_at(0, 3), 7 * HOUR)  # Monday 00:00 -> 07:00
        self.assertEqual(next_plan_at(7 * HOUR, 3), 10 * HOUR)  # strictly after now
        self.assertEqual(next_plan_at(18 * HOUR, 3), 19 * HOUR)
        self.assertEqual(next_plan_at(19 * HOUR, 3), DAY + 7 * HOUR)  # after 19:00 -> next day 07:00

    def test_maximum_matching_does_not_strand_a_feasible_pair(self):
        # The preferred edge 0-1 blocks the greedy matcher, while 0-2 and 1-3 form two pairs.
        pairs = maximum_cardinality_matching([[1, 2], [0, 3], [0], [1]])
        self.assertEqual(len(pairs), 2)
        self.assertEqual({node for pair in pairs for node in pair}, {0, 1, 2, 3})

    def test_maximum_matching_handles_odd_cycles(self):
        # A triangle with one outside neighbor per vertex requires blossom contraction to match all six.
        graph = [[1, 2, 3], [0, 2, 4], [0, 1, 5], [0], [1], [2]]
        pairs = maximum_cardinality_matching(graph)
        self.assertEqual(len(pairs), 3)
        self.assertEqual(len({node for pair in pairs for node in pair}), 6)

    def test_plan_match_finds_two_pairs_where_greedy_finds_one(self):
        links = {("a", "b"): 1, ("a", "c"): 2, ("b", "d"): 2}

        def run(preset):
            desk = Desk(None, 8, 7 * HOUR, preset, roads={})
            ids = ("a", "b", "c", "d")
            desk.orders = {
                oid: {
                    "id": oid,
                    "lastPickupAt": 5000,
                    "legs": [{"pickup": {"placeId": oid}, "delivery": {"placeId": oid}}],
                }
                for oid in ids
            }
            desk.held = dict.fromkeys(ids)
            desk.single_stops = lambda oid: [{"orderId": oid}]
            desk.chain_minutes = lambda first, second: links.get((first[0]["orderId"], second[0]["orderId"]))
            posted = []

            def record_pair(stops, order_ids):
                posted.append(order_ids)
                for order_id in order_ids:
                    desk.held.pop(order_id, None)

            desk.post_pair = record_pair
            desk.plan()
            return posted

        self.assertEqual(len(run(PRESETS["l8_plan"])), 1)
        self.assertEqual(len(run(PRESETS["l8_plan_match"])), 2)


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


class Cancel(unittest.TestCase):
    """RULES: when a cancelled order's gig is withdrawn, post its other cars again."""

    order = PairChange.order

    def test_withdrawn_gig_reposts_the_other_car(self):
        desk = Desk(None, 8, 10 * HOUR, PRESETS["l8_plan"])
        for oid in ("A", "B"):
            desk.orders[oid] = self.order(oid)
            desk.requests[oid] = {"referenceFeeCents": 5000, "note": None, "legs": [{}]}
        stops = [{"orderId": oid, "leg": 0, "kind": kind} for oid in ("A", "B") for kind in ("pickup", "delivery")]
        desk.carry({"type": "post", "stops": stops, "audience": {}, "schedule": []}, "g1")
        desk.handle({"kind": "order_cancelled", "orderId": "A", "gigs": [{"gigId": "g1", "outcome": "withdrawn"}]})
        posted = [a["stops"][0]["orderId"] for a in desk.outbox if a["type"] == "post"]
        self.assertEqual(posted, ["B"])
        self.assertNotIn("A", desk.orders)

    def test_shortened_gig_keeps_the_other_car(self):
        desk = Desk(None, 8, 10 * HOUR, PRESETS["l8_plan"])
        for oid in ("A", "B"):
            desk.orders[oid] = self.order(oid)
            desk.requests[oid] = {"referenceFeeCents": 5000, "note": None, "legs": [{}]}
        stops = [{"orderId": oid, "leg": 0, "kind": kind} for oid in ("A", "B") for kind in ("pickup", "delivery")]
        desk.carry({"type": "post", "stops": stops, "audience": {}, "schedule": []}, "g1")
        desk.handle({"kind": "order_cancelled", "orderId": "A", "gigs": [{"gigId": "g1", "outcome": "shortened"}]})
        self.assertEqual([a for a in desk.outbox if a["type"] == "post"], [])
        self.assertEqual(desk.gigs_of("B"), ["g1"])


class LaneFee(unittest.TestCase):
    """Params.fee_lane: a one-car request's typical fee is averaged in log with its lane's other requests."""

    def desk(self, fee_lane, legs=1):
        desk = Desk(None, 8, 0, Params(fee_lane=fee_lane))
        place = {"privateAddress": False}
        leg = {"pickup": {**place, "placeId": "x"}, "delivery": {**place, "placeId": "y"}, "car": {"premium": False}}
        desk.requests["A"] = {"referenceFeeCents": 8000, "legs": [leg] * legs}
        return desk

    def test_noisy_fee_moves_to_the_lane_mean(self):
        with unittest.mock.patch.dict(pricing.LANE_FEES, {"x>y>0>0": [math.log(4000), 3]}):
            self.assertAlmostEqual(self.desk(1).typical_fee("A"), 4000 * 2**0.25, places=6)  # 3 at 4000, 1 at 8000

    def test_off_unknown_lane_or_trade_in_keep_the_request_fee(self):
        with unittest.mock.patch.dict(pricing.LANE_FEES, {"x>y>0>0": [math.log(4000), 3]}, clear=True):
            self.assertEqual(self.desk(0).typical_fee("A"), 8000)
            self.assertEqual(self.desk(1, legs=2).typical_fee("A"), 8000)
        with unittest.mock.patch.dict(pricing.LANE_FEES, {}, clear=True):
            self.assertEqual(self.desk(1).typical_fee("A"), 8000)


class Charging(unittest.TestCase):
    """RULES: an electric car under 30% needs a charging stop only on a route over 200 km (Params.charge_km)."""

    def stops(self, km, charge_km):
        window = {"from": 0, "to": DAY}
        car = {"premium": False, "electric": True, "chargePercent": 20}
        order = {
            "id": "A",
            "legs": [
                {
                    "car": car,
                    "pickup": {"placeId": "x", "privateAddress": False, "window": window},
                    "delivery": {"placeId": "y", "privateAddress": False, "window": window},
                }
            ],
            "deadline": DAY,
        }
        roads = {("x", "y"): {"km": km, "minutes": km}}
        return dispatch.stops_for(order, [0], None, dispatch.Retry(), charge_km=charge_km, roads=roads)

    def test_short_route_needs_no_charging_stop(self):
        self.assertFalse(self.stops(150, 200)[0]["withCharging"])

    def test_long_route_keeps_the_charging_stop(self):
        self.assertTrue(self.stops(250, 200)[0]["withCharging"])

    def test_starter_rule_charges_every_low_battery_car(self):
        self.assertTrue(self.stops(150, 0)[0]["withCharging"])


class Chains(unittest.TestCase):
    """Desk.build_chains: one driver takes several cars when each delivery is near the next pickup."""

    def desk(self, chain_max):
        roads = {(a, b): {"km": 0 if a == b else 20, "minutes": 0 if a == b else 60} for a in "xyz" for b in "xyz"}
        desk = Desk(None, 8, 0, Params(chain_max=chain_max, pair_km=30, pair_margin_h=4, pair_lead_min=60), roads)
        for oid, (start, end) in {"A": ("x", "y"), "B": ("y", "z"), "C": ("z", "x")}.items():
            window = {"from": 0, "to": DAY}
            car = {"premium": False, "electric": False, "chargePercent": None}
            pickup = {"placeId": start, "privateAddress": False, "window": window}
            delivery = {"placeId": end, "privateAddress": False, "window": window}
            desk.orders[oid] = {
                "id": oid,
                "legs": [{"car": car, "pickup": pickup, "delivery": delivery}],
                "deadline": DAY,
                "deliveredAt": [None],
                "lastPickupAt": DAY - 2 * HOUR,
            }
            desk.requests[oid] = {"referenceFeeCents": 5000, "note": None, "legs": [{}]}
        return desk

    def chains(self, chain_max):
        desk = self.desk(chain_max)
        return sorted(len(c) for c in desk.build_chains({o: desk.single_stops(o) for o in "ABC"}))

    def test_three_cars_in_one_chain(self):
        self.assertEqual(self.chains(3), [3])

    def test_chain_max_two_makes_a_pair_and_a_single(self):
        self.assertEqual(self.chains(2), [1, 2])

    def test_chain_match_still_builds_the_full_chain(self):
        desk = self.desk(3)
        desk.p = Params(chain_max=3, chain_match=1, pair_km=30, pair_margin_h=4, pair_lead_min=60)
        chains = desk.build_chains({o: desk.single_stops(o) for o in "ABC"})
        self.assertEqual(sorted(len(c) for c in chains), [3])

    def test_late_deadline_breaks_the_chain(self):
        desk = self.desk(3)
        desk.orders["C"]["deadline"] = 3 * HOUR  # C can't wait for A and B first
        chains = desk.build_chains({o: desk.single_stops(o) for o in "ABC"})
        self.assertTrue(all(c.index("C") == 0 for c in chains if "C" in c))


class ChainPartners(unittest.TestCase):
    """Desk.chain_partners: a request that one driver could carry with a held car gets fit_cut off its price."""

    desk = Chains.desk

    def request(self, start, end):
        window = {"from": 0, "to": DAY}
        leg = {"pickup": {"placeId": start, "privateAddress": False, "window": window}}
        leg["delivery"] = {"placeId": end, "privateAddress": False, "window": window}
        return {"legs": [leg], "options": [{"kind": "same_day", "deadline": DAY}]}

    def test_counts_held_cars_before_or_after_it(self):
        desk = self.desk(3)
        desk.held = {"A": None}  # x -> y
        self.assertEqual(desk.chain_partners(self.request("y", "z")), 1)  # after A
        self.assertEqual(desk.chain_partners(self.request("z", "x")), 1)  # before A
        self.assertEqual(desk.chain_partners(self.request("q", "r")), 0)  # no road: too far

    def test_charging_stop_minutes_count_in_the_timing(self):
        desk = self.desk(3)
        desk.p = Params(pair_km=30, pair_margin_h=0, pair_lead_min=0)
        first, second = ("x", "y", 0, 60, 0), ("y", "z", 0, 130, 0)  # 60 min drive, no link, 60 min drive
        self.assertEqual(desk.link_minutes(first, second), 0)
        self.assertIsNone(desk.link_minutes(first, ("y", "z", 0, 130, 40)))  # +40 min charging: 160 > 130

    def test_fit_cut_lowers_the_price(self):
        req = request([SAME])
        self.assertEqual(quote(req, 8, Params(quote_mult=1.4, fit_cut=0.1), partners=1)["same_day"], 13000)
        self.assertEqual(quote(req, 8, Params(quote_mult=1.4, fit_cut=0.1), partners=0)["same_day"], 14000)


class NextOffer(unittest.TestCase):
    """Desk.offer_next: a driver who books gig A is offered our unbooked gig B that starts where A ends."""

    desk = Chains.desk

    def setUp(self):
        self.d = self.desk(3)
        self.d.p = Params(next_offer_mult=1.0, pair_km=30, pair_margin_h=1, pair_lead_min=60)
        for oid in "AB":
            stops = self.d.single_stops(oid)
            self.d.posts[f"g{oid}"] = {
                "type": "post",
                "stops": stops,
                "audience": {},
                "schedule": [{"at": 0, "feeCents": 5000}],
            }
            self.d.leg_gigs[oid] = {0: f"g{oid}"}
        self.d.booked = {"gA"}
        self.d.drivers = {
            "d1": {"id": "d1", "rating": 5.0, "completedGigs": 99, "licence": "manual", "homePlaceId": "x"}
        }

    def test_offers_the_car_that_starts_where_the_booked_gig_ends(self):
        self.d.offer_next("gA", "d1")
        self.assertEqual(self.d.outbox, [{"type": "offer", "gigId": "gB", "driverId": "d1", "feeCents": 5000}])

    def test_no_offer_when_the_next_car_would_be_late(self):
        self.d.orders["B"]["deadline"] = 3 * HOUR  # 60 lead + 60 + 0 + 60 drive = 180 min: misses the 1 h margin
        self.d.offer_next("gA", "d1")
        self.assertEqual(self.d.outbox, [])


class HomeFee(unittest.TestCase):
    """Desk.home_factor: a gig ending where many drivers live opens at home_fee x its fee."""

    desk = Chains.desk

    def test_lower_fee_where_many_drivers_live_at_the_delivery(self):
        d = self.desk(3)
        d.p = Params(home_fee=0.8, home_n=2)
        d.near = {"y": [{}, {}], "z": [{}]}
        last_a, last_b = d.single_stops("A")[-1], d.single_stops("B")[-1]  # A ends at y (2 drivers), B at z (1)
        self.assertEqual(d.home_factor(last_a), 0.8)
        self.assertEqual(d.home_factor(last_b), 1.0)
        d.p = Params(home_n=2)
        self.assertEqual(d.home_factor(last_a), 1.0)  # off by default


class NoteReader(unittest.TestCase):
    """note_reader=1: the note's facts reach the posted stops, the audience and the hold decisions."""

    desk = Chains.desk

    def setUp(self):
        self.d = self.desk(3)
        self.d.p = Params(note_reader=1, pair_km=30, pair_margin_h=4, pair_lead_min=60)
        for oid in "BC":
            self.d.requests[oid]["arrivedAt"] = 0
        self.d.requests["A"] = {
            "referenceFeeCents": 5000,
            "legs": [{}],
            "arrivedAt": 0,
            "note": {"text": "Ei kilpiä, siirtokilvet mukaan. Manuaali. Perillä klo 15 mennessä.", "language": "fi"},
        }

    def test_plates_deadline_and_licence(self):
        pickup, delivery = self.d.single_stops("A")
        self.assertTrue(pickup["withPlates"])
        self.assertEqual(delivery["window"]["to"], 15 * HOUR)
        self.assertTrue(self.d.manual(["A", "B"]))
        self.assertFalse(self.d.manual(["B"]))

    def test_earlier_deadline_moves_the_last_pickup(self):
        self.assertEqual(self.d.last_pickup(self.d.orders["A"]), DAY - 2 * HOUR - (DAY - 15 * HOUR))
        self.assertEqual(self.d.last_pickup(self.d.orders["B"]), DAY - 2 * HOUR)


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
            set(config.PRESETS),
            {
                "starter",
                "l1",
                "l8",
                "l8_plan",
                "l8_plan2",
                "l8_chain",
                "l8_notes",
                "l8_charge",
                "l8_lane",
                "l8_early",
                "l8_plan_match",
                "l8_guarded",
                "l8_v3",
                "l8_v2",
                "l8_v1",
            },
        )
        self.assertIs(PRESETS["starter"], DEFAULT)

    def test_l8_plan_match_is_gated_and_keeps_the_l8_plan_parameters(self):
        self.assertEqual(PRESETS["l8_plan"].pair_match, 0)
        self.assertEqual(PRESETS["l8_plan_match"], from_overrides(["pair_match=1"], PRESETS["l8_plan"]))

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
