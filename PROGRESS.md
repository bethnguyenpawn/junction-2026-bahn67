# Progress

Experiment details: [LESSONS.md](LESSONS.md) · Challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## Status (Sat 14 Nov, early morning)

**Level 8 (the final's level), `--preset l8`:**

| | 10 tuning weeks `l8-*` | 10 unseen weeks `l8x-*` | Ranked weeks |
|---|---|---|---|
| Kit starter | −€604,425 (53.6% on time) | — | 0/10 |
| **Ours** | **+€79,155** (95.6%, worst 92.0%) | **+€82,446** (95.9%, worst 94.2%) | **20/20** |

For scale: top teams on the level-8 practice board make ≈ €12,000–14,700/week, House best ≈ €14,400/week (different weeks, rough comparison). Ours ≈ €8,080/week.

**Level 1, `--preset l1`:** +€34,186 on `l1-*` vs −€28,978 for the starter (fee ladder by reprice). Does not transfer to level 8.

## The level-8 system in five rules

1. **Quote 1.6× the list price** (competitor is 26–54% above list; at list price we won everything and were 46% late).
2. **+0.01× per won order still without a driver** (backlog): take fewer cars when overloaded.
3. **Decline trips > 500 km** (quote 10× list: never wins, costs nothing).
4. **Only offer delivery options with ≥ 8 h slack** (deadline − drive − now); same-day cars won at midday found no driver.
5. **Open driver fees at 0.8× the typical fee**, +0.1×/hour, steep 1.5× after `deadline_close`.

## Code

| File | What it does |
|---|---|
| `main.py` | Runs a world: practice advance loop, final live-stream loop (`--final`). |
| `dispatch.py` | `Desk`: answers events (post, reprice, withdraw, retry); fee schedules; level-1 ladder. |
| `pricing.py` | `quote()`: the five pricing rules above (levels 4+). Levels 1–3: list price; no quote = declined. |
| `config.py` | `Params` (every tunable number) and `PRESETS` (`starter`, `l1`, `l8`). Default = kit starter exactly. |
| `evaluate.py` | Benchmark over fixed seeds (≤ 6 worlds at once) → `results/log.jsonl`. |
| `analysis/` | `fees.py` (money, booking delays), `orders.py` (late%/margin by distance, option, day, town). |
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
2. **Dealer trust (level 8):** dealers accept up to 25% higher prices after on-time deliveries; price per dealer by our on-time count.
3. **After `deadline_close`:** steep fee level/timing at level 8, or direct offers to drivers near the pickup.
4. **Price-war day:** competitor −20% on one unannounced day; detect from losing streaks.
5. Check `--preset l8` on levels 4–7 (sanity), and level 2–3 ideas (multi-car gigs).

## Deadlines

- **Sat 14:00, 20:00:** test finals (live clock, ~19 min).
- **Sun 07:30:** final is set, registration closes. **Sun 08:00:** final (level 8, ~34 min).
- **Sun 10:00:** final submission on the Junction platform: submission hash (team page), code link, 5–10 slides.

## Conduct

No ranking runs without team agreement · never print or commit the key · one change per experiment on the same seeds, logged in LESSONS.md · at most 6 of 8 world slots.
