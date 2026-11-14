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
    backlog_k: float = 0.0          # + backlog_k per won order still without a driver
    dense_n: int = 0                # pickup with >= dense_n drivers living within 30 km ...
    dense_cut: float = 0.0          # ... - dense_cut
    private_add: float = 0.0        # + this when a stop is a private address (>= 5 = decline)
    decline_km: float = 0.0         # decline (quote 10x list) when the first leg is longer
    min_slack_h: float = 0.0        # quote only options with deadline - drive - now >= this many hours (0 = first option only)

    # --- Normal driver fee schedule, as multiples of the request's typical fee (referenceFeeCents).
    open_mult: float = 1.0          # opening fee
    raise_per_step: float = 0.10    # added per step (levels 2+; level 1 allows one step)
    raise_every_min: int = HOUR     # minutes between steps
    raise_steps: int = 6            # steps in the schedule, so the cap is open + (steps-1)*raise

    # --- Steep schedule after deadline_close.
    steep_open_mult: float = 1.5
    steep_raise_per_step: float = 0.25
    steep_every_min: int = 30
    steep_steps: int = 5

    # --- Level 1 ladder: our own raises by reprice for unbooked gigs. Fee = min(cap, open_mult + per_hour x hours).
    ladder_per_hour: float = 0.0
    ladder_cap: float = 1.5
    tick_min: int = 10              # how often the practice loop wakes up to raise fees

    # --- Tested and off: kept so every experiment in LESSONS.md can be rerun (see the experiment number).
    later_mult: float = 1.0         # Exp. 14: factor on next_day / within_3_days prices
    trust_w: float = 0.0            # Exp. 8: price x (1 + trust_w x 1% x dealer's on-time count, max 25)
    sparse_n: int = 0               # Exp. 17: pickup with < sparse_n drivers within 30 km ...
    sparse_add: float = 0.0         # ... + sparse_add
    explore_lo: float = 0.0         # research: a random price in [explore_lo, explore_hi] per request
    explore_hi: float = 0.0
    offer_mult: float = 0.0         # Exp. 18: direct offers at offer_mult x opening fee ...
    offer_n: int = 3                # ... to this many drivers living near the delivery place
    dense_fee: float = 1.0          # Exp. 23: fee factor when the pickup has >= dense_n drivers near
    slack_fee: float = 1.0          # Exp. 23: fee factor with >= slack_fee_h hours before lastPickupAt
    slack_fee_h: float = 24.0
    pair_fee: float = 0.0           # Exp. 24: two-car gigs; fee = pair_fee x both typical fees
    pair_km: float = 30.0           # first car's delivery within this many road km of the second's pickup
    pair_lead_min: int = 60         # the driver starts no earlier than this many minutes from now
    pair_margin_h: float = 2.0      # both cars due at least this long after the planned delivery
    adapt_target: float = 0.0       # Exp. 25: steer the price so we win this share of our quotes
    adapt_step: float = 0.01        # +step x (1 - target) per win, -step x target per loss
    adapt_lo: float = -0.3          # limits of the adjustment
    adapt_hi: float = 0.3
    adapt_backlog: int = 5          # only lower the price while at most this many won orders lack a driver
    cost_k: float = 0.0             # Exp. 26: + cost_k x (typical fee / list - cost_mid)
    cost_mid: float = 0.9

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT = Params()

# Named configurations. DEFAULT reproduces the kit starter; the others are our tuned systems (see LESSONS.md).
PRESETS = {
    "starter": DEFAULT,
    # Level 1: fee ladder by reprice. +€34,186 on l1-a..j (starter -€28,978), worst week 91.1%.
    "l1": Params(open_mult=0.7, ladder_per_hour=0.3, ladder_cap=1.5),
    # Level 8 (the final): price 1.45x list + 0.03 per driverless order, 0.2 cheaper where >= 40 drivers live within
    # 30 km of the pickup, 0.2 dearer for private addresses; decline > 550 km; only options with >= 8 h slack;
    # fee opens 0.8x, +0.1x every 30 min. 30 weeks (l8 €95,102, l8x €99,994, l8y €112,847): €307,943, worst week 92.6%.
    "l8": Params(quote_mult=1.45, backlog_k=0.03, decline_km=550, min_slack_h=8, open_mult=0.8, raise_every_min=30,
                 dense_n=40, dense_cut=0.2, private_add=0.2),
    # Previous l8 (Sat night): same without the driver-density and private-address rules. €297,267, worst 91.0%.
    "l8_v2": Params(quote_mult=1.45, backlog_k=0.03, decline_km=550, min_slack_h=8, open_mult=0.8, raise_every_min=30),
    # Previous level-8 preset (practice round "Saturday 00:00": €46,496, rank 43/62): +€79,155 / +€82,446.
    "l8_v1": Params(quote_mult=1.6, backlog_k=0.01, decline_km=500, min_slack_h=8, open_mult=0.8),
}


def from_overrides(overrides: list[str], base: Params = DEFAULT) -> Params:
    """Parses ["open_mult=0.8", "raise_steps=4"] into a Params, with types from the defaults."""
    types = {f.name: type(getattr(DEFAULT, f.name)) for f in fields(Params)}  # types from the field defaults, not the preset
    changes = {}
    for item in overrides:
        key, _, value = item.partition("=")
        if key not in types:
            raise SystemExit(f"Unknown parameter {key!r}. Known: {', '.join(types)}")
        changes[key] = types[key](value)
    return replace(base, **changes)
