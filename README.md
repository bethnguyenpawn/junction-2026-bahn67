# 🚗 Bahn Express AI Agent — Junction 2026

Team `bahn67`'s system for the **Spread** challenge by Bahn Express. It runs a car-transport company for one simulated week in Finland:
it quotes prices to car dealers, wins orders, and hires freelance drivers to move the cars.

**Score = gross margin** (prices in − driver fees, refunds, penalties out). **At least 90% of won orders must arrive on time**, or the team is not ranked.
**The final is Sunday 15 Nov 08:00:** one level-8 week on a live clock (~34 min). The 10 ranked teams with the highest margin present to the jury.

More: [PROGRESS.md](PROGRESS.md) (status, next steps, deadlines) · [LESSONS.md](LESSONS.md) (every experiment, including what failed) · [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md) (the challenge in plain words).

## 📊 Status (Sat 14 Nov, late morning)

| Level 8 | Margin per week | Notes |
|---|---|---|
| Official starter | −€60,442 | never ranked (46% late) |
| **`--preset l8`** (current) | **+€10,265** | 30 test weeks, all ranked, worst week 92.6% on time. Use this for ranking runs and the final. |
| Our practice round "Saturday 00:00" (old preset) | €9,299 | **rank 43 of 62** |
| 10th place / House best / 1st in that round | €15,095 / €14,358 / €17,185 | **top 10 needs ≈ +€6,000/week** |

What we have measured:
- We win ~23% of the requests we quote. Win rate vs our price: 1.2× list 61%, 1.4× 40%, 1.6× 19%. Profit per request is flat from 1.1× to 1.4×, so **price tuning alone won't close the gap**.
- We use only 100–150 of the 650–950 drivers a week, and driver fees are ~60% of revenue: **cheaper drivers are the big lever**.
- Didn't work: dealer-trust pricing, flat fees, other fee caps, direct offers to drivers near the delivery town, separate prices per delivery option.
- Cheaper base price (1.4×) and longer trips (> 550 km) look good on some weeks but leave a week under 90% on fresh weeks.

Next:
1. **Test final Sat 14:00 / 20:00:** `python main.py --final --preset l8` (the live loop has never run; check it keeps up and survives a restart).
2. Cheaper drivers: multi-car gigs (return trips, two cars from one yard), offers to drivers who just finished our gigs nearby.
3. Price-war day (competitor −20% for one day), and handling after `deadline_close`.

## ⚙️ How it works

### Talking to the game server

We use the official `spread` Python kit. It sends HTTPS + JSON to `https://spread.bahnexpress.com`, with our team key in the header `Authorization: Bearer <key>` (read from `.env`).

1. **Start a week:** `POST /v1/worlds` with `{"level": 8, "seed": "l8-a"}` → a world id. A world is one simulated week; the clock stands at Monday 00:00. The same seed always gives the same week.
2. **Load the map:** `GET /v1/map` → towns, and road km and minutes between them.
3. **Move the clock:** `POST /v1/worlds/{id}/advance` with
   ```json
   {"untilEvent": ["price_request", "order_won", ...], "max": 1440, "actions": []}
   ```
   = "run to the next event we care about, at most to midnight". The server answers with the events since the last call, e.g.
   ```json
   {"kind": "price_request", "request": {"id": "R00042", "options": [
       {"kind": "same_day", "listPriceCents": 10000}, {"kind": "next_day", "listPriceCents": 9000}]}}
   ```
4. **Decide:** our code turns each event into an action:
   - price request → quote, e.g. list × 1.45: `{"type": "quote", "requestId": "R00042", "prices": {"same_day": 14500, "next_day": 13050}}`
   - order won → post a gig for drivers: `{"type": "post", "stops": [...], "schedule": [{"at": 600, "feeCents": 4000}, ...]}`
   - deadline warning → raise the fee: `{"type": "reprice", "gigId": "...", "schedule": [...]}`
5. **Send and move on:** the next `advance` carries these in `actions` (max 50 per call). The server applies them at the current minute, moves the clock, and returns new events: order won or lost, driver booked, car delivered, money in or out.
6. **Repeat** 4–5 (~1,500 times) until the week ends.
7. **Score:** `GET /v1/worlds/{id}/score` → margin and on-time %.

**The final** works the same, except the clock runs by itself (no `advance`): events arrive over a WebSocket, and we send the same action JSON with `POST /v1/worlds/{id}/actions`. If our program restarts, it rebuilds its state from the world's snapshot and event history.

### How our level-8 system decides

