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

| Level 1, same 10 weeks (`l1-a` … `l1-j`) | Margin | On time |
|---|---|---|
| Official starter | −€28,978 (−€2,898/week) | 93.6% |
| **Our best so far:** fee ladder (open 0.7× typical fee, +0.3×/hour, cap 1.5×) | **+€34,186 (+€3,419/week)** | 93.2% |

Details: [PROGRESS.md](PROGRESS.md) (what's done, next steps, deadlines) and [LESSONS.md](LESSONS.md) (every experiment with numbers).

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
python main.py --level 1 --seed l1-a                    # play one practice week
python evaluate.py --level 1 --seeds 10                 # benchmark on 10 fixed weeks (~2-4 min)
python evaluate.py --level 1 --set open_mult=0.7 ladder_per_hour=0.3 --note "what I'm trying"
python analysis/fees.py                                 # analyse the worlds of the last benchmark
```

- `--set name=value` overrides any parameter in `config.py` (`Params`). Defaults reproduce the official starter exactly.
- Every `evaluate.py` run appends its settings and scores to `results/log.jsonl`. Add a row to `LESSONS.md` for each experiment.
- Do **not** play ranking runs (`board: true`) without agreeing as a team: each round has only 5 per level.

### Project Structure

```text
junction-2026/
├── main.py              # Runs a world: practice advance loop + final live-stream loop
├── dispatch.py          # Desk: answers events; driver fees, fee ladder, recovery from problems
├── pricing.py           # Quotes (list price until level 4; no quote = declined)
├── config.py            # All tunable parameters (Params)
├── evaluate.py          # Benchmark over fixed seeds -> results/log.jsonl
├── analysis/fees.py     # Fee/booking analysis from reveal + events
├── results/log.jsonl    # Log of every benchmark run
├── docs/                # Official docs (RULES, HANDBOOK, API, ...) + our summaries
├── tests/
├── PROGRESS.md          # Status, next steps, deadlines
├── LESSONS.md           # Experiment log
└── CLAUDE.md            # Context for Claude Code sessions
```

### Development Roadmap

- [x] Initialize GitHub repository.
- [x] Install the official Python starter kit.
- [x] Complete the first Level 1 simulation (starter baseline).
- [x] Split the starter into our modules (identical results).
- [x] Benchmark harness (`evaluate.py`) and fee analysis.
- [x] Level 1: profitable with a fee ladder (+€3,419/week).
- [ ] Level 1: fewer late cars (long trips, deadline handling).
- [ ] Level 2 (drivers learn fees) and Level 3 (multi-car gigs, direct offers).
- [ ] Custom pricing from Level 4.
- [ ] Levels 5–8, test finals (Sat 14:00, 20:00), final (Sun 08:00).
- [ ] Prepare the final submission and presentation.

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
