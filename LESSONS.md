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

## Practice ranking check (level 8, round "Saturday 00:00")

Played the round's 5 secret weeks with `--preset l8` (ranking runs, started by the user).

| Week | Margin | On time |
|---|---|---|
| 1 | €8,251 | 95.8% |
| 2 | €8,174 | 96.7% |
| 3 | €7,752 | 96.5% |
| 4 | €11,273 | 95.1% |
| 5 | €11,046 | 95.3% |
| **Total** | **€46,496** | 95.8%, 5/5 ranked |

Rank 11 of 25 while the round was open; final rank **43 of 62** (10th €75,475, House best €71,790, 1st €85,925).
Our own estimate (+€8,080/week) matched the secret weeks (+€9,299/week), so the seed sets predict well.
**Lesson:** we are reliable (on-time never below 95%) but under-earn by ≈ €5,000/week vs House best. Next gains must come from margin, not safety.

# Saturday night: closing the gap to the top 10

Base = `--preset l8` (quote 1.6, backlog 0.01, decline > 500 km, slack ≥ 8 h, open fee 0.8): l8 €79,155 · l8x €82,446.

## Experiment 8: dealer trust pricing (`trust_w`) ✗ did not work

- **Idea:** level-8 dealers accept 1% more per on-time order (max 25), so price each dealer at base × (1 + trust_w × 1% × count). Count kept from our own ledger (revenue without late refund = +1; late = halve), rebuilt in `rejoin`.
- **Result:** worse. Raising prices costs more wins than it earns.

| Change | l8 | l8x |
|---|---|---|
| trust_w = 1.0 | €66,483 (−€12.7k) | €70,850 (−€11.6k) |
| trust_w = 0.4 | €73,819 (−€5.3k) | — |

- **Lesson:** the base price was already too high; trust is worth more as *extra wins at the same price* than as a higher price. Code kept (off by default).

## Experiment 9: re-tune the base price with all rules on ✓ biggest gain

The other rules (slack, backlog) changed after `quote_mult` was tuned, so we re-swept it.

| quote_mult | backlog_k | l8 | l8x | Worst week | Verdict |
|---|---|---|---|---|---|
| 1.6 (old) | 0.01 | €79,155 | €82,446 | 92.0% | old preset |
| 1.75 | 0.01 | €48,658 | — | 93.6% | ✗ too few wins |
| 1.45 | 0.01 | €91,050 | €94,424 | **89.1%** (l8x) | ✗ one week unranked |
| 1.35 | 0.01 | €91,724 | — | 90.4% | ✗ too close to 90% |
| 1.25 | 0.01 | €87,136 | — | 88.9% | ✗ unranked week |
| 1.35 | 0.02 | €91,311 | €95,444 | 90.5% (l8x) | ✗ too close |
| **1.45** | **0.02** | **€88,447** | **€91,159** | **91.6%** | ✓ **new best: +€18,005 (+11%) over 20 weeks, 20/20 ranked** |

- **Lesson:** a lower price wins more; a stronger backlog brake (0.02 per driverless order) keeps the overload weeks safe.

## Experiment 10: relax the safety filters (on q1.45, bk0.02)

| Change | l8 | l8x | Worst | Verdict |
|---|---|---|---|---|
| slack ≥ 6 h (from 8) | €90,200 | €91,604 | 90.2% | ✗ +€2.2k for too much risk |
| decline > 600 km (from 500) | €89,701 | — | 91.2% | ~ +€1.3k on l8, needs l8x |

## Experiment 11: driver fees without raises ✗

- **Idea:** from level 2 drivers learn our raises and wait (median booking now 64 min after posting). A flat fee (0.9×, no raises) should stop the waiting.
- **Result:** l8 €79,952 (−€8.5k), worst week 89.3% ✗. Raises still find drivers for the hard cars.

Where the money goes now (q1.45 bk0.02, per week): revenue €23,885, driver fees −€14,412 (60%), late refunds −€318, failed visits −€212. 4.5% of orders late. Booked fee median 0.90× typical.

## Experiment 12: decline distance (on q1.45, bk0.02)

| decline_km | l8 | l8x | Worst | Verdict |
|---|---|---|---|---|
| 500 | €88,447 | €91,159 | 91.6% | old |
| **600** | **€89,701** | **€100,035** | 91.2% | ✓ +€10.1k (400–599 km orders are now profitable and on time) |
| 700 | €94,514 | €102,323 | **85.1%** | ✗ unranked weeks |

