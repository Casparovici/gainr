# 31. Trading 212: card spending into gripr, fills and interest into gainr

## Status

Accepted

## Context

Trading 212 is one of the reader's two brokers and also their everyday debit card. Both run on a
single Trading 212 Invest account, in EUR with a USD cash wallet beside it:

- **gainr** keeps the investing side by hand under broker "Trading212" in the Main portfolio. On
  2 October 2026 it was short of what Trading 212 held in several holdings (buys
  not yet entered), and most of all in TDIV. That gap is about fifty auto-invest buys of €1–3 that
  Trading 212 makes from cashback and interest, which nobody types in.
- **gripr** keeps the card side as the account "T212 Debit". Every card payment is entered by hand
  with a category. Top-ups from ING arrive as transfers ING → T212 Debit, and money set aside to
  invest moves T212 Debit → Beleggen, the gripr account linked to Main (ADR 0014). At Trading
  212 itself both are the same cash, so that last transfer never shows up there.

Trading 212 has a public API (beta, `v0`). Probing it with a read-only key showed:

- `/equity/history/orders` gives every fill with ISIN, quantity, price, the cash it moved
  (`walletImpact.netValue`, fees included), the FX rate and the fees. Some fills are paid from the
  USD wallet, with the net value in USD. `initiatedFrom: AUTOINVEST` marks the auto-invest buys.
- `/equity/history/dividends` gives each dividend in euros.
- `/equity/history/transactions` lists card payments only as anonymous `WITHDRAW`s, the same as a
  withdrawal to a bank. The **CSV export** (`POST /equity/history/exports`, written in the
  background, then downloaded from a pre-signed link) has `Card debit` rows with **merchant name
  and category**, plus `Deposit`, `Interest on cash` (EUR and USD, daily), `Spending cashback` (per
  payment) and `Currency conversion`. Listing exports is limited to about one call a minute, so
  collecting an export takes a minute or two.
- Authentication is HTTP Basic with a key and secret. The key is generated read-only (no order
  execution) and restricted to the home connection's IP address.
- Trading 212 isn't reachable through Enable Banking (ADR 0029), and doesn't offer PSD2
  account-information access of its own.

The reader decided four things:
- Card payments the sync books take the category last given at that merchant.
- gainr books fills and dividends only from the day the sync is switched on, not back-filled.
- Instruments are found by an ISIN stored on the asset.
- Interest and cashback go to gainr as one combined deposit a week, not a row per day.

## Decisions

**One provider, two syncs.** `trading212_provider.py` is the only module that talks to Trading
212. It reads fills, dividends and the CSV export, and nothing else: it has no call that could
place an order. Its input is treated as untrusted:
- amounts are parsed as finite `Decimal`s, text is trimmed and length-capped;
- pagination only follows Trading 212's own `/api/v0/` paths;
- the export link must be https, and is downloaded without the credentials.

The key lives in the server's environment (`GAINR_T212_API_KEY`, `GAINR_T212_API_SECRET`). A 401
or 403 is reported as "check the key and the allowed IP", because a changed home IP address is
the likely cause.

**gripr: Trading 212 is a third bank connection.** `bank_connections.provider` says how a bank is
read: `enablebanking`, or `trading212` with no consent. "Connected" then means the key is set, and
there is nothing to connect, renew or end. Trading 212's single account (keyed `T212`) maps to T212
Debit like any bank account. Only the card's own activity reaches gripr:

- `Card debit` (and any other card row) becomes a bank entry with the merchant as the
  counterparty and the merchant category as the description: "Netflix — Utilities". It runs
  through the same steps as ING: match a hand entry, else fulfil a recurring rule, else book.
- When a card payment is booked rather than matched, it takes the **category of the most recent
  card payment at the same merchant** (normalised name), learned from rows the reader entered
  that were matched, or from booked rows they categorised later. A new merchant stays
  uncategorised. Only expenses teach categories.
- `Deposit` and `Withdrawal` say nothing about the other side. Like Trade Republic's entries
  (ADR 0029, check mode), they wait two days and may then claim a row another bank booked. That's
  how a top-up claims the ING → T212 Debit transfer the ING sync booked through the Adyen rule.
- Transfers between T212 Debit and the gripr account linked to the portfolio Trading 212 books
  into (Beleggen) are never matched by a Trading 212 entry: at Trading 212 they're the same cash.
- Interest, cashback, trades, dividends and currency conversions are left to gainr.

`bank_synced_transactions.merchant` records each card entry's merchant for the category lookup.

**gainr: a broker sync.** `broker_connections` has one row (`Trading212`, seeded off) with the
portfolio it books into, a start date, and the instruments held back for lack of an asset.
`broker_synced_items` records every handled fill, dividend and week, keyed as the booked row's
`source_ref` (`t212:fill:<id>`, `t212:dividend:<ref>`, `t212:week:2026-W40`), so each is booked
once. It runs from the daily timer after the bank sync, or with "Sync now" in gainr's settings:

