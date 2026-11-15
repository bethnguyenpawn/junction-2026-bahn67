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
    backlog_h: float = 0.0  # Exp. 45: count only those whose last pickup is within this many hours (0 = all)
    fit_cut: float = 0.0  # Exp. 45: - this for a request that could share a driver with a held or posted car
    market_k: float = 0.0  # Exp. 44: + market_k x the competitor's learned level move this week and today (market.py)
    market_lo: float = -0.1  # limits of that price change, x list
    market_hi: float = 0.1
    dense_n: int = 0  # pickup with >= dense_n drivers living within 30 km ...
    dense_cut: float = 0.0  # ... - dense_cut
    private_add: float = 0.0  # + this when a stop is a private address (>= 5 = decline)
    dest_k: float = 0.0  # + dest_k x the delivery place's competitor price offset (lanes.json, x list)
    decline_km: float = 0.0  # decline (quote 10x list) when the first leg is longer
    min_slack_h: float = 0.0  # quote only options with >= this many hours slack (0 = first option only)
    # Outage (RULES: the competitor is down in one region for a working day, 08-18; dealers pay a backup ~30% more):
    # when today we won >= outage_rate of >= outage_n answered quotes with a pickup within outage_km, + outage_add.
    outage_add: float = 0.0
    outage_n: int = 8
    outage_rate: float = 0.75
    outage_km: float = 100.0
    # Price war (RULES: one working day the competitor is 20% cheaper everywhere, 08-18): when today (Tue-Fri) we won
    # < war_rate of >= war_n answered quotes, - war_cut for the rest of the day.
    war_cut: float = 0.0
    war_n: int = 15
    war_rate: float = 0.15

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

    # --- Batch planning (two-car gigs): hold plain one-car orders with slack, and every plan_every_h hours (07-19)
    # pair the held cars so one driver delivers both (round trips first); post the rest alone when they can't wait.
    plan_every_h: float = 0.0  # 0 = off: post every order when won
    hold_h: float = 8.0  # hold an order only with >= this many hours until its latest pickup
    wait_h: float = 0.0  # an unpaired held car waits for the next plan only with >= this many hours spare (0 = hold_h)
    split_after_min: int = 0  # a two-car gig no driver booked within this many minutes goes back to one gig per car
    chain_fresh_head: int = 0  # Exp. 62: 1 = a car posted before is never the first car of a chain (no new notice)
    chain_max: int = 0  # >= 2: plan chains of up to this many cars per driver, also from posted unbooked one-car gigs
    # (Desk.plan_chains); 0 = pairs of held cars only (Desk.plan_pairs)
    chain_replan: int = 0  # 1: a chain no driver booked within split_after_min goes back into the next plan (not split)
    chain_private: int = 0  # 1: cars to or from a private address may join chains (their slot is respected)
    pair_match: int = 0  # 1: plan_pairs takes the largest set of pairs (Edmonds' matching) instead of greedy pairs
    chain_match: int = 0  # 1: build_chains starts from the largest set of pairs (match_pairs), then grows chains
    # (uses pair_fee, pair_km, pair_lead_min, pair_margin_h below)

    # --- Normal driver fee schedule, as multiples of the request's typical fee (referenceFeeCents).
    open_mult: float = 1.0  # opening fee
    raise_per_step: float = 0.10  # added per step (levels 2+; level 1 allows one step)
    raise_every_min: int = HOUR  # minutes between steps
    raise_steps: int = 6  # steps in the schedule, so the cap is open + (steps-1)*raise
    night_hold: int = 0  # Exp. 48 (worse): count raise_every_min only in reading hours (07-23)
    slow_every_min: int = 0  # Exp. 57 (worse): raise this often when every car has >= slow_after_h to its last pickup
    slow_after_h: float = 12.0
    early_cut: float = 0.0  # Exp. 64: x typical off the opening fee of a gig whose first car is ready >= early_h
    early_h: float = 12.0  # hours from now (same cap): drivers who know they work tomorrow book such gigs at once

    # --- Notes (Exp. 49): 1 = notes.py reads ready time, deadline, closing time, plates and manual gearbox from the
    # dealer's note (right on all 5,790 noted cars of cached weeks); 0 = the starter's keyword matcher.
    note_reader: int = 0
    charge_km: float = 0.0  # Exp. 55: > 0 = charging stop for a car under 30% only on routes over this (RULES: 200)
    fee_lane: int = 0  # Exp. 61: 1 = fee base = typical fee averaged with its lane's (fees.json): the world adds noise

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
    home_fee: float = 1.0  # Exp. 47: x the fee of a gig whose last delivery has >= home_n drivers living within 30 km
    home_n: int = 60
    chain_home: int = 0  # Exp. 47: build_chains prefers chains ending where >= home_n drivers live, like round trips
    next_offer_mult: float = 0.0  # Exp. 46: on a booking, offer that driver our unbooked car near where they finish
    chain_charging: int = 0  # Exp. 45: electric cars with a charging stop may join chains (+40 min in the timing)
    chain_fee_step: float = 0.0  # Exp. 45: - this from pair_fee for each car beyond the second
    tradein_mult: float = 0.0  # Exp. 53: > 0 quotes a trade-in (two legs) at this x list, no private surcharge
    early_quote_cut: float = 0.0  # Exp. 65: x list off when the car is ready >= early_h after the request
    rush_n: int = 0  # Exp. 66: a dealer with >= rush_n requests this week has its ready cars posted at once, no hold
    rush_until_h: float = 48.0  # ... until this many hours after Monday 00:00
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
    # Level 8 without planning (the base of l8_plan): price 1.45x list + 0.03 per driverless order, 0.2 cheaper
    # where >= 40 drivers live within 30 km of the pickup, 0.2 dearer for private addresses, + the competitor's
    # offset for the delivery place (lanes.json, -0.17x Vantaa .. +0.18x Joensuu); decline > 550 km; only options
    # with >= 8 h slack; fee opens 0.8x, +0.1x every 30 min. 30 weeks (l8 €99,661, l8x €104,324, l8y €116,611): €320,596, worst week 91.5%.
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
    # l8 + batch planning of two-car gigs (Exp. 37).
    # l8x €116,121 (l8: €104,324), worst week 93.2%; ranking round "Saturday 12:00": €71,409 in 5 weeks, worst 94.9%.
    "l8_plan": Params(
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
        plan_every_h=3,
        pair_km=30,
        pair_fee=0.9,
        pair_margin_h=4,
        split_after_min=120,
        wait_h=24,
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

# Experimental l8_plan matcher: prefer the largest set of simultaneously feasible pairs.
PRESETS["l8_plan_match"] = replace(PRESETS["l8_plan"], pair_match=1)

# Experimental expected-profit pricing, based on the current lane-aware l8 quote. Use only for low-risk requests;
# preserve the proven delivery-place, distance, deadline and driver fee rules through the flat-price fallback.
# CURRENT BEST: l8_plan + price 1.40x and pair links up to 50 km (Exp. 41). l8 €112,459, l8x €119,506
# (+€5,802 over 20 weeks vs l8_plan), l8y €138,040; worst week 91.9%, 30/30 ranked.
PRESETS["l8_plan2"] = replace(PRESETS["l8_plan"], quote_mult=1.40, pair_km=50)
# CANDIDATE: l8_plan2 + chains of up to 3 cars from held cars and posted unbooked gigs, planned every hour (Exp. 42).
# l8 €119,744 (+6.5%), worst week 94.1%. Not yet checked on l8x and l8y.
PRESETS["l8_chain"] = replace(PRESETS["l8_plan2"], chain_max=3, plan_every_h=1)

# Exp. 49: + the note reader (notes.py): ready time, deadline, site hours, plates, manual gearbox from the dealer's
# note. Failed visits 8.7 -> 0.3/week, late orders 14.3 -> 11.3/week; +€7.8k on l8 + l8x.
PRESETS["l8_notes"] = replace(PRESETS["l8_chain"], note_reader=1)

# Exp. 55: a charging stop only where RULES need one (route over 200 km), not for every electric car under 30%: the
# short-route cars pay no stop and can join chains. +€6.4k over 30 weeks (+1.6%), worst 92.9%.
PRESETS["l8_charge"] = replace(PRESETS["l8_notes"], charge_km=200)

# Exp. 61: fees built on the lane's mean typical fee (fees.json, analysis/typical.py) instead of the request's noisy
# one (~11% noise per request; drivers book by their own cost). +€9.4k over 30 weeks (+2.2%), worst 93.7%.
PRESETS["l8_lane"] = replace(PRESETS["l8_charge"], fee_lane=1)

# Exp. 64: a gig whose first car is ready 12 h or more from now opens at 0.7x instead of 0.8x (same cap): drivers who
# know they work tomorrow book it at once. +€6.6k over 30 weeks (+1.5%), worst 92.9%. early_cut=0.2: -€13.9k on l8 + l8x.
PRESETS["l8_early"] = replace(PRESETS["l8_lane"], early_cut=0.1)

PRESETS["l8_guarded"] = replace(
    PRESETS["l8"], opt=1, opt_backlog=0.04, opt_guard_late=0.08, opt_guard_backlog=3, opt_delta_cap=0.06
)


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
