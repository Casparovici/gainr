<!-- markdownlint-configure-file { "MD024": { "siblings_only": true } } -->

# Changelog

What changed in the app, newest first. Every push to `main` is deployed, so entries are grouped
by the day they went live. **Added** is new, **Changed** works differently, **Fixed** was wrong.
The reasoning behind bigger changes is in [`docs/adr/`](docs/adr/README.md).

## 2026-10-05

### Changed

- listr: Recepten is a list, a row per recipe, instead of tiles, so a long cookbook scans quickly.
- gripr: Overview's net worth by account type chart is replaced by "Money put aside": per month, the net money that went into investments, savings and reservations (the pots).
- gripr: a one-off month (like a large one-off transfer into savings) no longer flattens the Money put aside chart: the scale leaves it out and marks it at the edge with its real amount.
- gripr: Overview's charts are labelled by period (25 Dec–24 Jan is P1), and Money put aside shows each line's average instead of this period's figure.

## 2026-10-04

### Added

- gainr: the same notifications bell: what the Trading 212 sync booked since your last look, instruments waiting for an asset, and a sync that isn't working.
- gripr: a notifications bell with a dot when something happened since your last look on that device: new transactions from the syncs (and how many need a category), money back for what you fronted, amounts still owed after a month, and banks that need attention.

### Changed

- gripr: the settings gear no longer carries a dot; bank problems show in the bell.
- gripr: Trade Republic is read once a day, in the morning sync, not on "Sync now".
- Android: the biometric lock (switched off since 14 Sep) is removed.
- gripr: accounts no longer have a currency setting; everything in gripr is in euros, as it already was in practice.

### Fixed

- gripr: Trade Republic stopped syncing after refusing too many reads in a day.
- On a phone, the floating add button no longer hides the last row of a list.
- gardnr: a care schedule can no longer repeat every 0 days, which left it due forever.
- listr: a list or recipe quantity of zero or less, and a recipe for zero people, are refused.

## 2026-10-03

### Added

- gripr: an expense can expect money back. Spending counts only your share, Accounts shows what you're owed, and a repayment from the person you named is booked as their refund.

### Changed

- gripr: money you're owed for fronted expenses counts in net worth until it's repaid or written off.
- Explanations sit behind an ⓘ next to their title instead of always taking up the screen.
- gripr: recurring payments on Trade Republic book on their due date again; the sync checks them off when Trade Republic reports them.

### Fixed

- gripr: a small card payment around the 2nd (Trading 212, ING) was booked as the Trade Republic saveback transfer.
- The morning sync runs at 06:30 instead of 08:00, so last night's card payments are there when you wake up.

## 2026-10-02

### Added

- gripr: Trading 212 card payments arrive by themselves, with the shop's name and the category you last gave that shop.
- gainr: Trading 212 fills, dividends and auto-invest buys are booked for you, plus one weekly deposit for interest and cashback.
- gripr: ING transactions arrive by themselves; you only categorise them.
- gripr: Trade Republic can be connected as a check on what you enter.
- gripr: virtual pots, for money set aside inside another account.
- gripr: an "Uncategorized" filter on Transactions.
- gainr: new assets are looked up on Yahoo as you type, so you pick the right listing.
- gainr: cost/income ratio in a bank's Financials.
- listr: order from Picnic without leaving listr: cart, delivery slot and checkout.
- listr: this week's Picnic offers.
- listr: Picnic prices and product pictures on linked products.
- listr: Picnic order history and spending.
- listr: Picnic deliveries are booked into gripr and restock Voorraad by themselves.
- gardnr: a care schedule can start on a date you pick.

### Changed

- gripr: all settings (period, banks) behind one gear.
- gripr: recurring rules on a bank-synced account let the bank's payment stand in for them.
- gripr: transfers into virtual pots keep booking when their bank is synced.

### Fixed

- gainr: a position's News card shows stories again.
- gripr: deleting an upcoming recurring payment no longer undoes a real loan repayment.
- listr: choosing a Picnic product shows all results again.
- The daily bank and Picnic syncs now get the server's credentials.