- **Fills** are booked as Buy/Sell for the cash they moved. `total_eur` is Trading 212's net
  value, `costs` its fees, and `value_eur` the difference. A fill paid from the USD wallet is
  converted at that day's EUR rate (point-in-time, via `price_service`), because Trading 212
  converted nothing. A fill matching a row already entered (same asset and quantity within 2 days,
  or a day's fills against that day's rows when the totals agree) is matched, not booked. A fill
  whose instrument currency differs from the asset's is held back with a message rather than
  booked in the wrong unit.
- **Dividends** are booked in euros, or matched to a Dividend of the same asset within 5 days
  and €0.02.
- **Interest and cashback** are summed per completed ISO week (Monday–Sunday, USD interest
  converted at the day's rate) and booked as one **Deposit** on the Sunday: "Trading 212: interest
  €0.84 + cashback €2.31, week 40 (28 Sep–04 Oct)". This is the cash the auto-invest buys spend. The
  export is only requested when a completed week is still unbooked, so about once a week.
- **Assets are found by ISIN** (`assets.isin`, not unique: an ISIN on two assets is held back with
  a message rather than guessed). A record for an unknown ISIN is held back and listed on the
  settings dialog (the gear in gainr's top row). The reader picks the asset it is, or adds one there (Yahoo listing picker
  included). The next run reads back to the oldest held record, however long ago it was.

**Daily timer.** `gainr-refresh.service` gained `scripts.sync_brokers` and now loads
`/etc/gainr/env`. Before, it ran the Picnic and bank syncs without the secrets the app runs with,
so their scheduled runs would have failed for want of credentials. The unit is installed by hand
on the server, as `deploy.sh` doesn't install units.

## Alternatives considered

- **The JSON transactions endpoint for the card**: one fast call, but every card payment reads
  `WITHDRAW` with no merchant. That's indistinguishable from a withdrawal to the bank, and nothing
  to categorise from.
- **Interest as gainr `Interest` rows**: the right type for a time-weighted return, since
  `Deposit` counts as money coming in, not as a return. The reader chose one combined weekly
  deposit to keep the ledger readable. Cashback is arguably money from outside anyway, and the
  interest is a few euros a month.
- **Auto-creating assets from an unknown ISIN** (Yahoo search by ISIN): less work, but a wrong
  listing (an American namesake, a different exchange's currency) could slip in unseen. The reader
  chose to link them.
- **Back-filling gainr from the first Trading 212 order**: possible with the same matching, but
  more old hand-entered rows to reconcile. The reader chose to start from the day it was switched
  on and fix the existing gaps (the TDIV auto-invest buys, GRID, JEDI) separately.

## Consequences

- Collecting an export takes a minute or two, so gripr's "Sync now" is slower when Trading 212 is
  on. The daily run doesn't mind.
- The key is restricted to the home IP address. If the provider changes it, both syncs report the
  refused key on their cards until the allowed IP is updated in the Trading 212 app.
- A USD-wallet fill is valued at the day's closing rate, not the rate of the conversion that
  eventually funded it. Currency conversion fees in the export aren't booked anywhere yet.
- T212 Debit becomes bank-fed. Its recurring rules (Allianz, Netflix) stop booking their own rows
  and wait for the card payment, as on ING.

## Addendum: moved to settings (2026-10-05)

The sync's card left the Transactions page for a gear in the top row of every gainr page, like gripr's.
A sync that needs attention shows in the notifications bell, which is where the card's status line was
the only other place to see it.

## Addendum: cashback and interest are told apart (2026-10-05)

The weekly batch used to be one Deposit in gainr for interest and cashback together. They're different
money: the interest is cash earned in the Invest account, while the cashback (1.5% of card spending,
invested in a pie once it reaches €1) is income the reader wants to see in gripr. The pie is TDIV, so its
auto-invest buys are fills in Main's existing TDIV position, and the cashback is the cash that pays for
them. With a cashback account chosen in gainr's settings
(`broker_connections.cashback_account_id`, the gripr account linked to Main), a completed week books:

- the **interest** as an Interest row in the portfolio's cash on the Sunday (`t212:week:<week>`);
- the **cashback** as a Deposit in the same portfolio (`t212:cashback-deposit:<week>`), so Main's cash
  matches Trading 212's, and as income in that gripr account under the Cashback category
  (`t212:cashback:<week>`), so income overviews count it. Net worth doesn't count it twice: a linked
  account takes its balance from the portfolio, not from its transactions.

Without a cashback account both stay one Deposit, as before. gripr's separate Cashback account was
retired once the pie's earlier shares were added to Main's TDIV position.

## Addendum: card payments match within two days (2026-10-06)

A card entry carries the day the payment was made, so the row entered for it is dated the same, give
or take a day. The generic 7-day matching window (ADR 0029, made for banks that report a payment days
late) let a Jumbo payment of €16.75 on the 5th claim the hand-entered €16.75 of the 1st, which the sync
never reads because it predates the start date, so the payment was never booked. Card payments now match
within two days; top-ups and withdrawals, which can post days after the transfer, keep seven.

