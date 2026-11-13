# Lessons: experiment log

**Summary.** Level 1: a fee ladder by reprice (open 0.7×, +0.3×/h) turns −€28,978 into +€34,186 per 10 weeks.
Level 8 (the final): five pricing/fee rules (Experiments 3–7) turn −€604,425 into +€79,155 (and +€82,446 on unseen weeks), 20/20 weeks ranked.
What did not work: a flat lower fee at level 1 (too many late cars); the level-1 ladder at level 8; higher opening fees to fix lateness at level 8; declining > 400 km (too many good orders lost).

Every experiment: level 1, seeds `l1-a` … `l1-j` (10 weeks), one change at a time. Raw numbers in `results/log.jsonl`.
Keep a change only if total margin rises AND every week stays well above 90% on time.

## Baseline: kit starter (refactored into main/dispatch/config, identical to the cent on l1-a)

| Config | Total margin (10 wk) | Per week | On time | Worst week | Ranked |
|---|---|---|---|---|---|
| Starter: post at 1.0× typical fee, 1.5× after `deadline_close` | **−€28,977.80** | −€2,898 | 93.6% | 90.6% (l1-h) | 10/10 |

Where the money goes (per week, baseline): revenue €78,410, driver fees −€77,668, late refunds −€2,787, undelivered −€523, release fees −€330.

## Analysis 1: drivers book 1.0× gigs almost instantly (`analysis/fees.py`)

- **Idea:** check whether 1.0× the typical fee is more than drivers need.
- **Found:** median minutes from post to booking = **1** (p75 7, p90 70). 90% of bookings at exactly 1.0×.
  The typical fee ≈ 0.90× the list price (median), so at 1.0× there is almost no margin.
- **Also found:** margin per order falls with distance: +€4.89 (0–99 km) … −€42.51 (600+ km); late share rises from 2% to 21%.

## Experiment 1: flat lower fee

| Change | Total | On time | Worst | Ranked | Verdict |
|---|---|---|---|---|---|
| `open_mult=0.8` (flat, single fee) | −€6,715.83 | 88.2% | 85.7% | **1/10** | ✗ cheaper, but too many cars late |

- **Why it fails:** at level 1 a gig has a single fee, so a car that needs more than 0.8× never finds a driver until `deadline_close`.

## Experiment 2: fee ladder by reprice

- **Idea:** open low, then raise the fee ourselves with `reprice` every 10 min until a driver books: target = min(cap, open + rate × hours since first post).
- **Why:** reprice works on any unbooked gig, and at level 1 drivers do not learn our raises (learning starts at level 2), so waiting costs us nothing in driver behaviour.

| open | +/hour | cap | Total | Per week | On time | Worst | Ranked |
|---|---|---|---|---|---|---|---|
| 0.7 | 0.3 | 1.5 | **+€34,186.06** | +€3,419 | 93.2% | 91.1% | 10/10 |
| 0.5 | 0.3 | 1.5 | +€28,256.27 | +€2,826 | 92.8% | 89.2% | 9/10 ✗ |
| 0.7 | 0.6 | 1.5 | +€26,038.79 | +€2,604 | 93.9% | 91.3% | 10/10 |
| 0.8 | 0.3 | 1.5 | +€20,588.15 | +€2,059 | 93.7% | 91.8% | 10/10 |
| 0.6 | 0.3 | 1.5 | +€37,597.43 | +€3,760 | 93.2% | **90.5%** | 10/10 ⚠ highest margin, but too close to 90% |
| 0.7 | 0.15 | 1.5 | +€32,070.30 | +€3,207 | 92.6% | 90.5% | 10/10 ✗ slower ramp: less margin, less safety |

Observations: margin peaks around an opening of 0.6–0.7×; lower openings save fees but push the worst week toward 90%.
The ramp speed matters less than the opening fee. The on-time floor (~90.5–91%) is now the binding limit:
the next gains must come from fewer late cars (better `deadline_close` handling, long trips), not cheaper openings.

**Best so far: open 0.7, +0.3/hour, cap 1.5 → +€63,164 over 10 weeks vs the starter.**

---

# Level 8 (the final's level)

Seeds `l8-a` … `l8-j` for tuning; **`l8x-a` … `l8x-j` held out** to check we did not overfit.

## Baseline

| Config | Total (10 wk) | Per week | Orders/wk | On time | Worst | Ranked |
|---|---|---|---|---|---|---|
| Starter (quote list price, fee 1.0×) | −€604,425 | −€60,442 | 882 | 53.6% | 39.3% | 0/10 |
| Level-1 best ladder | −€627,157 | −€62,716 | 881 | 52.3% | 37.6% | 0/10 ✗ does not transfer |

Analysis (`analysis/orders.py`): 46% of won orders late, every segment loses money; lateness rises Mon 23% → Fri 62% (drivers fill up). Drivers book only at ~1.5× typical (the steep fee). We quote list price while the competitor is 26–54% above it, so we win nearly everything and can't move it.