## 2026-10-01

### Added

- gripr: Upcoming shows every planned payment for the rest of the period.

### Changed

- All modules have gardnr's new look, each in its own colour.
- The theme toggle moved into the module menu on a phone.

## 2026-09-30

### Added

- gainr: a Calendar tab per position, with earnings, dividends and your own events.
- gainr: extra news sources for ETFs, gold and crypto.
- gainr: a journal entry can be about several positions.
- gripr: refunds, for money that comes back for something you paid.
- gripr: averages on the Overview trend charts.

### Changed

- Every module has its own logo and colour.
- gripr: Categories and Budget are now one page.
- gripr: calmer Accounts and Budget pages that fit on one screen.

### Fixed

- The Android app couldn't open.
- gripr: hover highlights and tints didn't show.
- gripr: an account's transaction list didn't fit a phone.
- gainr: Cash's target on Home looked different from the other rows.

## 2026-09-29

### Added

- listr: import recipes from Mealie.
- gardnr: Vandaag looks a week ahead, with undo after "Gedaan".
- gardnr: add a plant from Planten without placing it on a map; search and filter Planten.
- gardnr: edit a care schedule.

### Changed

- gardnr works on a phone: separate view and edit modes for the map, finger-sized markers, resize by dragging a corner.
- gardnr: Tuinen has its own edit mode; Planten shows cards on a phone.
- gardnr: a plant's panel opens on what needs doing; forms open as normal dialogs.

### Fixed

- gardnr: something due today was shown as overdue.
- gardnr: a new plant couldn't be placed inside a bed.
- gardnr: failed loads and saves were silent.

## 2026-09-28

### Added

- gripr: chart a single category's spending over the last 12 months.

### Changed

- gainr, listr and gardnr get gripr's mobile navigation.
- gainr: the positions tables read properly on a phone.
- gripr: Overview's income vs. expense chart is a line chart, and its tiles were reworked.
- gripr: Accounts no longer shows its own net worth tile.

### Fixed

- gripr: an account's detail dialog had a see-through background.

## 2026-09-26

### Added

- gripr: future-dated transactions sit in an "Upcoming" section.
- gripr: a recurring payment is booked 2 days before it's due, so you can adjust it.
- gripr: more than one account can track a gainr portfolio.

### Fixed

- gripr: a future-dated transaction counted in totals immediately.

## 2026-09-25

### Added

- gainr: multiple portfolios, each with its own ledger and performance.
- gainr: edit a holding's DLT rating from its detail panel.

## 2026-09-24

### Added

- gripr: a monthly savings goal per savings or investment account.

### Fixed

- Security: a file request could read files outside the frontend build.
- Security: the logo lookup could be redirected into the local network.

## 2026-09-22

### Added

- gainr: the Cash row opens like a position, with the balance per broker and transfers between brokers.

### Fixed

- gainr: a Sell's calculated total added costs instead of subtracting them.
- listr: a Voorraad item with a minimum of 1 never showed as in stock.
- listr: the Voorraad status could show the wrong colour after a quick tap.

## 2026-09-19

### Added

- gainr: a Journal page with every position note.
- listr: Voorraad, the products you keep at home, with counts and minimums.
- gardnr: touch dragging, care-log photos, and a Vandaag view across gardens.
- A script to pull the latest server backup onto a dev machine.

## 2026-09-18

### Changed

- The modules have new names: ipper → gainr, pefi → gripr, grecipe → listr, gardy → gardnr.

## 2026-09-16

### Added

- gripr: a brokerage account can track a gainr portfolio's value; transfers mirror into its cash.
- gardnr: rename or delete a garden; each garden's tile shows what's overdue.

### Changed

- gripr: resuming a paused recurring rule skips the pause instead of booking it all.

### Fixed

