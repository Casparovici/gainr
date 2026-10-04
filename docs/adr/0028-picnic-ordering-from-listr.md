# 28. Ordering from listr: the Picnic cart, delivery slots and checkout

## Status

Accepted. The cart and slot calls are verified against the live account; checkout is built
on `picnic-api`'s documented flow and was deliberately **not** run against the live account
during development (it places a real, paid order), so its first real use is the reader's own.

## Context

Until now listr could only *add* to the Picnic cart ("Push naar Picnic", ADR 0011); choosing a
delivery time and ordering meant switching to Picnic's app. The reader asked to do both in
listr, and to see product pictures there.

Picnic's private API (as documented by the open-source `picnic-api` client, 4.10) covers it:
`GET /cart`, `POST /cart/add_product` / `remove_product`, `GET /cart/delivery_slots`,
`POST /cart/set_delivery_slot`, and checkout as `POST /cart/checkout/start` (with the cart's
modification timestamp `mts`), then `POST /cart/checkout/initiate_payment`, which returns the
bank's payment page (iDEAL), then `GET /cart/checkout/{transaction}/status` until `FINISHED`,
or `POST /cart/checkout/cancel`. Product pictures are public at
`/static/images/{image_id}/{size}.png`.

## Decisions

**Money only moves on the reader's own bank approval.** listr never pays. Ordering starts
Picnic's checkout and sends the reader to their bank's payment page; the order is placed only
when they approve the payment there, exactly as in Picnic's app. Abandoning it cancels the
checkout.

**An order is only started for the cart the reader saw.** The page shows the cart's version
(`mts`) and ordering sends that version back; Picnic refuses a checkout for any other, so an
order can't silently include something added meanwhile (in Picnic's own app, say). A confirm
dialog states the item count, the amount and the delivery window before going to the bank.

**A slot has to be chosen, not just accepted.** Picnic preselects a slot ("IMPLICIT"); ordering
stays disabled until the reader picks one, so a delivery never lands at a time nobody chose.
Full and closed windows stay visible (greyed, "vol") so it's clear why a time isn't offered.
The cut-off for the chosen window and any minimum order value are shown.

**The trip to the bank and back.** The bank returns to listr's cart page (`app_return_url`);
the pending payment is kept in the browser's localStorage for an hour so the page can pick up
where it left off, and it polls Picnic's status every few seconds until the order is placed.
Picnic is the record; the local note is only a convenience, and losing it loses nothing.

**Pictures are Picnic's own, linked directly.** The image id comes with search results and cart
lines; a linked catalog item stores it (`grecipe_items.picnic_image_id`, saved when picked,
refreshed with the price, ADR 0027). The browser loads the picture from Picnic's public URL.

## Alternatives considered

- **Hand off to Picnic's app for checkout.** Safest, but exactly the switch the reader wanted to
  avoid; the bank approval already gives the same guarantee.
- **Test checkout against the live account during development.** Would have meant placing and
  paying for a real order (or relying on cancel behaving as documented) without the reader
  having asked for one. Not done; the flow is unit-tested with a fake provider, and the first
  live order is the reader's own.

## Consequences

- If Picnic changes the checkout flow, ordering fails with Picnic's own message (shown as-is);
  it can't over-charge, since payment is still the bank's step.
- Inside the Android app the bank page opens in the app's web view; whether the banking app
  hands control back cleanly depends on the bank. If it doesn't, reopening the cart page picks
  up the pending payment, or it can be cancelled from there.
- Product pictures load from Picnic's servers, so Picnic sees those requests, as it already
  does for every Picnic call this app makes.

## Addendum (October 2026): Aanbiedingen

listr also shows this week's offers (`/listr/aanbiedingen`, linked from the cart), so something
on offer can go into the cart with one tap. `picnic-api` has no call for them; they come from
the page Picnic's app opens for its Aanbiedingen tab, `GET /pages/promo-page-root` (found via the
`nl.picnic-supermarkt://store/page;id=promo-page-root` link on `category-tree-root`).

- It's a ~3 MB Fusion page: sections (a BLOCK per section, titled by its first text; the personal
  "Keuzekorting" box is a SUSPENSE block) holding product tiles. A tile's analytics context
  carries the offer (`promotion_label`, and `strikethrough_price` when Picnic shows one) and the
  tile contains the product's `sellingUnit`, the same structure search results use. On the live
  page that gave 24 sections and 203 offers.
- Parsed defensively: anything that doesn't match is skipped, so a change to Picnic's page shows
  fewer offers (or none) rather than an error. Fetched at most once per calendar day (offers
  run for a week); an empty result isn't kept, so a failed read is retried on the next visit.
- Adding an offer is an ordinary `POST /cart/add_product`: Picnic applies the promotion in the
  cart itself, so listr doesn't compute discounts.
