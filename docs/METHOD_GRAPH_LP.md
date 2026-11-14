# Method: network pricing with a graph and a linear program

An extra rule on top of the team's `l8` system. Code: [network.py](../network.py). Switch it on with `--set lp=1 lp_k=0.05 lp_ref_h=2.5`.

## Result

| On the team's `l8` | 10 test weeks (`l8`) | 10 held-out weeks (`l8x`) | Worst week |
|---|---|---|---|
| `l8` | €95,102 | €99,994 | 95.7% |
| **`l8` + network pricing** | **€96,348** | **€100,609** | 96.3% (`l8`), 92.3% (`l8x`) |

**+€1,861 over 20 weeks (about +1%).** That's a small gain, within week-to-week noise, so it isn't proven.

## The idea in one sentence

**Price each request by what it costs our whole driver network to move it, after the cars we already hold have taken the nearest drivers.**

## The graph

```
            Oulu (17 drivers)
               │
   Vaasa (26) ─┼─ Jyväskylä (33) ── Joensuu (26)
               │
        Tampere (88) ── Lahti (29)
               │
  Turku (24) ─ Helsinki (246) ─ Porvoo (18)
```

- **Nodes:** the 30 towns on the map.
- **Edges:** the road minutes between every pair of towns, from the map.
- **Supply:** each town offers driver capacity in proportion to the drivers who live there: capacity = 0.05 × drivers.
- **Demand:** each car we've won that has no driver yet needs one unit, and so does the new request.

## The linear program

It finds the cheapest way to give every waiting car a driver:

```
minimise    Σ cost[town, car] × x[town, car]   +   24 h × (cars no town can take)

subject to  every car gets one driver:           Σ_town x[town, car] + unserved[car] = 1
            no town gives more than it has:       Σ_car  x[town, car] ≤ capacity[town]
            x ≥ 0
```

- **cost[town, car]** = the hours a driver from that town spends getting to the pickup and getting home from the delivery. The drive itself is the same for every driver, so it's left out.
- The solver is scipy's HiGHS. It takes about 9 ms, well inside the 4.5 real seconds the final allows per request.

**Marginal cost of a request** = the LP's total cost with the new car − the cost without it.

- **It's low** (about 1 hour) when a driver with spare capacity lives near both the pickup and the delivery.
- **It's high** (6 hours or more) when the nearby drivers are already needed for cars we hold, or when no one lives near either end.

On one test week the median was 2.2 hours, and 90% of requests were under 6 hours.

## The price rule

```
price = list price × (team's l8 multiplier + 0.05 × (marginal hours − 2.5))
```

- At 1 hour: 0.075 cheaper. We want more cars that are easy to move.
- At 6 hours: 0.175 dearer. We win fewer cars that would strain the network.

## Why we tried it

The team's rules each see one thing:
- **"40+ drivers within 30 km of the pickup":** a yes-or-no step that ignores the delivery end and the cars we already hold.
- **The overload brake:** global, so one busy region raises prices across the whole country.

The network sees all of this at once: where drivers live, where each car starts and ends, and which drivers our waiting cars are already using.

## What we learned

| Variant | 10 weeks | Worst week | Verdict |
|---|---|---|---|
| **Network term on top of `l8`** | **€96,348** | **96.3%** | small gain, safer |
| Network term replacing the "40+ drivers" rule | €82,270 | 94.2% | worse |
| Tighter capacity replacing the global overload brake | €81,869 | 93.8% | worse |
| Network term + base price 1.40× | €95,481 | 94.9% | no gain |

1. **The network view adds to the team's simple rules but can't replace them.** Dropping either rule cost about €13k.
2. **The first version read the marginal cost from the LP's dual price.** When a town's capacity is used exactly, that dual isn't unique: a test got 24 hours for a car that really costs 1 hour. The code now takes the difference between two LP solves, which is always right. An offline test checks this ([tests/test_network.py](../tests/test_network.py)).

## The gaps

1. **The gain is within noise.** +1% over 20 weeks needs more weeks to confirm, and it hasn't been checked on the final held-out set (`l8y`).
2. **Capacity is a guess.** 0.05 × the drivers living in a town is fixed. Who actually works each day could be learned from views and bookings during the week.
3. **It plans one moment, not the day.** The LP sees the cars waiting now, not the requests likely to come in the next hours.
4. **Drivers don't chain in the model.** A driver who delivers in town B could take the next car from B. A min-cost flow over time could model that and price return trips cheaply.
5. **Only two settings were tried** for the price weight (0.05, 0.10) and one for the reference (2.5 h).

## How to run it

```powershell
cd junction-2026-bahn67
.\.venv\Scripts\python.exe evaluate.py --level 8 --preset l8 --set lp=1 lp_k=0.05 lp_ref_h=2.5 --note "network pricing"
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

It needs `numpy` and `scipy` in the venv (`pip install scipy`). With `lp=0`, the default, nothing changes.
