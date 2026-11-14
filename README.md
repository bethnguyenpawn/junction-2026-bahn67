# 🚗 Bahn Express AI Agent — Junction 2026

Team `bahn67`'s bot for the **Spread** challenge by Bahn Express. For one simulated week in Finland it quotes prices to car dealers, wins orders, and hires freelance drivers to move the cars.

- **Score = gross margin:** prices in, minus driver fees, refunds and penalties.
- **At least 90% of won orders must arrive on time**, or the team is not ranked.
- **The final is Sunday 15 Nov 08:00:** one level-8 week on a live clock (~34 min). The top 10 by margin present to the jury.

Status and next steps: [PROGRESS.md](PROGRESS.md) · every experiment: [LESSONS.md](LESSONS.md) · the challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## 🚀 Setup

You need Python 3.9+ and git.

**1. Get the code and install**

```bash
git clone git@github.com:bethnguyenpawn/junction-2026-bahn67.git
cd junction-2026-bahn67
git checkout otso/level1-baseline        # our working branch
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt          # the official Spread kit + numpy
```

**2. Add the team key**

```bash
cp .env.example .env
```

Open `.env` and replace `put-your-team-key-here` with the `bahn67` key; ask a teammate for it. Don't create a new team at `/join`: that would be a different team. Never commit `.env`.

**3. Check it works**

```bash
python -m unittest discover -s tests                 # 18 tests OK (no key needed)
python main.py --level 8 --seed l8-a --preset l8     # plays one practice week, ~1 min
```

The week should end with about `margin € 13,272   305 orders   95.4% on time   Ranked.` A key problem shows as `HTTP 401`.

## ▶️ Commands

```bash
python main.py --level 8 --seed l8-a --preset l8                         # one practice week
python evaluate.py --level 8 --preset l8                                 # benchmark: 10 fixed weeks, ~1-2 min
python evaluate.py --level 8 --preset l8 --seed-prefix l8x               # the same on 10 other weeks
python evaluate.py --level 8 --preset l8 --set quote_mult=1.5 --note "idea"   # try one change
python analysis/orders.py --note "idea"                                  # which orders were late / lost money
python main.py --final --preset l8                                       # the final (live clock)
```

- **Presets** (`config.py`): `l8` is the current best, used for the final. `starter` = the official starter, and the `l8_v*` presets are older versions. `--set name=value` changes any parameter.
- **Test weeks:** tune on `l8`, confirm on `l8x`, and use `l8y` only as a final check. Each `evaluate.py` run is logged in `results/log.jsonl`.
- **Ranking runs** (`--board`) only when the team agrees: 5 per round, and they can't be undone.

## 📁 Files

| File | What it is for |
|---|---|
| `main.py` | Starts a world and runs it: the practice loop (`advance`) or the final loop (live events). Recovers after errors. |
| `dispatch.py` | The `Desk`: turns each event into actions (quote, post a gig, raise a fee, retry a failed pickup). |
| `pricing.py` | The price for each request, or a decline. |
| `config.py` | Every tunable number (`Params`) and the presets. |
| `lanes.json` | How much dearer the competitor is per delivery town (fitted by `analysis/lanes.py`). |
| `evaluate.py` | Benchmark: plays 10 fixed weeks in parallel and logs the score. |
| `analysis/` | Scripts that study finished weeks: late orders, win rate by price, the fitted models. |
| `tests/` | Offline unit tests. |
| `docs/` | The official rules, handbook and API, plus our summary. |
| `PROGRESS.md` / `LESSONS.md` | Status and next steps / every experiment with numbers. |
| `CLAUDE.md` | Context for Claude Code sessions. |
| `ruff.toml` | Code style; the VS Code Ruff extension formats on save. |

## ⚙️ How it works

### API calls, step by step

We use the official `spread` Python kit. It sends HTTPS + JSON to `https://spread.bahnexpress.com` with the header `Authorization: Bearer <team key>`.

