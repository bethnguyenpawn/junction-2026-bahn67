"""The competitor's price level this week and today, learned from our own wins and losses (Exp. 44).

A dealer takes our price with chance logistic(SLOPE x (level - price) + TRUST x trust share), where price is our
cheapest quoted option x list minus the delivery place's offset (lanes.json) and `level` is the price we win half
the time at. The level is LEVEL on an average day, plus the weekday's usual move (WEEKDAY: Monday is cheap), plus
this week's move (spread WEEK_SD) and this day's move (spread DAY_SD). After each answer the most likely week and
day moves are refitted (maximum a posteriori, Gaussian priors), so early answers move the estimate only a little.
The constants come from 225 level-8 weeks (analysis/competitor.py): the day's move is larger than the week's,
and learning both predicts the next answers much better (log loss 0.552 fixed, 0.525 with the weekday, 0.439).
"""

from __future__ import annotations

import math

from config import DAY

SLOPE = 8.1  # log-odds per 1.0x list of our price
TRUST = 2.59  # log-odds at full dealer trust (25 on-time orders)
LEVEL = 1.308  # price at a 50% win chance on an average day, x list
WEEKDAY = (-0.213, 0.096, 0.031, 0.065, 0.021)  # usual move of each weekday, Mon-Fri, x list
WEEK_SD = 0.077  # how much weeks differ, x list
DAY_SD = (0.260, 0.145, 0.153, 0.115, 0.161)  # how much each weekday differs from its usual move, x list
NEWTON_STEPS = 4  # per refit, starting from the last estimate


class Market:
    """The learned moves of the competitor's level, x list: `move(at)` = this week's + that day's."""

    def __init__(self) -> None:
        self.answers: dict[int, list[tuple[float, float, bool]]] = {}  # day -> (price, trust share, won)
        self.week = 0.0
        self.days: dict[int, float] = {}
        self.fresh = True  # the estimate includes every answer

    def add(self, at: int, price: float, trust_share: float, won: bool) -> None:
        self.answers.setdefault(at // DAY, []).append((price, trust_share, won))
        self.fresh = False

    def move(self, at: int) -> float:
        if not self.fresh:
            self.fit()
        return self.week + self.days.get(at // DAY, 0.0)

    def fit(self) -> None:
        """Joint Newton steps on the week's move and every day's move (the days are linked only through the week, so
        each step solves its small system exactly by eliminating the days)."""
        for _ in range(NEWTON_STEPS):
            grads, curves = {}, {}
            for day, rows in self.answers.items():
                base, grad, curve = LEVEL + weekday(day) + self.week + self.days.get(day, 0.0), 0.0, 0.0
                for price, trust_share, won in rows:
                    p = logistic(SLOPE * (base - price) + TRUST * trust_share)
                    grad += SLOPE * (won - p)
                    curve += SLOPE * SLOPE * p * (1 - p)
                grads[day], curves[day] = grad, curve
            day_grad = {d: grads[d] - self.days.get(d, 0.0) / day_sd(d) ** 2 for d in grads}
            day_curve = {d: curves[d] + 1 / day_sd(d) ** 2 for d in curves}
            week_grad = (
                sum(grads.values())
                - self.week / WEEK_SD**2
                - sum(curves[d] * day_grad[d] / day_curve[d] for d in grads)
            )
            week_curve = sum(curves.values()) + 1 / WEEK_SD**2 - sum(curves[d] ** 2 / day_curve[d] for d in curves)
            step = clip(week_grad / week_curve)
            self.week += step
            for d in grads:
                self.days[d] = self.days.get(d, 0.0) + clip((day_grad[d] - curves[d] * step) / day_curve[d])
        self.fresh = True


def clip(step: float) -> float:
    """Damped Newton step: a one-sided day cannot jump far at once."""
    return max(-0.1, min(0.1, step))


def weekday(day: int) -> float:
    return WEEKDAY[day] if 0 <= day < len(WEEKDAY) else 0.0


def day_sd(day: int) -> float:
    return DAY_SD[day] if 0 <= day < len(DAY_SD) else max(DAY_SD)


def logistic(z: float) -> float:
    return 1 / (1 + math.exp(-max(-30.0, min(30.0, z))))
