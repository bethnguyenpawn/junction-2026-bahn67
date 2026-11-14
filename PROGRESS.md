# Progress

Status, what we learned, and what's next. Every experiment with its numbers: [LESSONS.md](LESSONS.md) · Challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## Status (Sat 14 Nov, 10:00)

**Use `--preset l8`** for ranking runs and the final.

| Level 8 | 30 test weeks (`l8`, `l8x`, `l8y`) | Per week | Worst week |
|---|---|---|---|
| Official starter (10 weeks) | −€604,425 | −€60,442 | 39.3% (never ranked) |
| `l8_v1` (practice round "Saturday 00:00": €46,496, rank 43 of 62) | €260,043 | €8,668 | 92.0% |
| `l8_v2` | €297,267 | €9,909 | 91.0% |
| **`l8` (current)** | **€307,943** | **€10,265** | **92.6%**, 30/30 ranked |

**Gap to the top 10:** 10th place in that round had €75,475 (≈ €15,100/week); House best €71,790. We need ≈ +€5,000/week.

Ranking round: run 5× `.venv/bin/python main.py --board --level 8 --preset l8` (only when the team agrees).

## The level-8 system (`--preset l8`)

1. **Price:** 1.45× the list price (the competitor is 26–54% above list); 0.2× less where ≥ 40 drivers live within 30 km of the pickup; 0.2× more for private addresses.
2. **Backlog brake:** +0.03× per won order still without a driver, so we take fewer cars when overloaded.
3. **Decline** (quote 10× list: never wins, costs nothing): trips over 550 km, and requests whose delivery options leave < 8 h to find a driver.
4. **Driver fee:** opens at 0.8× the typical fee, +0.1× every 30 min up to 1.3×; after `deadline_close` 1.5× rising to 2.5×.
5. **Recovery:** after a crash or server restart, the bot rebuilds its state from the world (tested: same result as without the restart).

## What we learned

- **Price curve:** win rate at 1.2× list 61%, 1.4× 40%, 1.6× 19%. Profit per request is flat from 1.1× to 1.4×, so a lower price only adds risk.
- **Drivers:** we use 100–150 of the 650–950 drivers a week; fees are ~60% of revenue. Our fee schedule is at its optimum as one level for all cars.
- **Mondays:** we win only 1–10% of quotes in most weeks; the competitor starts each week cheap and raises its prices for dealers we rarely win.
- **Safety:** cheaper base prices and longer trips always look good on some weeks but leave a fresh week under 90%. Always check `l8x` and `l8y`.
- **Tried, no gain** (code kept, off): dealer-trust pricing, prices per delivery option, flat fees, other fee caps, fee level per car, direct offers to drivers near the delivery town, two-car gigs, win-rate steering, price by our cost.

## Code

| File | What it does |
|---|---|
| `main.py` | Runs a world: practice loop (`advance`), final loop (live stream, skips a failing event, rebuilds after errors). |
| `dispatch.py` | `Desk`: answers each event with actions (post, reprice, withdraw, retry); fee schedules. |
| `pricing.py` | `quote()`: the pricing rules. Levels 1–3: list price (no quote = declined). |
| `config.py` | `Params` (every tunable number; used ones first, tested-and-off ones last) and `PRESETS`. Defaults = kit starter. |
| `evaluate.py` | Benchmark over 10 fixed weeks (≤ 6 worlds at once) → `results/log.jsonl`. |
| `analysis/` | `orders.py` (late%/margin by distance, day, town), `market.py` (win rate by price, drivers near pickup), `fees.py`. |
| `tests/` | Offline unit tests: `python -m unittest discover -s tests`. |

## Next (in priority order)

1. **Test final today 14:00 (and 20:00):** start `.venv/bin/python main.py --final --preset l8` before 14:00. Check it keeps up with the clock and that the score looks like a practice week.
2. **Cheaper drivers:** offers to drivers who just finished our gigs nearby; holding new orders a few minutes to pair them.
3. **Dealer trust as extra wins** (raising prices for trusted dealers failed): e.g. a weaker backlog brake for them.
4. **Price-war day** (competitor −20% for one unannounced day) and the outage region (competitor down, +30% prices).

## Deadlines

- **Sat 14:00, 20:00:** test finals (live clock, ~19 min).
- **Sun 07:30:** the final is set. **Sun 08:00:** the final (level 8, ~34 min).
- **Sun 10:00:** submission on the Junction platform: submission hash (team page), code link, 5–10 slides.

## Rules

No ranking runs without team agreement · never print or commit the key · one change per experiment on the same seeds, logged in LESSONS.md · at most 6 of 8 world slots.