- Clearing a field didn't save.
- gripr: a rule starting long ago booked its whole backlog at once.
- gardnr: the map and the plant list could disagree about what's overdue.
- listr: the calendar-feed token check is now timing-safe.

## 2026-09-15

### Added

- gardnr, a fourth module for garden plants and their care.
- The module switcher is a compact pill.

### Changed

- gainr: Transactions shows asset names, and the asset field filters as you type.

## 2026-09-14

### Added

- listr: push a list to your Picnic cart, and import recipes from Picnic.
- gainr: a valuation snapshot on a position's Financials tab.
- gainr: a Drift column, and a clickable "Other" slice on the allocation donut.
- gainr and gripr: collapsible summary tiles and budget sections.
- Each module has its own header accent.

### Changed

- Every transaction row opens its edit view on click.
- gainr: target weights are edited from a position's detail panel, not the table.
- gainr: more compact summary tiles.
- listr: picking a Picnic product searches by the ingredient's name straight away.

### Fixed

- Transactions tables scrolled sideways on a phone; Edit and Delete could wrap.
- The Android app's biometric prompt kept coming back after unlocking.
- listr: the Weekplanner was unreadable on a phone, and the sub-nav lost its highlight.
- gripr: Budget tiles and summary tiles didn't line up.

## 2026-09-13

### Added

- listr, a third module for grocery lists and recipes, with a Weekplanner, recipe categories and a calendar feed.
- An Android app.
- Household members can use the app through a Tailscale device share.
- gainr: a target allocation weight per holding and for cash.
- gainr: add a transaction for a new holding in one step.
- gainr: long position notes collapse; the News section folds away.
- gripr: rename accounts and categories in place; bank icons on accounts.
- gripr: periods can start on any day of the month.
- gripr: budgets for income categories.
- gripr: categories linked to a loan, so repayments lower its balance.
- gripr: recurring rules every N weeks, months or years, with an Upcoming section and a repeat icon.
- gripr: click a category to see its transactions for the period.

### Changed

- gripr: more compact tiles; balance source shown as an icon.
- Light mode is a shade darker.

### Fixed

- gainr: Home and its chart were slow.
- listr: the calendar feed showed up empty.
- listr: product pickers work with the keyboard.
- listr: quantities showed as "1.000 stuks".

## 2026-09-12

### Added

- gripr: a Recurring tab.
- gripr: an account detail view, and subtotals per account type.
- gripr: budget suggestions for empty categories.
- gripr: archive and delete categories.
- gripr: custom account colours, and grey swatches.
- gripr: subcategory, category and amount filters on Transactions; most-used accounts first.
- gainr: a DLT Rating column.
- A sticky header.

### Changed

- Row actions are icons.

### Fixed

- The colour picker closed as you moved toward it, and resetting a colour did nothing.
- Dialogs didn't close when clicking outside them.
- gripr: Recurring showed the subcategory instead of the category.

## 2026-09-11

### Added

- gripr, a personal finance module next to the portfolio dashboard.
- gripr: an MCP server to add transactions from a chat assistant.
- gripr: category icons and colours, subcategories, drag to reorder, CSV export.
- gainr: a position detail card with transactions, news, financials and a notes journal.
- gainr: realised and unrealised gains, sortable and hideable columns, collapsible charts, logos.
- gainr: CSV export of all transactions.
- Dark mode.
- Hosting on a home server as a single process.

### Changed

- gripr: Accounts, Categories and Budget use tile grids; net worth moved to the bottom.
- gainr: logos resolve for funds through their issuer.
- gainr: the allocation panel lists every position.

### Fixed

- The app was unusable on a phone.
- Inputs were white-on-white in dark mode.
- gainr: European holdings were priced days late.
- gainr: blurry, missing and invisible logos.
- gainr: the positions table showed the wrong price date and duplicate tickers.
- gripr: the month picker could break.

## 2026-09-10

### Added

- First version of gainr: Home with headline metrics, time-weighted performance against benchmarks, allocation and positions, all derived from the transaction ledger, with daily prices from Yahoo Finance.
