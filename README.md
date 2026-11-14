# 🚗 Bahn Express AI Agent — Junction 2026

Our team's AI agent for the Bahn Express logistics challenge at Junction 2026.

## 👥 Team Responsibilities

| Role | Team Members | Main Files |
|---|---|---|
| Pricing & Order Selection | Otso, Linh, Bao | `pricing.py` |
| Driver Dispatch & Optimization | Otso, Linh, Bao | `dispatch.py` |
| Backend & API Integration | Anh | `main.py`, `config.py` |
| Testing & Evaluation | Entire Team | `evaluate.py`, `tests/` |

### Pricing & Dispatch — Otso, Linh, Bao

- Develop pricing and order selection algorithms.
- Optimize driver fees and delivery scheduling.
- Maximize profit while maintaining reliable deliveries.
- Improve `pricing.py` and `dispatch.py`.

### Backend & API Integration — Anh

- Integrate the official Bahn Express Python kit.
- Handle API communication and simulation events.
- Connect pricing and dispatch modules.
- Manage system reliability and error handling.

### Testing & Evaluation — Entire Team

- Run simulations from Level 1 to Level 8.
- Track gross margin and on-time delivery rates.
- Compare algorithms using identical simulation seeds.
- Debug and improve the agent together.
- Prepare the final presentation and submission.

## 🎯 Project Goal

Build an autonomous logistics agent that **maximizes gross margin while maintaining at least 90% on-time deliveries**.

Our development priorities are:

1. Maximize profitable delivery orders.
2. Optimize driver fees and transportation costs.
3. Maintain reliable on-time deliveries.
4. Build a robust system capable of handling Level 8 challenges.

## 📊 Status (Sat 14 Nov, morning)

**Read this first.** Full details: [PROGRESS.md](PROGRESS.md) (status, next steps) · [LESSONS.md](LESSONS.md) (every experiment, including what failed) · [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md) (the challenge in plain words).

**The final is Sunday 08:00: one level-8 week, live clock, ~34 min.** Only the top 10 by margin (and ≥ 90% on time) present to the jury.

### Where we stand

| | Level-8 margin per week | Notes |
|---|---|---|
| Official starter | −€60,442 | never ranked (46% late) |
| `--preset l8` (current, tested) | **+€9,909** (30 test weeks, all ranked, worst 91.0% on time) | use this for ranking runs |
| `--preset l8b` (candidate) | +€10,043 (20 weeks, worst 92.3%), +8% over `l8` on the same weeks | final check on `l8y` still to do |
| Practice round "Saturday 00:00" (old preset `l8_v1`) | €9,299 (€46,496 / 5 weeks) | **rank 43 of 62** |
| 10th place / House best / 1st in that round | €15,095 / €14,358 / €17,185 | top 10 needs ≈ **+€6,000/week** |

### How our level-8 system decides

1. **Quote above list price:** 1.45× list (competitor is 26–54% above list), +0.03× for each won order still without a driver (brake when overloaded).
2. **Decline** (quote 10× list: never wins, costs nothing) trips over 550 km, and requests whose delivery options leave < 8 h to find a driver.
3. **Driver fee:** opens at 0.8× the typical fee, +0.1× every 30 min up to 1.3×; after `deadline_close` 1.5× rising to 2.5×.
4. `l8b` adds: 0.2× cheaper where ≥ 40 drivers live within 30 km of the pickup, 0.2× dearer for private addresses, base 1.4×, decline over 600 km.

### What we know about the game (measured)

- We win ~23% of the requests we quote. Win rate vs our price: 1.2× list 61%, 1.4× 40%, 1.6× 19%. Profit per request is flat from 1.1× to 1.4×, so **price tuning alone won't close the gap**.
- We use only 100–150 of the 650–950 drivers a week. **Driver fees are ~60% of revenue: cheaper drivers are the big lever.**
- Didn't work: dealer-trust pricing, flat fees, other fee caps, direct offers to drivers near the delivery town (almost never accepted), separate prices per delivery option.

### Next

1. Check `l8b` on the `l8y` weeks → make it the default if it holds.
2. **Test final Sat 14:00 / 20:00:** run `python main.py --final --preset l8` to check the live loop keeps up and survives a restart (never run live yet).
3. Cheaper drivers: multi-car gigs (return trips, two cars from one yard), offers to drivers who just finished our gigs nearby.
4. Price-war day (competitor −20% for one day) and handling after `deadline_close`.