## Experiment 13: fees after `deadline_close` and raise speed (on q1.45, bk0.02, decline 600)

| Change | l8 | l8x | Worst | Verdict |
|---|---|---|---|---|
| steep fee 1.25× (from 1.5×) | €92,428 | — | 89.7% | ✗ unranked week |
| steep fee 2.0× | €86,330 | — | 91.7% | ✗ less margin |
| raise 0.05×/h (from 0.1×) | €88,309 | — | 91.1% | ✗ |
| raise every 30 min (from 60) | €97,260 | €102,988 | **90.5%** | ~ +€10.5k but too close to 90% |
| raise every 30 min + quote 1.5 | €93,346 | €99,101 | 91.6% | ✓ €192,447 |
| **raise every 30 min + backlog 0.03** | **€93,789** | **€96,294** | **92.3%** | ✓ **€190,083, safest → new preset** |
| open fee 0.7× (from 0.8×) | €77,249 | — | 91.4% | ✗ −€12k |

- **Lesson:** faster raises book drivers sooner (fewer cars near their deadline); the stronger backlog brake buys back the safety.
- **New `--preset l8`:** q1.45, backlog 0.03, decline > 600 km, slack ≥ 8 h, fee 0.8× +0.1× every 30 min → **€190,083 over 20 weeks** vs €161,601 for `l8_v1` (+18%), worst week 92.3%.

## Experiment 14: price by delivery option (`later_mult`) ✗

| Change (on raise30, bk0.03) | l8 | Verdict |
|---|---|---|
| next_day / within_3_days at 0.9× the same_day price | €88,910 | ✗ −€4.9k |
| … at 1.1× | €87,403 | ✗ −€6.4k |

Code kept, off by default (1.0).

## Experiment 15: quote 1.4 (on raise30, bk0.03)

l8 €96,223 · l8x €100,096 (worst 91.3%) · l8y €115,529 (worst **90.8%**). +€6k but the fresh weeks show it is too close to 90% → not adopted.

## Final check on 10 fresh weeks (`l8y`, never used for tuning)

| Preset | l8y total | Worst week |
|---|---|---|
| `l8_v1` (ranked 11th in round "Saturday 00:00") | €98,442 | 92.8% |
| q1.45, bk0.03, raise30, decline 600 | €115,168 (+17%) | **90.5%** (l8y-j: 500–599 km orders 26% late) |
| q1.4, same | €115,529 | 90.8% |

## Experiment 16: decline > 550 km (compromise) ✓ adopted

| Preset | l8 | l8x | l8y | 30 weeks | Worst |
|---|---|---|---|---|---|
| `l8_v1` | €79,155 | €82,446 | €98,442 | €260,043 | 92.0% |
| decline 600 | €93,789 | €96,294 | €115,168 | €305,251 | 90.5% |
| **decline 550 → `--preset l8`** | **€89,964** | **€95,598** | **€111,705** | **€297,267 (+14%)** | **91.0%** |

**Why 550 over 600:** −€270/week for half a point more safety on the worst week. The final is one week, played once; being unranked loses everything.
**Stopped here:** every further change gained < €300/week or cost safety.

# Saturday morning: structural ideas (on `--preset l8`, seeds l8-a..j, base €89,964)

## Experiment 17: price by drivers near the pickup (`dense_n`, `dense_cut`, `sparse_n`, `sparse_add`)

Drivers living within 30 km of the pickup, from the driver list (`dispatch.drivers_near`, one read).

| Change | l8 | Worst | Verdict |
|---|---|---|---|
| ≥ 40 drivers near: −0.1 | €93,776 | 93.9% | ✓ |
| **≥ 40 drivers near: −0.2** | **€94,887** | **94.1%** | ✓ best (+€4.9k), needs l8x/l8y check |
| ≥ 40 drivers near: −0.3 | €92,407 | 94.2% | ✗ |
| −0.2 dense, +0.2 when < 5 near | €95,508 | 92.6% | ~ +€0.6k, less safe |
| quote 1.3 + dense −0.2 | €91,373 | 92.7% | ✗ 280–385 orders/week (vs ~205), same margin |

