# Bahn Spread Challenge: a guide to the starter

This guide explains the official challenge rules and the current `dispatch.py` starter for someone who knows Python but is new to logistics optimisation. It is based on the official documentation and the code in this repository. No simulations have been run for this explanation.

## 1. The challenge

The official rules describe a one-week simulation in Finland. Dealers send requests to your team and a competitor. Your system quotes a price; if the dealer chooses yours, you get an order to move one or two cars. You then post a gig—one or more car moves with ordered pickup and delivery stops—to freelance drivers. Your score is the money you collect minus driver fees, refunds, fines, and penalties. To be ranked, at least 90% of your won orders must arrive on time. A trade-in is one request with two legs: the new car going to the customer and the old car coming back.

There is no separate “broker” entity in the docs. Your team and the competitor are the two services dealers can buy from; your code acts as your team’s dispatcher. A request has a response deadline, usually 15 simulated minutes after it arrives. An order has a delivery deadline. A gig has a fee schedule, which says what drivers will be paid as time passes. Those are three different clocks to keep track of.

```text
Dealer sends request ──> Your team quotes ──> Dealer chooses a quote
                                                │
                                                ▼
Driver books a gig <── Your team posts gig <── You now have an order
        │
        ▼
Car is picked up and delivered ──> revenue, fees, refunds, score
```

The dealer’s list price is a public reference price, not the competitor’s actual quote. Drivers choose gigs themselves based on the fee, their location, schedule, and other work. They can drop a booking; a failed pickup can cost you money. Orders and gigs can also be cancelled, changed, or delayed. The rules spell out the account deductions, including partial refunds for late deliveries, full price plus a penalty for cars still undelivered at the end, and fines for some handling mistakes.

