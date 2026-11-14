# CLAUDE.md

Team project for Junction 2026, **Spread** challenge by Bahn Express: a Python program that dispatches car transports for one simulated week. Score = gross margin; ≥ 90% of won orders on time or unranked. The final is **Sunday 15 Nov 08:00, level 8, live clock**. Only the final decides the top 10; after that the jury judges elegance, clarity, creativity and robustness, not margin.

Read first: `PROGRESS.md` (status, next steps), `LESSONS.md` (every experiment with numbers), `docs/CHALLENGE_SUMMARY.md`. Authoritative rules: `docs/RULES.md` > `docs/HANDBOOK.md` > other docs. `docs/API.md` and `docs/openapi.json` for routes. Kit types: `.venv/lib/python*/site-packages/spread/types.py` — use exact field names from there, never guess.

## Commands

```bash
.venv/bin/python main.py --level 8 --seed l8-a --preset l8_plan [--set name=value ...]   # one week
.venv/bin/python evaluate.py --level 8 --preset l8_plan [--seed-prefix l8x] --set ... --note "..."   # 10-week benchmark, ~2 min
.venv/bin/python analysis/orders.py --note "..."     # per-order late%/margin of a logged run (caches results/raw/)
.venv/bin/python main.py --final --preset l8_plan         # the final
.venv/bin/python -m unittest discover -s tests       # offline tests: run before every commit
~/.vscode/extensions/charliermarsh.ruff-*/bundled/libs/bin/ruff format .   # style (ruff.toml, 120 cols); the user's editor formats on save
```
Scripts load `.env` themselves (`main.load_env`). Use `.venv/bin/python`, not system python (3.15 system, kit in venv). Run benchmarks **one at a time in the foreground** (detached background `&` runs were blocked by the permission classifier); a long one may be auto-moved to background — wait for its notification.

## Code map

- `main.py` — `play_practice` (advance loop, wakes on `dispatch.WAKE_ON` events, plus every `tick_min` when the ladder is on) and `play_final` (rebuild via `Desk.rejoin`, then WebSocket stream). `--board` creates a RANKING run: only the user runs it, never Claude without explicit OK.
- `dispatch.py` — `Desk`: state + `handle(event)` → actions in `outbox`. Fee decisions: `fee_schedule`, `steep_schedule`, `fees_for`, `ladder_mult`, `tick` (reprices unbooked non-urgent gigs upward). Note reader `window_from_note`. `drivers_near(roster, places)` = drivers living within 30 km of each place (built by `main.load_near` only when a rule needs it: one extra read). `Desk.offer` = direct offers (off; tested useless). `Desk.pair` = two-car gigs (off, `pair_fee`). `Desk.learn` = win-rate steering (off, `adapt_target`). `Desk.ease` = fee factor for easy cars (off). `fees_for(stops)` builds every gig's schedule.
- `pricing.py` — `quote(request, level, params, Situation)`: levels 1–3 list price (**no quote = declined**). `opt=1`: per-option expected-profit price from the fitted win/late logistic models (`best_price`; coefficients `win_*`, `late_*` in Params, fitted by `analysis/winmodel.py` / `latemodel.py`, numpy needed only there). Flat rules (`flat_mult`), levels 4+: list × (`quote_mult` + `backlog_k` × backlog), decline (10× list) over `decline_km` or more than `max_legs` legs (trade-ins), offer only options with ≥ `min_slack_h` slack. Optional: `dest_k` (+ the competitor's offset for the delivery place from `lanes.json`, refit with `analysis/lanes.py`), `dense_n/dense_cut` (cheaper where many drivers live near the pickup), `private_add` (private addresses). Off: `opt_trust_gain` (value of building trust, Exp. 29), `market_lr` (learn the week's competitor level from wins vs `win_chance`, Exp. 31), `monday_add` (Exp. 32), `return_mult` (return-trip offers, `Desk.offer_return`, Exp. 33), `outage_add/_n/_rate/_km` (price up where we win most quotes today = competitor outage, `Desk.outage_near`, Exp. 34: −€1.9k at +0.3, neutral at +0.1), `war_cut/_n/_rate` (cheaper on the detected price-war day, `Desk.price_war`, Exp. 35: neutral), `trust_w`, `later_mult`, `adapt`, `cost_k`, `explore_lo/hi` (research: random prices).
- `analysis/orders.py --note "..."` — per-order late%/margin by distance, option, day, hour, town. `analysis/market.py --note "..."` — win rate by price, drivers near pickup/delivery. `analysis/common.py` loads worlds by log note (caches events, reveal, snapshot, driver list).
- `config.py` — `Params` dataclass; every tunable number, used ones first, "tested and off" ones last (with their LESSONS experiment number). Defaults reproduce the kit starter exactly. `--set k=v` overrides.
- `evaluate.py` — seeds `l{level}-a..` (`--seed-prefix l8x` for the holdout set), ≤ 4 parallel worlds (other 4 slots for teammates), checks open-world count first, appends JSON line (commit, params, per-seed scores).

## Invariants / gotchas

