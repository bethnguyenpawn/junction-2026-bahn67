# CLAUDE.md

Team project for Junction 2026, **Spread** challenge by Bahn Express: a Python program that dispatches car transports for one simulated week. Score = gross margin; ≥ 90% of won orders on time or unranked. The final is **Sunday 15 Nov 08:00, level 8, live clock**. Only the final decides the top 10; after that the jury judges elegance, clarity, creativity and robustness, not margin.

Read first: `PROGRESS.md` (status, next steps), `LESSONS.md` (every experiment with numbers), `docs/CHALLENGE_SUMMARY.md`. Authoritative rules: `docs/RULES.md` > `docs/HANDBOOK.md` > other docs. `docs/API.md` and `docs/openapi.json` for routes. Kit types: `.venv/lib/python*/site-packages/spread/types.py` — use exact field names from there, never guess.

## Commands

```bash
.venv/bin/python main.py --level 1 --seed l1-a [--set name=value ...]      # one week
.venv/bin/python evaluate.py --level 1 --seeds 10 --set ... --note "..."   # 10-week benchmark, ~2-4 min, logs results/log.jsonl
.venv/bin/python analysis/fees.py [worldId ...]                            # analyse last benchmark (caches results/raw/)
```
Scripts load `.env` themselves (`main.load_env`). Use `.venv/bin/python`, not system python (3.15 system, kit in venv). Run benchmarks **one at a time in the foreground** (detached background `&` runs were blocked by the permission classifier); a long one may be auto-moved to background — wait for its notification.

## Code map

- `main.py` — `play_practice` (advance loop, wakes on `dispatch.WAKE_ON` events, plus every `tick_min` when the ladder is on) and `play_final` (rebuild via `Desk.rejoin`, then WebSocket stream). No `--board` flag on purpose.
- `dispatch.py` — `Desk`: state + `handle(event)` → actions in `outbox`. Fee decisions: `fee_schedule`, `steep_schedule`, `fees_for`, `ladder_mult`, `tick` (reprices unbooked non-urgent gigs upward). Note reader `window_from_note`.
- `pricing.py` — `quote()`; list price of first option. **Levels 1–3: no quote = declined (not won).** Real pricing from level 4.
- `config.py` — `Params` dataclass; every tunable number. Defaults reproduce the kit starter exactly (ladder off). `--set k=v` overrides.
- `evaluate.py` — seeds `l{level}-a..`, ≤ 6 parallel worlds, checks open-world count first, appends JSON line (commit, params, per-seed scores).

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

## Current best (level 1, 10 seeds)

`--set open_mult=0.7 ladder_per_hour=0.3 ladder_cap=1.5` → +€34,186 (+€3,419/week), 93.2% on time, worst week 91.1%. Starter: −€28,978. (`open_mult=0.6` gives +€37,597 but worst week 90.5% — too risky.) Update this section when it changes.
