"""Network pricing: a graph of towns and a transportation LP that says what one more car costs us.

The graph: the 30 towns of the map are nodes, the road minutes between them are the edge weights.
Each town supplies driver capacity in proportion to the drivers who live there (from the driver list).

The LP, solved when a price request arrives:

    minimise   sum_{h,o} c[h,o] * x[h,o]  +  M * sum_o u[o]
    subject to sum_h x[h,o] + u[o] = 1        for every car o that needs a driver  (dual: marginal cost of o)
               sum_o x[h,o]       <= cap[h]   for every town h                     (dual: price of a driver in h)
               x, u >= 0

  o      the cars we have won that no driver holds yet, plus the new request
  c[h,o] hours a driver from town h spends getting to the pickup and home from the delivery
         (road minutes h -> pickup + delivery -> h); the drive itself is the same for every driver
  cap[h] lp_alpha x drivers living in town h: the share of them we can expect to book now
  u[o]   a car that no town can take (cost M): it will likely be late

The new request's marginal cost is the LP's total cost with it minus without it: the extra hours the whole
network spends when we add this car, after the cars we already hold have taken the nearest drivers. It is the
trip of the nearest driver with spare capacity, plus what other cars lose when it takes a driver they needed.
(This equals the dual of the request's row when that dual is unique.) pricing.flat_mult turns it into a price.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix

UNSERVED_H = 24.0  # cost of a car that no town can take, in hours


class Network:
    def __init__(self, roads: dict, roster: list, alpha: float):
        homes: dict[str, int] = {}
        for driver in roster:
            homes[driver["homePlaceId"]] = homes.get(driver["homePlaceId"], 0) + 1
        self.towns = sorted(homes)
        self.cap = np.array([alpha * homes[t] for t in self.towns])
        self.roads = roads

    def hours(self, town: str, pickup: str, delivery: str) -> float:
        to = self.roads.get((town, pickup))
        back = self.roads.get((delivery, town))
        if to is None or back is None:
            return UNSERVED_H
        return (to["minutes"] + back["minutes"]) / 60

    def marginal(self, new: tuple[str, str], waiting: list[tuple[str, str]]) -> Optional[float]:
        """Marginal cost, in hours, of the car `new` = (pickup, delivery) on top of the cars in `waiting`:
        the LP's total cost with the new car minus without it. (The dual of the new car's row says the same when
        it is unique, but when a town's capacity is used exactly the dual can be anything in a range.)"""
        with_new = self.solve(waiting + [new])
        if with_new is None:
            return None
        without = self.solve(waiting) if waiting else 0.0
        return None if without is None else with_new - without

    def solve(self, cars: list[tuple[str, str]]) -> Optional[float]:
        """The LP's minimum total cost, in hours, of finding a driver for every car in `cars`."""
        n_towns, n_cars = len(self.towns), len(cars)
        if n_towns == 0:
            return None
        cost = np.array([[self.hours(t, p, d) for (p, d) in cars] for t in self.towns])  # towns x cars
        n_x = n_towns * n_cars
        c = np.concatenate([cost.ravel(), np.full(n_cars, UNSERVED_H)])

        # Demand rows: for car o, sum_h x[h,o] + u[o] = 1.
        rows, cols = [], []
        for o in range(n_cars):
            rows += [o] * n_towns
            cols += [h * n_cars + o for h in range(n_towns)]
        rows += list(range(n_cars))
        cols += [n_x + o for o in range(n_cars)]
        a_eq = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n_cars, n_x + n_cars))

        # Capacity rows: for town h, sum_o x[h,o] <= cap[h].
        rows = [h for h in range(n_towns) for _ in range(n_cars)]
        cols = list(range(n_x))
        a_ub = coo_matrix((np.ones(n_x), (rows, cols)), shape=(n_towns, n_x + n_cars))

        res = linprog(c, A_ub=a_ub, b_ub=self.cap, A_eq=a_eq, b_eq=np.ones(n_cars), bounds=(0, None), method="highs")
        return float(res.fun) if res.status == 0 else None