See the [official rules](https://spread.bahnexpress.com/kit/RULES.md).

## 2. The simulation

A **world** is one simulated week. In practice, the clock stays still until the code advances it. `advance` applies any supplied actions at the current simulated minute, then moves the clock and returns events. That lets practice runs be repeated with the same seed and actions.

A **ranking round** consists of five secret practice worlds at each level, shared across teams. Ranking worlds cannot be copied or revealed, and deleting one early does not remove it from the ranking.

The **final** is one secret level 8 world per team. Its clock moves by itself, so your system must respond to a live event stream. If the system stops, the final keeps running without it. These distinctions are documented in [HANDBOOK.md](https://spread.bahnexpress.com/kit/HANDBOOK.md) and [API.md](https://spread.bahnexpress.com/kit/API.md).

Events tell your dispatcher that something needs attention or has changed: examples include `price_request`, `order_won`, `visit_failed`, and `deadline_close`. Actions are your responses: quote a request, post or reprice a gig, withdraw a gig. Several events can arrive in one advance or stream update, and the starter handles them one by one.

The levels add complications. Level 8, which is also the final’s level, combines a shortage of drivers, uneven driver supply by town, a competitor that is more expensive than the list price, an unannounced price war, and dealer trust earned through on-time delivery. So the challenge is to balance two things: winning profitable orders and having enough driver capacity to deliver them on time. Winning every available order can make your score and ranking worse.

## 3. `dispatch.py`, function by function

Line references below refer to the current [`dispatch.py`](dispatch.py).

### State and event handling

- **`Retry` (lines 28–32)** is a small record of special instructions for retrying a pickup: when to try again, whether the driver needs a manual licence, and whether to bring plates.
- **`Desk.__init__` (39–48)** stores the `World`, level, and current simulated minute. It initializes memory for requests, orders, gigs, booked drivers’ gigs, urgent orders, and the outgoing action queue. It also creates a `PricingPolicy`. It makes no API call itself.
- **`Desk.rejoin` (50–84)** rebuilds that state after a restart from a `DeskSnapshot` and event history. It restores open gigs and active orders, reconstructs price learning from wins and losses, retries certain missed pickups, and quotes open requests. It receives the current snapshot and past events; it queues actions. It does not directly call an API.
- **`Desk.handle` (86–114)** dispatches one event to the relevant handler. A win records pricing feedback and creates gigs; a failed visit triggers a retry; a deadline warning raises fees. It receives a `DeskEvent` and usually queues actions.
- **`delivered` (116–120)** removes the delivered leg from the gig bookkeeping and updates the order’s `deliveredAt` value. It receives an order ID, leg number, and simulated delivery minute.
- **`quote` (121–123)** remembers the `PriceRequest` and queues a `quote` action. The prices come from `PricingPolicy.prices`. No API call yet.
- **`win` (125–128)** adds a newly won order to memory and posts its undelivered legs.
- **`change` (130–134)** updates an order after a change event. If it can withdraw the order’s gigs, it reposts the remaining undelivered work.
- **`repost` (136–149)** handles a gig whose window expired before a driver booked it. It removes the old gig’s legs from its internal mapping and queues a replacement post, with expired stop windows removed.
- **`raise_fees` (151–160)** marks an order urgent and reprices its gigs that no driver currently holds, using the steeper urgent schedule.
- **`fees_for` (162–165)** calculates the fee for a number of cars using the request’s `referenceFeeCents`, scaled by cars per order leg. It picks the ordinary rising schedule or steep urgent schedule.
- **`retry` (167–173)** reacts to a failed visit. For “not ready” or “closed”, it calculates a later pickup time; for licence or plate failures, it sets the relevant retry flag. It then posts that leg again.
- **`post` (175–186)** builds a post action with stops, driver audience, and fee schedule. Premium cars require experienced drivers. Low charge on an electric car sets `withCharging`. For multi-leg work, it tries one combined gig first; if the world rejects it (for example, because the trip would exceed the 12-hour driving limit), it sends that post and then tries one gig per leg if no gig was accepted.
- **`gigs_of` (188–190)** returns the distinct gig IDs currently associated with an order.
- **`carry` (192–196)** records a successfully accepted gig and maps its stops back to their legs.
- **`withdraw` (198–206)** ensures any queued post is sent, then refuses to withdraw if a driver already holds one of the gigs. Otherwise it clears the leg mapping and queues `withdraw` actions.
- **`send_post_of` (208–211)** sends queued post actions for an order immediately, so its gig IDs can be known before later bookkeeping.
- **`send` (213–217)** submits the queued actions with `world.act(actions)` and passes the results to `read_results`. In normal practice play, queued actions are usually sent with the next `advance`; this direct send is used when the code needs the result immediately.
- **`read_results` (219–224)** records the ID of each accepted post. It ignores rejected posts and non-post actions.

### Helpers for stops, fees, and notes

- **`retry_from` (226–233)** chooses when a failed pickup should be tried again. It waits at least two hours, and can account for a dealer’s moved deadline.
- **`undelivered` (235–237)** returns the leg indexes not marked delivered.
- **`pickups` (239–242)** counts how many pickup stops a gig contains.
- **`without_windows` (244–247)** removes a stop’s own time window when that window has already ended. This lets the world use its late-delivery rules for stops without a private booked slot.
- **`rising` (250–254)** makes a six-step schedule: the initial fee followed by 10% increases per hour, up to 1.5 times the starting fee. Level 1 uses one step.
- **`steep` (256–258)** makes the urgent schedule: starting at 1.5 times the fee and increasing by one quarter of the starting fee each half-hour, up to 2.5 times. Level 1 again uses one step.
- **`stops_for` (261–277)** creates pickup and delivery stops for each leg. It applies note-based windows, retry pickup timing, plates, and charging instructions. It returns stop records; it does not submit them.
- **`narrower` (280–281)** attaches a custom window only if it is tighter than the broader window.
- **`window_from_note` (294–326)** reads some clock times and opening-hour ranges from a note, based on keyword matches. It can narrow a pickup or delivery window. It is a limited reader: it does not understand every note or all the day, equipment, and car requirements described in the handbook.

### Running a world and the command line

- **`play_practice` (329–344)** snapshots the world, creates a `Desk`, and loops until the world ends. Each loop sends queued actions with `world.advance(until=WAKE_ON, max=..., actions=...)`, handles returned events, updates the clock, and prints a daily score report.
- **`play_final` (346–367)** reads past events and a snapshot, creates a desk, rebuilds its memory with `rejoin`, and sends any resulting actions. It then consumes `world.stream(...)`, updates its clock using events or the final clock, handles actions, sends them, and reports daily scores.
- **`report` (369–371)** formats a score as margin, revenue, order count, on-time share, and undelivered share. It only prints.
- **`next_final` (374–393)** checks which final world belongs to the team and waits until there is a live one. It uses `client.final()`, `client.world(...)`, and `world.snapshot()`. It retries when no final is set yet.
- **`main` (395–446)** parses `--level`, `--seed`, `--board`, and `--final`. It creates a `Client`; then either finds and runs the final, or creates a practice or ranking world and runs it. In practice mode it tries to delete a stopped practice world. It prints the ending score and ranking status.
- **`if __name__ == "__main__"` (448–449)** calls `main()` when you run the file directly.

### API calls made by this code

The starter uses the Python client methods provided by the kit. In `dispatch.py`, the main calls are:

| Call | Where | Purpose |
|---|---:|---|
| `Client()` | 403 | Reads the configured server URL and team key. |
| `client.create(...)` | 420 | Creates a practice or ranking world. |
| `world.snapshot()` | 331, 350, 386 | Reads the current world state. |
| `world.advance(...)` | 337 | Applies queued actions and advances a practice world to the next relevant event or midnight. |
| `world.act(actions)` | 217 | Sends queued actions immediately and gets their results. |
| `world.events()` | 349 | Reads event history to rebuild after a restart. |
| `world.stream(...)` | 357 | Receives live events in the final. |
| `world.score()` | 343, 364, 439 | Reads the current or final score. |
| `world.delete()` | 429 | Deletes an interrupted practice world when possible. |
| `client.worlds()` | 353 | Finds the level associated with the final world. |
| `client.final()` | 380, 359 | Finds the team’s final and reads its current clock. |
| `client.world(...)` | 380 | Gets a `World` handle for the final world ID. |

`pricing.py` is imported separately and does not make API calls. The API methods’ routes and semantics are described in the [official API reference](https://spread.bahnexpress.com/kit/API.md).

## 4. What the current decisions do

### Quotes

`quote` sends exactly the price dictionary returned by `PricingPolicy.prices` (`dispatch.py` lines 121–123). In [`pricing.py`](pricing.py), levels 1–3 quote the first option at list price (lines 25–28). At higher levels, it still quotes only the first option, with an adjustment based on past wins and losses for the same dealer, route lane, and option (lines 30–35, 37–54, 56–64). Each win nudges the adjustment up by 1%; each loss nudges it down by 1%. The factor is bounded between 5% below list and 8% above list at levels 4–6, or 16% above at levels 7–8. This is a simple adaptive rule, not a model of the competitor’s current price, delivery risk, or driver capacity.

### Gig creation

On a win, `win` posts the undelivered legs immediately (lines 125–128). `post` creates the ordered stops and applies driver eligibility and vehicle needs (175–186). It tries to bundle a trade-in, with a split into separate gigs if the combined post is rejected.

### Driver fees

Ordinary fees start from a per-leg share of the request’s typical driver fee, then rise hourly (162–165, 250–254). A deadline warning triggers steep fees for unbooked gigs (151–160, 256–258). This schedule is based on elapsed time and urgency; it does not estimate the driver’s actual cost for the route or use the driver roster.

### Failures

Failed visits cause the failed leg to be posted again, with a delay or added licence/plate requirement when the reason identifies one (167–173). Expired gigs are reposted after removing expired windows (136–149). If a driver already holds a gig, the starter avoids withdrawing it during a change of plan (198–206). These handlers help recover work, but recovery can still be costly and slow.

## 5. Weaknesses at level 8, and what to improve first

The official handbook gives a concrete example: on seed `spread-1`, the starter loses **€72,612.51** and delivers only **45.5%** of won orders on time, so it is not ranked. That is documented performance on that seed, not a guarantee for every week. The points below combine documented challenge mechanics with observations of this code.

1. **It wins too much work without checking whether it can deliver it.** It quotes the first option on every request (`pricing.py` 25–35), usually at or near list price. The rules say list price wins most level 8 requests, while the market has only about a third of normal driver capacity. That creates a large backlog and puts the 90% delivery minimum at risk.
2. **It doesn’t price by delivery risk or option.** It ignores all but the first option, even when the dealer accepts a slower option that could allow a feasible gig. It doesn’t weigh route difficulty, ready time, deadlines, competition, existing orders, or driver availability in a town before quoting.
3. **The fee policy starts too low for a shortage.** The rules say the typical fee is from a normal week and often finds no driver in shortage levels. The code starts at that typical fee and waits for hourly increases; its higher urgent fees come only at the deadline warning, three hours before the last on-time pickup. That can leave too little time for drivers to notice and reach the car.
4. **It does not plan around driver supply or work already in progress.** The roster is not queried. The code does not use gig views, bookings, or drops to estimate local capacity, and it does not reserve scarce capacity for orders likely to be profitable and on time.
5. **Level 8’s changes are mostly ignored.** Pricing only reacts to a coarse lane/dealer win/loss tally. There is no explicit detection of the price war, outage, flu, bulk order, or town-level driver shortage. The event loop can receive related events, but the decision policy does not use them to adjust quotes or dispatch choices.
6. **It can miss hidden car requirements.** `window_from_note` handles a subset of clock phrases. The documentation says notes can also reveal later readiness, manual transmission requirements, missing plates, tighter deadlines, actual site hours, and summer tyres. The starter doesn’t generally parse those facts. It handles `licence` and `no_plates` only after a visit has failed, which means avoidable failure costs.
7. **Its objective is poorly aligned with trust.** At level 8, on-time orders increase dealer trust and late orders halve it. The starter’s broad quoting can harm both immediate margin and future prices accepted by the same dealer.

### Improvement order

The most useful first change is **selective quoting**: predict whether an order can be delivered on time and profitably, and account for capacity already committed before accepting more work. Next, choose delivery options and fees based on route and time feasibility. Then improve note reading and failure avoidance. After that, refine price adaptation and dealer trust management.

The challenge mechanics above are documented in the official rules and handbook; the diagnosis of the starter’s missed opportunities is an inference from those mechanics and the inspected Python code.

## Official references

- [Challenge document index (`llms.txt`)](https://spread.bahnexpress.com/llms.txt)
- [RULES.md](https://spread.bahnexpress.com/kit/RULES.md)
- [HANDBOOK.md](https://spread.bahnexpress.com/kit/HANDBOOK.md)
- [API.md](https://spread.bahnexpress.com/kit/API.md)