## Research: price curve (`explore_lo/hi`, random price 1.0–2.0× list per request, 10 weeks)

Win rate by our price/list: 1.0 83% · 1.1 80% · 1.2 61% · 1.3 50% · 1.4 40% · 1.5 26% · 1.6 19% · 1.7 10%.
Monday is much lower (1.3×: 24% vs ~58% Tue–Fri). Profit per request is flat from 1.1× to 1.4×.

## What limits margin (findings)

- We quote ~910 requests/week and win ~23% (205 orders); the competitor takes the rest.
- We use only 100–150 of the 650–950 drivers a week (30–60 a day): **drivers are not scarce; the fee is the lever.**
- Driver fees are ~60% of revenue, booked at 0.9–1.0× typical. Short trips (< 100 km) earn €18–25/order; 400–599 km €47–84.
- Private-address orders: 11.4% late, €8/order (at q1.3) → candidate to decline.

## Experiment 18: direct offers to drivers near the delivery town (`offer_mult`) ✗

- **Idea:** they pay no trip home and the app never notifies them, so they should take the car cheaply. On each new gig, offer it to 3 of them (those who viewed our gigs in the last day first).
- **Result:** almost nobody takes it. ~4,500 offers per 10 weeks: ~3,500 expire unread (the driver isn't working), ~950 declined.

| offer fee | accepted | l8 | Verdict |
|---|---|---|---|
| 0.75 × opening fee (0.6× typical) | 18 | €90,652 | ✗ no effect |
| 1.1 × opening fee | 107 | €89,700 | ✗ |

Code kept, off by default.

## Experiment 19: fee cap (`raise_steps`) ✗ current is best

| raise_steps (cap) | l8 | Worst |
|---|---|---|
| 4 (1.1×) | €84,996 | 90.8% |
| 5 (1.2×) | €89,310 | 92.2% |
| **6 (1.3×, current)** | **€89,964** | 93.2% |
| 7 (1.4×) | €88,223 | 93.2% |

Booked step: 922 at the opening fee, 460 at the cap, the rest between (10 weeks).

## Experiment 20: private addresses (`private_add`)

| Change | l8 | On time | Worst |
|---|---|---|---|
| base | €89,964 | 95.8% | 93.2% |
| **+0.2 on private-address requests** | **€90,944** | 97.0% | **94.3%** ✓ |
| decline them (+9) | €86,080 | 97.2% | 95.2% ✗ |

## Experiment 21: combine (dense −0.2 at ≥ 40 drivers, private +0.2) and spend the safety

| On l8 + dense −0.2 + private +0.2 | l8 | Worst | l8x | Worst |
|---|---|---|---|---|
| (nothing else) | €95,102 | 95.7% | | |
| decline > 600 km | €99,178 | 93.0% | | |
| decline > 700 km | €100,357 | 93.9% | €103,280 | **88.9%** ✗ |
| decline > 600, quote 1.4 (`l8b`, see Exp. 22) | **€99,847** | **94.7%** | **€101,017** | **92.3%** ✓ |
| decline > 600, backlog 0.02 | €101,369 | 93.8% | €102,815 | **89.3%** ✗ |

## Experiment 22: final check on `l8y` → new `--preset l8`

| Preset | l8 | l8x | l8y | 30 weeks | Worst week |
|---|---|---|---|---|---|
| old `l8` (now `l8_v2`) | €89,964 | €95,598 | €111,705 | €297,267 | 91.0% |
| `l8b` (dense, private, q1.4, decline 600) | €99,847 | €101,017 | €111,010 | €311,874 | **89.9%** ✗ (l8y-a unranked) |
| **dense −0.2 + private +0.2 → new `l8`** | **€95,102** | **€99,994** | **€112,847** | **€307,943 (+3.6%)** | **92.6%** ✓ |

- **Lesson:** the two new rules add margin *and* safety; the extra relaxations (cheaper base price, longer trips) that looked good on 20 weeks failed on fresh weeks. `l8b` removed from the presets.

# Saturday late morning (base: new `--preset l8`, l8 €95,102 · l8x €99,994 · l8y €112,847)

## Experiment 23: fee level by how easy the car is (`dense_fee`, `slack_fee`) ✗

Scale the whole normal fee schedule for easy cars (many drivers near the pickup, or ≥ 24 h before the last pickup).

| Change | l8 | Worst |
|---|---|---|
| dense pickup fee × 0.9 | €91,929 | 94.8% |
| dense pickup fee × 0.8 | €82,965 | 93.6% |
| dense pickup fee × 1.1 | €93,472 | 94.9% |
| ≥ 24 h left: fee × 0.9 | €92,124 | 93.3% |
| all fees × 1.1 | €91,581 | 94.6% |

- **Lesson:** the fee schedule is at its optimum as one level for all cars; lower fees lose bookings, higher fees lose margin.

## Experiment 24: two-car gigs (`pair_fee`, `pair_km`, `pair_margin_h`) ~ not adopted

- **Idea:** a driver delivers car A and picks up car B near A's destination: one trip there and one home for two cars, so pay less than two fees. A new one-car order joins a waiting (unbooked) one-car gig when both can be delivered on time within 12 h of driving; the waiting gig is withdrawn and one two-car gig posted.
- Potential: ~900 pairable orders over 10 weeks; in practice ~35 pairs/week form (most gigs are booked before a partner arrives).

| Change | l8 | l8x | l8y | Worst |
|---|---|---|---|---|
| pair fee 1.0×, 30 km | €95,473 | | | 93.3% |
| 0.9×, 30 km | €92,401 | | | 93.4% |
| 0.8×, 30 km | €96,116 | | | 95.2% |
| 0.7×, 30 km | €87,400 | | | 92.2% |
| 0.8×, 100 km | €92,440 | | | 92.3% |
| **0.8×, 60 km** | €98,485 | €101,293 | €117,377 | **89.1%** ✗ (l8y) |
| 0.8×, 60 km, 4 h margin | €98,293 | €99,567 | | 92.8% |

- **Lesson:** +€3–4k per 10 weeks at best, about the noise; paired cars are late more often (6% vs 4%). Code kept, off.

## Experiment 25: win-rate steering (`adapt_target`, …) ~ not adopted

- **Why:** in 7 of 10 weeks we win only 1–10% of quotes on Monday (25–55% other days): the competitor starts the week cheap and raises its prices for dealers we rarely win. Some weeks also have one weak day (likely the price war).
- **Idea:** after each answer to a real quote, move the price: −0.01 × target per loss, +0.01 × (1 − target) per win (limits ±0.3), so we win `adapt_target` of our quotes.

| Change | l8 | l8x | Worst |
|---|---|---|---|
| target 30% | €89,893 | | 95.6% |
| target 40% | €92,085 | | 95.4% |
| target 25%, only lower | €98,073 | | 95.0% |
| **target 40%, only lower** | €98,517 | €100,773 | 91.7% |
| … limit −0.5 | €95,616 | | 93.7% |
| … step 0.02 | €96,930 | | 94.8% |

- **Lesson:** raising the price on winning streaks costs margin; only-lower gives +€4.2k over 20 weeks (+2%) but a lower worst week. Code kept, off.

## Experiment 26: price by our cost (`cost_k`) ✗

- **Idea:** quote_mult + cost_k × (typical fee / list − 0.9): the typical fee is 0.82× list on short trips but 0.95× on long ones.

| cost_k | l8 | Worst |
|---|---|---|
| 0 (current) | €95,102 | 95.7% |
| 1 | €94,544 | 93.5% |
| 2 | €79,460 | 91.7% |
| −1 | €67,457 | 95.1% |

- **Lesson:** a flat markup on the list price is best; the competitor's lane prices already follow how hard a lane is for drivers.

## Practice round "Saturday 09:00" (`--preset l8`, played by the user)

| Week | Us | House best | 1st (DaVinci's Night Shift) |
|---|---|---|---|
| 1 | €5,495 / 168 orders | €7,622 / 258 | €10,735 / 331 |
| 2 | €10,577 / 260 | €7,802 / 241 | €15,187 / 376 |
| 3 | €9,212 / 258 | €11,773 / 368 | €15,462 / 400 |
| 4 | €13,113 / 335 | €13,666 / 317 | €20,883 / 483 |
| 5 | €8,605 / 254 | €9,796 / 274 | €15,305 / 397 |
| **Total** | **€47,002**, 97.3% on time, rank 28 of 36 finished | €50,660 | €77,573, 97.2% |

- **Lesson:** the top teams win 1.4–2× more orders at the same margin per order and the same on-time share. We are too cautious (97% on time where 90% is needed).

## Experiment 27: dealer trust is the volume lever (analysis)

- One dealer (D01) sends ~1/3 of all requests (330–380/week), D02 ~120–160. Trust counts per dealer, and **a late order halves it**: D01 ends the week at only 15–25 because ~3–4 of its orders a week are late.
- **At the same price (1.35–1.55× list, Tue–Fri), our win rate rises with the dealer's trust:** 0–4: 36% · 5–9: 40% · 10–14: 46% · 15–19: 67% · 20–24: 77% · 25: 82%.
- Late orders (89 of 2,592 over 10 weeks): mostly no driver ever booked (`deadline_close` + `gig_expired`), then failed visits (notes) and drops; D01 has 36 of them.

| Try to use it (on l8) | l8 | Worst | Verdict |
|---|---|---|---|
| fee × 1.15 for dealers with trust ≥ 5 (`trust_fee`) | €89,922 | 95.5% | ✗ not more on time |
| fee × 1.3 for them | €79,577 | 93.2% | ✗ |
| slack ≥ 12 h for dealers with trust ≥ 10 (`trust_safe_n`, `trust_slack_h`) | €94,404 | 95.4% | ✗ |
| decline > 400 km for them (`trust_km`) | €90,303 | 94.0% | ✗ |
| −0.1 for dealers with ≥ 20 requests (`big_n`, `big_cut`) | €92,409 | 93.3% | ✗ the competitor also cuts for them |
| −0.2 for them | €87,430 | 94.0% | ✗ |
| quote 1.3 + opening fee 0.9 | €85,117 | 94.5% | ✗ volume without margin |
| quote 1.3 + opening fee 1.0, +0.05 steps | €77,777 | 93.5% | ✗ |

Also checked: gigs for a later day do not overpay (46% book at the opening fee); same-day gigs hit the cap 30% of the time.

## Experiment 28: expected-profit pricing with fitted models (`opt`) ~ promising, not safe yet

- **Win model** (`analysis/winmodel.py`, logistic regression on 19,450 random-price quotes): P(win) from price/list (−6.1 per 1.0×), dealer trust (+1.9 at 25 ≈ the rules' +25%), Monday (−1.4), drivers near the pickup, distance, dealer size. Held-out log loss 0.48 vs 0.70 for a constant; calibrated (pred 0.29 → real 0.29, 0.90 → 0.86).
- **Lateness model** (`analysis/latemodel.py`, 16,118 won orders): P(late) from slack (−0.73 per day), private address (+1.4), drivers near pickup/delivery, backlog (+0.29 per 10), distance. The riskiest 5% by the model are 22% late (average 5.9%).
- **Price** = per option, the price that maximises P(win) × (price × (1 − P(late) × 0.5) − fee − backlog cost − P(late) × lost trust).

| On l8 (flat rules off for price; slack ≥ 8 h and decline > 550 km kept) | l8 | l8x | Worst |
|---|---|---|---|
| current `l8` (flat 1.45×) | €95,102 | €99,994 | 92.6% |
| win model only, backlog cost 0.03 | **€103,493** | | **89.8%** ✗ |
| win model only, backlog cost 0.04 | €101,936 | €102,473 | 90.8% (too close) |
| win model only, fee 1.05 | €102,870 | €100,546 | **88.9%** ✗ |
| win model only, backlog cost 0.05 | €99,504 | €96,151 | **88.5%** ✗ |
| win + lateness model | €100,969 | | 91.9% |
| win + lateness model + trust loss 1.0 | €99,027 | | **88.7%** ✗ |

- **Lesson:** the models add margin (+€6–8k per 10 weeks) by pricing each request to its situation, but take more risk in overloaded weeks. Next: a stronger capacity term (e.g. backlog brake on top), check on l8x. Code kept, off (`opt=0`).

## Restart test (the final's recovery path) ✓

Played `l8-a` to Wednesday 12:00, threw the desk away, rebuilt it with `Desk.rejoin` from the snapshot and events, played on: **€11,739.88 vs €11,737.33 uninterrupted**, same orders and on-time share. `play_final` now also skips an event whose handling fails and rebuilds after any other error, instead of stopping.
