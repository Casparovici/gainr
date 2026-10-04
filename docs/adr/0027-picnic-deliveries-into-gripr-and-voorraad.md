# 27. Picnic deliveries into gripr and Voorraad, and prices on linked products

## Status

Accepted

## Context

listr already reads the Picnic order history (ADR 0011's addendum). Two follow-ups were asked
for:

1. A delivered order should land where it matters without retyping it: as a gripr expense, and
   as stock in listr's Voorraad.
2. The products the reader linked to Picnic (the cart picker on a list) should show what they
   cost.

The reader already books some Picnic payments in gripr by hand, and not consistently: on
19 Sep 2026 one order's charge (groceries plus deposit) was booked on its order date;
for the 9 Sep delivery, one expense for the three orders' groceries without deposit
was booked five days later. Anything automatic must recognise both shapes, or switching it on
double-counts.

## Decisions

**Opt-in, with a start date.** A single-row `picnic_sync_settings` (off by default) holds the
gripr account and category to book on and a `since` date (defaults to the day it's switched on).
Only deliveries on or after `since` are processed, so turning it on never rewrites history unless
the reader picks an earlier date on purpose. Without an account and category it only restocks.

**Processed once per delivery.** `picnic_synced_deliveries` records each processed delivery and
what happened (orders booked, orders matched, units restocked), which is also what the order
history shows next to it. Booked expenses carry `source_ref = "picnic_order:<order id>"`.

**Match before booking.** For each delivery, first look for one hand-booked expense covering
the whole delivery, then one per order. A match is an expense on the chosen account for exactly
the charged amount (with deposit) *or* the groceries alone (without), dated from three days
before the first order to seven days after the delivery. A matched hand-entered row is tagged
with the order's `source_ref` so a later order can't claim it again; an imported row keeps its
own reference. Only unmatched orders are booked: on the order date, for the charged amount (what
Picnic debits), notes "Picnic". Verified against a copy of the real database before shipping:
both hand-booked payments above were recognised, and only one small order nobody had booked
would have been added.

**Restocking follows Voorraad's opt-in.** Every delivered product adds its number of selling
units to each catalog item linked to it, but only items already tracked in Voorraad; tracking
stays the reader's choice. This is the one automatic exception to ADR 0015's "the count is
manual"; the count/status rule itself moved into `listr_inventory_service` so the Voorraad
buttons and a delivery apply the same one.

**Prices from search, not the product page.** Picnic's product page carries the price only
inside display markup; its search results carry a clean `display_price` and `unit_quantity` per
product, and searching each linked product's name and taking the result with the same id found
all 33 linked products. Three columns on `grecipe_items` (`picnic_price` NUMERIC in EUR, the only
currency Picnic sells in; `picnic_unit_quantity`; `picnic_price_at`) are filled when a product
is picked and refreshed by `refresh_prices`: on demand ("Prijzen bijwerken" on Producten) and
daily. The same refresh also keeps the product's picture id (`picnic_image_id`, ADR 0028).

**When it runs.** Opening Picnic-bestellingen processes new deliveries (it has just fetched
them anyway); "Nu verwerken" does it on demand; and `scripts/sync_picnic.py` does both
processing and the price refresh from the existing daily timer (`gainr-refresh.service`), so it
happens without opening the app. The script never fails the unit over Picnic: without a session,
or during an outage, it logs and tries again the next day.

## Alternatives considered

- **Book every delivery, no matching.** Simplest, but double-counts the payments already booked
  by hand, which is exactly what the reader does today.
- **Book per delivery instead of per order.** Matches the 9 Sep hand booking's shape, but not the
  19 Sep one, and orders are what Picnic charges. Matching handles both shapes; booking stays
  per order.
- **Read the price from the product page.** One call per product like search, but the price sits
  in UI markup whose shape changes with Picnic's app, where search results already have a
  structured price this client parses.

## Consequences

- Hand-booked Picnic payments keep working as before; the automatic booking fills in only what's
  missing. An order booked by hand later than a week after delivery, or for an amount that
  matches neither the charged nor the deposit-free total (say, net of a deposit refund), won't
  be recognised and appears twice; the order history marks which deliveries were booked, so
  that's visible and fixable by deleting one.
- Deposit refunds for returned crates aren't booked.
- Picnic occasionally answers a burst of requests with an access-denied. That reads as an
  expired session and asks the reader to reconnect: safe, if occasionally unnecessary.
- The price is per Picnic selling unit and can't be compared to a list line's own quantity
  ("300 gram" vs "1 kilo"); the list's "≈ € … bij Picnic" estimate counts one of each, the same
  count-1 rule the cart push follows, so it's a floor rather than a quote.
