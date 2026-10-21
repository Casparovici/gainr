# 29. ING transactions into gripr via Enable Banking

## Status

Accepted

## Context

Most of gripr's ledger is ING: about 10,300 of 12,800 transactions sit on the ING current
account, all typed in by hand or booked by a recurring rule. The roadmap asked for ING
transactions to arrive in gripr by themselves, leaving the reader only the categorising.

ING's own developer portal only serves its PSD2 APIs to licensed third parties: production calls
need eIDAS certificates (QWAC/QSeal), which are issued to companies, not individuals.
GoCardless Bank Account Data (formerly Nordigen), the usual free route for individuals, stopped
taking sign-ups in July 2025.

A comparison of September 2026's real ING entries against the hand-entered gripr rows found
that 65 of 93 lined up one-to-one (same amount and direction within a week, 62 on the same day).
The rest showed how hand entry and the bank differ:

- several bank lines merged into one entry (two health-insurance premiums as one entry, two
  other insurance premiums as one);
- recurring rules whose amount differs from what's actually paid (a salary rule a few hundred euros
  below what's actually paid);
- savings-pot transfers (ING → Afschrijving Auto, Onderhoud Auto, Reservering Vakantie, …) that
  are really one transfer from ING to Trade Republic (one transfer on 25 Sep is exactly their sum);
- payments never entered at all.

## Decisions

**Enable Banking, in its free restricted mode.** Enable Banking Oy is an account-information
provider licensed by the Finnish FSA (Fin-FSA) under PSD2. Its restricted production mode gives
real data, free, for accounts the app owner links themselves, which fits a single-user app. The
app is registered in Enable Banking's control panel; every call carries a short-lived RS256 JWT
signed with the app's private key. That key lives on the server outside the repo
(`/etc/gainr/enablebanking.key`, root-only), named by `GAINR_ENABLEBANKING_KEY_PATH`, next to
`GAINR_ENABLEBANKING_APP_ID` and `GAINR_ING_REDIRECT_URL`. Access is read-only (AIS): nothing
here can move money, and the ING login happens at ING, so bank credentials never pass through
gripr. `enablebanking_provider.py` is the only module that talks to it, so moving to another
aggregator touches one adapter.

**One consent, keyed on IBANs.** "Connect ING" on the Accounts page starts a consent for the
maximum ING allows (180 days; 179 requested). The reader approves in the ING app and comes back
to `/api/gripr/ing/callback`, which checks the one-time `state` the consent started with before
turning the code into a session. The redirect URL comes from config, not the request. The
consent covers ING's current accounts only: ING doesn't expose Oranje Spaarrekeningen through
PSD2. Enable Banking gives an account a new uid on every consent, so `ing_sync_accounts` keys on
the IBAN, and reconnecting keeps the reader's choice of gripr account per ING account. A consent
that expires or is revoked is noticed on the next sync: the session is cleared and the card asks
for a reconnect.

**Opt-in, with a start date.** Like the Picnic sync (ADR 0027), it books nothing until switched
on, and never anything dated before `since`. The reader switched on from 3 Oct 2026, the day
after their last hand-entered ING row. Each run re-reads from a week before the previous run, so
entries ING books late are still picked up; `ing_synced_transactions` records every handled
entry by ING's own `entry_reference`, which makes re-reading harmless.

**Each new entry, oldest first, gets the first of these that applies:**

1. *The incoming half of a transfer between two synced ING accounts* (ING → a child's account) is
   skipped. The outgoing half books it once.
2. *A row already in gripr is claimed*: same amount, same direction on that account, dated
   within 7 days, not claimed by another entry. This covers the hand entries around the
   switch-over and the expenses the Picnic sync books (in either order: the Picnic sync's own
   matching also recognises an ING-booked expense).
3. *It fulfils a recurring rule* on that account: due within 5 days, amount within 10% of the
   rule's. It's booked for what the bank actually moved, under the rule's category (so a
   loan-linked category still moves the loan balance), and the rule moves on to its next
   occurrence. A rule whose name appears in the counterparty or description beats one that only
   fits, then the closest amount, then the closest date. A transfer the bank already recognises
   as one fulfils only a transfer rule, and the bank's other side wins over the rule's.
