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
- `dispatch.py` — `Desk`: state + `handle(event)` → actions in `outbox`. Fee decisions: `fee_schedule`, `steep_schedule`, `fees_for`, `ladder_mult`, `tick` (reprices unbooked non-urgent gigs upward). Note reader `window_from_note`. `drivers_near(roster)` = drivers living within 30 km of each place (driver list loaded by `main.load_roster` only when a rule needs it). `Desk.offer` = direct offers (off; tested useless).
- `pricing.py` — `quote()`: levels 1–3 list price (**no quote = declined**). Levels 4+: list × (`quote_mult` + `backlog_k` × backlog), decline (10× list) over `decline_km`, offer only options with ≥ `min_slack_h` slack. Optional: `dense_n/dense_cut` (cheaper where many drivers live near the pickup), `private_add` (private addresses). `trust_w`, `later_mult`, `offer_mult`, `explore_lo/hi` (research: random prices) exist but are off.
- `analysis/orders.py --note "..."` — per-order late%/margin by distance, option, day, hour, town. `analysis/market.py --note "..."` — win rate by price, drivers near pickup/delivery. `analysis/common.py` loads worlds by log note (caches events, reveal, snapshot, driver list).
- `config.py` — `Params` dataclass; every tunable number. Defaults reproduce the kit starter exactly (ladder off). `--set k=v` overrides.
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

Presets in `config.PRESETS`, use `--preset NAME` with main.py / evaluate.py:
- `l8` (the final's level): quote 1.45× list + 0.03 per driverless order, decline > 550 km, options with ≥ 8 h slack, fee 0.8× +0.1× every 30 min. **€297,267 over 30 weeks (l8 €89,964, l8x €95,598, l8y €111,705), 30/30 ranked, worst 91.0%.**
- `l8b` (candidate): `l8` + 0.2 cheaper at ≥ 40 drivers near the pickup, +0.2 private addresses, quote 1.4, decline > 600 km. l8 €99,847, l8x €101,017 (+8% over `l8`), worst 92.3%. **Not yet checked on l8y.**
- `l8_v1`: the previous level-8 preset (q1.6, bk0.01, decline 500, raise hourly): €260,043 on the same 30 weeks.
- Practice ranking L8, round "Saturday 00:00" (with `l8_v1`): `bahn67` final rank 43/62, €46,496 (10th €75,475, House best €71,790). Top 10 needs ≈ +€6,000/week. Driver fees (~60% of revenue) are the main lever; we use only ~15% of the drivers.
- `l1`: fee ladder 0.7× +0.3×/h cap 1.5× → +€34,186 on l1-a..j (starter −€28,978).
- `starter`: the default; reproduces the kit starter exactly.
Confirm a level-8 change on `l8` AND `l8x`; use `l8y` only as a final check (don't tune on it). Target worst week ≥ 91%. Update this section when it changes.
