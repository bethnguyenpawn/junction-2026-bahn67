# Bahn Express AI Agent — Junction 2026

Team `bahn67`'s bot for the **Spread** challenge by Bahn Express. For one simulated week in Finland it quotes prices to car dealers, wins orders, and hires freelance drivers to move the cars.

- **Score = gross margin:** prices in, minus driver fees, refunds and penalties.
- **At least 90% of won orders must arrive on time**, or the team is not ranked.
- **The final is Sunday 15 Nov 08:00:** one level-8 week on a live clock (~34 min). The top 10 by margin present to the jury.

Status and next steps: [PROGRESS.md](PROGRESS.md) · every experiment: [LESSONS.md](LESSONS.md) · the challenge in plain words: [docs/CHALLENGE_SUMMARY.md](docs/CHALLENGE_SUMMARY.md)

## Setup

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
python -m unittest discover -s tests                 # 37 tests OK (no key needed)
python main.py --level 8 --seed l8-a --preset l8     # plays one practice week, ~1 min
```

The week should end with about `margin € 13,272   305 orders   95.4% on time   Ranked.` A key problem shows as `HTTP 401`.

## Commands

```bash
python main.py --level 8 --seed l8-a --preset l8_plan2                   # one practice week
python evaluate.py --level 8 --preset l8_plan2                           # benchmark: 10 fixed weeks, ~2 min
python evaluate.py --level 8 --preset l8_plan2 --seed-prefix l8x         # the same on 10 other weeks
python evaluate.py --level 8 --preset l8_plan2 --set pair_fee=0.8 --note "idea"   # try one change
python analysis/orders.py --note "idea"                                  # which orders were late / lost money
python main.py --board --level 8 --preset l8_plan2                      # ranking run: only one at a time per team
python main.py --final --preset l8_plan2                                 # the final (live clock)
python main.py --world WORLD_ID --preset l8_plan2                        # continue a world that stopped (e.g. server restart)
```

- **Presets** (`config.py`): **`l8_plan2` is the current best**, used for ranking runs and the final: `l8_plan` (batch planning) with price 1.40× and pair links up to 50 km. `l8` is without batch planning, `l8_chain` chains up to 3 cars per driver (candidate, Exp. 42), `l8_plan_match` pairs with maximum matching (+3.2% over `l8_plan`, Exp. 43), `l8_guarded` is an experiment that was not adopted (Exp. 38), `starter` = the official starter, and the `l8_v*` presets are older versions. `--set name=value` changes any parameter.
- **Test weeks:** tune on the `l8-a..j` weeks, confirm on `l8x`, and use `l8y` only as a final check. Each `evaluate.py` run is logged in `results/log.jsonl`; it waits up to five minutes when all team practice slots are taken.
- **Ranking runs** (`--board`) only when the team agrees: 5 per round, and they can't be undone.

## Files

| File | What it is for |
|---|---|
| `main.py` | Starts a world and runs it: the practice loop (`advance`) or the final loop (live events). Rebuilds from the world after errors and server restarts; `--world` continues a stopped world. |
| `dispatch.py` | The `Desk`: turns each event into actions (quote, post a gig, raise a fee, retry a failed pickup). |
| `pricing.py` | The price for each request, or a decline. |
| `config.py` | Every tunable number (`Params`) and the presets. |
| `lanes.json` | How much dearer the competitor is per delivery town (fitted by `analysis/lanes.py`). |
| `evaluate.py` | Benchmark: plays 10 fixed weeks in parallel and logs the score. |
| `analysis/` | Scripts that study finished weeks: late orders, win rate by price, car sharing (`sharing.py`), the fitted models. |
| `tests/` | Offline unit tests. |
| `docs/` | The official rules, handbook and API, plus our summary. |
| `PROGRESS.md` / `LESSONS.md` | Status and next steps / every experiment with numbers. |
| `CLAUDE.md` | Context for Claude Code sessions. |
| `ruff.toml` | Code style; the VS Code Ruff extension formats on save. |

## How it works

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

## What we tune: parameters and models

Winning means picking good numbers. All of them live in `Params` in `config.py`, and a preset is one set of them. Try a change without editing code: `--set name=value`.

### Parameters used by `--preset l8_plan2`

| Parameter | Value | What it does | Why this value |
|---|---|---|---|
| `quote_mult` | 1.40 | Base price = list price × this | The competitor is 26–54% above list. 1.45 without planning (cheaper won cars we then delivered late); with planning 1.40 is safe (Exp. 41) |
| `backlog_k` | 0.03 | +0.03× per won order that has no driver yet | Slows winning when we're overloaded |
| `dense_n`, `dense_cut` | 40, 0.2 | −0.2× where ≥ 40 drivers live within 30 km of the pickup | Those cars are easy to move (Exp. 17, 21) |
| `private_add` | 0.2 | +0.2× when a stop is a private address | Private addresses are late ~3× as often (Exp. 20) |
| `dest_k` | 1.0 | + the competitor's offset for the delivery town (`lanes.json`), −0.17× Vantaa … +0.18× Joensuu | Fitted from data; +4.1% (Exp. 30) |
| `decline_km` | 550 | Decline trips longer than this | Longer trips push a fresh week under 90% on time (Exp. 16) |
| `min_slack_h` | 8 | Only quote delivery options that leave ≥ 8 h to find a driver | Tight options are late |
| `open_mult` | 0.8 | A gig's fee opens at 0.8× the typical fee | Fees are ~60% of revenue |
| `raise_per_step`, `raise_every_min`, `raise_steps` | 0.1, 30, 6 | +0.1× every 30 min, up to 1.3× | Best tested as one schedule for all cars |
| `steep_*` | defaults | After the deadline warning: 1.5×, +0.25× every 30 min, up to 2.5× | Last chance to find a driver |
| `plan_every_h` | 3 | Batch planning: hold won cars with ≥ 8 h (`hold_h`) to their latest pickup; every 3 h (07:00–19:00) pair them into two-car gigs | One driver delivers two cars: ~45% more orders (Exp. 37) |
| `pair_km`, `pair_margin_h` | 50, 4 | Pair car A with car B if B's pickup is ≤ 50 km from A's delivery and both arrive ≥ 4 h before their deadline | Round trips first, then the shortest link; 50 km finds more partners than 30, 80 is too far (Exp. 40–41) |
| `pair_fee` | 0.9 | A two-car gig pays 0.9× both typical fees | Pairs are booked within a minute |
| `wait_h` | 24 | An unpaired car waits for the next plan only with ≥ 24 h to spare, else it's posted alone | Cars held too long were late 19% |
| `split_after_min` | 120 | A pair nobody books within 2 h is split into two one-car gigs | Fixed three weeks under 90% |

To decline, we quote 10× list: it never wins and costs nothing.

### Fitted models (`analysis/`, numpy)

| Model | Predicts | Learned from | Used by |
|---|---|---|---|
| Lane table: `lanes.py` → `lanes.json` | How much dearer the competitor is per delivery town | 19,450 quotes at random prices | `l8`, `l8_plan` (`dest_k`), **on** |
| Win model: `winmodel.py` → `win_*` | Chance the dealer takes our price (price, dealer trust, Monday, drivers nearby, distance) | the same quotes | `opt` pricing (off) |
| Late model: `latemodel.py` → `late_*` | Chance a won order is late (slack, private address, drivers nearby, backlog) | 16,118 won orders | `opt` pricing (off) |

`opt=1` switches from the flat rules to "the price with the highest expected profit" from the win and late models. It remains off in `l8`: the guarded lane-aware experiment gained on tuning seeds but lost €3.7k across fresh holdouts (Exp. 38).

### Tested and off

Every other `Params` field is a rule we tested that didn't help. They're kept so each test can be rerun; the experiment number is next to each field in `config.py`, and the numbers are in `LESSONS.md`. They include: dealer-trust pricing, Monday prices, learning the week's price level, win-rate steering, direct offers to drivers (also return trips, Exp. 33), two-car gigs posted as soon as cars are won (Exp. 24, replaced by planning), per-car fee levels, and price by cost.

**In progress: chain dispatcher** (`--preset l8_chain`, Exp. 42). Every hour, held cars and posted gigs no driver has booked yet are chained, up to 3 cars per driver: +6.5% on the tuning weeks, being checked on the others.

Also tested: reacting to the competitor's outage day (`outage_add`, Exp. 34) and price-war day (`war_cut`, Exp. 35). The bot detects both, but changing the price on those days doesn't pay.

### How to test a change

```bash
python evaluate.py --level 8 --preset l8_plan2 --set pair_fee=0.8 --note "pf0.8"                    # 10 tuning weeks
python evaluate.py --level 8 --preset l8_plan2 --seed-prefix l8x --set pair_fee=0.8 --note "x: pf0.8"   # 10 holdout weeks
```

Compare with `l8_plan2`: €112,459 on the tuning weeks, €119,506 on `l8x`, €138,040 on `l8y` (`l8_plan`: €109,576 / €116,587). Keep a change only if margin rises on both sets and every week stays ≥ 91% on time. Then log it in `LESSONS.md`.

## Status (Sat 14 Nov, 16:00)

| Level 8 | Margin per week | Orders per week |
|---|---|---|
| Official starter | −€60,442 (never ranked) | |
| `l8`, 30 test weeks | €10,687, worst week 91.5% on time | ~275 |
| **`l8_plan`**, ranking round "Saturday 12:00" | **€14,282**, worst week 94.9% on time (€71,409 for 5 weeks) | **373** |
| 10th / 1st place in that round | €17,886 / €19,842 | ~430–470 |
| `l8_plan2`, ranking round "Saturday 15:00" | €13,138, worst week 93.8% (€65,689 for 5 weeks, rank 30 of 36; 10th €82,653) | 366 |
| Test final Sat 14:00 (live clock) | €1,365 in 3 working days, 94.1% on time: rank 32 of 55 (1st €4,023) | 68 (1st: 158) |

**The gap is still volume:** the top teams win ~450 orders a week at €40–43 each; we win 373 at €38. In the test final the competitor was cheap and we won 1% of quotes at ≥ 1.45× list, so we are testing cheaper prices (Exp. 39). The biggest lever is driver cost: a car in a pair costs us 0.76× its typical fee, a car alone 1.06×, and half our cars still go alone (Exp. 40). Details and next steps: [PROGRESS.md](PROGRESS.md).

## Team and rules

| Area | Members | Main files |
|---|---|---|
| Pricing & order selection | Otso, Linh, Bao | `pricing.py` |
| Drivers & fees | Otso, Linh, Bao | `dispatch.py` |
| API integration, reliability in the final | Anh | `main.py`, `config.py` |
| Testing, evaluation, presentation | Everyone | `evaluate.py`, `tests/`, `analysis/` |

- **One change at a time**, benchmarked on the same weeks, and logged in `LESSONS.md`. Keep it only if margin rises and every week stays ≥ 91% on time.
- **At most one benchmark at a time:** the team has 8 world slots, and `evaluate.py` uses at most 4, leaving 4 for others.
- **Run the tests before merging.** Never commit `.env`.

## Links

[Handbook](https://spread.bahnexpress.com/handbook) · [Rules](https://spread.bahnexpress.com/rules) · [API](https://spread.bahnexpress.com/api) · [Leaderboard](https://spread.bahnexpress.com/leaderboard) · [Team page](https://spread.bahnexpress.com/team) (submission hash) · [Run viewer](https://spread.bahnexpress.com/viewer/) · [Judging](https://spread.bahnexpress.com/judging)