- Defaults must stay identical to the starter (−€3,220.38 on `l1-a` level 1). If you change default behaviour, change the default in `Params` deliberately and note it.
- Level 1 gigs accept **one fee step**; multi-step schedules only from level 2. Our ladder works around this with `reprice` (allowed on any unbooked gig).
- From level 2 drivers learn our raises (running mean of booked/first-viewed fee and wait time) — level-1 ladder results may not transfer.
- Money is integer cents, times integer world minutes (Monday 00:00 = 0). The client rejects floats with fractions: always `int(... + 0.5)`.
- Max 50 actions per request, 8 unfinished practice worlds per team (shared with teammates), rate limit shared per key.
- Drop duplicate events by `seq`. 502/503/504 = server restarting → `Unreachable`; wait, re-read state, continue.
- Final: 20 actions/s, 50 reads/s, clock runs by itself; decision code must be fast and clock-independent.

## Rules of conduct

- **Never print, log or commit `SPREAD_KEY`.** `.env` is git-ignored; don't `cat` it (check with grep for the placeholder instead).
- **Never create ranking runs (`board: true`) without the user's explicit OK.** They're limited (5/level/round), can't be revealed, deletion still counts.
- Don't delete worlds that aren't ours / still running for teammates. Our evaluate runs finish their worlds.
- **Experiments:** one parameter change at a time, same 10 seeds, then add a row to `LESSONS.md` (idea / why / effect). Keep a change only if margin rises AND every week stays well above 90% (target worst week ≥ 91%).
- **Git:** remote is SSH with a YubiKey → the user runs `git fetch` / `git push` themselves (`! git ...`); merge locally after their fetch. We work on branch `otso/level1-baseline` (no PR for now); don't commit to `main` directly. Commit only when asked. Remote: `git@github.com:bethnguyenpawn/junction-2026-bahn67.git`.
- Report numbers, not prose. The user prefers short, plain explanations.

## Current best

**`l8_plan`** (Exp. 37): `l8` + batch planning of two-car gigs (`plan_every_h=3 pair_km=30 pair_fee=0.9 pair_margin_h=4 split_after_min=120 wait_h=24`, `Desk.plan`, `Desk.split`). Use it for ranking runs, test finals and the final. With the pair fix (uncommitted, `Desk.withdraw` reposts the other car of a withdrawn pair): l8 €109,576, l8x €116,587, worst 93.2%; l8y not run. Ranking round "Saturday 12:00": **€71,409 in 5 weeks, 373 orders/week, worst 94.9%**, rank 32 (10th €89,431). Test final Sat 14:00: €1,365, 68 orders (1st 158), 94.1%: a cheap week, we won 1% of quotes at ≥ 1.45×; quotes all in time. Exp. 39: `quote_mult=1.40` +€3.5k/20 weeks on l8+l8x (check l8y next); `market_lr=0.01 market_hi=0` +€5.9k l8 / −€1.3k l8x. Next: pair_fee 0.8, plan_every_h 2.

Presets in `config.PRESETS`, use `--preset NAME` with main.py / evaluate.py:
- `l8` (`l8_plan` without planning): quote 1.45× list + 0.03 per driverless order, −0.2 at ≥ 40 drivers near the pickup, +0.2 private addresses, + delivery-place offset (`dest_k=1`, `lanes.json`), decline > 550 km, options with ≥ 8 h slack, fee 0.8× +0.1× every 30 min. **€320,596 over 30 weeks (l8 €99,661, l8x €104,324, l8y €116,611), 30/30 ranked, worst 91.5%.**
- `l8_guarded` (experimental, off): expected-profit quotes only where fitted lateness ≤ 8% and backlog < 3, capped to ±6% of list around `l8`; lost €3,664 over 20 fresh holdout weeks (`l8v`, `l8u`) vs `l8` (Exp. 38).
- `l8_v3`: previous `l8` without the delivery-place offset: €307,943, worst 92.6% (played in the Sat-09:00 round). `l8_v2`: without the density/private rules: €297,267, worst 91.0%. `l8_v1`: Sat-00:00 ranking preset: €260,043.
- Tried and failed the l8y check: `l8b` (+ quote 1.4, decline > 600): €311,874 but a 89.9% week. Cheaper base price / longer trips keep failing on fresh weeks.
- Practice round "Saturday 09:00" with `l8_v3`: €47,002, rank 28/36 finished (House best €50,660, 10th €68,719). Top teams win 1.4–2× more orders at the same margin/order.
- Dealer trust drives win rate (36% at trust 0–4 → 82% at 25, same price); a late order halves it. `opt=1` (Exp. 28–29): safe with `max_legs=1 opt_late_refund=1.0 opt_backlog=0.04 dense_cut=0` (worst 91.4%) but only +€2.4k/20 weeks vs `l8`; pricing low to build trust loses money.
- Tested ≈ no gain (Exp. 23–27): fee level per car, two-car gigs posted at once (Exp. 24; planning fixed it), win-rate steering, price by cost. Restart/rejoin verified to reproduce the uninterrupted score.
- Practice ranking L8, round "Saturday 00:00" (with `l8_v1`): `bahn67` final rank 43/62, €46,496 (10th €75,475, House best €71,790). Top 10 needed ≈ +€5,000/week then. Driver fees (~60% of revenue) are the main lever; we use only ~15% of the drivers.
- `l1`: fee ladder 0.7× +0.3×/h cap 1.5× → +€34,186 on l1-a..j (starter −€28,978).
- `starter`: the default; reproduces the kit starter exactly.
Confirm a level-8 change on `l8` AND `l8x`; use `l8y` only as a final check (don't tune on it). Target worst week ≥ 91%. Update this section when it changes.
