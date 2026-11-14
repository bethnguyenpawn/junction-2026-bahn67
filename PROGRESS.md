# Progress

Status, what we learned, and what's next. Every experiment with its numbers: [LESSONS.md](LESSONS.md) · Challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## Status (Sat 14 Nov, 13:30)

**Use `--preset l8_plan`** for ranking runs, the test finals and the final.

| Level 8 | Test weeks | Per week | Worst week |
|---|---|---|---|
| Official starter | 10 weeks: −€604,425 | −€60,442 | 39.3% (never ranked) |
| `l8_v1` → `l8_v3` (older versions) | 30 weeks: €260,043 → €307,943 | €8,668 → €10,265 | 91.0–92.6% |
| `l8` (pricing rules, no planning) | 30 weeks: €320,596 | €10,687 | 91.5% |
| **`l8_plan`** (`l8` + two-car gigs) | 10 weeks `l8x`: €116,121 (`l8`: €104,324) | **€11,612** | **93.2%** |

| Practice ranking round | Preset | Us | Rank | 10th / 1st |
|---|---|---|---|---|
| "Saturday 00:00" | `l8_v1` | €46,496 | 43 of 62 | €75,475 / – |
| "Saturday 09:00" | `l8_v3` | €47,002 | 28 of 36 | €68,719 / €77,573 |
| **"Saturday 12:00"** | **`l8_plan`** | **€71,409**, 373 orders/week, worst 94.9% | – | €87,915 / €98,990 |

**Gap:** the top 10 win ~430–470 orders/week at €40–43 each; we win 373 at €38. We need ≈ +€3,300/week. Our worst on-time week is 94.9% (90% needed), so we can afford to win more.

**Experimental matching candidate:** `l8_plan_match` uses maximum-cardinality matching over the same deadline- and route-feasible pair edges; current round-trip and short-link preferences guide ties. Offline tests pass, including exhaustive comparison on all undirected graphs up to six nodes. The fresh `l8fresh14` baseline attempt completed only 3/10 weeks (€35,312.53 total, 95.76% weighted on-time, 93.77% worst, 3/3 ranked) before practice capacity filled. A one-seed candidate pilot then waited 327 seconds and timed out with all eight slots occupied; it created no world. The candidate remains unbenchmarked; keep `l8_plan` as best. `evaluate.py` now retries slot-full responses for up to five minutes. Continue the matched test when slots are available.

Ranking round: one person runs `for i in 1 2 3 4 5; do .venv/bin/python main.py --board --level 8 --preset l8_plan || break; done` (only one ranking run per team at a time; a second one gets HTTP 409).

## The level-8 system (`--preset l8_plan`)

1. **Price:** 1.45× the list price (the competitor is 26–54% above list); 0.2× less where ≥ 40 drivers live within 30 km of the pickup; 0.2× more for private addresses; plus the competitor's offset for the delivery place (−0.17× Vantaa … +0.18× Joensuu, `lanes.json`).
2. **Backlog brake:** +0.03× per won order still without a driver, so we take fewer cars when overloaded.
3. **Decline** (quote 10× list: never wins, costs nothing): trips over 550 km, and requests whose delivery options leave < 8 h to find a driver.
4. **Batch planning:** won cars with ≥ 8 h until their latest pickup are held. Every 3 h (07:00–19:00) the held cars are paired so one driver delivers two (car B's pickup ≤ 30 km from car A's delivery, both ≥ 4 h early), at 0.9× both typical fees. A car that can't wait 24 h for the next plan is posted alone; a pair nobody books within 2 h is split into two gigs.
5. **Driver fee:** opens at 0.8× the typical fee, +0.1× every 30 min up to 1.3×; after `deadline_close` 1.5× rising to 2.5×.
6. **Recovery:** after a crash or server restart, the bot rebuilds its state from the world (tested: same result as without the restart); held cars are posted at once.

## What we learned