1. **Start a week:** `POST /v1/worlds` with `{"level": 8, "seed": "l8-a"}` returns a world id. The clock stands at Monday 00:00, and the same seed always gives the same week.
2. **Load the map:** `GET /v1/map` returns the towns, plus road km and minutes between them.
3. **Move the clock:** `POST /v1/worlds/{id}/advance` with
   ```json
   {"untilEvent": ["price_request", "order_won", ...], "max": 1440, "actions": []}
   ```
   runs to the next event we care about, at most one day. It returns the events since the last call, e.g.
   ```json
   {"kind": "price_request", "request": {"id": "R00042", "options": [
       {"kind": "same_day", "listPriceCents": 10000}, {"kind": "next_day", "listPriceCents": 9000}]}}
   ```
4. **Decide:** `dispatch.py` turns each event into an action:
   - price request → quote: `{"type": "quote", "requestId": "R00042", "prices": {"same_day": 14500, "next_day": 13050}}`
   - order won → post a gig for drivers: `{"type": "post", "stops": [...], "schedule": [{"at": 600, "feeCents": 4000}, ...]}`
   - deadline warning → raise the fee: `{"type": "reprice", "gigId": "...", "schedule": [...]}`
5. **Send:** the next `advance` carries these in `actions` (max 50 per call). The server applies them, moves the clock, and returns new events: order won or lost, driver booked, car delivered, money in or out.
6. **Repeat** steps 4–5 (~1,500 times) until the week ends.
7. **Score:** `GET /v1/worlds/{id}/score` returns the margin and the on-time share.

**In the final** the clock runs by itself, so there is no `advance`. Events arrive over a WebSocket, and we send the same action JSON with `POST /v1/worlds/{id}/actions`. After a crash, the bot rebuilds its state from the world's snapshot and event history.

### How the bot decides (level 8, `--preset l8`)

1. **Price:** 1.45× the list price (the competitor is 26–54% above list), with adjustments:
   - +0.03× for each won order that still has no driver, to slow down when overloaded;
   - −0.2× where ≥ 40 drivers live near the pickup;
   - +0.2× for private addresses;
   - the competitor's offset for the delivery town, from −0.17× (Vantaa) to +0.18× (Joensuu).
2. **Decline** trips over 550 km, and requests that leave < 8 h to find a driver. To decline, we quote 10× list: it never wins and costs nothing.
3. **Driver fee:** the gig opens at 0.8× the typical fee and rises 0.1× every 30 min, up to 1.3×. After the deadline warning: 1.5×, rising to 2.5×.

## 📊 Status (Sat 14 Nov)

| Level 8 | Margin per week |
|---|---|
| Official starter | −€60,442 (never ranked) |
| **Our `l8`**, 30 test weeks | **€10,687**, all ranked, worst week 91.5% on time |
| Practice round "Saturday 09:00" (previous `l8`) | €9,400: rank 28 of 36 |
| 10th / 1st place in that round | €13,744 / €15,515 |

**The gap is volume:** the top teams win ~400 orders a week, we win ~255, at the same margin per order (€35–40). Details, findings and next steps: [PROGRESS.md](PROGRESS.md).

## 👥 Team and rules

| Area | Members | Main files |
|---|---|---|
| Pricing & order selection | Otso, Linh, Bao | `pricing.py` |
| Drivers & fees | Otso, Linh, Bao | `dispatch.py` |
| API integration, reliability in the final | Anh | `main.py`, `config.py` |
| Testing, evaluation, presentation | Everyone | `evaluate.py`, `tests/`, `analysis/` |

- **One change at a time**, benchmarked on the same weeks, and logged in `LESSONS.md`. Keep it only if margin rises and every week stays ≥ 91% on time.
- **At most one benchmark at a time:** the team has 8 world slots, and `evaluate.py` uses 6.
- **Run the tests before merging.** Never commit `.env`.

## 📚 Links

[Handbook](https://spread.bahnexpress.com/handbook) · [Rules](https://spread.bahnexpress.com/rules) · [API](https://spread.bahnexpress.com/api) · [Leaderboard](https://spread.bahnexpress.com/leaderboard) · [Team page](https://spread.bahnexpress.com/team) (submission hash) · [Run viewer](https://spread.bahnexpress.com/viewer/) · [Judging](https://spread.bahnexpress.com/judging)
