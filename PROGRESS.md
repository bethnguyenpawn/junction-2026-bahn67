# Progress

Status, what we learned, and what's next. Every experiment with its numbers: [LESSONS.md](LESSONS.md) · Challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## Status (Sat 14 Nov, 14:00)

**Use `--preset l8`** for ranking runs and the final.

| Level 8 | 30 test weeks (`l8`, `l8x`, `l8y`) | Per week | Worst week |
|---|---|---|---|
| Official starter (10 weeks) | −€604,425 | −€60,442 | 39.3% (never ranked) |
| `l8_v1` (practice round "Saturday 00:00": €46,496, rank 43 of 62) | €260,043 | €8,668 | 92.0% |
| `l8_v2` | €297,267 | €9,909 | 91.0% |
| `l8_v3` (practice round "Saturday 09:00") | €307,943 | €10,265 | 92.6% |
| **`l8` (current)** | **€320,596** | **€10,687** | **91.5%**, 30/30 ranked |

**Practice round "Saturday 09:00" with `l8_v3`:** €47,002 (97.3% on time), rank 28 of 36 finished; House best €50,660, 10th €68,719, 1st €77,573.
**Gap:** the top teams win ~400 orders/week vs our ~255 at the same margin per order (€35–40) and on-time share. We need ≈ +€4,000/week.

Ranking round: run 5× `.venv/bin/python main.py --board --level 8 --preset l8` (only when the team agrees).

## The level-8 system (`--preset l8`)

1. **Price:** 1.45× the list price (the competitor is 26–54% above list); 0.2× less where ≥ 40 drivers live within 30 km of the pickup; 0.2× more for private addresses; plus the competitor's offset for the delivery place (−0.17× Vantaa … +0.18× Joensuu, `lanes.json`).
2. **Backlog brake:** +0.03× per won order still without a driver, so we take fewer cars when overloaded.
3. **Decline** (quote 10× list: never wins, costs nothing): trips over 550 km, and requests whose delivery options leave < 8 h to find a driver.
4. **Driver fee:** opens at 0.8× the typical fee, +0.1× every 30 min up to 1.3×; after `deadline_close` 1.5× rising to 2.5×.
5. **Recovery:** after a crash or server restart, the bot rebuilds its state from the world (tested: same result as without the restart).

## What we learned

- **Price curve:** win rate at 1.2× list 61%, 1.4× 40%, 1.6× 19%. Profit per request is flat from 1.1× to 1.4×, so a lower price only adds risk.
- **Drivers:** we use 100–150 of the 650–950 drivers a week; fees are ~60% of revenue. Our fee schedule is at its optimum as one level for all cars.
- **Mondays:** we win only 1–10% of quotes in most weeks; the competitor starts each week cheap and raises its prices for dealers we rarely win.
- **Safety:** cheaper base prices and longer trips always look good on some weeks but leave a fresh week under 90%. Always check `l8x` and `l8y`.
- **Dealer trust drives volume:** at the same price we win 36% of a dealer's requests at trust 0–4 and 82% at trust 25. One dealer sends 1/3 of all requests; each late order halves its trust.
- **Lanes:** the competitor's price depends on where the car goes, the same in every world (HANDBOOK). Fitted from 19,450 random-price quotes: −0.17× list for Vantaa up to +0.18× for Joensuu/Ylivieska (`lanes.json`, `analysis/lanes.py`). Using it: +4.1% over 30 weeks.
- **Expected-profit pricing** (`opt`, fitted win and lateness models): with a full lateness penalty and trade-ins declined it is safe (worst 91.4%), but only +€2.4k over 20 weeks vs `l8`: not worth switching (Exp. 29). Pricing low to build dealer trust loses money (Exp. 29). Learning the week's price level from wins/losses: +1.3% but a fresh week at 90.6% (Exp. 31).
- **Tried, no gain** (code kept, off): dealer-trust pricing, prices per delivery option, flat fees, other fee caps, fee level per car, direct offers to drivers near the delivery town, two-car gigs, win-rate steering, price by our cost, higher fees or stricter filters for trusted dealers, lower prices for big dealers.

## Code

| File | What it does |
|---|---|
| `main.py` | Runs a world: practice loop (`advance`), final loop (live stream, skips a failing event, rebuilds after errors). |
| `dispatch.py` | `Desk`: answers each event with actions (post, reprice, withdraw, retry); fee schedules. |
| `pricing.py` | `quote(request, level, params, Situation)`: flat rules, or expected-profit pricing (`opt`). Levels 1–3: list price. |
| `config.py` | `Params` (every tunable number; used ones first, tested-and-off ones last) and `PRESETS`. Defaults = kit starter. |
| `evaluate.py` | Benchmark over 10 fixed weeks (≤ 6 worlds at once) → `results/log.jsonl`. |
| `analysis/` | `orders.py` (late%/margin by distance, day, town), `market.py` (win rate by price, drivers near pickup), `winmodel.py` / `latemodel.py` (fit the pricing models, needs numpy), `fees.py`. |
| `tests/` | Offline unit tests: `python -m unittest discover -s tests`. |

## Next (in priority order)

1. **Test final today 14:00 (and 20:00):** start `.venv/bin/python main.py --final --preset l8` before 14:00. Check it keeps up with the clock and that the score looks like a practice week.
2. **Cheaper drivers:** offers to drivers who just finished our gigs nearby.
3. **Price-war day** (competitor −20% for one unannounced day) and the outage region (competitor down, +30% prices).

## Deadlines

- **Sat 14:00, 20:00:** test finals (live clock, ~19 min).
- **Sun 07:30:** the final is set. **Sun 08:00:** the final (level 8, ~34 min).
- **Sun 10:00:** submission on the Junction platform: submission hash (team page), code link, 5–10 slides.

## Rules

No ranking runs without team agreement · never print or commit the key · one change per experiment on the same seeds, logged in LESSONS.md · at most 6 of 8 world slots.
