"""Offline tests for the learned competitor level (market.py) and how pricing follows it."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import market
import pricing
from config import DAY, HOUR, Params
from dispatch import Desk
from market import Market


def answers(m: Market, day: int, move: float, n: int, seed: int = 1) -> None:
    """n dealers' answers on `day` (09:00-17:00) when the competitor's level is `move` off the weekday's usual."""
    rng = random.Random(seed)
    level = market.LEVEL + market.weekday(day) + move
    for k in range(n):
        price = rng.uniform(1.1, 1.6)
        won = rng.random() < market.logistic(market.SLOPE * (level - price))
        m.add(day * DAY + 9 * HOUR + k * 8 * HOUR // n, price, 0.0, won)


class LearnedLevel(unittest.TestCase):
    def test_no_answers_means_no_move(self):
        self.assertEqual(Market().move(2 * DAY), 0.0)

    def test_learns_a_dear_week(self):
        m = Market()
        for day in range(3):
            answers(m, day, +0.10, 150, seed=day)
        self.assertGreater(m.move(2 * DAY), 0.08)  # today: clear after 150 answers
        self.assertGreater(m.move(3 * DAY), 0.03)  # a new day starts from the week's move, shrunk towards usual

    def test_a_usual_monday_is_not_a_cheap_week(self):
        m = Market()
        answers(m, 0, 0.0, 200)  # Monday at its usual low level
        self.assertLess(abs(m.move(DAY)), 0.03)

    def test_a_cheap_day_moves_today_more_than_the_week(self):
        m = Market()
        answers(m, 1, 0.0, 150, seed=1)
        answers(m, 2, -0.25, 150, seed=2)  # a price war on Wednesday
        today, tomorrow = m.move(2 * DAY + 17 * HOUR), m.move(3 * DAY)
        self.assertLess(today, -0.12)
        self.assertGreater(tomorrow, -0.06)

    def test_few_answers_move_less_than_many(self):
        one, many = Market(), Market()
        one.add(DAY + 9 * HOUR, 1.1, 0.0, False)  # a loss at a price that usually wins
        for k in range(30):
            many.add(DAY + 9 * HOUR + k, 1.1, 0.0, False)
        self.assertGreater(one.move(DAY + 10 * HOUR), many.move(DAY + 10 * HOUR) + 0.1)
        self.assertGreater(one.move(DAY + 10 * HOUR), -market.DAY_SD[1] * 1.5)


REQUEST = {
    "id": "R1",
    "respondBy": 12 * HOUR,
    "legs": [{"pickup": {"placeId": "x"}, "delivery": {"placeId": "nowhere"}}],
    "referenceFeeCents": 5000,
    "options": [{"kind": "same_day", "deadline": 20 * HOUR, "listPriceCents": 10000}],
}


class Pricing(unittest.TestCase):
    def price(self, params, move):
        return pricing.quote(REQUEST, 8, params, pricing.Situation(market=move))["same_day"]

    def test_price_follows_the_level_within_limits(self):
        p = Params(quote_mult=1.4, market_k=0.5, market_lo=-0.1, market_hi=0.1)
        self.assertEqual(self.price(p, 0.0), 14000)
        self.assertEqual(self.price(p, 0.1), 14500)
        self.assertEqual(self.price(p, -0.6), 13000)  # capped at -0.1
        self.assertEqual(self.price(Params(quote_mult=1.4), 0.1), 14000)  # off by default

    def test_relative_price_is_the_cheapest_option_minus_the_delivery_offset(self):
        request = dict(REQUEST, options=[*REQUEST["options"], {"kind": "next_day", "listPriceCents": 8000}])
        self.assertAlmostEqual(pricing.relative_price(request, {"same_day": 14000, "next_day": 10400}), 1.3)


class DeskLearns(unittest.TestCase):
    def test_answers_move_the_next_quote(self):
        desk = Desk(None, 8, DAY + 9 * HOUR, Params(quote_mult=1.4, market_k=1.0))
        for n in range(1, 13):
            req = dict(REQUEST, id=f"R{n}", dealerId="D1", arrivedAt=DAY + 9 * HOUR + n, respondBy=DAY + 10 * HOUR)
            desk.quote(req)
            desk.learn(req["id"], won=False)  # every quote lost: the competitor is cheaper than usual today
        prices = [a["prices"]["same_day"] for a in desk.outbox]
        self.assertEqual(prices[0], 14000)  # nothing learned yet
        self.assertLess(prices[-1], 13500)
        self.assertEqual(len(desk.market.answers[1]), 12)


if __name__ == "__main__":
    unittest.main()
