# Lessons: experiment log

**Summary.** Level 1: a fee ladder by reprice (open 0.7×, +0.3×/h) turns −€28,978 into +€34,186 per 10 weeks.
Level 8 (the final): pricing and fee rules (Exp. 3–21, 30) turn the starter's −€60,442/week into ~€10,700/week (`l8`); batch planning of two-car gigs (Exp. 37, `l8_plan`) adds ~45% more orders: €71,409 in the 5-week ranking round "Saturday 12:00", every week ≥ 94.9% on time.
What did not work: most price ideas after Exp. 30 (trust, weekdays, outage/price-war days, learning the market, expected-profit pricing); direct offers to drivers; posting two-car gigs as soon as cars are won (Exp. 24, pairs too rare).

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

## Experiment 29: making `opt` safer; trust as an investment ✗ (no clear gain)

- **Diagnosis** (`analysis/orders.py`, l8x, opt vs `l8`): `opt` won 79 two-leg trade-ins (private addresses), **43% late**; flat `l8` almost never wins them. Late orders also cluster in same-day options with 24–36 h slack at 1.3–1.5×.
- New `max_legs=1` (decline trade-ins) and `opt_trust_gain` (value of +1 trust per request we expect from that dealer later this week). Both off by default.

| opt + backlog cost 0.04 + … | l8 | l8x | Worst |
|---|---|---|---|
| `l8` (flat, for reference) | €95,102 | €99,994 | 92.6% |
| max_legs=1 | | €98,259 | **89.4%** ✗ |
| max_legs=1, late refund share 1.0 | **€98,156** | €99,248 | 91.4% |
| … + trust gain 0.0015 | €94,363 | | 93.6% |
| … + trust gain 0.005 | €83,338 (+15% orders) | | 92.6% |

- **Lesson:** a stronger lateness penalty makes `opt` safe (worst 91.4%), but it is only +€2.4k over 20 weeks vs `l8`: too thin to switch. Buying trust with lower prices loses money at every strength: the extra wins come at prices that don't pay.

## Experiment 30: price per delivery place (competitor's lane prices) ✓ adopted (+4.1%)

- **Why:** the top teams win ~400 orders/week vs our ~255 at the same margin per order. HANDBOOK: the competitor's price per lane is "higher where little work comes back and where few drivers live near the delivery place", and this part is "almost the same in every world".
- **Check** (`analysis/lanes.py`, 19,450 random-price quotes from the two explore runs): adding one indicator per delivery place to the win model improves log loss on *other worlds* (fit on seeds a–e, test on f–j) from 0.458 to 0.436. The pickup place adds nothing.
- **Offsets** (`lanes.json`, x list price): Vantaa −0.17, Helsinki −0.10, Hyvinkää −0.09, Espoo −0.05 … Joensuu +0.18, Ylivieska +0.18, Savonlinna +0.17, Kemi +0.16. New rule `dest_k`: price + dest_k × offset.

| `l8` + dest_k | l8 | l8x | l8y | Worst |
|---|---|---|---|---|
| 0 (previous `l8`, now `l8_v3`) | €95,102 | €99,994 | €112,847 | 92.6% |
| **1.0** | **€99,661** | **€104,324** | **€116,611** | **91.5%** (l8x-b, always our hardest week) |
| 1.5 | €95,749 | | | 95.6% |

- **Lesson:** +€12,653 over 30 weeks (+4.1%), on weeks the table was not fitted on as well (l8x, l8y). The fitted size (1.0) is the best. Adopted into `l8`.

## Experiment 31: learn the week's competitor price level ✗ (not safe enough)

- **Idea:** the competitor's level differs by week (26–54% above list) and moves during it. At each quote the win model (+ delivery-place offsets) predicts our win chance; each answer moves `market` by `market_lr × (won − expected)`, and our price by `market` (x list). New `pricing.win_chance`, `Desk.market`; off by default.
- **Trace** (`l8x-b`, step 0.003): Mon 24 wins vs 36 expected, Tue–Thu close, **Fri 47 vs 10**: the competitor gets much dearer by Friday (it raises prices for dealers we rarely win).

| `l8` + market_lr | l8 | l8x | l8y | Worst |
|---|---|---|---|---|
| 0 (`l8`) | €99,661 | €104,324 | €116,611 | 91.5% |
| 0.003 | €99,445 | | | 96.6% |
| 0.01 | €96,866 | | | 93.8% |
| 0.01, raise only | €95,809 | | | 96.5% |
| 0.01, lower only | €102,402 | €106,574 | €115,725 | **90.6%** (l8y-a) ✗ |
| 0.01, lower only, at most −0.1 | €99,316 | €103,315 | | 93.8% |

- **Lesson:** raising the price when we win more than expected loses (the extra wins were worth having). Lowering when we lose more gains +€4.1k over 30 weeks only when it may go down to −0.2×, and then a fresh week falls under 91%. Same pattern as before: cheaper prices win orders we then deliver late.

## Experiment 32: weekday prices ✗

- **Weekday in the win model** (random-price quotes, fit on seeds a–e, test on f–j): log loss on other worlds gets *worse* (0.436 → 0.454). The competitor's day factor is new in every world (HANDBOOK), so a weekday table would fit noise.
- **Monday only** (`monday_add`, off): −0.2× → €96,361 on l8 (vs €99,661); +0.2× → €98,884. Cheaper Mondays don't build enough trust to pay; dearer ones lose the few Monday wins. Monday price doesn't matter.

## Experiment 33: return-trip offers ✗

