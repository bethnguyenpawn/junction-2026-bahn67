# How the system works: algorithms and functions

A guide to the whole code base, file by file. Each function gets one or two plain sentences: what it does and why. For the results behind each rule, see [LESSONS.md](../LESSONS.md); for the challenge itself, see [CHALLENGE_SUMMARY.md](CHALLENGE_SUMMARY.md).

## The big picture

The system plays one simulated week as a car-transport dispatcher. Everything follows one loop:

```
                ┌──────────────────────────────────────────────┐
                │                 the world                    │
                │  (the game server: dealers, drivers, clock)  │
                └──────────────┬───────────────▲───────────────┘
                     events    │               │  actions
       (price request, order won,              │  (quote, post gig,
        driver booked, deadline warning…)      │   reprice, withdraw…)
                               ▼               │
                ┌──────────────────────────────┴───────────────┐
                │  main.py      the loop: move the clock,      │
                │               pass each event to the desk    │
                │  dispatch.py  the desk: one answer per event │
                │  pricing.py   what to quote                  │
                │  network.py   what a car costs our drivers   │
                │  config.py    every tunable number           │
                └──────────────────────────────────────────────┘
```

The three decisions that make the money:

1. **Which requests to win, and at what price.** `pricing.py`, optionally helped by `network.py`.
2. **What to pay drivers.** The fee schedules in `dispatch.py`.
3. **What to do when things go wrong:** failed visits, expired gigs, deadline warnings. Handled in `dispatch.py`.

## The algorithms in short

| Algorithm | Where | In one line |
|---|---|---|
| **Flat markup pricing** | `pricing.flat_mult` | Price = list price × (1.45 + adjustments). The competitor is 26–54% above the list price. |
| **Overload brake** | `pricing.flat_mult`, `Desk.backlog` | +0.03 to the multiplier for each won order still without a driver, so we win fewer cars when overloaded. |
| **Slack filter** | `pricing.quote`, `pricing.slack` | Quote only delivery options that leave at least 8 hours to find a driver. |
| **Distance filter** | `pricing.quote` | Decline trips over 550 km: they were often late. |
| **Driver density** | `dispatch.drivers_near` | Count drivers within 30 km of each town, the app's notification radius. Cheaper prices where 40+ live. |
| **Rising fee schedule** | `dispatch.fee_schedule` | The driver fee opens at 0.8× the typical fee and rises 0.1× every 30 minutes, up to 1.3×. |
| **Steep fee after the warning** | `dispatch.steep_schedule` | After `deadline_close`: 1.5×, rising to 2.5×. |
| **Dealer trust tracking** | `Desk.on_ledger` | Counts each dealer's on-time orders from our own account, as the rules describe. |
| **Expected-profit pricing** (off) | `pricing.best_price` | Picks the price that maximises P(win) × profit, using two logistic models fitted on past weeks. |
| **Network LP pricing** (off) | `network.Network` | A transportation LP over the towns gives each request's marginal cost in driver hours. |
| **Note reading** | `dispatch.window_from_note` | Finds clock times near keywords in the dealer's note and narrows the pickup or delivery window. |
| **Restart recovery** | `Desk.rejoin` | Rebuilds everything from the server after a crash, so the final can go on. |

---

## `config.py`: every tunable number

| Name | What it is |
|---|---|
| `Params` | One frozen dataclass with every setting: prices, fees, filters, and experiments that were switched off. **The defaults reproduce the kit's starter exactly**; a rule set to 0 (or 1.0 for a factor) is off. |
| `PRESETS` | Named settings: `starter` (the kit's starter), `l1` (best at level 1), **`l8` (the final's system)**, and the older `l8_v2` and `l8_v1`. |
| `from_overrides(overrides, base)` | Turns `--set quote_mult=1.5 lp=1` from the command line into a `Params`, using each field's type. An unknown name stops with an error. |

---

## `main.py`: the loop

