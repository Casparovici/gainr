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
| [0034](0034-gripr-depreciation.md) | gripr: a recurring transfer into a fund can be an asset's depreciation; the asset loses value by that amount when it books |
| [0035](0035-transaction-attachments.md) | gainr and gripr: files (invoices, contract notes) attached to a transaction, stored in the database so the backup covers them |
| [0036](0036-listr-leftovers.md) | listr: leftovers as their own dated table, not Voorraad items; a cooked meal-plan day takes one off |
| [0037](0037-trainr-module.md) | trainr: a fifth module for workouts; planned and done are one row, average speed is derived, gym entries are sets × reps × kg from a seeded, user-extensible exercise list; rides and runs import from a Strava export |
| [0038](0038-taskr-agenda.md) | taskr: an agenda over gardnr and trainr; modules contribute through one item shape, nothing of theirs is copied or completed in taskr; an addendum adds tasks taskr owns |
| [0039](0039-sqlite-schema-and-connection.md) | SQLite: one guarded migration aligns the migrated schema with the models (and a test keeps them aligned); WAL, and foreign keys enforced |
| [0040](0040-trainr-exercise-demos.md) | trainr: an exercise links a how-to demo from the vendored, public-domain free-exercise-db catalogue; photos come from jsDelivr pinned to one commit, and the guided workout shows them |
| [0041](0041-gainr-income-mwr-rebalance.md) | gainr: dividend income (received, and expected from the last 12 months), a money-weighted return (XIRR) per chart range, and a buy-only rebalance helper; all derived, no new tables or providers |
| [0042](0042-deploy-ci-gate-and-rollback.md) | Deploy: the server only deploys a commit whose CI passed, backs up before migrating, rolls back when the health check fails, and reports the outcome on the commit |
| [0043](0043-listr-recipe-photos.md) | listr: one photo per recipe, stored inline and re-encoded like gardnr care-log photos; the Mealie import brings its picture along |
| [0044](0044-briefr-agent-reports.md) | briefr: a seventh module for agent reports; agents commit TOML-headed Markdown files to a private repository the server pulls and imports, with no ingestion endpoint; the server exports tickers and weights (no amounts) for the agents |
| [0045](0045-briefr-performance-reports.md) | briefr: daily, weekly and monthly performance reports computed on the server from gainr's ledger (time-weighted return, price change and euro contribution per holding, benchmarks), written into briefr directly, one report per portfolio; no model, and no amounts leave the server |
| [0046](0046-trainr-weekly-gym-plan.md) | trainr: every Sunday the server plans next week's three gym sessions from fixed muscle-growth rules over the last three weeks, around the other sports, puts them in the planner and reports in briefr; the history never leaves the server |
| [0047](0047-hourly-live-quotes.md) | gainr: an hourly live quote per asset (three columns on `assets`, fetched by an hourly timer, never by a request) values holdings and re-prices only the chart's today point; history and returns stay on daily closes |
| [0048](0048-vandaag-start-screen.md) | Vandaag at `/`: one start screen of what waits today across the modules, from one endpoint taskr hosts (`/api/taskr/today`); gainr Home moves to `/gainr`; the module switcher shows counts and taskr loses its tile |
| [0049](0049-language-setting.md) | All modules: a per-browser language setting (English or Dutch); every UI string goes through a small `t()` keyed by its source text, with one dictionary per module and direction, and a test that every string has its translation; server-written text stays as written |
| [0050](0050-notr-notes.md) | notr: a notes module; gainr's Journal becomes a view of it (one table, links to positions, plants and recipes, all optional); Markdown with pictures stored in the database and claimed by the note whose text shows them; one renderer and one editor for every note |
| [0051](0051-money-weighted-headline.md) | gainr: the money-weighted return (XIRR) is the headline performance figure (chart header, "This year" and "Since start" tiles); the time-weighted return stays as the chart's line, the benchmark comparison and the fallback where no rate exists |
| [0052](0052-listr-store-order.md) | listr: supermarkets, each an order of the categories (its aisles); a shopping list set to a store shows its groups in that order, and the standard category order applies without one |
| [0053](0053-position-price-chart.md) | gainr: a price chart in a position's detail (1D, 1W, 1M, YTD, 3Y); ranges of a week or more are daily closes plus the live quote, 1D is the last session's 15-minute bars fetched on demand and cached in memory for 10 minutes, never stored, with the last week's closes as the fallback |
| [0054](0054-briefr-home-chef.md) | briefr: a weekly home-chef agent suggests five recipes (preferably from Dutch sites), written out in its report since the server never fetches a recipe page; "Plan in listr" makes one a listr recipe once (matched by its page, ingredients only on certain product matches) and puts it on a chosen day of the weekplanner; listr's product catalog goes to the agents as context |
