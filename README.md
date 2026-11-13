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

## 🚀 Getting Started

We are starting with **Level 1** and will progressively develop our agent through **Level 8**.

### Project Structure

```text
junction-2026-bahn67/
├── main.py          # Backend & API — Anh
├── pricing.py       # Pricing — Otso, Linh, Bao
├── dispatch.py      # Dispatch — Otso, Linh, Bao
├── evaluate.py      # Testing — Entire Team
├── config.py        # Shared configuration
├── tests/
└── README.md
```

### Run the Official Starter

Requirements: Python 3.9 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install https://spread.bahnexpress.com/kit/spread-0.1.0-py3-none-any.whl
```

Set the environment variables using your own team key:

```bash
export SPREAD_URL=https://spread.bahnexpress.com
export SPREAD_KEY="YOUR_TEAM_KEY"
```

Run Level 1:

```bash
spread-starter --level 1
```

### Development Roadmap

- [x] Initialize GitHub repository.
- [x] Install the official Python starter kit.
- [x] Complete the first Level 1 simulation.
- [ ] Implement custom pricing logic.
- [ ] Implement custom dispatch logic.
- [ ] Integrate algorithms with the backend.
- [ ] Optimize Level 1 profitability.
- [ ] Progress through Levels 2–8.
- [ ] Test the final system and prepare submission.

## Shared Level 8 seed test

Team members should test their methods on the same five practice seeds:

```bash
python3 main.py --level 8 --seed l8a
python3 main.py --level 8 --seed l8b
python3 main.py --level 8 --seed l8c
python3 main.py --level 8 --seed l8d
python3 main.py --level 8 --seed l8e
```

For each seed, manually record the final margin and on-time percentage, and
the total margin across all five seeds (weeks). If a branch uses a
parameter-based preset instead of the heuristic method, use the same preset
for every command:

```bash
python3 main.py --level 8 --seed l8a --preset YOUR_PRESET
```

## 🤝 Collaboration

- Work on separate Git branches.
- Keep the `main` branch stable.
- Use pull requests to merge changes.
- Test changes before merging.
- Share simulation results with the team.

## 📚 Resources

- [Challenge Overview](https://spread.bahnexpress.com/how)
- [Official Starter Kit](https://spread.bahnexpress.com/kit/)
- [Handbook](https://spread.bahnexpress.com/handbook)
- [API Reference](https://spread.bahnexpress.com/api)
- [Challenge Rules](https://spread.bahnexpress.com/rules)
- [Leaderboard](https://spread.bahnexpress.com/leaderboard)

---

Built by our team for **Junction 2026 — Bahn Express Challenge**.
