"""Offline tests for the network LP (network.py). No key needed."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from network import UNSERVED_H, Network  # noqa: E402

# Two towns, A and B, one hour apart.
ROADS = {(a, b): {"km": 0 if a == b else 100, "minutes": 0 if a == b else 60} for a in "AB" for b in "AB"}


def roster(a: int, b: int) -> list:
    return [{"homePlaceId": "A"}] * a + [{"homePlaceId": "B"}] * b


class NetworkTest(unittest.TestCase):
    def test_nearest_driver_with_spare_capacity(self):
        # A car inside town A, a driver lives in A: no trip there or home.
        net = Network(ROADS, roster(1, 1), alpha=1.0)
        self.assertAlmostEqual(net.marginal(("A", "A"), []), 0.0, places=6)

    def test_cars_we_hold_use_up_the_nearest_drivers(self):
        # A's only driver is taken by a waiting car in A, so the new car in A needs B's driver: 1 h there + 1 h home.
        net = Network(ROADS, roster(1, 1), alpha=1.0)
        self.assertAlmostEqual(net.marginal(("A", "A"), [("A", "A")]), 2.0, places=6)

    def test_no_capacity_left_costs_the_unserved_price(self):
        net = Network(ROADS, roster(1, 0), alpha=1.0)
        self.assertAlmostEqual(net.marginal(("A", "A"), [("A", "A")]), UNSERVED_H, places=6)

    def test_a_trip_home_counts(self):
        # Pick up in A, deliver in B, driver from A: no trip there, 1 h home.
        net = Network(ROADS, roster(1, 0), alpha=1.0)
        self.assertAlmostEqual(net.marginal(("A", "B"), []), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
