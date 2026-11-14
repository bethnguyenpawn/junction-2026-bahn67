# Progress

Experiment details: [LESSONS.md](LESSONS.md) · Challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## Summary (Sat 14 Nov, late morning)

**Current `--preset l8`** (use it for ranking runs and the final):

| Level 8 | 30 test weeks (`l8`, `l8x`, `l8y`) | Per week | Worst week |
|---|---|---|---|
| `l8_v1` (round "Saturday 00:00": €46,496, rank 43 of 62) | €260,043 | €8,668 | 92.0% |
| `l8_v2` (Sat night) | €297,267 | €9,909 | 91.0% |
| **`l8` (now)** | **€307,943** | **€10,265** | **92.6%**, 30/30 ranked |

To play a ranking round: run 5× `.venv/bin/python main.py --board --level 8 --preset l8`.

## Saturday morning (structural ideas, details in LESSONS.md Exp. 17–21)

**Gap:** practice round "Saturday 00:00" ended with `bahn67` 43rd of 62 (€46,496); 10th place €75,475, House best €71,790.
Top 10 needs ≈ +€6,000/week, more than parameter tuning gives.

Findings:
- We win ~23% of the ~910 requests we quote (~205 orders/week). Price curve: 1.2× list wins 61%, 1.4× 40%, 1.6× 19%; profit per request is flat from 1.1× to 1.4×.
- We use only 100–150 of the 650–950 drivers a week: **the driver fee, not the number of drivers, limits us.** Fees are ~60% of revenue.
- Worked: 0.2 cheaper where ≥ 40 drivers live within 30 km of the pickup; +0.2 on private addresses (11% late, €8/order).
- Did not work: direct offers to drivers near the delivery town (almost all unread or declined), a different fee cap.

**Result:** the two rules that worked are now in `--preset l8` (+3.6% over 30 weeks, worst week 92.6%). The candidate `l8b` (also cheaper base price and longer trips) had an unranked week on `l8y` and was dropped.

## The level-8 system (`--preset l8`)

1. **Quote 1.45× the list price** (competitor is 26–54% above list); **0.2× less** where ≥ 40 drivers live within 30 km of the pickup, **0.2× more** for private addresses.
2. **+0.03× per won order still without a driver** (backlog brake: take fewer cars when overloaded).
3. **Decline trips > 550 km** (quote 10× list: never wins, costs nothing).
4. **Only offer delivery options with ≥ 8 h slack** (deadline − drive − now); otherwise decline.
5. **Driver fee opens at 0.8× the typical fee, +0.1× every 30 min**; 1.5× after `deadline_close`.
6. (Level 1 only: fee ladder by reprice, `--preset l1`.)

Tried and rejected overnight (see LESSONS.md): dealer-trust pricing (−€12k), flat fees without raises, steep fee 1.25×/2.0×, 6 h slack, decline > 600 km (a 90.5% week) and > 700 km, per-option prices, opening fee 0.7×.

## Code

| File | What it does |
|---|---|
| `main.py` | Runs a world: practice advance loop, final live-stream loop (`--final`). |
| `dispatch.py` | `Desk`: answers events (post, reprice, withdraw, retry); fee schedules; level-1 ladder. |
| `pricing.py` | `quote()`: the pricing rules above (levels 4+), plus drivers-near-pickup and private-address adjustments. Levels 1–3: list price; no quote = declined. |
| `config.py` | `Params` (every tunable number) and `PRESETS` (`starter`, `l1`, `l8`, `l8_v2`, `l8_v1`). Default = kit starter exactly. |
| `evaluate.py` | Benchmark over fixed seeds (≤ 6 worlds at once) → `results/log.jsonl`. |
| `analysis/` | `fees.py` (money, booking delays), `orders.py` (late%/margin by distance, option, day, town), `market.py` (win rate by price, drivers near pickup). |
| `tests/` | Offline unit tests (pricing rules, fee schedules, config): `python -m unittest discover -s tests`. |

```bash
python evaluate.py --level 8 --preset l8                      # tuning weeks (~2 min)
python evaluate.py --level 8 --preset l8 --seed-prefix l8x    # unseen weeks: always check both
python evaluate.py --level 8 --preset l8 --set quote_mult=1.5 --note "idea"   # an experiment
python analysis/orders.py --note "idea"                       # why orders were late / lost money
python main.py --final --preset l8                            # the final (live stream)
```

## Next (in priority order)

1. **Test `--final --preset l8` in a test final (Sat 14:00 or 20:00).** The live loop has never run; check it keeps up and survives a restart.
2. **Cheaper drivers** (fees are ~60% of revenue; we use ~15% of the drivers): multi-car gigs (return trips, two cars from one yard), offers to drivers who just finished our gigs nearby.
3. **Dealer trust as extra wins, not higher prices** (raising prices failed): e.g. lower the backlog brake for trusted dealers.
4. **After `deadline_close`:** steep fee level/timing at level 8, or direct offers to drivers near the pickup.
5. **Price-war day:** competitor −20% on one unannounced day; detect from losing streaks.
6. Check `--preset l8` on levels 4–7 (sanity), and level 2–3 ideas (multi-car gigs).

## Deadlines

- **Sat 14:00, 20:00:** test finals (live clock, ~19 min).
- **Sun 07:30:** final is set, registration closes. **Sun 08:00:** final (level 8, ~34 min).
- **Sun 10:00:** final submission on the Junction platform: submission hash (team page), code link, 5–10 slides.

## Conduct

No ranking runs without team agreement · never print or commit the key · one change per experiment on the same seeds, logged in LESSONS.md · at most 6 of 8 world slots.
