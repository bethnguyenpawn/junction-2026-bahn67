import unittest

from evaluate import is_ranked, margin_euros
from pricing import PricingPolicy, quote_prices


class PricingTests(unittest.TestCase):
    def setUp(self):
        self.request = {
            "id": "R1",
            "dealerId": "D1",
            "batchId": None,
            "arrivedAt": 540,
            "respondBy": 555,
            "legs": [],
            "options": [
                {"kind": "same_day", "deadline": 1200, "listPriceCents": 10000},
                {"kind": "next_day", "deadline": 2640, "listPriceCents": 8000},
            ],
            "referenceFeeCents": 4000,
            "note": None,
        }

    def test_levels_one_to_three_quote_only_the_first_option(self):
        # Empty legs have no usable route map: decline rather than take
        # an order whose travel feasibility cannot be established.
        self.assertEqual(quote_prices(self.request, 1), {})
        self.assertEqual(quote_prices(self.request, 3), {})

    def test_market_levels_start_at_list_price_for_first_option(self):
        self.assertGreater(quote_prices(self.request, 4)["same_day"], 10000)

    def test_policy_raises_after_wins_and_lowers_after_losses(self):
        policy = PricingPolicy(4)
        baseline = policy.prices(self.request)["same_day"]
        policy.record_win(self.request, "same_day")
        raised = policy.prices(self.request)["same_day"]
        self.assertGreater(raised, baseline)
        policy.record_loss(self.request)
        self.assertEqual(policy.prices(self.request)["same_day"], baseline)

    def test_score_helpers_use_cents(self):
        score = {"marginCents": 12345, "ranked": True}
        self.assertEqual(margin_euros(score), 123.45)
        self.assertTrue(is_ranked(score))


if __name__ == "__main__":
    unittest.main()