- **Price curve:** win rate at 1.2× list 61%, 1.4× 40%, 1.6× 19%. Profit per request is flat from 1.1× to 1.4×, so a lower price only adds risk.
- **Drivers:** we use 100–150 of the 650–950 drivers a week; fees are ~60% of revenue. Our fee schedule is at its optimum as one level for all cars.
- **Sharing drivers is the volume lever** (Exp. 37): 85% of won cars could share a driver with another. Holding cars and pairing them every 3 h gives ~45% more orders at the same margin per order; pairs are booked within a minute.
- **Mondays:** we win only 1–10% of quotes in most weeks; the competitor starts each week cheap and raises its prices for dealers we rarely win.
- **Safety:** cheaper base prices and longer trips always look good on some weeks but leave a fresh week under 90%. Always check `l8x` and `l8y`.
- **Dealer trust drives volume:** at the same price we win 36% of a dealer's requests at trust 0–4 and 82% at trust 25. One dealer sends 1/3 of all requests; each late order halves its trust.
- **Lanes:** the competitor's price depends on where the car goes, the same in every world (HANDBOOK). Fitted from 19,450 random-price quotes: −0.17× list for Vantaa up to +0.18× for Joensuu/Ylivieska (`lanes.json`, `analysis/lanes.py`). Using it: +4.1% over 30 weeks.
- **Expected-profit pricing** (`opt`, fitted win and lateness models): with a full lateness penalty and trade-ins declined it is safe (worst 91.4%), but only +€2.4k over 20 weeks vs `l8`: not worth switching (Exp. 29). Pricing low to build dealer trust loses money (Exp. 29). Learning the week's price level from wins/losses: +1.3% but a fresh week at 90.6% (Exp. 31). Return-trip offers to drivers who just delivered for us: 1–3 of 41–104 accepted (Exp. 33). Outage pricing: detected reliably, but a higher price there loses orders and trust (Exp. 34). Price-war day: detected, cutting our price is neutral (Exp. 35). Guarded expected-profit pricing (`l8_guarded`, only low-risk requests, ±6% around `l8`): +€2.0k on tuning weeks but −€3.7k on 20 fresh weeks (Exp. 38); fresh lateness clusters on 300–499 km trips and `next_day` options.
- **Tried, no gain** (code kept, off): dealer-trust pricing, prices per delivery option, flat fees, other fee caps, fee level per car, direct offers to drivers near the delivery town, two-car gigs posted at once (Exp. 24, replaced by planning), win-rate steering, price by our cost, higher fees or stricter filters for trusted dealers, lower prices for big dealers.

## Code

| File | What it does |
|---|---|
| `main.py` | Runs a world: practice loop (`advance`), final loop (live stream, skips a failing event, rebuilds after errors). |
| `dispatch.py` | `Desk`: answers each event with actions (post, reprice, withdraw, retry); batch planning of two-car gigs; fee schedules. |
| `pricing.py` | `quote(request, level, params, Situation)`: flat rules, or expected-profit pricing (`opt`). Levels 1–3: list price. |
| `config.py` | `Params` (every tunable number; used ones first, tested-and-off ones last) and `PRESETS`. Defaults = kit starter. |
| `evaluate.py` | Benchmark over 10 fixed weeks (≤ 4 worlds at once) → `results/log.jsonl`. |
| `analysis/` | `orders.py` (late%/margin by distance, day, town), `market.py` (win rate by price, drivers near pickup), `winmodel.py` / `latemodel.py` / `lanes.py` (fit the models, need numpy), `fees.py` (how fast drivers book). |
| `tests/` | Offline unit tests: `python -m unittest discover -s tests`. |

## Next (in priority order)

1. **Test finals Sat 14:00 and 20:00:** start `.venv/bin/python main.py --final --preset l8_plan` before each begins. Check it keeps up with the clock and the score looks like a practice week.
2. **Win more orders now that planning frees drivers** (one change at a time, on `l8`, `l8x`, then `l8y`): `quote_mult=1.40`, `decline_km=600`, a lower `pair_fee` (0.8).
3. **Cars still undelivered at the week's end:** 0.6–0.8% in 2 of 5 ranking weeks, −€355 and −€836. Find out why and fix.
4. **Final Sun 08:00** with the best validated preset; start it before 08:00 and watch the log.

## Deadlines

- **Sat 14:00, 20:00:** test finals (live clock, ~19 min).
- **Sun 07:30:** the final is set. **Sun 08:00:** the final (level 8, ~34 min).
- **Sun 10:00:** submission on the Junction platform: submission hash (team page), code link, 5–10 slides.

## Rules

No ranking runs without team agreement · never print or commit the key · one change per experiment on the same seeds, logged in LESSONS.md · at most 4 of 8 world slots.
