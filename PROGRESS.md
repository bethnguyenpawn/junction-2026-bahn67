# Progress

Status of our Spread (Bahn Express) system. Newest at the top of each section.
Experiment details and numbers: [LESSONS.md](LESSONS.md). The challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md).

## Where we are (Friday 13 Nov, evening)

| | Level 1, 10 weeks (`l1-a` … `l1-j`) | On time | Ranked weeks |
|---|---|---|---|
| Kit starter | −€28,978 (−€2,898/week) | 93.6% | 10/10 |
| **Our best: fee ladder 0.7× → +0.3×/hour → cap 1.5×** | **+€34,186 (+€3,419/week)** | 93.2% | 10/10 |
| For reference: leader of the level-1 ranking round "Friday 20:01" | ≈ +€10,600/week (5 different weeks) | 96.6% | 5/5 |

## Done

1. **Setup**
   - Python venv `.venv` with the official kit (`pip install -r requirements.txt`).
   - Team key in `.env` (git-ignored); template in `.env.example`. Our scripts read `.env` themselves.
   - `.gitignore` for secrets, venvs, caches, the kit downloads (`kit/`) and raw run data (`results/raw/`).
   - Challenge docs saved in `docs/` (HANDBOOK, RULES, API, openapi.json, how.html, judging.html) so we can grep them.
2. **Baseline:** ran the kit starter on level 1, seed `l1-a`: −€3,220.38, 94.2% on time, ranked. See [docs/STARTER_NOTES.md](docs/STARTER_NOTES.md) for how it works.
3. **Refactor:** split the starter into our modules, with every fee number in `config.Params`. Verified identical to the cent on `l1-a`.
4. **`evaluate.py`:** plays 10 fixed seeds in parallel (≤ 6 worlds at once), prints per-week margin and on-time, and appends a JSON line (commit, params, seeds, scores) to `results/log.jsonl`.
5. **`analysis/fees.py`:** pulls `/events` and `/reveal` of ended worlds (cached in `results/raw/`) and reports where money goes, booking delays, margin by distance, and booking rate by hour.
6. **Fee ladder:** open low, then raise unbooked gigs by `reprice` every 10 minutes. Turned the level-1 loss into a profit (see LESSONS.md).

## Code layout

| File | What it does |
|---|---|
| `main.py` | Runs a world: practice advance loop and final stream loop. `python main.py --level 1 --seed l1-a [--set name=value ...]` |
| `dispatch.py` | `Desk`: answers each event with actions (post, reprice, withdraw, retry). `fee_schedule`, `steep_schedule`, and the ladder (`ladder_mult`, `tick`). |
| `pricing.py` | `quote()`: list price of the first option. **Levels 1–3: a request without a quote is declined, so we must quote to win.** |
| `config.py` | `Params`: all tunable numbers. Defaults = starter behaviour (ladder off). |
| `evaluate.py` | Benchmark over fixed seeds, logs to `results/log.jsonl`. |
| `analysis/fees.py` | Fee and booking analysis from reveal + events. |

## How to run

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then put the team key in .env

python main.py --level 1 --seed l1-a                                   # one week, starter behaviour
python evaluate.py --level 1 --seeds 10                                # 10-week benchmark (~2-3 min)
python evaluate.py --level 1 --set open_mult=0.7 ladder_per_hour=0.3 \
       --note "what this tries"                                        # an experiment
python analysis/fees.py                                                # analyse the last benchmark's worlds
```

## Rules of conduct we follow

- No ranking runs (`board: true`) without the team agreeing: each round has only 5 per level, and they can't be revealed.
- Never print or commit the team key.
- One change per experiment, always on the same seeds; log idea / why / effect in LESSONS.md.
- At most 6 of our 8 world slots in use, so teammates can still run.

## Next

1. Make the ladder the default once tuning settles; tune `tick_min`, the cap and the `deadline_close` escalation.
2. Long trips lose money (−€42/order at 600+ km, 21% late). Two options: a higher opening fee by distance, or, at levels 1–3, decline the worst requests by not quoting.
3. Level 2: drivers learn our raises, so a ladder that always rises teaches them to wait. Measure it on `l2-*` seeds before trusting level-1 numbers.
4. Level 3: two-car gigs and direct offers.
5. Before Sunday: test the `--final` stream loop in a test final (Saturday 14:00 and 20:00).

## Deadlines

- **Fri 23:59:** preliminary submission on the Junction platform (submission hash from https://spread.bahnexpress.com/team + code link).
- **Sat 14:00, 20:00:** test finals (live clock).
- **Sun 07:30:** final is set, registration closes. **Sun 08:00:** final (level 8, ~34 min).
- **Sun 10:00:** final submission (hash, code link, 5–10 slides).