| Function | What it does |
|---|---|
| `load_env(path)` | Reads `SPREAD_URL` and `SPREAD_KEY` from `.env` if they aren't already set. It never prints the key. |
| `load_near(world, params)` | Reads the driver list and counts the drivers near each town, but only when a rule needs it, since it costs one extra request. |
| `load_network(world, params)` | Builds the towns graph for network pricing, only when `lp=1`. |
| `make_desk(world, level, now, params)` | Creates the `Desk` with everything it needs: the map's roads, drivers near each town, and the network. |
| `play_practice(world, level, params)` | **The practice loop.** It sends the desk's actions with each `advance`, moves the clock to the next event that needs an answer (at most to midnight), and passes every event to the desk. It skips repeated events after a server restart, and prints the score each day. |
| `play_final(world, params)` | **The final loop.** It rebuilds the desk from the server (`rejoin`), then answers events from the live stream as they come. One event that fails is logged and skipped, so the week never stops. |
| `report(label, score)` | Prints one line: margin, revenue, orders, on-time share. |
| `next_final(client)` | Waits until the organisers set the final (or a test final), then returns its world. |
| `main()` | Reads the command line (`--level`, `--seed`, `--preset`, `--set`, `--board`, `--final`) and runs a practice world, a ranking run or the final. In the final it restarts itself after any error. It deletes a failed practice world to free the slot, but never deletes a ranking run, since that would still count. |

---

## `pricing.py`: what to quote

### What the desk knows when it quotes

`Situation` holds the facts about one request: road km and minutes of the first leg, our backlog (won orders without a driver), the dealer's trust count, drivers near the pickup and the delivery, the dealer's request count this week, whether it's Monday, and the network's marginal cost (`lp_hours`).

### The decision

```
quote(request)
  │
  ├─ level 1–3: quote the list price of the first option (every quote wins)
  │
  ├─ trip longer than decline_km (550)?             → decline
  ├─ network says no spare driver within lp_max_h?  → decline (off by default)
  ├─ keep only options with slack ≥ min_slack_h (8 h)
  │     none left?                                   → decline
  │
  ├─ opt = 1:  price each option with best_price()   (off by default)
  └─ else:     price = list price × flat_mult()
```

| Function | What it does |
|---|---|
| `quote(request, level, params, s)` | **The quoting decision above.** It returns the prices per option, or a decline. |
| `flat_mult(request, level, params, s)` | **The price multiplier:** `quote_mult` (1.45) + `backlog_k` × backlog (0.03 each) − 0.2 where 40+ drivers live near the pickup + 0.2 for private addresses + `lp_k` × (network hours − 2.5) when network pricing is on. Other terms are experiments that are switched off. |
| `best_price(request, option, params, s)` | **Expected-profit pricing** (`opt=1`, off). It tries every price from 1.0× to 2.0× the list price in steps of 0.02 and keeps the one with the highest *P(win) × (price × (1 − P(late) × refund) − expected fee − lost trust)*. Both chances come from logistic models fitted on past weeks. |
| `slack(request, option, s)` | Minutes to spare = the option's deadline − the drive − the moment the dealer decides. Little slack means little time to find a driver. |
| `private(request)` | True when any stop is a private address. These were late more often. |
| `logistic(z)` | 1 / (1 + e^−z): turns a model score into a chance between 0 and 1. |
| `decline(request)` | Quotes 10× the list price. It never wins and costs nothing; sending no quote would cost the dealer's goodwill. |
| `is_decline(request, prices)` | True when every price is a decline, so the desk knows which quotes were meant to win. |

---

## `network.py`: what a car costs our drivers (off by default)

**The graph:** the 30 towns are nodes and the road minutes between them are edges. Each town supplies capacity = `lp_alpha` (0.05) × the drivers who live there.

**The linear program** gives every car that needs a driver a town, at the lowest total cost:

```
minimise    Σ cost[town, car] × x[town, car]  +  24 h × (cars no town can take)
subject to  each car gets one driver:      Σ_town x[town, car] + unserved[car] = 1
            no town gives more than it has: Σ_car  x[town, car] ≤ capacity[town]
```

cost[town, car] = road hours from the town to the pickup + from the delivery back to the town.

| Function | What it does |
|---|---|
| `Network(roads, roster, alpha)` | Counts the drivers living in each town and sets each town's capacity. |
| `hours(town, pickup, delivery)` | A driver's extra travel for one car: home → pickup + delivery → home, in hours. |
| `marginal(new, waiting)` | **The answer we use:** the LP's cost with the new car minus without it. That's the extra hours our network spends on this car, after our other waiting cars have taken the nearest drivers. Typically 1 hour (a driver lives near both ends) up to 6 hours or more. |
| `solve(cars)` | Builds the LP as sparse matrices and solves it with scipy's HiGHS, in about 9 ms. It returns the minimum total hours. |

