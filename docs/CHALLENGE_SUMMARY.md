# The challenge in plain words

Our summary of the Spread challenge by Bahn Express. Where it differs from `RULES.md`, the rules are correct.

## The job

We run a car-transport company for one simulated week in Finland, with software instead of people.

1. **Dealers ask for prices.** About 1,000 requests a week, e.g. "move this car from Tampere to Helsinki by tomorrow 20:00". We have 15 minutes to answer.
2. **We quote and maybe win.** Levels 1–3: every quote wins the first option at its list price (no quote = declined). From level 4 a competitor quotes too.
3. **We hire a freelance driver per car** by posting a *gig* with a *fee*. Drivers decide for themselves whether the fee pays their time, the trip to the car and the trip home.
4. **The driver moves the car.** On time: the dealer pays the price. Late: we refund part of it. Never delivered: no price, plus a penalty of 2× the price.

**Score = gross margin** = revenue from delivered cars − driver fees − refunds − penalties − fines.
**At least 90% of won orders must be on time**, or we are not ranked. A team that wins nothing is not ranked.

The core trade-off: a **low fee** earns more per car but may find no driver, so the car is late. A **high fee** moves the car but earns little or loses money.

## Worlds, weeks and seeds

- A **world** is exactly **one simulated week**: Monday 00:00 to the next Wednesday 22:00. Requests come Mon 08:00 – Fri 18:00.
- A **seed** is the recipe for a world. Same seed + level + actions = the same week to the cent, so we compare versions of our bot on the same seeds.
- Different seeds differ in: the requests (lanes, times, dealers), the cars, the drivers (±20% in number, where they live, which days they work), typical-fee noise, cancellations and changes. Higher levels add competitor prices, notes, weather, surprise events and a driver shortage.
- We test on 10 seeds because one week is noisy, and the final is a week we have never seen.
- Practice worlds wait for us (we move the clock with `advance`). Max 8 unfinished worlds per team; an ended world frees its slot and can still be read and revealed.

## Levels

| Level | Adds |
|---|---|
| 1 Posting | One car per gig, one fee. Every quote wins. Dealers can cancel. |
| 2 Market | Fee schedules that rise; drivers learn our raises and can drop bookings. |
| 3 Network | Several cars per gig, direct offers to one driver. |
| 4 Quotes | The competitor: we can lose orders on price. |
| 5 Full | Dealer notes, changes of plan, failed visits, weather. |
| 6 Surprises | A competitor outage, flu among drivers, a bulk order. |
| 7 Shortage | About a third of the drivers; the competitor is ~25% above list price. |
| 8 Trust | Uneven shortage by town, a price-war day, dealers trust on-time teams. **The final is level 8.** |

## Leaderboards and the final

- **Ranking rounds** (practice rankings): 5 secret weeks per level, the same for every team, played once each with `board: true`. A rank only after all 5, each ≥ 90% on time. Rounds open Sat 00, 09, 12, 15, 18, 21 and Sun 00, 03, 06. **They do not count for the final**; they show where we stand. House starter = the kit's starter; House best = the organisers' best bot. Ranking runs can't be revealed or forked.
- **The final:** Sunday 09:00 (moved from 08:00), one secret level-8 week, live clock (~34 min; a weekday hour = 18 s). Our program must run by itself, survive restarts and keep up. The 10 ranked teams with the highest margin present to the jury.
- **The jury** ignores margin once we are in the top 10. It judges: **elegant** (few parts, each with a reason), **clear** (we can explain how it decides), **creative** (an unexpected idea), **robust** (good on unseen weeks, survives restarts). For each big idea: the idea, why, and the measured effect with and without it on the same weeks.

## Submission (Junction platform)

- Preliminary: Friday 23:59. Final: Sunday 10:00.
- Submission hash (from https://spread.bahnexpress.com/team), link to the code, and a presentation (5–10 slides or a short video).
