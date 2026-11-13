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

## 📊 Status

**Level 8 (the final's level), `--preset l8`:** +€8,080/week over 20 test weeks, **every week ranked** (worst 92% on time). The official starter loses €60,442/week there and is never ranked.

| Level 8 | 10 tuning weeks | 10 unseen weeks |
|---|---|---|
| Official starter | −€604,425, 0/10 ranked | — |
| **Ours** | **+€79,155, 10/10 ranked** | **+€82,446, 10/10 ranked** |

How it works (five rules): quote 1.6× list price, higher when many orders still lack a driver; decline trips over 500 km; only offer delivery options with ≥ 8 h to find a driver; open driver fees at 0.8× the typical fee.
Details: [PROGRESS.md](PROGRESS.md) (status, next steps, deadlines) · [LESSONS.md](LESSONS.md) (every experiment with numbers).

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
python main.py --final --preset l8                               # play the final (live)
python -m unittest discover -s tests                             # offline tests (no key needed)
```

- Presets (`config.PRESETS`): `starter` (default, identical to the official starter), `l1`, `l8`. `--set name=value` overrides any `Params` field.
- Every `evaluate.py` run appends settings and scores to `results/log.jsonl`. Add a row to `LESSONS.md` for each experiment, and check level-8 changes on both seed sets.
- Do **not** play ranking runs (`board: true`) without agreeing as a team: each round has only 5 per level.

### Project Structure

```text
junction-2026/
├── main.py              # Runs a world: practice advance loop + final live-stream loop
├── dispatch.py          # Desk: answers events; driver fees, recovery from problems
├── pricing.py           # Quotes: price multiplier, backlog, distance and slack filters
├── config.py            # All tunable parameters (Params) and presets
├── evaluate.py          # Benchmark over fixed seeds -> results/log.jsonl
├── analysis/            # fees.py, orders.py: analysis of ended weeks (reveal + events)
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
- [x] **Level 8 profitable and ranked on 20/20 test weeks** (+€8,080/week).
- [ ] Test the live final loop in a test final (Sat 14:00 / 20:00).
- [ ] Level 8: dealer trust, handling after `deadline_close`, price-war day.
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
