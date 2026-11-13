# How the kit starter works

Source: `spread/starter.py` in the kit wheel (~430 lines, ~200 of logic). Our `main.py` / `dispatch.py` / `pricing.py` / `config.py` are this code split into modules, verified identical to the cent on seed `l1-a` at default parameters.

1. `play_practice` loops: it sends the pending actions with `advance(until=WAKE_ON, max=midnight)`, then gives each returned event to a `Desk`.
   `WAKE_ON` = price_request, order_won, order_changed, order_cancelled, visit_failed, gig_expired, deadline_close.
2. `Desk` remembers requests, won orders, which gig carries each car (`leg_gigs`), booked gigs, each gig's original post, and orders that got `deadline_close` (`urgent`).
3. `price_request` → quote the first option at its list price.
4. `order_won` → post one gig per order (or one per car when a trade-in is too long for one gig).
5. Fee = typical fee × cars / legs. Normal schedule: 1.0×, +0.1× per hour up to 1.5× (**level 1 allows one step, so only 1.0×**).
6. `deadline_close` → reprice the order's unbooked gigs to the steep schedule: 1.5×, +0.25× per 30 min up to 2.5× (level 1: 1.5× only).
7. `gig_expired` → post the gig again without its stop windows, so the car can still go, late.
8. `visit_failed` → post the car again: 2 h later for `not_ready`/`closed`, with a manual-licence audience for `licence`, with plates for `no_plates`.
9. `order_changed` → withdraw and repost, unless a driver already holds the gig. `order_cancelled` → forget the order.
10. `window_from_note` narrows pickup/delivery windows from clock times near keywords in the note (matters from level 5).
11. `rejoin` + `play_final` rebuild state from the snapshot and event history, then follow the live stream (for the final and restarts).

## Measured (level 1)

- Seed `l1-a`: −€3,220.38, 94.2% on time, 990 orders, ranked.
- 10 seeds `l1-a` … `l1-j`: −€28,977.80 total, 93.6% on time, worst week 90.6%.
- On the level-1 ranking round "Friday 20:01", House starter scored −€31,659 over 5 weeks and was not ranked (one week under 90%).
- Why it loses: the typical fee is ≈ 0.9× the list price, so paying 1.0× the typical fee leaves no margin, and late cars cost refunds.
