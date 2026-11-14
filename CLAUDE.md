# CLAUDE.md

Team project for Junction 2026, **Spread** challenge by Bahn Express: a Python program that dispatches car transports for one simulated week. Score = gross margin; ≥ 90% of won orders on time or unranked. The final is **Sunday 15 Nov 08:00, level 8, live clock**. Only the final decides the top 10; after that the jury judges elegance, clarity, creativity and robustness, not margin.

Read first: `PROGRESS.md` (status, next steps), `LESSONS.md` (every experiment with numbers), `docs/CHALLENGE_SUMMARY.md`. Authoritative rules: `docs/RULES.md` > `docs/HANDBOOK.md` > other docs. `docs/API.md` and `docs/openapi.json` for routes. Kit types: `.venv/lib/python*/site-packages/spread/types.py` — use exact field names from there, never guess.

## Commands

```bash
.venv/bin/python main.py --level 8 --seed l8-a --preset l8 [--set name=value ...]   # one week
.venv/bin/python evaluate.py --level 8 --preset l8 [--seed-prefix l8x] --set ... --note "..."   # 10-week benchmark, ~2 min
.venv/bin/python analysis/orders.py --note "..."     # per-order late%/margin of a logged run (caches results/raw/)
.venv/bin/python main.py --final --preset l8         # the final
.venv/bin/python -m unittest discover -s tests       # offline tests: run before every commit
```
Scripts load `.env` themselves (`main.load_env`). Use `.venv/bin/python`, not system python (3.15 system, kit in venv). Run benchmarks **one at a time in the foreground** (detached background `&` runs were blocked by the permission classifier); a long one may be auto-moved to background — wait for its notification.

## Code map

- `main.py` — `play_practice` (advance loop, wakes on `dispatch.WAKE_ON` events, plus every `tick_min` when the ladder is on) and `play_final` (rebuild via `Desk.rejoin`, then WebSocket stream). `--board` creates a RANKING run: only the user runs it, never Claude without explicit OK.
- `dispatch.py` — `Desk`: state + `handle(event)` → actions in `outbox`. Fee decisions: `fee_schedule`, `steep_schedule`, `fees_for`, `ladder_mult`, `tick` (reprices unbooked non-urgent gigs upward). Note reader `window_from_note`. `drivers_near(roster, places)` = drivers living within 30 km of each place (built by `main.load_near` only when a rule needs it: one extra read). `Desk.offer` = direct offers (off; tested useless). `Desk.pair` = two-car gigs (off, `pair_fee`). `Desk.learn` = win-rate steering (off, `adapt_target`). `Desk.ease` = fee factor for easy cars (off). `fees_for(stops)` builds every gig's schedule.
- `pricing.py` — `quote(request, level, params, Situation)`: levels 1–3 list price (**no quote = declined**). `opt=1`: per-option expected-profit price from the fitted win/late logistic models (`best_price`). The current `l8` preset falls back to its flat quote when predicted lateness > 8% or backlog ≥ 3, and caps changes at 6% of list. Flat rules (`flat_mult`), levels 4+: list × (`quote_mult` + `backlog_k` × backlog), decline (10× list) over `decline_km`, offer only options with ≥ `min_slack_h` slack. Optional: `dense_n/dense_cut` and `private_add`. Off: `trust_w`, `later_mult`, `adapt`, `cost_k`, `explore_lo/hi`.
- `analysis/orders.py --note "..."` — per-order late%/margin by distance, option, day, hour, town. `analysis/market.py --note "..."` — win rate by price, drivers near pickup/delivery. `analysis/common.py` loads worlds by log note (caches events, reveal, snapshot, driver list).
- `config.py` — `Params` dataclass; every tunable number, used ones first, "tested and off" ones last (with their LESSONS experiment number). Defaults reproduce the kit starter exactly. `--set k=v` overrides.
- `evaluate.py` — seeds `l{level}-a..` (`--seed-prefix l8x` for the holdout set), ≤ 6 parallel worlds, checks open-world count first, appends JSON line (commit, params, per-seed scores).

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

- `l8` (current final strategy): expected-profit prices only when fitted late risk ≤ 8% and backlog < 3; cap changes at ±6% of `l8_flat`, otherwise fall back to flat pricing. Keep the 8 h slack and 550 km filters, plus the existing fee schedule. **20 matched weeks (l8 + fresh l8z): €191,625, 20/20 ranked, worst 94.6%; +€2,091 over flat on identical seeds.**
- `l8_guarded`: alias for the promoted `l8` strategy.
- `l8_flat`: previous l8 formula; **€307,943 over 30 historical weeks (l8 €95,102, l8x €99,994, l8y €112,847), 30/30 ranked, worst 92.6%.**
- `l8_v2`: previous `l8` without the density/private rules: €297,267, worst 91.0%. `l8_v1`: Sat-00:00 ranking preset: €260,043.
- Tried and failed the l8y check: `l8b` (+ quote 1.4, decline > 600): €311,874 but a 89.9% week. Cheaper base price / longer trips keep failing on fresh weeks.
- Practice round "Saturday 09:00" with prior `l8_flat`: €47,002, rank 28/36 finished (House best €50,660, 10th €68,719). Top teams win 1.4–2× more orders at the same margin/order.
- Dealer trust drives win rate (36% at trust 0–4 → 82% at 25, same price); a late order halves it. Full expected-profit pricing gained margin but failed at 88.6% and 89.5% worst weeks. The guarded version passed the fresh `l8z` holdout with higher margin and 94.6% worst on time.
- Tested ≈ no gain (Exp. 23–27): fee level per car, two-car gigs, win-rate steering, price by cost. Restart/rejoin verified to reproduce the uninterrupted score.
- Practice ranking L8, round "Saturday 00:00" (with `l8_v1`): `bahn67` final rank 43/62, €46,496 (10th €75,475, House best €71,790). Top 10 needs ≈ +€5,000/week over current `l8`. Driver fees (~60% of revenue) are the main lever; we use only ~15% of the drivers.
- `l1`: fee ladder 0.7× +0.3×/h cap 1.5× → +€34,186 on l1-a..j (starter −€28,978).
- `starter`: the default; reproduces the kit starter exactly.
The guarded strategy passed the `l8` tuning set and fresh `l8z` holdout. Do not tune further on `l8z`; use a new seed prefix for future holdouts. Target worst week ≥ 91%. Update this section when it changes.
