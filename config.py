"""Shared parameters. Every tunable number lives here, so an experiment is one changed field
and evaluate.py can log exactly which settings produced which score."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace

HOUR, DAY = 60, 24 * 60


@dataclass(frozen=True)
class Params:
    """Every tunable number. Defaults = the kit starter exactly; a rule with value 0 (or 1.0 for a factor) is off."""

    # --- Quoting (levels 4+; levels 1-3 always win at list price). Price = list x quote_mult + adjustments.
    quote_mult: float = 1.0
    backlog_k: float = 0.0  # + backlog_k per won order still without a driver
    dense_n: int = 0  # pickup with >= dense_n drivers living within 30 km ...
    dense_cut: float = 0.0  # ... - dense_cut
    private_add: float = 0.0  # + this when a stop is a private address (>= 5 = decline)
    dest_k: float = 0.0  # + dest_k x the delivery place's competitor price offset (lanes.json, x list)
    decline_km: float = 0.0  # decline (quote 10x list) when the first leg is longer
    min_slack_h: float = 0.0  # quote only options with >= this many hours slack (0 = first option only)

    # --- Expected-profit pricing (levels 4+; 0 = off): quote the price that maximises
    # P(win | price, situation) x (price - expected cost). P is a logistic model fitted by analysis/winmodel.py.
    opt: int = 0
    win_const: float = 8.014
    win_mult: float = -6.142  # per 1.0x of list price
    win_trust: float = 1.885  # at full dealer trust (25)
    win_monday: float = -1.397
    win_dense: float = 0.158
    win_km100: float = 0.129
    win_big: float = -0.121
    late_const: float = -1.349  # P(late) = logistic of these terms (analysis/latemodel.py)
    late_slack24: float = -0.727  # per day of slack
    late_km100: float = 0.066
    late_private: float = 1.415
    late_near_pu: float = -0.805  # x log(1 + drivers near the pickup) / 4
    late_near_de: float = -0.264  # x log(1 + drivers near the delivery) / 4
    late_backlog10: float = 0.291  # per 10 won orders without a driver
    late_hour: float = 0.042  # request after 15:00
    opt_fee: float = 0.95  # expected driver fee, x the typical fee
    opt_backlog: float = 0.03  # + this x typical fee per won order still without a driver (shadow price of capacity)
    opt_late_refund: float = 0.5  # share of the price lost when late (refund, ranking risk)
    opt_late_trust: float = 0.0  # value of a full-trust dealer's trust lost when late, x list price
    opt_trust_gain: float = 0.0  # Exp. 29: value of +1 trust, x list per later request of that dealer
    opt_lo: float = 1.0  # price range searched, x list
    opt_hi: float = 2.0
    opt_guard_late: float = 0.0  # if > 0, use flat pricing when predicted lateness exceeds this share
    opt_guard_backlog: int = 0  # if > 0, use flat pricing when driverless backlog reaches this count
    opt_delta_cap: float = 0.0  # if > 0, cap optimizer price change from flat quote as share of list

    # --- Protect dealer trust (level 8): a late order halves the dealer's count, so book drivers sooner for
    # dealers whose count is high.
    big_n: int = 0  # a dealer that has sent >= big_n requests so far this week (0 = off) ...
    big_cut: float = 0.0  # ... gets quote_mult - big_cut: win more of the big dealers, so their trust grows
    trust_safe_n: int = 0  # for a dealer with count >= this (0 = off) ...
    trust_slack_h: float = 0.0  # ... quote only options with at least this much slack
    trust_km: float = 0.0  # ... and decline trips longer than this (0 = keep decline_km)
    trust_fee: float = 1.0  # fee factor for orders of a dealer with count >= trust_fee_n; 1.0 = off (Exp. 27: worse)
    trust_fee_n: int = 5

    # --- Normal driver fee schedule, as multiples of the request's typical fee (referenceFeeCents).
    open_mult: float = 1.0  # opening fee
    raise_per_step: float = 0.10  # added per step (levels 2+; level 1 allows one step)
    raise_every_min: int = HOUR  # minutes between steps
    raise_steps: int = 6  # steps in the schedule, so the cap is open + (steps-1)*raise

    # --- Steep schedule after deadline_close.
    steep_open_mult: float = 1.5
    steep_raise_per_step: float = 0.25
    steep_every_min: int = 30
    steep_steps: int = 5

    # --- Level 1 ladder: our own raises by reprice for unbooked gigs. Fee = min(cap, open_mult + per_hour x hours).
    ladder_per_hour: float = 0.0
    ladder_cap: float = 1.5
    tick_min: int = 10  # how often the practice loop wakes up to raise fees

    # --- Tested and off: kept so every experiment in LESSONS.md can be rerun (see the experiment number).
    later_mult: float = 1.0  # Exp. 14: factor on next_day / within_3_days prices
    trust_w: float = 0.0  # Exp. 8: price x (1 + trust_w x 1% x dealer's on-time count, max 25)
    sparse_n: int = 0  # Exp. 17: pickup with < sparse_n drivers within 30 km ...
    sparse_add: float = 0.0  # ... + sparse_add
    explore_lo: float = 0.0  # research: a random price in [explore_lo, explore_hi] per request
    explore_hi: float = 0.0
    offer_mult: float = 0.0  # Exp. 18: direct offers at offer_mult x opening fee ...
    offer_n: int = 3  # ... to this many drivers living near the delivery place
    dense_fee: float = 1.0  # Exp. 23: fee factor when the pickup has >= dense_n drivers near
    slack_fee: float = 1.0  # Exp. 23: fee factor with >= slack_fee_h hours before lastPickupAt
    slack_fee_h: float = 24.0
    pair_fee: float = 0.0  # Exp. 24: two-car gigs; fee = pair_fee x both typical fees
    pair_km: float = 30.0  # first car's delivery within this many road km of the second's pickup
    pair_lead_min: int = 60  # the driver starts no earlier than this many minutes from now
    pair_margin_h: float = 2.0  # both cars due at least this long after the planned delivery
    adapt_target: float = 0.0  # Exp. 25: steer the price so we win this share of our quotes
    adapt_step: float = 0.01  # +step x (1 - target) per win, -step x target per loss
    adapt_lo: float = -0.3  # limits of the adjustment
    adapt_hi: float = 0.3
    adapt_backlog: int = 5  # only lower the price while at most this many won orders lack a driver
    cost_k: float = 0.0  # Exp. 26: + cost_k x (typical fee / list - cost_mid)
    cost_mid: float = 0.9
    max_legs: int = 0  # Exp. 29: decline requests with more legs (trade-ins have 2)
    market_lr: float = 0.0  # Exp. 31: learn the week's competitor level: + this x (won - expected) per answer
    market_lo: float = -0.2  # limits of the learned level, x list
    market_hi: float = 0.3
    monday_add: float = 0.0  # Exp. 32: + this on Monday
    return_mult: float = 0.0  # Exp. 33: after a delivery, offer the driver our open gig towards home at this x fee
    return_km: float = 60.0  # ... if its first pickup is within this many road km

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT = Params()

# Named configurations. DEFAULT reproduces the kit starter; the others are our tuned systems (see LESSONS.md).
PRESETS = {
    "starter": DEFAULT,
    # Level 1: fee ladder by reprice. +€34,186 on l1-a..j (starter -€28,978), worst week 91.1%.
    "l1": Params(open_mult=0.7, ladder_per_hour=0.3, ladder_cap=1.5),
    # Level 8 (the final): price 1.45x list + 0.03 per driverless order, 0.2 cheaper where >= 40 drivers live within
    # 30 km of the pickup, 0.2 dearer for private addresses, + the competitor's offset for the delivery place
    # (lanes.json, -0.17x Vantaa .. +0.18x Joensuu); decline > 550 km; only options with >= 8 h slack;
    # fee opens 0.8x, +0.1x every 30 min. 30 weeks (l8 €99,661, l8x €104,324, l8y €116,611): €320,596, worst week 91.5%.
    "l8": Params(
        quote_mult=1.45,
        backlog_k=0.03,
        decline_km=550,
        min_slack_h=8,
        open_mult=0.8,
        raise_every_min=30,
        dense_n=40,
        dense_cut=0.2,
        private_add=0.2,
        dest_k=1.0,
    ),
    # Previous l8 (Sat noon): same without the delivery-place offsets. €307,943, worst week 92.6%.
    "l8_v3": Params(
        quote_mult=1.45,
        backlog_k=0.03,
        decline_km=550,
        min_slack_h=8,
        open_mult=0.8,
        raise_every_min=30,
        dense_n=40,
        dense_cut=0.2,
        private_add=0.2,
    ),
    # Previous l8 (Sat night): same without the driver-density and private-address rules. €297,267, worst 91.0%.
    "l8_v2": Params(
        quote_mult=1.45,
        backlog_k=0.03,
        decline_km=550,
        min_slack_h=8,
        open_mult=0.8,
        raise_every_min=30,
    ),
    # Previous level-8 preset (practice round "Saturday 00:00": €46,496, rank 43/62): +€79,155 / +€82,446.
    "l8_v1": Params(quote_mult=1.6, backlog_k=0.01, decline_km=500, min_slack_h=8, open_mult=0.8),
}

# Experimental expected-profit pricing, based on the current lane-aware l8 quote. Use only for low-risk requests;
# preserve the proven delivery-place, distance, deadline and driver fee rules through the flat-price fallback.
PRESETS["l8_guarded"] = replace(PRESETS["l8"], opt=1, opt_backlog=0.04, opt_guard_late=0.08,
                                opt_guard_backlog=3, opt_delta_cap=0.06)


def from_overrides(overrides: list[str], base: Params = DEFAULT) -> Params:
    """Parses ["open_mult=0.8", "raise_steps=4"] into a Params, with types from the defaults."""
    types = {f.name: type(getattr(DEFAULT, f.name)) for f in fields(Params)}  # from the defaults, not the preset
    changes = {}
    for item in overrides:
        key, _, value = item.partition("=")
        if key not in types:
            raise SystemExit(f"Unknown parameter {key!r}. Known: {', '.join(types)}")
        changes[key] = types[key](value)
    return replace(base, **changes)
