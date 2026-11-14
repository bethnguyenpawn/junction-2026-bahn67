# Progress

Status, what we learned, and what's next. Every experiment with its numbers: [LESSONS.md](LESSONS.md) · Challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## Status (Sun 15 Nov, 00:10)

**Use `--preset l8_early`** (`l8_lane` + a lower opening fee for cars ready 12 h or more later, Exp. 64) for ranking runs and the final. Fallback: `l8_lane`.

| Level 8 | Test weeks | Per week | Worst week |
|---|---|---|---|
| Official starter | 10 weeks: −€604,425 | −€60,442 | 39.3% (never ranked) |
| `l8_v1` → `l8_v3` (older versions) | 30 weeks: €260,043 → €307,943 | €8,668 → €10,265 | 91.0–92.6% |
| `l8` (pricing rules, no planning) | 30 weeks: €320,596 | €10,687 | 91.5% |
| `l8_plan` (`l8` + two-car gigs, pair fix) | 20 weeks: `l8` €109,576, `l8x` €116,587 (`l8`: €99,661 / €104,324) | €11,308 | 93.2% |
| `l8_plan2` (+ price 1.40, links ≤ 50 km) | 30 weeks: `l8` €112,459, `l8x` €119,506, `l8y` €138,040 | €12,334 | 91.9%, 30/30 ranked |
| `l8_chain` (+ chains of 3, plan every hour) | 30 weeks: `l8` €119,744, `l8x` €132,510, `l8y` €142,551 | €13,160 (+6.7%) | 90.3% (l8y-a), 30/30 ranked |
| `l8_notes` (+ reads the dealers' notes; Exp. 52 slack fix) | 30 weeks: `l8` €125,036, `l8x` €135,759, `l8y` €149,830 | €13,688 (+4.0%) | 93.8%, 30/30 ranked |
| `l8_charge` (+ charging stop only on routes > 200 km, cancellation fix) | 30 weeks: `l8` €128,702, `l8x` €139,629, `l8y` €150,912 | €13,975 (+2.1%) | 92.9%, 30/30 ranked |
| `l8_lane` (+ fees on the lane's mean typical fee) | 30 weeks: `l8` €132,001, `l8x` €140,942, `l8y` €155,720 | €14,289 (+2.2%) | 93.7%, 30/30 ranked |
| **`l8_early`** (+ opening fee 0.7× for cars ready ≥ 12 h later) | 30 weeks: `l8` €134,315, `l8x` €144,272, `l8y` €156,651 | **€14,508 (+1.5%)** | **92.9%**, 30/30 ranked |

| Practice ranking round | Preset | Us | Rank | 10th / 1st |
|---|---|---|---|---|
| "Saturday 00:00" | `l8_v1` | €46,496 | 43 of 62 | €75,475 / – |
| "Saturday 09:00" | `l8_v3` | €47,002 | 28 of 36 | €68,719 / €77,573 |
| **"Saturday 12:00"** | **`l8_plan`** | **€71,409**, 373 orders/week, worst 94.9% | 32 of 51 | €89,431 / €99,211 |
| "Saturday 15:00" (as team "slow") | `l8_plan2` | €65,689, 366 orders/week, worst 93.8% | 30 of 36 | €82,653 / €92,830 |
| "Saturday 21:00" | `l8_notes` | €69,561, 361 orders/week, worst 95.0% | 26 of 40 | €83,479 / €105,424 |
| **"Sunday 00:00"** (at 00:10, 24 teams done) | **`l8_early`** | **€72,623**, 359 orders/week, €40.4/order, worst 96.7% | **17 of 24** | €79,287 / €102,582 |
| Test final Sat 14:00 (live, Thu–Wed) | `l8_plan` | €1,365, 68 orders, 94.1% | 32 of 55 | €3,292 / €4,023 |
| Test final Sat 20:00 (live, full week) | `l8_chain` | €12,963, 334 orders, 97.6% | 41 of 75 | €16,623 / €19,592 |

**Gap (round Sunday 00:00):** −€1.3k/week to 10th (was −€2.8k in round 21:00); behind 10th in 4 of 5 weeks. Same margin per order as ranks 2–10 (€36.6–42.2), but they win 386–443 orders/week to our 359: ~40 more orders/week at our margin would reach the top 10. 1st (Juhus): 473 orders at €43.3.

Earlier: in the 20:00 test final the top 10 won 390–500 orders at €41–49 each; we won 334 at €38.8 (+€3.7k needed, +28%). Of 1,030 requests we won 340, lost 558 on price and declined 132 (105 of them > 550 km). Winning more by any means tried tonight lowers the margin: drivers are scarce, so extra cars cost more (Exp. 45).

Ranking round: one person runs `for i in 1 2 3 4 5; do caffeinate -i .venv/bin/python main.py --board --level 8 --preset l8_early || break; done` (only one ranking run per team at a time; a second one gets HTTP 409).

## The level-8 system (`--preset l8_early`)

1. **Price:** 1.40× the list price (the competitor is 26–54% above list); 0.2× less where ≥ 40 drivers live within 30 km of the pickup; 0.2× more for private addresses; plus the competitor's offset for the delivery place (−0.17× Vantaa … +0.18× Joensuu, `lanes.json`).
2. **Backlog brake:** +0.03× per won order still without a driver, so we take fewer cars when overloaded.
3. **Decline** (quote 10× list: never wins, costs nothing): trips over 550 km, and requests whose delivery options leave < 8 h to find a driver.
4. **Chains:** won cars with ≥ 8 h until their latest pickup are held. Every hour (07:00–19:00) the held cars and our posted one-car gigs nobody has booked yet are joined into chains of up to 3 cars per driver (next pickup ≤ 50 km from the last delivery, every car ≥ 4 h early, ≤ 12 h of work; round trips first), at 0.9× the summed typical fees. A car that can't wait 24 h is posted alone; a chain nobody books within 2 h is split.
5. **Driver fee:** opens at 0.8× the typical fee (0.7× when the first car is ready 12 h or more later: drivers who know they work tomorrow book those at once, Exp. 64), +0.1× every 30 min up to 1.3×; after `deadline_close` 1.5× rising to 2.5×.
6. **Notes** (`notes.py`): reads each dealer note (Finnish, Swedish, English, with typos and corrections) into ready time, deadline, the sites' real hours, plates and manual gearbox; right on all 5,790 noted cars of our cached weeks. The pickup goes in the site's real hours from the ready time, the delivery by the earlier deadline, with transfer plates and a manual-licence audience when needed. Failed visits 8.7 → 0.3 a week, late orders 14.3 → 11.3.
7. **Charging:** an electric car under 30% gets a charging stop only on a route over 200 km (RULES); the starter added one to every such car, so 11 short-route cars a week paid for a stop and could not join chains (Exp. 55).
8. **Cancellations:** when a dealer cancels a car of an unbooked chain, the world withdraws the gig; we post its other cars again (RULES; before, they were never delivered; Exp. 60).
9. **Fee base:** every fee is a multiple of the car's typical fee, and the world adds ~11% noise to each one. We use the lane's mean typical fee from 36k past requests (`fees.json`), averaged with the request's own, so a car whose typical fee came out high no longer opens high (Exp. 61).
10. **Recovery:** after a crash or server restart, the bot rebuilds its state from the world (tested: same result as without the restart); held cars are posted at once.

## What we learned

- **Price curve:** win rate at 1.2× list 61%, 1.4× 40%, 1.6× 19%. Profit per request is flat from 1.1× to 1.4×, so a lower price only adds risk.
- **Drivers:** we use 100–150 of the 650–950 drivers a week; fees are ~60% of revenue. Our fee schedule is at its optimum as one level for all cars.
- **Sharing drivers is the volume lever** (Exp. 37): 85% of won cars could share a driver with another. Holding cars and pairing them every 3 h gives ~45% more orders at the same margin per order; pairs are booked within a minute.
- **Mondays:** we win only 1–10% of quotes in most weeks; the competitor starts each week cheap and raises its prices for dealers we rarely win.
- **Safety:** cheaper base prices and longer trips always look good on some weeks but leave a fresh week under 90%. Always check `l8x` and `l8y`.
- **Dealer trust drives volume:** at the same price we win 36% of a dealer's requests at trust 0–4 and 82% at trust 25. One dealer sends 1/3 of all requests; each late order halves its trust.
- **Lanes:** the competitor's price depends on where the car goes, the same in every world (HANDBOOK). Fitted from 19,450 random-price quotes: −0.17× list for Vantaa up to +0.18× for Joensuu/Ylivieska (`lanes.json`, `analysis/lanes.py`). Using it: +4.1% over 30 weeks.
- **Expected-profit pricing** (`opt`, fitted win and lateness models): with a full lateness penalty and trade-ins declined it is safe (worst 91.4%), but only +€2.4k over 20 weeks vs `l8`: not worth switching (Exp. 29). Pricing low to build dealer trust loses money (Exp. 29). Learning the week's price level from wins/losses: +1.3% but a fresh week at 90.6% (Exp. 31). Return-trip offers to drivers who just delivered for us: 1–3 of 41–104 accepted (Exp. 33). Outage pricing: detected reliably, but a higher price there loses orders and trust (Exp. 34). Price-war day: detected, cutting our price is neutral (Exp. 35). Guarded expected-profit pricing (`l8_guarded`, only low-risk requests, ±6% around `l8`): +€2.0k on tuning weeks but −€3.7k on 20 fresh weeks (Exp. 38); fresh lateness clusters on 300–499 km trips and `next_day` options.
- **Driver cost per car** (Sat 23:00): a car alone costs €71 (1.07× typical), in a 2-chain €49, in a 3-chain €35. Lone cars are 54% of fees; that is where the top teams' margin must come from. Longer links (80/120 km), private cars in chains, cheaper trade-ins, a 2 h chain margin, slower raises for cars with time, cheaper 3-car chains: noise (l8 and l8x move ±€3–5k in opposite directions); cheaper later options −€7.3k (Exp. 53–59). Only fixes that follow the rules held on every set (notes, charging, cancellations).
- **When a gig is posted decides how it books** (Exp. 64, 4 traced weeks): gigs whose first car is ready ≥ 12 h later book 94–99% (1-car in 25 min, chains in 1–2 min, 51–93% at the opening fee); chains for cars already ready book 43–55%. Opening those early gigs at 0.7× instead of 0.8×: +1.5% over 30 weeks; at 0.6×: −€13.9k on 20 weeks.
- **Sunday night (Exp. 63, 65, 66), on `l8_lane`/`l8_early`, none adopted:** price by the de-noised cost −€2.4k; cheaper quotes for cars ready ≥ 12 h later −€3.4k (l8 + l8x); posting big dealers' ready cars at once early in the week (trust starts on delivery; D01 is at trust 0–1 every Tuesday morning) −€2.7k. Ready-now chains: 35% book in 10 min, 23% in 30–120 min, so the 2 h split stays.
- **Notes matter** (Exp. 49): the world acts on every note; the starter's reader missed all plates and manual cars and many ready times and deadlines. Reading them well: +3.8% over 30 weeks and the worst week 90.3% → 93.8%. The reveal holds each won order's true note facts, so a reader can be scored offline.
- **Saturday night (Exp. 47–51), not adopted:** fees by where drivers live (`home_fee`), a brake that counts only urgent cars, no fee raises at night, cheaper price with the note reader, explicit chain windows: neutral or worse. Snow-touched orders are late 9.8% vs 3.3% (~1.8 extra late a week; forecasts come 24 h ahead).
- **Saturday evening (Exp. 44–46), all on `l8_chain`, none adopted:** the competitor's level is learnable (week ±0.08×, day ±0.12–0.26×, Monday −0.21×; log loss 0.552 → 0.439) but following it is neutral; cheaper base price, long trips, chain-aware discounts, a narrower backlog brake and cheaper shared gigs all win more orders at a lower margin; 4-car chains, private addresses and charging cars in chains, and other split times are neutral or worse; offering the next car to a driver who just booked: 1 of 84 accepted. Differences under ~€3k on 10 weeks are noise.
- **Tried, no gain** (code kept, off): dealer-trust pricing, prices per delivery option, flat fees, other fee caps, fee level per car, direct offers to drivers near the delivery town, two-car gigs posted at once (Exp. 24, replaced by planning), win-rate steering, price by our cost, higher fees or stricter filters for trusted dealers, lower prices for big dealers.

## Code

| File | What it does |
|---|---|
| `main.py` | Runs a world: practice loop (`advance`), final loop (live stream; a failing event or tick is logged and skipped; rebuilds after a lost connection). |
| `dispatch.py` | `Desk`: answers each event with actions (post, reprice, withdraw, retry); batch planning of two-car gigs; fee schedules. |
| `notes.py` | `read(note, arrived_at)` → `Facts` (ready, deadline, site hours, plates, manual) from a dealer note; `due`, `open_interval`. |
| `pricing.py` | `quote(request, level, params, Situation)`: flat rules, or expected-profit pricing (`opt`). Levels 1–3: list price. |
| `config.py` | `Params` (every tunable number; used ones first, tested-and-off ones last) and `PRESETS`. Defaults = kit starter. |
| `evaluate.py` | Benchmark over 10 fixed weeks (≤ 4 worlds at once) → `results/log.jsonl`. |
| `market.py` | `Market`: the competitor's level this week and today, learned from our wins and losses (`market_k`, off). |
| `analysis/` | `typical.py` (writes `fees.json`: each lane's mean typical fee), `orders.py` (late%/margin by distance, day, town), `market.py` (win rate by price, drivers near pickup), `winmodel.py` / `latemodel.py` / `lanes.py` / `competitor.py` (fit the models, need numpy), `fees.py` (how fast drivers book), `sharing.py` (cars shared vs alone). |
| `tests/` | Offline unit tests: `python -m unittest discover -s tests`. |

## Next (in priority order)

**Biggest lever: driver cost per car.** A car sharing a driver costs ~0.77× its typical fee, a car alone ~1.06×.

Still 42% of cars travel alone (140/week at €68 vs €42 shared): held > 24 h without partner 36, chain split 30, charging stop 26, posted alone with < 24 h left 24, private address 18.5.

1. **Close the gap to the top 10** (round Sunday 00:00: −€1.3k/week vs 10th, behind in 4 of 5 weeks, ~+9% needed: ~40 more orders/week at our margin). Adopt a change before the final only if it wins > €3k on l8 + l8x with every week ≥ 91%.
2. **Late orders left** (11.3/week): booked in time but late 3.3, driver drops 2.9, order changes 2.6, booked only after the deadline warning 1.9. Snow: post and price snow-touched orders earlier/higher.
3. **Final Sun 09:00** with `l8_early` (fallback `l8_lane`). Check it live in the 01:00 test final.

**Estimated margin:** `l8_early` ≈ €14,508/week on our 30 test weeks (+1.5% over `l8_lane`, +3.8% over `l8_charge`, +6.0% over `l8_notes`).

**Ranking runs:** one person, five in a row: `for i in 1 2 3 4 5; do caffeinate -i .venv/bin/python main.py --board --level 8 --preset l8_early || break; done`.

**After a crash or server restart:** a practice or ranking run that stopped continues with `.venv/bin/python main.py --world WORLD_ID --preset l8_early` (the command is printed when it stops). The bot now also waits and rebuilds by itself.

**Keys:** the final and the submission are played with the `bahn67` key in `.env`.

**Branches:** we play `otso/level1-baseline`. `main` has Anh's older Friday version (kit starter + hand-made pricing, not benchmarked); don't merge it into our branch before the final. After the final, merge our branch into `main` for the submission.

## Deadlines

- **Sat 14:00, 20:00:** test finals (live clock, ~19 min).
- **Sun 01:00:** last test final (live clock, same as the real one): start `--final` a few minutes before.
- **Sun 09:00:** the final (level 8, ~34 min, moved from 08:00). Start `main.py --final --preset l8_early` before 09:00; it waits and plays by itself. Leave it running until ~09:35; if it crashes, run the same command again (it continues the same week). The team page shows from ~30 min before whether we are connected.
- **Sun 10:00:** submission on the Junction platform: submission hash (team page), code link, 5–10 slides.

## Rules

No ranking runs without team agreement · never print or commit the key · one change per experiment on the same seeds, logged in LESSONS.md · `evaluate.py` uses ≤ 4 worlds per run (two runs side by side fill the team's 8).