`pricing.flat_mult` turns the marginal hours into a price: +0.05 per hour above 2.5 hours, and cheaper below. Turn it on with `--set lp=1 lp_k=0.05 lp_ref_h=2.5`. See [METHOD_GRAPH_LP.md](METHOD_GRAPH_LP.md) for the results.

---

## `dispatch.py`: the desk

### Map and drivers

| Function | What it does |
|---|---|
| `_load_map(client)` | Loads the map once (it's free and the same for every world) and keeps it in memory. |
| `roads_of(client)` | The roads keyed by (from, to), with km and minutes. |
| `places_of(client)` | The towns keyed by id, with latitude and longitude. |
| `straight_km(a, b)` | Straight-line km between two towns. The app notifies drivers within 30 km in a straight line, not by road. |
| `drivers_near(roster, places)` | For each town, the drivers who live within 30 km. It shows where cars are easy to move. |

### Fee schedules

| Function | What it does |
|---|---|
| `fee_schedule(now, fee, level, p)` | **The normal driver fee:** `open_mult` × the typical fee, then +`raise_per_step` every `raise_every_min` minutes, for `raise_steps` steps. In `l8`: 0.8×, 0.9×, … up to 1.3×, every 30 minutes. Level 1 allows only one step. |
| `steep_schedule(now, fee, level, p)` | **The fee after a deadline warning:** 1.5×, +0.25× every 30 minutes, up to 2.5×. It's expensive, but a late car costs more. |

### The `Desk`: one answer for each event

The desk remembers our requests, orders, gigs, booked drivers, urgent orders and each dealer's trust. Its answers wait in `outbox` until they're sent.

**Event handling**

| Method | What it does |
|---|---|
| `handle(event)` | **The dispatcher.** It sends each event to its handler: price request → `quote`, order won → `win`, order changed → `change`, failed visit → `retry`, gig expired → `repost`, deadline warning → `raise_fees`, booked/dropped/delivered → update the books, account line → `on_ledger`. |
| `rejoin(snapshot, history)` | **Restart recovery.** It rebuilds every gig, order, booking, urgent order and dealer trust count from the server, then answers what was missed: posts orders without a gig, retries failed visits, and quotes open requests. A test showed the same result as an uninterrupted week. |
| `on_ledger(line)` | **Dealer trust.** A revenue line with no late refund is an on-time order: +1 for that dealer, up to 25. A late refund or undelivered penalty halves the dealer's count, as the rules describe. |
| `delivered(order_id, leg, at)` | Marks a car delivered and forgets its gig. |

**Quoting**

| Method | What it does |
|---|---|
| `quote(request)` | Builds the `Situation` (road km, backlog, trust, drivers nearby, network cost), asks `pricing.quote`, and puts the quote in the outbox. |
| `lp_hours(request)` | Collects our waiting cars (won, undelivered, no driver) and asks the network for the new car's marginal cost. Only when `lp=1`. |
| `backlog()` / `backlog_count()` | The number of won orders with a car that no driver holds yet. It drives the overload brake. |
| `learn(request_id, won)` | Win-rate steering (off): nudges the price after each win or loss towards a target win rate. |

**Posting gigs**

| Method | What it does |
|---|---|
| `win(order)` | A new order: post a gig for its cars, or pair it with a waiting gig when pairing is on. |
| `post(order, legs, retry)` | **Posts a gig.** It sets the audience (experienced drivers for premium cars, a manual licence after a licence failure), builds the stops, and adds the fee schedule. A trade-in that's too long for one gig goes as two. |
| `fees_for(stops)` | Chooses the schedule for a gig: the steep one if any of its orders is urgent, otherwise the normal one, scaled by the typical fee of each car. |
| `ease(order)` | A fee factor for easy cars (off; tests showed one fee level is best). |
| `ladder_mult(order_id)` / `tick()` | Level-1 fee ladder: since level 1 allows one fee step, it raises unbooked gigs itself with `reprice` every few minutes. |
| `pair(order)` | Two-car gigs (off): puts a new car in one gig with a waiting car when one driver can deliver both on time. |
| `single_stops(order_id)` | The stops of a plain one-car order that can be paired (no private address, plates or charging). |
| `chain_minutes(first, second)` | Checks that one driver can deliver car 1, drive to car 2's pickup, and deliver car 2 on time within 12 hours of driving. |
| `offer(action, gig_id)` | Direct offers (off): offers a new gig to drivers who live near the delivery town. In tests almost nobody read them. |

**Fixing problems**

| Method | What it does |
|---|---|
| `raise_fees(order_id)` | **After a deadline warning:** marks the order urgent and reprices its unbooked gigs to the steep schedule. |
| `retry(order_id, leg, reason)` | **After a failed visit:** posts the car again without the cause. `not_ready` or `closed`: pick up later. `licence`: manual-licence drivers only. `no_plates`: fetch plates on the way. |
| `repost(gig_id)` | **After a gig expired:** posts it again without its own windows, so the car can still go, late. |
| `change(order)` | **After the dealer changed the order:** withdraws and reposts its gig, unless a driver already holds it. |
| `withdraw(order_id)` | Takes an order's gigs out of the app. It does nothing if a driver holds one. |

**Bookkeeping**

| Method | What it does |
|---|---|
| `gigs_of(order_id)` | The gigs that carry an order's undelivered cars. |
| `carry(action, gig_id)` | Remembers a gig the world accepted, and which cars it carries. |
| `send_post_of(order_id)` / `send()` | Sends the outbox to the world right away when the desk needs a gig's id at once. Normally the outbox goes with the next `advance`. |
| `read_results(actions, results)` | Reads the world's answers and remembers each accepted gig. |

### Helper functions

| Function | What it does |
|---|---|
| `retry_from(order, request, leg, now)` | When to try again after `not_ready` or `closed`: two hours later, or when a moved deadline says the car is ready. |
| `undelivered(order)` | The legs of an order not yet delivered. |
| `without_windows(stops, before)` | Drops stop windows that have already ended, so the world's own window (to the end of the week) applies. |
| `stops_for(order, legs, note, retry)` | Builds a pickup and a delivery stop for each car. It adds a charging stop for electric cars under 30% and plates after a `no_plates` failure, and narrows the windows from the note. |
| `narrower(stop, window, base)` | Adds a window to a stop only when it's narrower than the order's own window. |
| `window_from_note(note, window, stop)` | **Note reading:** finds clock times and opening-hour ranges ("klo 9-16", "not before 13:30", "deliver by 17:00") near Finnish, Swedish and English keywords, and narrows the window. It's the starter's keyword matcher. |

---

## `evaluate.py`: the benchmark

| Function | What it does |
|---|---|
| `run_seed(level, seed, params)` | Plays one week on a fixed seed and returns its score. It waits for a free practice slot if teammates hold all 8. |
| `git_commit()` | The current commit id, so each logged run says which code produced it. |
| `main()` | Plays 10 fixed weeks (`l8-a`…`l8-j`, or another set with `--seed-prefix`), at most 6 at once, prints each week and the total, and appends a record to `results/log.jsonl`. |

**How to compare two versions:** run both on the same seeds and keep a change only if the total margin rises **and** every week stays at or above 91% on time. Confirm on `l8x`, and use `l8y` only as a last check.

---

## `analysis/`: learning from finished weeks

| Script | What it shows |
|---|---|
| `common.py` | Loads the worlds of a logged run by its note, and caches their events, reveal and driver list in `results/raw/`. |
| `fees.py` | Where the money goes, and how long after posting gigs get booked, at what fee. |
| `orders.py` | Which orders were late or lost money, by distance, delivery option, day, hour and town. |
| `market.py` | Win rate by our price, and how drivers near the pickup and delivery affect margin. |
| `winmodel.py` | Fits the logistic model of P(dealer takes our quote) from price, trust, Monday, drivers nearby, distance and dealer size. Prints the `win_*` settings. Needs numpy. |
| `latemodel.py` | Fits the logistic model of P(order arrives late) from slack, distance, private address, drivers nearby, backlog and hour. Prints the `late_*` settings. Needs numpy. |

## `tests/`: offline checks (no key needed)

| File | What it checks |
|---|---|
| `test_pricing_config.py` | The quoting rules (list price at levels 1–3, markup, backlog, distance and slack filters, density, private addresses, whole cents), the fee schedules, and the settings parser. |
| `test_network.py` | The network LP on a 2-town map: a nearby free driver costs 0 hours; a driver already used by another car means a trip from the next town; no capacity costs the 24-hour price; the trip home counts. |

Run them with `.venv\Scripts\python.exe -m unittest discover -s tests` (Windows) or `.venv/bin/python -m unittest discover -s tests` (Mac/Linux).
