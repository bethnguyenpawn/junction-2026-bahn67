# Progress

Experiment details: [LESSONS.md](LESSONS.md) · Challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## Morning summary (Sat 14 Nov, overnight tuning)

**New `--preset l8`** (the old one is kept as `l8_v1`):

| | 30 test weeks (`l8`, `l8x`, `l8y`) | Per week | Worst week |
|---|---|---|---|
| `l8_v1` (ranked **11th of 25**, round "Saturday 00:00", €46,496) | €260,043 | €8,668 | 92.0% |
| **`l8` (new)** | **€297,267** | **€9,909 (+14%)** | 91.0%, 30/30 ranked |

On the 10 fresh weeks `l8y` (never used for tuning): €111,705 vs €98,442 (+13%).
If the ranking weeks scale the same way, €46,496 → ≈ €53,000, around 10th place last round (10th was €51,157).

**To check after 09:00 (new ranking round):** run 5×
`.venv/bin/python main.py --board --level 8 --preset l8`

## The level-8 system (six rules)

1. **Quote 1.45× the list price** (competitor is 26–54% above list).
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

0. **Play the 09:00 ranking round with the new preset** and compare with 11th / €46,496.
1. **Test `--final --preset l8` in a test final (Sat 14:00 or 20:00).** The live loop has never run; check it keeps up and survives a restart.
2. **Dealer trust as extra wins, not higher prices** (raising prices failed): e.g. lower the backlog brake for trusted dealers.
3. **After `deadline_close`:** steep fee level/timing at level 8, or direct offers to drivers near the pickup.
4. **Price-war day:** competitor −20% on one unannounced day; detect from losing streaks.
5. Check `--preset l8` on levels 4–7 (sanity), and level 2–3 ideas (multi-car gigs).

## Deadlines

- **Sat 14:00, 20:00:** test finals (live clock, ~19 min).
- **Sun 07:30:** final is set, registration closes. **Sun 08:00:** final (level 8, ~34 min).
- **Sun 10:00:** final submission on the Junction platform: submission hash (team page), code link, 5–10 slides.

## Conduct

No ranking runs without team agreement · never print or commit the key · one change per experiment on the same seeds, logged in LESSONS.md · at most 6 of 8 world slots.
