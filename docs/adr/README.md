# Architecture decision records

One file per decision that shaped the schema, a data source, caching or the app's structure:
the context, what was decided, the alternatives, and the consequences. Numbered in the order
they were made; a later ADR or an addendum records when a decision changed.

| ADR | Decision |
|---|---|
| [0001](0001-performance-series-cache.md) | Cache gainr's daily performance series in memory |
| [0002](0002-target-weight-allocation.md) | Target allocation weight: nullable column + a cash singleton |
| [0003](0003-loan-linked-category-balance-adjustment.md) | Loan-linked categories adjust the loan balance via reverse-and-reapply |
| [0004](0004-gripr-period-boundary.md) | A configurable period-start-day, not just calendar months |
| [0005](0005-listr-module.md) | listr: a third module, filename-prefixed like gripr |
| [0006](0006-listr-meal-planning.md) | Recipe categories (many-to-many) and meal-plan history |
| [0007](0007-listr-ics-calendar-feed.md) | Read-only ICS feed, published via Tailscale Funnel on its own port |
| [0008](0008-household-tailscale-access.md) | Household access is a Tailscale device share, not a login |
| [0009](0009-android-capacitor-wrapper.md) | Android app: Capacitor wrapping the live site, not a second frontend |
| [0010](0010-gripr-inline-rename-and-bank-logos.md) | Inline-rename pattern + a fixed bank-logo catalog |
| [0011](0011-listr-picnic-integration.md) | Picnic: a hand-rolled Python client, cart push as count-1, recipe import from the instructions tab |
| [0012](0012-gardnr-module.md) | gardnr: a fourth module, garden map as an in-app shape editor rather than a photo |
| [0013](0013-backup-strategy.md) | Daily off-box backup of portfolio.db via rclone |
| [0014](0014-gripr-gainr-portfolio-bridge.md) | gripr↔gainr bridge: transfers mirror as transactions, market movement only as a balance |
| [0015](0015-listr-inventory.md) | listr Voorraad: status is manual, then later derived from a count vs. a minimum |
| [0016](0016-position-journal.md) | gainr Journal: same rows as the position Notes tab, plus global many-to-many labels |
| [0017](0017-cash-by-broker-and-transfers.md) | Cash per broker, and a Transfer type separate from Deposit/Withdraw |
| [0018](0018-gripr-savings-goals.md) | gripr: savings goals for transfers into savings/investment accounts |
| [0019](0019-gainr-multi-portfolio.md) | gainr: multiple portfolios, each with its own ledger, positions, and performance |
| [0020](0020-gripr-future-dated-transactions.md) | gripr: future-dated transactions excluded from totals; recurring pre-books one occurrence within 2 days of due |
| [0021](0021-gripr-portfolio-links.md) | gripr↔gainr bridge generalizes from one hardcoded link to a table of account↔portfolio pairs |
| [0022](0022-listr-mealie-import.md) | listr imports recipes from self-hosted Mealie; Mealie wins on re-import, food→product picks are remembered |
| [0023](0023-gripr-refunds.md) | gripr: a Refund type nets against expense-category spend, counted in the linked expense's period |
| [0024](0024-journal-notes-on-multiple-positions.md) | gainr: a journal note links to one or more positions via an association table |
| [0025](0025-position-calendar.md) | gainr: a Calendar tab per position — Yahoo's earnings/dividend dates (cached daily) plus your own events |
| [0026](0026-news-sources-per-position.md) | gainr: extra news sources per position — sector, industry or any Yahoo symbol, merged into the News card |
| [0027](0027-picnic-deliveries-into-gripr-and-voorraad.md) | Picnic deliveries become gripr expenses (matched against hand-booked ones first) and restock Voorraad; prices on linked products |
| [0028](0028-picnic-ordering-from-listr.md) | Ordering from listr: the Picnic cart, a chosen delivery slot, and checkout that only completes on the reader's own bank approval |
| [0029](0029-ing-transactions-into-gripr.md) | Bank transactions (ING, Trade Republic) into gripr via Enable Banking: matched against what's already there, filed under the recurring rule they fulfil, otherwise booked uncategorised |
| [0030](0030-news-from-yahoo-headline-feed.md) | gainr: news comes from Yahoo's RSS headline feed (per symbol and sector) and a news search (industries) after Yahoo retired yfinance's endpoint |
| [0031](0031-trading212-sync.md) | Trading 212 through its own API: card payments into gripr's T212 Debit (merchant names, learned categories), fills, dividends and a weekly interest/cashback deposit into gainr, assets found by ISIN |
| [0032](0032-gripr-expected-back.md) | gripr: an expense can expect money back; spending counts your share, the rest is "owed to you" until repaid or written off |
| [0033](0033-gripr-euro-only.md) | gripr is euro-only: the unused account currency is dropped |