**Team rules:** one change at a time on the same seeds (`l8`, then `l8x`; `l8y` only as a final check), log it in LESSONS.md; at most 6 practice worlds per person running at once (team limit 8); ranking runs (`--board`) only when agreed; never commit `.env`.

## 🚀 Getting Started

Requirements: Python 3.9 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt     # installs the official Spread kit

cp .env.example .env                # then put the team key in .env (never commit it)
```

Our scripts read `SPREAD_URL` and `SPREAD_KEY` from `.env` automatically.

### Run

```bash
python main.py --level 8 --seed l8-a --preset l8                 # play one practice week
python evaluate.py --level 8 --preset l8                         # benchmark on 10 fixed weeks (~2 min)
python evaluate.py --level 8 --preset l8 --seed-prefix l8x       # same on 10 unseen weeks
python evaluate.py --level 8 --preset l8 --set quote_mult=1.5 --note "what I'm trying"
python analysis/orders.py --note "what I'm trying"               # which orders were late / lost money
python analysis/market.py --note "what I'm trying"               # win rate by price, drivers near pickup
python main.py --final --preset l8                               # play the final (live)
python -m unittest discover -s tests                             # offline tests (no key needed)
```

- Presets (`config.PRESETS`): `starter` (default, identical to the official starter), `l1`, `l8`, `l8b` (candidate), `l8_v1` (previous). `--set name=value` overrides any `Params` field.
- Every `evaluate.py` run appends settings and scores to `results/log.jsonl`. Add a row to `LESSONS.md` for each experiment, and check level-8 changes on `l8` and `l8x`.
- Do **not** play ranking runs (`board: true`) without agreeing as a team: each round has only 5 per level.

### Project Structure

```text
junction-2026/
├── main.py              # Runs a world: practice advance loop + final live-stream loop
├── dispatch.py          # Desk: answers events; driver fees, recovery from problems
├── pricing.py           # Quotes: price multiplier, backlog, distance, slack, driver-density, private-address rules
├── config.py            # All tunable parameters (Params) and presets
├── evaluate.py          # Benchmark over fixed seeds -> results/log.jsonl
├── analysis/            # fees.py, orders.py, market.py: analysis of ended weeks (reveal + events)
├── results/log.jsonl    # Log of every benchmark run
├── docs/                # Official docs (RULES, HANDBOOK, API, ...) + our summaries
├── tests/               # Offline unit tests: pricing rules, fees, config
├── PROGRESS.md          # Status, next steps, deadlines
├── LESSONS.md           # Experiment log
└── CLAUDE.md            # Context for Claude Code sessions
```

### Development Roadmap

- [x] Starter split into our modules (identical results), benchmark harness, analysis scripts.
- [x] Level 1 profitable: fee ladder (+€3,419/week vs −€2,898 for the starter).
- [x] **Level 8 profitable and ranked on 30/30 test weeks** (+€9,909/week); practice round "Saturday 00:00": 43/62.
- [ ] Test the live final loop in a test final (Sat 14:00 / 20:00).
- [x] Level 8 research: price curve, driver supply by town, private addresses (candidate `l8b`, +8%).
- [ ] Level 8: cheaper drivers (multi-car gigs), handling after `deadline_close`, price-war day.
- [ ] Final (Sun 08:00), then submission by Sun 10:00 (hash, code link, 5–10 slides).

## 🤝 Collaboration

- Work on separate Git branches.
- Keep the `main` branch stable.
- Use pull requests to merge changes.
- Test changes before merging.
- Share simulation results with the team.

## 📚 Resources

- [Challenge Overview](https://spread.bahnexpress.com/how) · [Our summary](docs/CHALLENGE_SUMMARY.md)
- [Official Starter Kit](https://spread.bahnexpress.com/kit/)
- [Handbook](https://spread.bahnexpress.com/handbook)
- [API Reference](https://spread.bahnexpress.com/api)
- [Challenge Rules](https://spread.bahnexpress.com/rules)
- [Leaderboard](https://spread.bahnexpress.com/leaderboard)
- [Judging & submission](https://spread.bahnexpress.com/judging)
- [Team page](https://spread.bahnexpress.com/team) (submission hash) · [Run viewer](https://spread.bahnexpress.com/viewer/)

---

Built by our team for **Junction 2026 — Bahn Express Challenge**.