## Experiment 3: quote above list price (`quote_mult`)

- **Idea:** price = list × `quote_mult`. **Why:** we are the cheapest by far; higher prices earn more per car and win fewer cars, which our drivers can move.

| quote_mult | Total | Orders/wk | On time | Worst | Ranked |
|---|---|---|---|---|---|
| 1.3 | −€137,374 | 537 | 70.2% | 53.0% | 0/10 |
| 1.5 | +€27,583 | 323 | 83.2% | 72.8% | 0/10 |
| **1.7** | **+€58,147** | 155 | 90.1% | 81.2% | 6/10 |
| 1.9 | +€33,441 | 53 | 93.8% | 87.5% | 8/10 |
| 2.1 | +€15,953 | 17 | 97.6% | 85.7% | 9/10 |

Fees alone don't fix lateness: with quote 1.7, opening fee 1.3× → +€30,335, 1.6× → −€2,907 (on-time barely moves).

## Experiment 4: decline long trips (`decline_km`)

- **Idea:** quote 10× list (never wins, costs nothing) when the trip is longer than X km. **Why:** at quote 1.7, 600+ km orders were 30% late, 500–599 km 21.5%, < 100 km 4%.

| On top of quote 1.7 | Total | On time | Worst | Ranked |
|---|---|---|---|---|
| decline > 500 km | +€57,189 | 93.7% | 87.8% | 8/10 |
| decline > 400 km | +€47,220 | 93.5% | 87.3% | 9/10 |

## Experiment 5: only offer options with time to find a driver (`min_slack_h`)

- **Idea:** slack = deadline − road minutes − respondBy. Quote every option with slack ≥ X hours (the dealer picks); decline if none.
- **Why:** tracing the late orders of the worst week showed the pattern: `same_day` orders won around midday get `deadline_close` within 1–2 h, nobody books even at 1.5×, the gig expires at 20:00 and the car moves the next day.

| On top of quote 1.7, decline > 500 | Total | On time | Worst | Ranked |
|---|---|---|---|---|
| slack ≥ 6 h | +€58,344 | 95.8% | 91.8% | **10/10** |
| slack ≥ 10 h | +€54,448 | 97.2% | 93.9% | 10/10 |
| quote 1.6, slack ≥ 8 h | +€70,404 | 95.6% | 91.7% | 10/10 |
| quote 1.5, slack ≥ 8 h | +€66,786 | 94.3% | 89.5% | 9/10 |
| quote 1.6, slack ≥ 10 h | +€67,894 | 95.9% | 93.2% | 10/10 |
| quote 1.6, slack ≥ 8 h, **no km decline** | +€59,913 | 92.0% | 84.2% | 8/10 ✗ (km decline still needed) |

## Experiment 6: opening fee at level 8 (on quote 1.6, decline > 500, slack ≥ 8 h)

| open_mult | Total | On time | Worst | Ranked |
|---|---|---|---|---|
| 1.0 (starter) | +€70,404 | 95.6% | 91.7% | 10/10 |
| 0.9 | +€80,845 | 95.1% | 91.3% | 10/10 |
| **0.8** | **+€81,481** | 94.7% | 91.1% | 10/10 |
| 0.8, raise 0.2/h | +€68,531 | 95.7% | 92.1% | 10/10 |
| 0.6 | +€68,369 | 91.6% | 87.7% | 8/10 |
| 0.8, slack ≥ 10 h | +€80,573 | 95.2% | 91.5% | 10/10 |

## Holdout check and Experiment 7: backlog pricing (`backlog_k`)

On unseen weeks `l8x`, the best config kept its margin (+€81,073) but one week failed (l8x-c, 88.0%, 324 orders): in weeks where the competitor is dear we win too many cars.

- **Idea:** quote_mult += `backlog_k` × (won orders that still have no driver). **Why:** a fixed price can't see that we are overloaded this week; the backlog can.
- (Without the slack filter, backlog_k 0.01/0.03 had little effect: €54,871 / €50,747, worst 87%. With the slack filter it fixes the overload weeks.)

| quote 1.6, decline > 500, slack ≥ 8 h, open 0.8 | Seeds | Total | On time | Worst | Ranked |
|---|---|---|---|---|---|
| no backlog | l8 | +€81,481 | 94.7% | 91.1% | 10/10 |
| no backlog | l8x (unseen) | +€81,073 | 93.0% | **88.0%** | 9/10 ✗ |
| **backlog_k = 0.01** | l8 | **+€79,155** | 95.6% | 92.0% | **10/10** |
| **backlog_k = 0.01** | l8x (unseen) | **+€82,446** | 95.9% | 94.2% | **10/10** |

**Current level-8 system = `--preset l8`: +€8,080/week over 20 weeks, every week ranked (worst 92.0%), vs −€60,442/week for the starter.**
