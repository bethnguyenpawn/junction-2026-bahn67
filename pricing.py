"""Quoting. Levels 1-3 have no competitor: every quote wins the first option at its list price.

Note: a request WITHOUT a quote is declined (RULES: "Up to level 3 ... you decline by sending no
quote"), so we must still quote to win anything. Real pricing starts at level 4.
"""
from __future__ import annotations

from typing import Optional

from spread.types import PriceRequest

from config import Params


def quote(request: PriceRequest, level: int, params: Params) -> Optional[dict]:
    """The prices to quote per option, or None to decline. Starter behaviour: list price of the first option."""
    first = request["options"][0]
    return {first["kind"]: first["listPriceCents"]}