1. **Price:** quote 1.45× the list price (the competitor is 26–54% above list), +0.03× for each won order that still has no driver (a brake when we are overloaded). 0.2× cheaper where ≥ 40 drivers live within 30 km of the pickup (cars there are easy to move), 0.2× dearer for private addresses (often late).
2. **Decline** (quote 10× list: never wins, costs nothing): trips over 550 km, and requests whose delivery options leave < 8 h to find a driver.
3. **Driver fee:** opens at 0.8× the typical fee, +0.1× every 30 min up to 1.3×. After the deadline warning: 1.5×, rising to 2.5×.

## 🚀 Getting started

Requirements: Python 3.9 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt     # installs the official Spread kit
cp .env.example .env                # then put the team key in .env (never commit it)
```

### Run

```bash
python main.py --level 8 --seed l8-a --preset l8                 # play one practice week
python evaluate.py --level 8 --preset l8                         # benchmark on 10 fixed weeks (~1-2 min)
python evaluate.py --level 8 --preset l8 --seed-prefix l8x       # same on 10 other weeks
python evaluate.py --level 8 --preset l8 --set quote_mult=1.5 --note "what I'm trying"
python analysis/orders.py --note "what I'm trying"               # which orders were late / lost money
python analysis/market.py --note "what I'm trying"               # win rate by price, drivers near pickup
python main.py --final --preset l8                               # play the final (live)
python -m unittest discover -s tests                             # offline tests (no key needed)
```

- **Presets** (`config.PRESETS`): `starter` (default, identical to the official starter), `l1`, `l8` (current), `l8_v2` and `l8_v1` (previous). `--set name=value` overrides any `Params` field.
- **Seed sets:** tune on `l8`, confirm on `l8x`, use `l8y` only as a final check.
- Every `evaluate.py` run appends its settings and scores to `results/log.jsonl`.

### Project structure

```text
junction-2026/
├── main.py              # Runs a world: practice advance loop + final live-stream loop
├── dispatch.py          # Desk: answers each event; driver fees, recovery from problems
├── pricing.py           # Quotes: price multiplier, backlog, distance, slack, driver-density, private-address rules
├── config.py            # All tunable parameters (Params) and presets
├── evaluate.py          # Benchmark over fixed seeds -> results/log.jsonl
├── analysis/            # fees.py, orders.py, market.py: analysis of ended weeks
├── tests/               # Offline unit tests: pricing rules, fees, config
├── results/log.jsonl    # Log of every benchmark run
├── docs/                # Official docs (RULES, HANDBOOK, API, ...) + our summaries
├── PROGRESS.md          # Status, next steps, deadlines
├── LESSONS.md           # Experiment log
└── CLAUDE.md            # Context for Claude Code sessions
```

## 👥 Team

| Role | Members | Main files |
|---|---|---|
| Pricing & order selection | Otso, Linh, Bao | `pricing.py` |
| Driver dispatch & fees | Otso, Linh, Bao | `dispatch.py` |
| Backend & API integration (kit, events, reliability in the final) | Anh | `main.py`, `config.py` |
| Testing & evaluation, presentation | Everyone | `evaluate.py`, `tests/`, `analysis/` |

### Working rules

- **One change at a time** on the same seeds, then add a row to `LESSONS.md` (idea, why, effect). Keep a change only if margin rises and every week stays ≥ 91% on time.
- **World slots:** the team can have 8 unfinished practice worlds; `evaluate.py` uses at most 6, so don't run two benchmarks at once.
- **Ranking runs** (`--board`) only when agreed as a team: each round has 5 per level, and they can't be undone.
- **Never commit `.env`** (the team key). Work on your own branch, keep `main` stable, run the tests before merging.

## 🗺️ Roadmap

- [x] Starter split into our modules (identical results), benchmark harness, analysis scripts.
- [x] Level 1 profitable: fee ladder (+€3,419/week vs −€2,898 for the starter).
- [x] **Level 8 profitable and ranked on 30/30 test weeks** (+€10,265/week).
- [x] Level 8 research: price curve, drivers by town, private addresses (+3.6%, safer: worst week 92.6%).
- [ ] Test the live final loop in a test final (Sat 14:00 / 20:00).
- [ ] Level 8: cheaper drivers (multi-car gigs), handling after `deadline_close`, price-war day.
- [ ] Final (Sun 08:00), then submission by Sun 10:00 (hash, code link, 5–10 slides).

## 📚 Resources

- [Challenge overview](https://spread.bahnexpress.com/how) · [Handbook](https://spread.bahnexpress.com/handbook) · [Rules](https://spread.bahnexpress.com/rules) · [API reference](https://spread.bahnexpress.com/api)
- [Starter kit](https://spread.bahnexpress.com/kit/) · [Leaderboard](https://spread.bahnexpress.com/leaderboard) · [Judging & submission](https://spread.bahnexpress.com/judging)
- [Team page](https://spread.bahnexpress.com/team) (submission hash) · [Run viewer](https://spread.bahnexpress.com/viewer/)