- **Idea** (HANDBOOK: an offer "reaches a driver who finishes one of your gigs far from home"): when a driver delivers our car, offer them directly our open gig that starts within `return_km` of there and ends nearer their home (`return_mult` × the app's current fee; `Desk.offer_return`). Off by default.

| On l8-a | Offers | Accepted | Declined | Expired (unread) | Margin |
|---|---|---|---|---|---|
| off (`l8`) | | | | | €13,272 |
| fee 1.0×, ≤ 60 km | 41 | **3** | 18 | 19 | €12,769 |
| fee 1.1×, ≤ 150 km | 104 | **1** | 52 | 48 | €13,140 |

- **Lesson:** drivers who have just delivered don't take a second gig from us: half don't read the offer, half say no, even above the app's fee. Same as Exp. 18: direct offers don't work in this world for us. Not benchmarked further.

## Experiment 34: outage pricing ✗

- **Data** (our `l8` weeks, quotes 08–18 by day and region within 80 km of a town): the outage is easy to see. `l8-a` Tuesday around Helsinki/Vantaa: we won 97 of 114 quotes (85%) vs 32% there on other days; `l8-d` Thursday around Helsinki/Espoo: 86 of 96 (90%) vs 36%. The backup costs ~30% more than the competitor, so we sell those cars ~0.3–0.5× list too cheap (≈ 100 orders/week). The price war shows too (`l8-c` Tuesday: 13% won vs ~45%).
- **Rule** (`outage_add`, off): today 08–18, if we won ≥ `outage_rate` (0.75) of ≥ `outage_n` (8) answered quotes with a pickup within `outage_km` (100 road km), add `outage_add` to the price. `Desk.outage_near`, unit-tested.

| `l8` + outage_add | l8 | Worst |
|---|---|---|
| 0 (`l8`) | €99,661 | 95.4% |
| 0.3 | €97,773 | 96.0% |
| 0.1 | €99,480 | 95.8% |

- **Trace** (`l8-a`, +0.3): the detector fires only on the real outage day (Tuesday, 41 quotes), but there we won 17 of 41 instead of ~85%: the backup is not much dearer than our usual price there (Helsinki region quotes are already low: dense −0.2, Vantaa −0.17). We also won fewer orders Wed–Fri: outage wins build trust with the big Helsinki dealers.
- **Lesson:** the outage is easy to detect but not worth a higher price; its wins are worth more as trust. Code kept, off.

## Experiment 35: price-war response ✗ (neutral)

- **Rule** (`war_cut`, off; `Desk.price_war`): Tue–Fri 08–18, when we won < 15% of ≥ 15 answered quotes today, quote `war_cut` cheaper for the rest of the day.
- **Result:** −0.2× → €99,840 on l8 (vs €99,661), worst week 95.4%. Most weeks never trigger it; `l8-c`, the clearest price-war week, got worse (€13,143 vs €13,608). In the war the competitor is at ~1.0–1.2× list: even −0.2× doesn't win those orders at a profit.
- **Lesson:** like the outage (Exp. 34), the event is easy to see but not worth reacting to with price.

## Experiment 36: where the money goes; opening fee recheck

- **Per week on `l8`** (10 weeks): revenue €26,883, driver fees −€16,288 (61%), failed visits −€265, late refunds −€261, other −€102 → margin €9,966. 275 orders, median order €31; 15 orders/week lose money (−€534); only 8/week late or undelivered (−€290 directly). So lateness is small money; revenue vs. driver fees is everything.
- **Opening fee on today's `l8`:** 0.75× €95,062, **0.8× €99,661 (kept)**, 0.85× €98,811.
- **The 15 money-losing orders a week** (−€534) have no pattern we can see at quote time. Of 152 in 10 weeks: 52 were late, 48 had a failed visit, and their fee was 1.3× typical (median; all orders 0.9×). They are spread over every distance, option and address type (short trips under 100 km: 5.8% lose money vs. 5.5% overall). They go wrong after we win them, so declining can't fix them.

## Experiment 37: batch planning of two-car gigs ✓ adopted (`--preset l8_plan`, +11% and +52% in ranking)

- **Why:** the top teams win ~450 orders/week at €40–43 each; we win ~275 at €36, and at a lower price our margin per order falls to €24. So their driver cost per car is far lower. In our weeks 85% of won cars could share a driver with another (car B's pickup ≤ 30 km from car A's delivery, on time, ≤ 12 h driving), but Exp. 24 formed only ~35 pairs/week: we posted every car at once and drivers booked it before a partner came.
- **Rule** (`plan_every_h` etc., `Desk.plan`): hold plain one-car orders with ≥ `hold_h` (8) hours to their latest pickup; every 3 h from 07:00 to 19:00 pair the held cars (round trips first, then the shortest link) into two-car gigs at `pair_fee` × both typical fees. An unpaired car waits for the next plan only with ≥ `wait_h` hours to spare, else it is posted alone. A pair no driver books within `split_after_min` (or whose car gets a deadline warning) is withdrawn and posted as two gigs (the withdraw goes alone first, so a pair a driver just booked is kept). Held orders don't count in the backlog brake.
- **Diagnosis** (`l8x-g`): pairs are booked within a median of 1 minute; held cars posted alone after waiting were late 19% (median 9 h to find a driver). Hence `wait_h`.

| `l8` + plan 3 h, link ≤ 30 km, … | l8 | l8x | Worst |
|---|---|---|---|
| none (`l8`) | €99,661 | €104,324 | 91.5% |
| pair fee 0.8 | €109,842 | | 91.4% |
| pair fee 0.9, margin 4 h | €110,847 | €110,817 | **86.0%** ✗ (3 weeks < 90% on l8x) |
| … split after 120 min | | €115,240 | 86.9% ✗ |
| … split after 60 min | | €114,024 | 89.6% ✗ |
| … split 120, wait_h 16 | | €119,898 | 89.9% ✗ |
| **… split 120, wait_h 24 (`l8_plan`)** | not run | **€116,121** | **93.2%** ✓ |

- **Ranking round "Saturday 12:00"** (5 fresh weeks, played by the user with `l8_plan`):

| Week | Margin | Orders | On time | Not delivered |
|---|---|---|---|---|
| 1 | €15,875 | 389 | 97.2% | 0.0% |
| 2 | €15,392 | 387 | 95.9% | 0.0% |
| 3 | €10,435 | 332 | 94.9% | 0.6% |
| 4 | €15,830 | 403 | 95.8% | 0.0% |
| 5 | €13,878 | 353 | 95.2% | 0.8% |
| **Total** | **€71,409** (Saturday 09:00 with `l8_v3`: €47,002) | 373/week (was ~255) | worst 94.9% | |

  Round leaders at the time: 1st €98,990, 10th €87,915, House best €77,560. The top 10 win ~430–470 orders/week at €40–43 each; we now win 373 at €38.
- **Lesson:** sharing drivers was the lever, not price. Planning lifts volume ~45% at the same margin per order, and on-time stays 95–97%, so there is now room to win more.
- **Open:** the `l8` and `l8y` benchmark weeks were never run with `l8_plan` (the 5 ranking weeks served as the fresh-week check). A lower `pair_fee` (pairs book in 1 minute) is untested.

## Experiment 38: guarded expected-profit pricing on lane-aware `l8` ✗ (holdout does not support adoption)

- **Bottleneck:** historical outcomes show that the model misses some delivery risk on longer jobs. Across the paired baseline and guarded `l8u-g` outcomes (429 won orders total), late share was elevated at 300–399 km (20.0%), 400–499 km (22.5%), and for `next_day` options (16.6%). Both `l8u-g` runs missed the 90% cutoff; the guarded candidate did not fix that failure.
- **Change:** experimental `l8_guarded` keeps the lane-aware `l8` quote as fallback, uses expected-profit prices only when fitted lateness is ≤8% and backlog is below 3, and caps each price change to ±6% of list. Existing distance and deadline filters remain active.

| Identical seeds | `l8` margin | `l8_guarded` margin | Difference | Ranked (`l8` / guarded) | Worst on time (`l8` / guarded) |
|---|---:|---:|---:|---:|---:|
| Tune `l8w-a..j` | €109,250 | €111,292 | +€2,042 | 10/10 / 10/10 | 92.62% / 93.49% |
| Fresh holdout `l8v-a..j` | €99,006 | €99,085 | +€79 | 10/10 / 10/10 | 91.79% / 92.76% |
| Fresh holdout `l8u-a..j` | €91,695 | €87,952 | −€3,744 | 9/10 / 9/10 | 88.84% / 89.25% |
| Both fresh holdouts, 20 weeks | €190,701 | €187,037 | **−€3,664** | 19/20 / 19/20 | 88.84% / 89.25% |

- **Decision:** keep lane-aware `l8` as the production preset; do not promote `l8_guarded`. The tune-set gain did not repeat on fresh holdouts, and the candidate lost margin there while neither strategy met the 90% requirement in one `l8u` week. `l8_guarded` remains available for further experiments only. The risk slices above are diagnostic signals from two paired outcomes, not a calibrated causal estimate.

## Test final Sat 14:00 (live clock, Thursday to Wednesday, `l8_plan`)

| | Orders | Margin | On time | Rank |
|---|---|---|---|---|
| bahn67 | 68 | €1,365 | 94.1% (82.4% after Thursday) | 32 of 55 ranked |
| 1st (akanegakirru) / 10th | 158 / 153 | €4,023 / €3,292 | 98.7% | |

- **Speed is fine:** the reveal shows every request got our quote in time (0 `unquoted`).
- **Cheap week:** the world played Monday to Wednesday without us, so every dealer's trust started at 0, and the competitor was cheap. Win rate by our price: 1.0–1.3× 48%, 1.3–1.45× 18%, 1.45–1.6× 1%, above 0%. Teams that price lower won 2.3× our orders. A fixed 1.45× has no answer to a cheap week.
- **Bug, fixed:** a dealer changed one car of a two-car gig (`order_changed`). `Desk.withdraw` withdrew the shared gig but reposted only the changed car; the other car (R00656) never got a driver and was not delivered. Now the other car is posted again alone (`PairChange` test).
- **Bad luck, not bugs:** R00655 found no driver in 6 h at steep fees; R00679 needed plates the request didn't mention (`no_plates`, retried with plates, late).

## Experiment 39: cheaper prices with planning (after the 14:00 test final)

The 14:00 test final showed a cheap week: at ≥ 1.45× list we won 1% of quotes. Planning leaves on-time room (worst ranking week 94.9%), so cheaper prices were retested on `l8_plan` (with the pair fix).

| `l8_plan` + | l8 | l8x | Worst |
|---|---|---|---|
| none (baseline with fix) | €109,576 | €116,587 | 93.2% |
| learn the week's level, lower only (`market_lr=0.01 market_hi=0`) | €115,459 (+5.4%) | €115,249 (−1.1%) | 92.2% |
| **`quote_mult=1.40`** | **€112,634** (+2.8%) | **€117,077** (+0.4%) | 92.2% |

- **Result:** 1.40 rises on both sets (+€3.5k over 20 weeks), more orders on both; learning the level is +€4.5k over 20 weeks but loses on `l8x`. Neither checked on `l8y` yet.

## Experiment 40: why half the cars still go alone; longer pair links

- **Measured** (`l8_plan`, 10 weeks, ~300 cars/week): 49% of cars travel in pairs at 0.76× their typical fee (€41.60/car); the rest go alone at 1.06× (€68.06/car). Alone because: held but no partner found 72 cars/week (extra cost vs a pair €1,181/week); in a pair no driver booked within 2 h, then split 33 (€774); private address 16 (€397); charging stop 13 (€181); other 20 (~€420).

| `l8_plan` + | l8 | l8x | Worst |
|---|---|---|---|
| none | €109,576 | €116,587 | 93.2% |
| `pair_km=50` | €112,169 (+2.4%) | €116,375 (−0.2%) | 93.0% |
| `pair_km=80` | €111,094 | | 93.9% |

- **Result:** links up to 50 km help on `l8`, flat on `l8x`: not adopted alone. Next: pair a newly won car with a posted, unbooked lone car; let an unbooked pair's fee rise instead of splitting it.

## Experiment 41: price 1.40 + pair links 50 km together ✓ adopted (`--preset l8_plan2`)

| `l8_plan` + | l8 | l8x | l8y | 20 weeks (l8 + l8x) | Worst |
|---|---|---|---|---|---|
| none | €109,576 | €116,587 | not run | €226,163 | 93.2% |
| `quote_mult=1.40` | €112,634 | €117,077 | | +€3,548 | 92.2% |
| `pair_km=50` | €112,169 | €116,375 | | +€2,381 | 93.0% |
| **both (`l8_plan2`)** | €112,459 | **€119,506** | **€138,040** | **+€5,802 (+2.6%)** | **91.9%** (l8y-a), 30/30 ranked |

- **Why together:** a cheaper price wins more cars, and longer links find more partners among them. Best on `l8x` and passes `l8y` (worst 91.9%).

## Ranking round "Saturday 15:00" (`l8_plan2`, played as team "slow")

| Run | Margin | Orders | On time | Cars in pairs | Fees ÷ revenue |
|---|---|---|---|---|---|
| 1 | €13,980 | 373 | 93.8% | 48% | 60% |
| 2 | €14,757 | 394 | 97.0% | 51% | 60% |
| 3 | €9,302 | 311 | 95.5% | 41% | 66% |
| 4 | €11,198 | 356 | 94.1% | 43% | 62% |
| 5 | €16,452 | 398 | 96.2% | 50% | 55% |
| **Total** | **€65,689**, rank 30 of 36 at the time | 366/week | worst 93.8% | 47% | 60% |

- **Gap:** 10th (razors) €82,653: 415 orders/week at €40 each; 1st (source-exp) €92,830: 425 at €44; us 366 at €36. We win 36% of quotes.
- **Driver cost:** a paired car costs 0.76× its typical fee, a car alone 1.10×. The worst week had the fewest pairs.
- **Other costs €1,131/week:** late refunds €613 (17 cars), failed visits €415 (12; 53% `not_ready`, 26% `no_plates`), release fees, undelivered, waiting €102.
- **Server restart:** run 2 stopped on HTTP 502. `main.py --world ID` now rebuilds a stopped world with `Desk.rejoin` and plays on (run 2 finished ranked, €14,757); the practice loop and `evaluate.py` now wait and rebuild by themselves after a restart or timeout.

## Experiment 42: chain dispatcher (`chain_max`) ✓ candidate (`--preset l8_chain`, `l8` weeks only so far)

- **Why:** half our cars still went alone at ~1.06–1.10× their typical fee, against 0.76× in a pair (Exp. 40). Pairs were formed only among cars held at the same plan time.
- **Rule** (`Desk.plan_chains`, `build_chains`, `chain_fits`): at each plan, the pool is the held cars **plus posted one-car gigs no driver has booked**. Greedy chaining joins the two chains with the best link (round trip home first, then the shortest empty drive) while one driver can still do the whole chain on time (each car `pair_margin_h` before its deadline, pickup slots kept, ≤ 12 h). A posted car joins only after its gig is confirmed withdrawn. `chain_max` cars per gig; fee `pair_fee` × their typical fees.
- **Measure:** `analysis/sharing.py --note "..."` (cars shared vs. alone and their fee ÷ typical fee).

| `l8_plan2` + | l8 | Cars shared | Worst |
|---|---|---|---|
| none (pairs, plan every 3 h) | €112,459 | ~49% | 92.0% |
| `chain_max=3` | €116,151 (+3.3%) | 55% | 94.0% |
| **`chain_max=3 plan_every_h=1`** | **€119,036 (+5.8%)** | 58% | 93.5% |
| … same, after `chain_fits` also keeps pickup slots (= `l8_chain`) | **€119,744 (+6.5%)** | | **94.1%** |
| … + `wait_h=12` | €119,212 | 58% | 93.9% |
| … + `chain_replan=1` (re-plan unbooked chains instead of splitting) | €115,868 | 63% | 93.4% ✗ |

- **Still alone with chains** (per week): no partner within 50 km and the deadlines 65 cars (€950 extra vs. shared), chain split after 2 h 29 (€599), private address 19 (€463), charging, retries, trade-ins 26 (~€620).
- **Lesson:** wider pools and hourly plans help (+€7.3k on `l8`); re-planning unbooked chains shares more cars but churns gigs and loses money. Private addresses in chains (`chain_private=1`) not tested yet.
- **Next:** `l8_chain` on `l8x` and `l8y`.

## Experiment 43: maximum-cardinality batch matching (`pair_match`, from the codex branch)

- **Opportunity:** `l8_plan` raised volume from about 255 to 373 orders/week, while the top teams win roughly 430–470. Historical analysis says 85% of our won cars could share a driver. `Desk.plan()` currently greedily takes round trips and then short links; a preferred edge can consume a car that would otherwise enable two feasible pairs.
- **Change:** experimental `l8_plan_match` builds the same directed route/deadline-feasible options as before, represents each order as one graph vertex, and uses Edmonds blossom maximum-cardinality matching to select the largest disjoint pair set. For each selected pair it keeps the best existing orientation (round trip first, then shortest link); `l8_plan` remains on its original greedy code path.
- **Offline validation:** the unit suite passes, including greedy-trap, odd-cycle, and preset-isolation checks. An exhaustive local comparison against brute force matched the optimum for all 33,867 undirected graphs with up to six vertices.
- **Partial baseline:** an approved `l8_plan` run on fresh seeds `l8fresh14-a` through `j` recorded only three completed weeks before team practice capacity filled. Those three made €35,312.53 total (€11,770.84/week), with 95.76% weighted on-time, 93.77% worst week, and 3/3 ranked. This is too small to support a strategy decision; the seven missing weeks have no score.
- **Harness fix:** `evaluate.py` now retries HTTP 409 practice-slot conflicts every ten seconds for up to five minutes, so temporary team-wide capacity pressure does not discard later seeds. Unit tests cover retry, non-capacity errors, and timeout behavior.
- **Candidate slot attempt:** the one-seed `l8_plan_match` pilot on `l8fresh14-a` waited 327 seconds and timed out while all eight team slots remained occupied. It created no candidate world and has no score.
- **Benchmark (Sat 17:10, `l8` weeks):** `l8_plan_match` €113,062 vs `l8_plan` €109,576 (+3.2%), worst 94.9%, 10/10 ranked. Below `l8_chain` (€119,744).
- **Merged into `otso/level1-baseline`:** the matching is `Desk.match_pairs`; `pair_match=1` uses it for pairs of held cars, and new `chain_match=1` starts `build_chains` from the matched pairs, then grows them into chains (not benchmarked yet). The slot wait in `evaluate.py` is kept.
- **`l8_chain` + `chain_match=1`** (Sat, `l8` weeks): €114,201 vs `l8_chain` €119,744 (**−€5.5k, −4.6%**), worst 93.5%. Locking in matched pairs first blocks better 3-car chains.
- **Decision:** keep the matching as an option (off); `l8_chain` stays the candidate.

## Experiment 44: learn the competitor's level per week and per day (`market.py`, `market_k`)

- **Idea:** the competitor's price = list × lane × **day factor** × **week level** (1.26–1.54 at level 8) × noise (HANDBOOK). We quote a fixed 1.40. In the 14:00 test final it was cheap and we won 1% of quotes at ≥ 1.45×.
- **Offline check** (`analysis/competitor.py`, 225 cached weeks, no worlds): one logistic win curve with a level per day; slope 8.1 per 1.0× list (pooled over weeks it looks flatter, 6.1).
  - The level is fixed by the seed: two random-price runs of the same week agree (correlation 0.97).
  - **Days differ more than weeks:** weeks ±0.077× list, days ±0.12–0.26×. **Monday is cheap every week (−0.21×)**: Exp. 31's learner read that as a cheap week.
  - Predicting each answer (log loss, lower = better): one level 0.552 · + usual weekday 0.525 · **+ learned week and day 0.439**.
- **Rule** (`market.py`): MAP estimate of the week's and today's move from all answers so far (Gaussian priors from the fit, Newton steps, 0.28 s per simulated week); price += `market_k` × move, within `market_lo`..`market_hi` (±0.1). Replaces Exp. 31's `market_lr`.

| `l8_chain` + | l8 | worst |
|---|---|---|
| — | €119,744 | 94.1% |
| `market_k=0.5` | €117,846 (−€1.9k) | 94.2% |

- **By day** (vs a cached `l8_chain`-like run): the same wins in total (3,319 vs 3,340). On Thursday a higher price lost 76 orders (−€5.6k). As in Exp. 31, raising the price on dear days loses: we have the capacity then, and each extra order also builds trust. Next: lower only (`market_k=1 market_hi=0`).
| `market_k=1 market_hi=0` (lower only) | €118,858 (−€0.9k) | 93.9% |

- **Decision:** within noise (weeks swing ±€1.5k); `market_k` stays off. The estimate is good, but following it does not change margin on these weeks.

## Test final Sat 20:00 (live, full week, `l8_chain`)

- **€12,963, 334 orders, 97.6% on time, rank 41/75** (1st Juhus €19,592 / 469 orders; 10th €16,623 / 393). We earn €38.8/order, the top 10 €41–49.
- **Where the 1,030 requests went:** won 340, lost on price 558, declined > 550 km 105, declined < 8 h slack 27.
- `l8_chain` validated meanwhile: **l8x €132,510 (+€13.0k vs `l8_plan2`), l8y €142,551 (+€4.5k)**, worst week 90.3% (l8y-a). 30 weeks: €394,805 vs €370,005 (+6.7%).

## Experiment 45: volume and cost with chains (`l8_chain` + …, `l8` weeks)

| Change | l8 | worst | Note |
|---|---|---|---|
| — (`l8_chain`) | €119,744 | 94.1% | |
| `quote_mult=1.35` | €115,551 (−€4.2k) | 92.2% | cheaper price still loses |
| `decline_km=700` | €117,888 (−€1.9k) | 92.4% | long trips still lose |
| `chain_max=4` | €117,157 (−€2.6k) | 94.4% | |
| `pair_fee=0.75` | €111,825 (−€7.9k) | 93.3% | 2,789 orders: slower bookings → backlog brake → fewer wins |
| `fit_cut=0.1` | €115,725 (−€4.0k) | 92.9% | 3,557 orders (+260) at a lower price |
| `backlog_h=8` | €116,610 (−€3.1k) | 92.4% | **3,946 orders (+20%)**, margin/order €29.3 vs €35.6 |
| `chain_private=1` (private addresses in chains) | €116,984 (−€2.8k) | 93.7% | |
| `chain_charging=1` (charging cars in chains, +40 min in the timing) | €119,472 (−€0.3k) | 93.8% | |
| … same on `l8x` | €125,983 (−€6.5k vs €132,510) | 91.5% | ✗ |
| `split_after_min=240` (keep unbooked chains together longer) | €115,759 (−€4.0k) | 93.4% | |

- **Drivers grab shared gigs at once** (cached chain weeks): 1-car gigs booked after a median 34 min (47% at the opening fee), 2-car gigs 3 min (70%), 3-car gigs 1 min (86%). We pay too much for shared gigs → test a lower `pair_fee`.
- **Chain-aware pricing** (`fit_cut`, `Desk.chain_partners`): a request that one driver could carry before or after a held or posted unbooked car is quoted `fit_cut` lower (it will likely share a driver at ~0.76× fee).


- **Why cars still go alone with chains** (140 of 336 cars/week, €68 vs €42 shared): held > 24 h without partner 36, chain split or withdrawn 30, electric car with a charging stop 26 (excluded from chains), posted alone with < 24 h left 24, private address 18.5 (excluded), trade-in 4.
- **The backlog brake holds back volume, and that is right:** with `backlog_h=8` (count only driverless cars due for pickup within 8 h) we win 20% more orders, but the won price falls (1.357× vs 1.421×) and the fee per order rises (€56.3 vs €53.1; lone cars 1.11× typical vs 1.06×). Drivers are scarce at level 8: more volume makes every car dearer. **Only cheaper delivery (more sharing) can raise both volume and margin.**
- **Noise:** re-running `l8_chain` on the current code gives exactly €119,744.01 (practice weeks are deterministic, and the new options are off by default). But any change sends drivers down a different path, so differences below ~€3k (2.5%) on 10 weeks are not real effects.

## Experiment 46: offer the next car when a driver books (`next_offer_mult`, `Desk.offer_next`) ✗

- **Idea** (HANDBOOK: a second gig costs a driver who has one of ours only the extra time, but the app never tells them of it): on `gig_booked`, offer that driver our unbooked one-car gig that starts nearest to where their gig ends and still fits after it, at its current fee. Unlike Exp. 18/33 the driver is working today and has just used the app.
- **Result:** €118,586 on `l8` (−€1.2k, noise), worst 93.9%. In 3 weeks: 84 offers, 58 expired unread, 25 declined, **1 accepted**. Direct offers do not work in this world for us (third try); code kept, off.

## Experiment 47: fees for the cheapest likely driver (`home_fee`, `home_n`, `chain_home`)

- **Who books our one-car gigs** (cached chain weeks, 1,559 bookings): drivers living near the **delivery** make 6% of the views but **25% of the bookings**, at a median 0.80× typical (61% at our opening fee, median 16 min); drivers near the pickup make 45% of views, 35% of bookings at 1.00×. HANDBOOK: their trip home is free.
- **Where the gig ends decides it:** gigs ending where 60+ drivers live within 30 km are booked by a driver living there 82% of the time (chains: 70%, 88% at the opening fee); where 0–9 live, 4%.
- **Rule:** a gig whose last delivery has ≥ `home_n` drivers living within 30 km gets `home_fee` × its fee (`Desk.home_factor`); `chain_home=1` makes `build_chains` prefer chains ending there, like round trips.

| `l8_chain` + | l8 | worst | orders |
|---|---|---|---|
| — | €119,744 | 94.1% | 3,296 |
| `home_fee=0.85` | €117,028 (−€2.7k) | 93.3% | 3,118 |
| `home_fee=0.75` | €114,485 (−€5.3k) | 91.7% | 2,982 |

- **Why it loses:** the fee per car falls (shared €40 vs €42), but bookings come a little later, so more won cars have no driver at any moment and the **backlog brake** (+0.03× per driverless car) raises every quote: 5–10% fewer orders. Same as `pair_fee=0.75`. The brake couples every fee saving to a volume loss → next: a brake that counts only cars at real risk (`backlog_h`) with a higher base price.
- **Night posting:** 11 gigs/week posted 21:00–07:00 book at a median 1.62× their opening fee (no driver reads notifications 23–07, but our ladder keeps raising): ~€200/week to save by starting their ladder at 07:00.
- **Decoupled brake** (`backlog_h=8 quote_mult=1.46`, brake counts only cars due within 8 h, base price where the old brake sat on average): l8 €119,022 (3,533 orders, +7%), worst 92.7%; + `home_fee=0.85`: €118,679 (3,322 orders), 92.5%. Both ≈ `l8_chain` (€119,744): more orders at a lower margin each. ✗

## Experiment 48: no fee raises at night (`night_hold`) ✗

- **Idea:** drivers read nothing 23:00–07:00, so raise steps count only reading minutes (`reading_minutes_after`).
- **Result:** l8 €118,276 (−€1.5k), l8x €128,971 (−€3.5k) and **one week at 89.0%** (unranked). A car posted in the evening opens the morning at its first fee, so its driver comes later. Off.
- **Measured on the way** (cached `l8_chain` weeks): gigs posted 24–48 h ahead book at the opening fee within ~12 min (median fee 0.80× typical), so posting early is not a leak; all raises together cost ~€2.5k/week. Only 2.3 bookings/week come from drivers who just delivered nearby: holding cars for planning does not hide them from passing drivers. Driver geography barely moves the fee (lone cars 0.80–1.04× typical in every pickup × delivery density cell); it moves win rate (12–49%) and lateness.

## Experiment 49: a real note reader (`notes.py`, `note_reader=1`, preset `l8_notes`) ✓

- **Why:** the reader was still the starter's keyword matcher. It read only clock times, put every time on the day the window starts, treated a note that mentions the delivery as delivery-only, and ignored plates, manual gearboxes, day words ("huomenna", "to.", "Fri"), corrections ("eikun 11.30", "korjaus: klo 10", "not 3pm") and the world's typos ("huomeenna", "desitnation", "maunal"). The rules say the world acts on the note anyway. In `l8_chain` weeks the notes had warned us about 7.7 of the 8.7 failed visits a week (3.8 not ready, 3.3 no plates, 0.6 licence).
- **How:** every word one typo from a keyword becomes the keyword. Then each sentence is read on its own: what it is about (ready / arrive by / the delivery site's hours / the pickup site's hours) and its last day and time that it does not deny; a correction sentence keeps the other half (day or time). Days count from the arrival day; a weekday is 2–6 days ahead; hours in words are 9–17. Revealed truth (`reveal.orders[].legs[]`: `readyAt`, `releasedAt`, `noteDeadline`, `pickupHours`, `deliveryHours`, `needsPlates`, `manualGearbox`) scored it on all 5,790 noted won cars of the cached weeks: ready time, deadline, closing time all right; pickup hours 5,305/5,307; plates 3 and manual 2 false alarms. The old reader: 311 ready times too early, 123 deadlines too late, 314 too early, all 252 plates/manual cars missed.
- **Use:** pickup window from the ready time; delivery window to the earlier of the option's and the note's deadline and the site's closing time that day (a car left at a closed site counts when it next opens: late); plates stop and manual licence on the first post (also in chains); the pickup window = the first weekday interval of the site's real hours that a driver can still reach (a driver plans by the stated hours, so a multi-day window would let them come after the real closing). Quotes: the slack check uses the note's deadline and a later ready time.

| `l8_chain` + | l8 | l8x | 20 weeks | Worst |
|---|---|---|---|---|
| — | €119,744 | €132,510 | €252,254 | 94.1% |
| `note_reader=1` without pickup hours | €121,715 | €131,947 | +€1.4k | 92.8% |
| **`note_reader=1`** | **€125,674** | **€134,376** | **+€7.8k (+3.1%)** | 92.8% |

- **l8y (untuned weeks): €152,963 vs €142,551 (+€10.4k, +7.3%), worst 92.6% (was 90.3%).** 30 weeks: **€413,013 vs €394,805 (+€18.2k, +4.6%)**, 30/30 ranked, worst 92.6% → `l8_notes` replaces `l8_chain`.

- **Per l8 week:** failed visits 8.7 → 0.3 (not ready, plates and licence → 0; closed 1.0 → 0.3), failed-visit fees €276 → €11, late orders 14.3 → 11.3, undelivered €183 → €114, on time 95.9% → 96.6%. Without pickup hours, closed-site failures rose to 4.3/week: the retry two hours later came after closing again.
- **Left:** late orders now: booked in time but late 3.3/week, drops 2.9, order changes 2.6 (a far new destination with the same deadline, or a missed private slot moved to another day), booked only after the deadline warning 1.9.

## Experiment 50: cheaper price with the note reader (`l8_notes` + `quote_mult=1.37`) ✗

- **Idea:** fewer late cars leave on-time room; spend it on volume.
- **Result:** l8 €125,034 vs €125,674 (3,474 vs 3,369 orders), worst 95.2%. More orders, same money: still no.

## Experiment 51: explicit windows on every chain stop ✗ (no effect)

- **Idea:** the world stretches a stop without its own window to the end of the world once no driver can make it, so a driver could book a chain that is already late (traced: a 3-car chain booked Wednesday, picked up Friday, due Thursday). Give every chain stop its order's window.
- **Result:** l8 €125,804.35 with and without, to the cent: an explicit window equal to the order's changes nothing. Code removed.
- **Also (Exp. 49c, now part of `note_reader`):** holds and our own deadline warning use the note's deadline and the delivery site's closing time (`Desk.last_pickup`; the world's `lastPickupAt` and `deadline_close` know only the option's deadline): l8 €125,804 (vs €125,674), worst 95.0%.
- **Snow** (measured, not acted on): `forecast` comes exactly 24 h ahead, 1–2 snow days a week in 2–6 towns. Orders touched by snow (28/week) are late 9.8% vs 3.3%: ~1.8 extra late orders/week. Summer tyres (the note fact that snow blocks): ~1 car/week.


## Experiment 52: code review fixes (Sat 22:00) ✓ kept (neutral)

- **Quote slack with a late ready day:** a car ready N days after the stated pickup day moves the won order's deadline by N days (RULES; seen in 91 of 91 such cars). `pricing.slack` subtracted the wait but not the moved deadline, so it declined some options it could have offered. Fixed: l8 €125,036 (−€768), l8x €135,759 (+€167), l8y €149,830 (+€1,509); 30 weeks €410,625 vs €409,717 (+€908), worst 93.8%: noise, kept because it matches the rules. These are now the `l8_notes` reference numbers.
- **Final loop:** an error in `desk.tick()` (planning, our own deadline warnings) was not caught like an error in an event, so it dropped that step's actions and rebuilt the desk. Now `main.guarded` logs and skips either; a lost connection still goes to the rebuild loop.
- **Note reader:** 200,000 random notes (word salad from the vocabulary, random characters, empty / missing notes): no exception, 0.04 ms a note.
- **Left as is:** `repost()` after `gig_expired` drops every window of the gig, also a pickup site's real hours (failed visits are 0.3 a week, so ≤ €11/week at stake).

## Where the driver money goes (Sat 23:00, `l8_notes`, 10 l8 weeks)

Per week: revenue €31,590, driver fees €18,464 (58%), late refunds + undelivered €565, other €58. Gap to the 10th team in round "Saturday 21:00": −€2.8k/week, behind in all 5 weeks.

| Car went | Cars/week | Fee/car | x typical | Share of fees |
|---|---|---|---|---|
| alone | 141 | €70.8 | 1.07 | 54% |
| … alone, booked after > 60 min | 57 | €80.1 | 1.20 | 25% |
| … alone, booked after the deadline warning | 13 | €107.7 | 1.76 | 7% |
| chain of 2 | 116 | €49.2 | 0.79 | 31% |
| chain of 3 | 80 | €34.6 | 0.77 | 15% |

Lone cars are the lever: each one moved into a chain saves ~€20–35. Also: 25% of gigs are booked within 1 minute of posting, median 23 min, p90 6.5 h. `driver_late` comes 0.3 times a week (not worth acting on).

## Experiment 53: trade-ins at their own price (`tradein_mult`) ✗

- **Why:** a trade-in (2% of requests, 21/week) is one driver's round trip from the dealer to a private customer and back, priced as two cars: list €111, typical fee only 0.53x list (one-car 0.95x). We quote them 1.6–2.1x (private surcharge) and win 38/210; margin €68 per trade-in vs ~€39 per car. 34/38 on time; the 4 late ones were days late (missed 1-hour slot).
- **Result:** 1.25x: l8 €127,440 (+€2.4k), l8x €132,312 (−€3.4k), worst 92.6%. 1.15x: l8 €124,405 (−€0.6k). More trade-ins = more days-late ones. Off.

## Experiment 54: longer links in chains (`pair_km` 50 → 80 / 120) ✗

- **Result:** 80 km: l8 €127,508 (+€2.5k), l8x €135,002 (−€0.8k), worst 92.5%; lone cars 141 → 128/week, 3-car chains 80 → 116 cars, but the total fee per car barely moved. 120 km: l8 €126,595 (+€1.6k). Noise. Off.

## Experiment 55: charging stop only on routes over 200 km (`charge_km=200`) ✓

- **Starter bug:** `stops_for` added a charging stop (40 min) to every electric car under 30%, but RULES require one only on a route over 200 km. 11 of the 15.6 such cars a week drive ≤ 200 km: they paid the driver for the stop and were kept out of chains.
- **Result:** l8 €128,446 (+€3.4k), l8x €137,900 (+€2.1k), l8y €150,673 (+€0.8k): **€417,019 over 30 weeks (+€6.4k, +1.6%), worst 92.9%**, 30/30 ranked → preset `l8_charge`. One fine in 10 weeks: a booked car whose destination the dealer changed from 163 to 507 km (a booked gig can't get a stop added; releasing costs more).

## Experiment 56: private-address cars in chains, with the charging fix (`chain_private=1`) ✗

- **Result:** l8 €126,276 vs €128,446 (−€2.2k), worst 94.0%. A private slot is too narrow for a chain. Off.

## Why cars still go alone with `l8_charge` (one week, l8-a, every one-car post traced to its code path)

Split chain (no booking within 2 h) 79, held without a partner until 24 h before the last pickup 75, private address at win 14, < 8 h to the last pickup at win 10, trade-in 6, order change 6, other 6. Split cars can be chained again later. Chains are booked 88% at 0–2 h of driving, 75–81% at 2–10 h, 47% at 10–12 h (19 gigs in 10 weeks); chains posted at 07:00 only 45% (5/week).

## Experiment 57: slower raises for cars with time (`slow_every_min`, `slow_after_h=12`) ✗ / chain margin 2 h ✗

- **Idea:** a car with ≥ 12 h to its last pickup needs no 0.8 → 1.3x climb in 2.5 h; raise every 60/90 min instead.
- **Result:** 60 min: l8 €130,703 (+€2.3k), l8x €132,506 (−€5.4k); 90 min: l8 €126,779 (−€1.7k). Off.
- `pair_margin_h=2` (with `charge_km=200`): l8 €128,316 (−€0.1k). Off.

## Experiment 58: cheaper 3-car chains (`chain_fee_step=0.1`: 0.8x instead of 0.9x) ✗

- **Why:** 62 of 80 cars a week in 3-car chains are booked within 5 minutes at 0.73x typical.
- **Result:** l8 €131,841 (+€3.4k), l8x €133,947 (−€4.0k, worst 91.9%), l8y €151,381 (+€0.7k): +€0.15k over 30 weeks. Noise. Off.
- **Fee per car by the option the dealer chose** (`l8_charge`): same_day 183 cars/week at 0.90x typical, next_day 147 at 0.92x, within_3_days 13 at 0.87x. Later options are not cheaper to move per typical fee.

## Experiment 59: cheaper later options again (`later_mult=0.9`, with chains) ✗

- **Idea:** with chains a later deadline should be cheaper to move, so steer dealers to it (Exp. 14 predates planning).
- **Result:** l8 €121,106 (−€7.3k). Later options are not cheaper per typical fee (table in Exp. 58). Off.

## Experiment 60: a cancellation reposts the other cars of its withdrawn gig (bug fix, always on)

- **Bug:** RULES: when the dealer cancels an order whose gig was still open, the world withdraws the gig: "Post its other cars again." `handle` only forgot the cancelled order, so the other cars of a chain kept a dead gig and were never delivered (undelivered = full refund + penalty + halved trust). 0.1 times a week (3 cancellations a week: shortened 1.5, continues 0.5, released 0.5, withdrawn 0.1). Now `Desk.cancel` posts them again.
- **Result** (`l8_charge`): l8 €128,702 (+€0.3k), l8x €139,629 (+€1.7k), l8y €150,912 (+€0.2k): **€419,243 over 30 weeks (+€2.2k), worst 92.9%**. These are now the `l8_charge` reference numbers.

## Experiment 61: fees on the lane's mean typical fee (`fee_lane=1`, `fees.json`) ✓

- **Rule gap:** HANDBOOK: the world builds the typical fee from the work's cost to a typical driver of the pickup town, scales it by one factor and **adds a noise for each request**. Measured on 120k cached requests: within a lane (pickup, delivery, private, premium) the log typical fee varies by ~11%; lane, pickup hour, battery, deadline, note explain only 8.6% of that, and the level moves 0.2% between worlds. Drivers book by their own cost, so every fee we built on the noisy number overpaid where the noise came out high (25% of gigs are booked within a minute at the opening fee).
- **How:** `analysis/typical.py` writes `fees.json` (2,036 lanes, 36,134 distinct requests, mean log fee + count). `pricing.typical_fee` averages the request's own fee in log with its lane's n requests: exp((n·mean + log fee)/(n+1)). `fees_for` uses it for every gig (alone, chains, steep).
- **Result** (on `l8_charge`): l8 €132,001 (+€3.3k), l8x €140,942 (+€1.3k), l8y €155,720 (+€4.8k): **€428,663 over 30 weeks (+€9.4k, +2.2%), worst 93.7% (was 92.9%)**, 30/30 ranked → preset `l8_lane`. Moving the code into `pricing.py` reproduces l8-a to the cent (€16,314.00). The test weeks' own requests are in the table (their own noise counts twice), so the final should gain a little more.

## Experiment 62: an announced car never leads a chain (`chain_fresh_head=1`) ✗

- **Rule:** the app notifies drivers near a gig's first pickup, and of each order only once. Chains led by a car we posted before were booked 57.6% (fresh head 83.6%; all cars posted before 36.1%).
- **Result:** l8 €127,024 (−€1.7k). The low booking is mostly selection (cars nobody wanted alone); chaining them anyway is still better. Off.