4. *Otherwise it's booked*: as a transfer when the counterparty is one of the reader's own
   accounts, else as an uncategorised expense or income. The notes carry the counterparty and the
   description (ING's "Omschrijving", without the IBAN/Kenmerk/Valutadatum lines), and the date
   is the transaction date rather than the booking date, as hand entry did.

**Recurring rules on bank-fed accounts stop booking.** A rule whose account or counter account
is fed by ING (sync on and the account mapped) books no rows: the bank's entry is the real
occurrence, and step 3 files it under the rule. Booking both would count every payment twice,
with the rule's estimate next to the real amount. `generate_due` only drops an occurrence that
was pre-booked before the account was bank-fed, and moves a rule on once its window has closed
without a bank entry, so a skipped month doesn't leave it stuck. Rules keep projecting into
Upcoming and Budget's recurring-based suggestion. Switching the sync off, or disconnecting,
makes them book again.

**Own accounts are counterparty rules.** Another synced ING account is recognised by IBAN
automatically. Anything else is a rule: an IBAN, a text the counterparty name or description
must contain, or both, plus the gripr account on the other side. Text matching ignores case,
spaces and punctuation, so a savings account typed as "B 145-58977" finds "Naar Oranje
spaarrekening B14558977". Both fields are for a payment processor's IBAN that many merchants
share: Trading 212 and HEMA both arrive from the same Adyen IBAN. The most specific matching rule
wins.

**Setup applied at switch-on.** Following this ADR, the reader's data was changed once:
- current accounts were added for the two children's
  Kinderrekeningen;
- the savings-pot rules (Afschrijving/Onderhoud Focus/107, Reservering vakantie, Beleggen
  kinderen) now start from Trade Republic instead of ING;
- the children's pocket-money rules point at their new current accounts;
- four counterparty rules were added: the Trade Republic IBAN, Trading 212 via Adyen, and both
  Oranje Spaarrekening numbers.

**When it runs.** `scripts/sync_ing.py` runs after the Picnic sync from the daily timer
(`gainr-refresh.service`); "Sync now" runs it on demand. Like the Picnic script, it never fails
the unit: no consent means nothing to do, and an outage is retried the next day.

**Finding what to categorise.** The Transactions category filter gained "Uncategorized"
(expenses, income and refunds without a category; transfers never have one), and the card's sync
result links straight to it.

## Alternatives considered

- **ING's own API.** Needs eIDAS certificates only a licensed company can get.
- **Import ING's CSV/CAMT export.** No third party involved, but not automatic: the reader would
  still download a file every few days. The roadmap asked for automatic.
- **Keep recurring rules booking, and match the bank against their rows.** Only works when the
  amounts are exact. September showed they often aren't, and every mismatch would be a duplicate
  pair to clean up by hand.
- **Book everything uncategorised and ignore recurring rules.** Simpler, but throws away the
  category the reader already maintains for most of the fixed costs.

## Consequences

- A third party, licensed and supervised, sees the ING transactions it relays. The private key
  is the sensitive part: with it and the app id, someone could read (never spend) ING
  transactions until the consent ends. It never leaves the server, and deleting it in Enable
  Banking's control panel revokes it.
- The consent has to be renewed every 180 days; the card warns two weeks ahead.
- Where hand entry used to merge bank lines, each line now gets its own row, and a rule whose
  amount is far off (health insurance booked as one entry, paid as two premiums) no longer fulfils.
  Those lines arrive uncategorised until the rule is split to match the bank.
- The ING credit card isn't available through PSD2. Its monthly settlement ("Incasso ING
  creditcard") arrives as one expense on ING. A counterparty rule can make it a transfer to the
  Creditcard account instead, if card purchases are booked there.
- Restricted mode is free today. Enable Banking could change that, as GoCardless did; the
  provider adapter and the CSV import path are the fallback.

## Addendum: one connection per bank, starting with Trade Republic (2026-10-02)

Trade Republic, where the reader's everyday card account is, is also reachable through Enable
Banking (its connection is marked beta there; consents last 90 days). Rather than a second copy of
the ING sync, the sync became bank-agnostic:

- **One row per bank** in `bank_connections` (seeded by migration: ING, Trade Republic), each with
  its own consent, on/off switch, start date and `source_prefix`. The `ing_*` tables became
  `bank_*`; ING's settings, account mapping, rules and handled entries carried over unchanged.
  Every handled entry, and the gripr row it books, is referenced as `<prefix>:<entry reference>`
  (`ing:…`, `tr:…`), so two banks' references can't collide. The registered callback
  (`/api/gripr/ing/callback`) finishes every bank's consent; the one-time state says which.
- **All banks sync in one pass**, oldest entry first across banks, so a transfer between two
  banks is booked once, from its outgoing half. The incoming half is skipped only from the
  sending bank's own start date. Before that date, that bank isn't booking anything, so the
  receiving side books the transfer itself. A bank that can't be read (no consent, an outage) is
  reported and skipped; the others still sync.
- **Own-account rules apply to every bank.** An account synced from any bank needs no rule.
- **Recurring transfers only defer to the bank when the bank can see both sides.** A transfer
  rule now lets the bank stand in for it only if one side is bank-fed *and* the other is
  recognisable: also fed, or the target of a counterparty rule. A transfer into a purely virtual
  pot (Onderhoud Auto: money set aside inside gripr that no bank ever moves) keeps booking its own
  rows once Trade Republic is fed. Afschrijving Auto, which the bank does see (as the TDIV purchase
  the counterparty rule points at), defers to it. This also matches the ING setup: a rule
  into an account gripr can't recognise in bank data couldn't be fulfilled anyway.

### Trade Republic sends amounts only: check mode

Trade Republic's real data settled the open question. Through Enable Banking, each entry carries
only a booking date, a signed amount and a credit/debit indicator: no counterparty, no
description, no IBAN, no entry reference. It also ignores `date_from` and pages through the whole
history, and reading too often hits its PSD2 rate limit (`ASPSP_RATE_LIMIT_EXCEEDED`). Nothing in
an entry can be categorised from, so the reader keeps entering Trade Republic payments by hand,
and the sync **checks** them instead of replacing them:

- `bank_connections.amount_only` (set for Trade Republic) marks a bank like this. Its entries are
  matched against existing rows exactly as before (same amount, same direction, within 7 days).
  Of 100 real entries from August–October, 77 matched a hand entry; only 12 matched on the same
  day, because Trade Republic books card payments a few days after the purchase. Whatever doesn't
  match is booked uncategorised, noted as not entered by hand, so gripr's Trade Republic balance
  agrees with the bank.
- An amount-only bank's entries are handled only **two days after it booked them**. By then the
  reader's own entry, or the other bank's half of a transfer, is in gripr first.
- **Transfers with ING are booked by ING.** ING knows the counterparty IBAN; Trade Republic doesn't.
  So ING's incoming half from Trade Republic is booked rather than skipped as a counterpart, and
  Trade Republic's half matches the row ING booked. Claims are per bank: a row one bank booked and
  claimed is still claimable by another bank's half.
- **Amount rules.** A counterparty rule can match an exact amount around a day of the month (±3
  days). "this exact amount around the 2nd → Afschrijving Auto" turns the monthly TDIV savings plan into a
  transfer into the account linked to gainr's Auto portfolio, mirrored there as a deposit. The same amount
  purchase mid-month stays an expense. It also makes Afschrijving Auto recognisable, so its
  recurring rules defer to the bank instead of booking two partial amounts next to the real one.
- Amount rules can also have a **ceiling** and a **direction**. Trade Republic's saveback is two
  entries a month: the reward coming in around the 1st (at most €15) and the same amount invested in
  an S&P 500 fund around the 2nd. "Money out, up to €15, around the 2nd → Cashback" books the
  purchase as a transfer into the Cashback account. The reward itself stays uncategorised income for
  the reader to file; the direction keeps the rule from reading the reward as the purchase. The kids'
  savings plan is the same shape as TDIV's: "money out, a fixed amount around the 2nd → Beleggingsrekening
  kinderen", mirrored as a deposit in the Kids portfolio. A card payment you didn't enter that fits a
  rule (a €6 purchase on the 3rd, under the saveback ceiling) would be read as that rule. Payments you
  did enter are matched first, so this only affects ones missing from gripr.
- Debits arrive signed ("-121.000000"); only the size is kept. Entries without a reference get one
  derived from account, date, direction, amount and their position among otherwise identical
  entries, so two €3.95 coffees on one day stay two. Paging stops at the first page with nothing
  on or after `date_from`, which keeps a daily run to one read.

**TDIV purchases in gainr: cash only.** Without a quantity in the bank data, the purchase is booked
as the cash it is, a deposit in the Auto portfolio. The reader enters the Buy with the exact
number of shares from the Trade Republic app, rather than gripr estimating it from the closing
price. The existing holding was entered as an opening
deposit and Buy on 2 Oct 2026, and Afschrijving Auto was then linked to Auto.

### Virtual pots

Onderhoud Auto and Reservering Vakantie are money set aside on paper. It really sits in the Trade
Republic account, and the reader books spending from them directly on the pot (a car
repair on Onderhoud Auto). The bank sees that spending as a Trade Republic debit, and never sees the
monthly move from Trade Republic into a pot. Left alone, that would cause two problems: a pot
expense would be booked a second time as "not entered" on Trade Republic, and a real €75 card
payment could be matched against the €75 set aside for car maintenance and never booked.

`pefi_accounts.held_in_account_id` marks an account as a pot inside another (one level deep: a pot
can't hold pots). The sync then treats the parent and its pots as one account at the bank:
- expenses and income on a pot count as the parent's bank entries;
- a transfer between the parent and its own pot never matches a bank entry;
- a recurring expense paid from a pot waits for the bank and is booked back on the pot, under the
  rule's category;
- a recurring move into a pot keeps booking, because the bank never sees it. This holds even if a
  counterparty rule happens to name the pot.

### Amount rules are for amount-only banks (2026-10-03)

A rule that matches only on amount, date and direction now applies only to entries from a bank
that sends nothing else (`amount_only`). Once Trading 212 was fed, an €8 Jumbo card payment on
2 October matched the saveback rule (money out, at most €15, around the 2nd) and was booked as
a transfer to Cashback. ING and Trading 212 name the other side, so they never need such a rule.

The saveback rule itself was then removed: cashback is a Trading 212 feature (1.5% of every T212
Debit card payment, invested in a pie once it reaches €1), not a Trade Republic one. It's handled
by the Trading 212 sync (ADR 0031): the cashback is part of gainr's weekly deposit, and the pie
buys are booked as fills.

### Recurring rules don't wait for an amount-only bank (2026-10-03)

Waiting for Trade Republic made its accounts' recurring payments late: its entries arrive two or
more days after it books them, which is itself often days after the payment. An amount-only bank
no longer counts as feeding its accounts. Their rules book on their own due date (pre-booked two
days ahead, as anywhere else), and the bank's entry checks the row off when it arrives. Rules must
then match what the bank actually does: the TDIV plan became one rule due on the 2nd instead of two
partial ones on the 25th, and the kids' plan moved to the 2nd.

### Trade Republic is read once a day (2026-10-04)

Trade Republic answered `429 ASPSP_RATE_LIMIT_EXCEEDED` after four syncs in a day: it ignores
`date_from`, so each read paged back until a page held only older entries, two requests per sync,
and "Sync now" read it as often as the morning run did. Paging now stops at the first page that
reaches back past `date_from` (one request), and an amount-only bank is read only by the scheduled
morning run; its entries wait two days anyway. A refused read is reported as "trying again
tomorrow morning" and doesn't ask Enable Banking about the session, which isn't the problem.

### Addendum: Trade Republic no longer waits; a hand entry claims the row (2026-10-06)

Waiting two days after Trade Republic booked an entry (on top of the days it takes to book a card
payment) made the connection feel useless, and the wait only existed so the reader's own entry came
first. It now runs the other way round:

- **No grace for an amount-only bank.** Its entries are handled on the next scheduled run (Trade
  Republic is still read once a day). Entries that don't say who's on the other side but come from a
  bank that otherwise can (a Trading 212 deposit or withdrawal) keep the two-day wait
  (`ANONYMOUS_GRACE_DAYS`), because they look for the other bank's half of a transfer.
- **A hand entry takes over the row.** `POST /gripr/transactions` goes through
  `bank_sync_service.create_or_claim`. If an amount-only bank already booked a plain expense or income
  of the same amount on that account (or the account a pot sits in) within `MATCH_DAYS`, still
  uncategorised and unclaimed (`bank_synced_transactions.outcome = 'booked'`), the entry updates that
  row instead of creating a second one. It keeps its `source_ref`, and the record moves to
  `outcome = 'claimed'` so it can't be claimed twice. Closest date first, so two identical coffees
  are two rows claimed by two entries. A row the reader has categorised is theirs: a later entry of the
  same amount is a new transaction. Transfers and refunds are never claimed.
- **Entries that can't say who's on the other side are handled last**, whatever their date, so the
  other bank's entry from the same run (ING's half of a transfer) is already in gripr. Trade Republic
  dated the 12th no longer books a transfer before ING's entry of the 13th can.

Not covered: an ING entry that only shows up in a *later* run than Trade Republic's half of the same
transfer. Trade Republic then books its half uncategorised and ING books the transfer, leaving one
row to delete by hand. It needs ING to post later than the daily run reads it.

### Addendum: categories learned per counterparty, matched loosely (2026-10-09)

A payment the bank sync books takes the category the reader last gave a payment to the same
counterparty. Trading 212 names the merchant; for ING the counterparty name stands in. Matching on
the exact name learned almost nothing: ING spells the same shop differently per payment (a branch
number, a city, a card terminal, a payment provider such as "via Rabo Smart Pay" or "BY BUCKAROO").

- **`bank_synced_transactions.merchant` holds a matching key**, not the exact name
  (`bank_sync_service.normalize_merchant`). It drops the payment provider, digits, punctuation and
  filler words, then keeps the first word, or the first two when the first is short or only says what
  kind of place it is ("restaurant", "nederlandse", ...). "Albert Heijn 1234 Amsterdam" and "ALBERT
  HEIJN 5678 UTRECHT" share "albert"; "Nederlandse Spoorwegen" and "Nederlandse Gereformeerde Kerk"
  stay apart. Rows recorded before the change were re-keyed by `scripts/rekey_merchants.py`, from the
  counterparty still in a bank-booked row's notes.
- **Filing similar ones is offered, never automatic.** After the reader categorises a bank-synced
  transaction, `GET /gripr/transactions/{id}/similar` counts the *uncategorised* transactions with the
  same key, and the page offers to file them too (`POST .../apply-to-similar`, through the transaction
  service so a loan-linked category keeps its effect). Transactions the reader already filed are never
  touched.

The key is a heuristic: two different shops whose names start with the same distinctive word
("Albert Heijn" and a hypothetical "Albert's Bikes") share a key. A learned category is only ever a
suggestion the reader sees and can change, and "apply to similar" says how many it will file before it
does.
