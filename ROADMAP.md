# Requirements

## Generic roadmap

1. Search across all modules: one search box that finds a transaction, a position, a recipe, a plant, an exercise or a task
2. Notifications on the phone (ntfy, or the Android app's own notifications) for what's due and what the syncs booked; the bell exists only in gainr and gripr, and is seen only when the app is open


## gainr Roadmap

1. In the news section, rather than showing individual articles, I want to get a summary of the most important news of the last week, and these snapshots per week should be saved so I can scroll through them going forward
2. Add some sort of model that decides whether the current valuation makes a position interesting to increase/trim
3. Add Watchlist
4. A "General" option in the Journal's position picker, so portfolio-level notes can be written in the app (migrated ones are linked to a hidden General position)
5. Stock splits and other corporate actions: Yahoo's price history is split-adjusted but the ledger's share counts aren't, so a split in a holding breaks its value and P&L until it's recorded

## gripr roadmap

1. Trade Republic investments into gainr
    - A TDIV purchase on Trade Republic books itself as a Buy in gainr's Auto portfolio with the real number of shares. Today the bank sync books only its cash, as a deposit in Auto, because Trade Republic's bank data carries no quantity (see the addendum on docs/adr/0029)
2. Debt payoff projection: loan balances move through linked categories, but nothing projects a payoff date at the current pace or the interest still to come
3. Overview polish: a different over-budget colour (some categories are red themselves) and the Reservations line sits on the €0 line in Money put aside
4. Net worth over time: a monthly history chart, not only today's total on Accounts
5. Yearly review: spending per category, income and savings rate for a year, against the year before
6. Suggest recurring rules from bank payments that repeat (same counterparty, similar amount, regular interval)

## listr roadmap

1. Recipe photos — an image on each recipe, shown in the Recepten list (currently text-only), especially useful for recipes imported from Picnic
2. Barcode scan to add an item to a list or the inventory, using the Android app's camera
3. Scale a recipe to N people: `servings` is stored, but the ingredient amounts don't scale with it
4. Cooking mode: a recipe's steps one at a time with the screen kept awake, like trainr's guided workout
5. A shopping list that refreshes on its own while two people shop from it at the same time

## gardnr roadmap

1. Option to lay a real photo of the garden under the map instead of (or alongside) the drawn zones
2. Polygon-shaped zones, not just rectangles/circles, for an irregularly-shaped bed or border
3. Seasonal care schedules: a schedule only runs in the months it applies (water April–September), so winter isn't full of watering
4. Weather from Open-Meteo (no key needed): skip watering after rain, and warn about frost
5. Harvest log with amounts: HARVEST is an action, but nothing records the yield

## trainr roadmap

1. Add overview of past workouts per period (week, month, year)
2. Exercise videos from ExerciseDB v2 (AscendAPI on RapidAPI, Hobby plan subscribed) instead of the free-exercise-db photo pairs: an MP4 per exercise looping silently in the guided workout
    - Store only the stable ExerciseDB id per exercise. Media URLs rotate every Monday 00:00 UTC, so the backend fetches fresh ones when a workout starts, one GetExerciseById call per exercise, because there's no batch endpoint. It may cache them until the next Monday only if the plan allows caching
    - The key goes in `GAINR_EXERCISEDB_API_KEY` (`backend/.env`, `/etc/gainr/env`). Without a key, or with the API down, fall back to the current photos (ADR 0040)
    - Check the Hobby plan's monthly quota and caching rights on the RapidAPI pricing page first
3. Workout templates and repeating plans: save a session ("Push day") once and plan it every Monday and Thursday instead of typing it every time
4. Body weight log, with its trend in the overview
5. Estimated 1RM per exercise, and a "new record!" in the guided workout when it's beaten

## taskr roadmap

1. Repeating tasks (every week, every month) and tasks without a date
2. The agenda as a calendar feed, like the meal plan's token-protected ICS feed, so the phone's calendar gives reminders
3. listr as an agenda source: leftovers close to their use-by date, and pantry items below their minimum (ADR 0038 already lists listr as the next source)

## briefr roadmap

1. The first agent, the nightly holdings scan: a cloud scheduled task at 02:00 that reads `agents/holdings-scan/BRIEF.md` and `context/holdings.md` in the agents repository and commits its report (ADR 0044)
2. The nightly app builder: picks one GitHub issue labelled `agent-ok`, opens a pull request (never merges) and reports it in briefr
3. A morning digest on top of the inbox, and a warning when an agent missed its run
4. briefr on the notification bell, "act" findings on taskr's agenda, and a Briefs section in a gainr position's detail
5. Import problems shown in the app instead of only in the server's log
6. Push notifications (ntfy) for "act" reports

## Implemented

- briefr: a seventh module, an inbox for the reports AI agents write overnight: Act / Watch / Info per report, findings linked to positions and sources, read and archive; reports arrive from a private agents repository the server pulls, and the server exports tickers and weights for the agents (see `docs/adr/0044-briefr-agent-reports.md`).
- gainr: an Income page (dividends received per month, year and holding, and expected over the next 12 months, with yields), the money-weighted return (XIRR) next to the time-weighted one per chart range, and a buy-only rebalance helper from the target weights (see `docs/adr/0041-gainr-income-mwr-rebalance.md`).
- taskr: your own tasks next to the modules' items. Add one with a title and a day, tick it off on the agenda (with an undo), and change or delete it (see the addendum on `docs/adr/0038-taskr-agenda.md`).
- trainr: how-to demos in the guided workout. Each exercise links a start and end photo plus the steps from free-exercise-db (public domain), which flip like a short GIF during a set. The next exercise's demo shows during the rest. On Oefeningen, a demo can be linked, changed or unlinked (see `docs/adr/0040-trainr-exercise-demos.md`).
- trainr: an Overzicht page with a dashboard per activity. Cycling and running show km this week,
  month, year and in total against the same point in the previous period, distance and average
  speed (or pace) per month or year, and records; home gym shows sessions and volume, weight
  progress per exercise and sets per muscle group (see the addendum on `docs/adr/0037-trainr-module.md`).
- trainr: import rides and runs from a Strava account export; re-importing a newer export only
  adds what's new.
- A fifth module, trainr (Dutch UI), for workouts: plan and log home gym sessions, runs and rides
  in a week/month planner and tick them off; runs and rides record distance, time and top speed; a
  gym session lists exercises with sets, reps and kg, starting from last time. Historie totals per
  month or year, and Oefeningen holds 43 suggested exercises you can extend (see
  `docs/adr/0037-trainr-module.md`).
- gainr: the Cash card's Transactions tab lists every deposit, withdrawal, dividend, interest
  payment, fee and transfer behind the balance (read-only).
- listr: leftovers under Voorraad > Restjes (freezer or fridge, meals, people, use-by date);
  marking a recipe cooked offers to store them, and a planner day can eat a leftover instead.
- All modules: dropdowns restyled with a chevron, more room and a hover state instead of the stock
  browser look.
- gainr: a Metrics tab in a position's detail with each closely tracked holding's analyst
  checklist, from Yahoo where it has the figures and pointing elsewhere where it doesn't; a
  journal note can carry the date it is about.
- gripr: a category's dialog and Overview's Spending by category break spending down by
  subcategory; an ING payment takes the (sub)category last given to that counterparty.
- gripr: Trade Republic payments arrive on the next morning run, and entering one by hand takes
  over the synced row instead of adding a second one.
- both: attach files such as invoices or receipts (PDF, PNG, JPEG, WebP, up to 10 MB) to a
  gainr or gripr transaction.
- gripr: a monthly transfer into a fund can be an asset's depreciation, lowering the car's value
  by its share.
- gainr: Trading 212's weekly batch tells interest and cashback apart, and its sync moved into a
  settings gear; settings sections start folded and sync is an icon everywhere.
- listr: Picnic order history and spending, and Picnic deliveries booked into gripr that restock
  Voorraad by themselves — the roadmap's "Picnic order history import" (done 2026-10-02, with
  ordering, offers, prices and product pictures).
- All modules: a settings gear on every page of every module with a font choice: the current Bricolage + Instrument, or Manrope + Inter, Fraunces + DM Sans, Space Grotesk + IBM Plex Sans, previewed on the options and remembered per browser. Package C's IBM Plex Mono for amounts is not applied.
- gripr: bank payments learn their category per counterparty with loose matching (branch numbers,
  cities and payment providers ignored), and after categorising one you're offered to file the other
  uncategorised ones from that counterparty too (see the 2026-10-09 addendum to ADR 0029).
- gripr: search on Transactions (notes, category, account or amount) and a select mode to file,
  move or delete several transactions at once.
- gripr: each category compared with its usual: on Overview's spending bars and in the category
  dialog, against the 3 periods before (at the same point in them while a period is running).

- gripr: the Overview tab reworked: a balance forecast for the current period, readable charts (a
  budget list instead of the bar chart, round axes, the unfinished period dashed, category colours),
  savings rate and runway, and a "Needs attention" list.

- gripr: savings rate and runway on Overview: the share of income kept this period (and over the 3
  before it), and how many months of typical spending your checking and savings would cover (the
  median of the last three completed periods, reservations left out).
- gripr: the balance forecast learns when you spend: the remaining budget follows the weekdays you
  have spent on over the past 12 weeks (recurring payments and purchases over €500 left out), and it
  shows what is safe to move out today: the forecast's low point minus a week of everyday spending.
- gripr: a "Needs attention" list on Overview: budgets overspent, or under 75%, three completed
  periods in a row, with a budget that would have fitted the average.

- gripr: a notifications bell — new synced transactions (and how many need a category), money back
  for what you fronted, amounts owed after a month, banks needing attention; "seen" is per device.
  gainr has the same bell for the Trading 212 sync.
- gripr: Trading 212 API — card payments arrive in T212 Debit with the merchant's name and take the
  category last given at that merchant; fills, dividends and a weekly interest/cashback deposit go
  into gainr (see `docs/adr/0031-trading212-sync.md`).
- gripr: the Beleggen account's balance follows gainr's portfolio value, daily and after each
  mirrored transfer (see `docs/adr/0014-gripr-gainr-portfolio-bridge.md`).
- gripr: ING API — ING transactions arrive in gripr by themselves, through Enable Banking (a
  licensed PSD2 provider, read-only); you only categorise them. Each entry is matched to what's
  already there, filed under the recurring rule it fulfils, or booked uncategorised, and money
  to or from your own accounts elsewhere becomes a transfer. Recurring rules on ING-fed accounts
  stop booking their own rows. Transactions gained an "Uncategorized" filter (see
  `docs/adr/0029-ing-transactions-into-gripr.md`).
- gainr: a Journal tab next to Home and Transactions — every position note across every holding
  at once, as a tile grid, each tile linking back to the position it's about. Notes can now
  carry labels (global, reusable, filterable as chips). A note added, edited, or deleted from
  the Journal is the exact same row the position's own Notes tab reads and writes — there's no
  separate journal data to keep in sync (see `docs/adr/0016-position-journal.md`).
- gardnr: four smaller additions in one pass — (1) dragging a zone or plant to reposition it now
  works with a finger, not just a mouse, completing the touchscreen gap the roadmap flagged;
  (2) a care log entry can carry a photo (resized/re-encoded server-side, stored inline in
  portfolio.db so it's covered by the existing backup, not on disk); (3) a new Vandaag tab lists
  every overdue/due-today action across every area at once, grouped by area, with a one-click "Nu
  gedaan" that logs it without opening the plant's detail panel; (4) a manual per-plant status
  (Gezond/Worstelt/Dood), shown as a coloured dot on the map marker, the Planten list, and the
  detail panel's title — unlike listr's inventory status this isn't opt-in, every plant starts
  Gezond, since a catalogued plant already implicitly has a status one way or the other (see
  the addendum on `docs/adr/0012-gardnr-module.md`).
- listr: a Voorraad (inventory) tab — track which catalog products you keep at home as In
  voorraad / Bijna op / Op, opt-in per product via the same search-or-add combobox lists and
  recipes already use. Items marked Bijna op/Op surface in a banner with a bulk "Naar
  boodschappenlijst" action (quantity 1 of each item's own unit, same as any manually added
  line). Status is a hand-maintained flag, not a counted quantity — nothing (cooking a recipe,
  checking off a list, pushing to Picnic) moves it automatically, since none of those reliably
  share a unit with however an item happens to be inventoried (see
  `docs/adr/0015-listr-inventory.md`).
- A fourth module, gardnr (Dutch UI, like listr — Tuinen/Planten), for cataloguing garden
  plants/trees and their care: register what you're growing, log care actions
  (water/prune/trim/fertilize/harvest/pest control/other) with the date, and set a recurring
  schedule per plant per action so the app surfaces what's due or overdue. Areas (front yard,
  back yard, ...) each get an in-app-drawn map — coloured zones for beds/lawn/paths and plant
  markers, both placed by clicking and draggable to reposition (mouse only for now) — hovering a
  plant marker shows its name, last action, and next due action. A plant marker's shape
  (rectangle/circle), width, height, and icon (one of eight) are all independently editable from
  its detail panel. A flat Plants list across all areas sorts most-overdue-first (see
  `docs/adr/0012-gardnr-module.md`).
- both: the header's app switcher (gainr/gripr/listr) is now a collapsed pill showing only the
  active module — hovering it (tapping on touch) expands the full list, picking one navigates
  and collapses it again. Scales to more modules later without needing more header width; the
  new names under consideration weren't applied yet, only the switcher UI.
- gainr: Transactions shows each row's asset name instead of its ticker; the Asset filter is a
  text field that filters by name substring as you type, instead of a dropdown of tickers. The
  add/edit transaction dialog's Asset field is now the same type-to-filter combobox instead of a
  long alphabetical dropdown, with "+ Add new asset…" still reachable from it.
- listr: a list's "Push naar Picnic" button adds every mapped, unchecked item to the real
  Picnic cart — a catalog item is mapped to a specific Picnic product once (search, pick), then
  every future push reuses it. Always pushes as count 1, never a guessed quantity, since
  Picnic's cart counts a product rather than a weight/volume (see docs/adr/0011).
- listr: "Importeren van Picnic" on Recepten — browse the account's Picnic cookbook (saved,
  self-created, and its weekly featured recipes), preview the parsed ingredients and
  step-by-step instructions, pick a category for anything new to the catalog, and import it as
  a real listr recipe. Completes the original "Picnic API" roadmap item alongside the cart
  push above (see docs/adr/0011).
- both: gainr's and gripr's Transactions tables no longer scroll sideways on a phone — below
  tablet width each row becomes a card with every field stacked vertically instead of arranged
  in columns, so nothing needed to be hidden to make it fit. Separately, three transaction-list
  tables (gainr Transactions, gripr Transactions, gripr's account detail dialog) were missing the
  `whitespace-nowrap` their actions cell needs to keep Edit and Delete on one line — without it,
  the browser wraps them onto two whenever the table's column-width algorithm squeezes that
  cell, which is often on a phone; Recurring and the category detail dialog already had it.
- gainr: Home's Allocation donut's "Other" slice is now interactive — clicking it (or its
  "grouped into Other" line in the list) drills the chart into just that tail, each position
  getting its own colour again since there are few enough to fit the 8-colour cap; "← All
  positions" returns to the full portfolio view. The cap itself stays — a colourblind-safe
  categorical palette genuinely can't scale past ~8 hues, so extending it wasn't the fix.
- gainr: the active positions table's Target column is now read-only for real holdings — its
  target weight is only editable from the position's own detail card, so a stray click in the
  table can't change an allocation target. Cash has no detail card to redirect to, so it stays
  editable inline, same as before. A new Drift column (hidden by default, turned on from the
  same Columns picker) shows the percentage-point and euro gap between a holding's actual and
  target weight, sorted by the percentage so a small position drifting hard doesn't get buried
  under a large one drifting a little.
- listr: the Weekplanner's day grid is unreadable on a phone — 7 columns leaves ~44px per
  day, cutting off the weekday, the date, and any planned recipe's title. Below `sm` it's now a
  scrolling list of full-width day rows instead (month view's leading/trailing days from
  adjacent months are dropped from that list — they only existed for the calendar's column
  alignment); the desktop calendar grid is unchanged.
- gainr: Integrate the DLT judgment about my positions to the active position overview — a colour-coded "DLT Rating" column (green Attractive / gray Neutral / red Critical, translated from De Lange Termijn's Dutch Oordeel). No API or export exists for this, so it's read from a screenshot of their dashboard and refreshed by hand via `backend/scripts/update_dlt_ratings.py`; anything DLT doesn't cover reads as Neutral rather than blank.
- gripr: MCP server foundation, with one action — add a transaction by describing it in chat (e.g. "Today spent 5,59 euro on groceries"). A thin wrapper (`mcp-server/`) over the existing REST API, not a second copy of the business logic: `list_accounts`/`list_categories` (read-only, so the calling model can resolve a name to an id instead of guessing) and `add_transaction` (validates type/amount/category-vs-transfer shape before ever calling the API). Removed again on 2026-10-05, together with `.mcp.json`.
- both: for both gainr and gripr, in transaction view, the filters and other input fields are shown in white with a white background in the dark mode — native form controls (select, date input) follow the CSS `color-scheme` property, not our `.dark` class; one line (`.dark { color-scheme: dark; }`) fixed every input at once
- gainr: remove ticker from active position overview — the name already identifies the row and the ticker is one click away in the position detail card
- both: Make the app more usable on a phone — the header's sub-nav no longer forces the page wider than the screen (its own scrollable strip below `sm`), gripr's Transactions table scrolls inside itself instead of dragging the whole page, and  three fixed 3-column stat rows (gripr Budget, and the position card's two stat grids) stack to one column so values stop clipping
- gainr: Ability to add notes (in journal form) to the position view, with a title and a notes field (with the ability to do some markdown like font bold/italic, etc.) — a Notes tab on the position detail card, journal-style entries newest first, `**bold**`/`*italic*`/`` `code` `` supported
- both: Add dark mode (not fully black please, rather very dark grey/anthracite) and ability to follow system settings — applies to gainr and gripr both, since they're one app; a Light/Dark/System toggle in the header, anthracite (slate-800/900) surfaces, remembered across reloads, and "System" reacts live to OS theme changes
- gainr: Export transactions to csv
- gainr: Extend to a personal finance app — gripr
- gripr: make frontend more visually appealing instead of all the list views — accounts, categories, budget are now card/tile grids
- gripr: make the category view into category tiles and hide the subcategories
- gripr: Possibility to re-arrange the order of accounts in the account view — drag to reorder within a type group
- gripr: Add a relevant logo to every category in categories view — lucide icon per top-level category, also on Budget tiles
- gripr: in budget view, after adding/updating a budget, close the input field so it looks better on screen. By clicking right next to it (a pencil icon) you can update it again
- gripr: Ability to change the color per category in categories view
- gripr: in accounts view, push the net worth tile to the bottom of the screen
- gripr: in transaction view, add sub category to the dialog
- gripr: in budget view, allow to re-arrange like we do in account view
- gripr: add csv export — Export CSV button on Transactions, mirroring gainr's
- gripr: fix the month view in categories and budget views — replaced the native month input (which broke on typing and threw a 422 when cleared) with a Prev/Next month stepper
- gripr: account view — clicking an account's card opens a detail dialog to update its name/type, edit the balance, and view every transaction on that account; for transactional accounts, a "Correct balance" flow lets you enter the real-world balance and choose whether the difference is a missing transaction or just drift to absorb into the opening balance; each account-type group in the accounts view now also shows its own subtotal, not just the overall net worth
- gripr: transaction view — added a Subcategory column next to Category so both levels always show regardless of which one a transaction is actually filed at; added Category and min/max amount filters (picking a top-level category also matches its subcategories, the same rollup Budget's "spent" already used); and the add/edit dialog's account picker now lists your most-used accounts first instead of the accounts view's type-grouped order
- gripr: new Recurring tab for subscriptions, salary, mortgage payments — configure a rule once (amount, account, category, weekly/monthly/yearly frequency, optional end date) and its transaction books itself into the ledger once the rule's date comes due; there's no background scheduler so this catches up opportunistically (and for however many periods were missed at once) whenever Accounts or Recurring is opened; pausing a rule, or it running past its end date, only stops future occurrences, past transactions stay put
- gripr: category view — archive and delete, for both top-level categories and subcategories. Archiving a top-level category hides its subcategories too (a "Show archived" toggle brings them back into view); deleting one cascades to its subcategories and un-tags (not deletes) every transaction filed under any of them — the money movement stays in the ledger, only the categorization goes away — and removes any budget lines set on it
- gripr: budget view — when a category's budget is empty, the input now offers up to three one-click suggestions: last month's budget for that category, the trailing-year average, and what's already committed via Recurring for it (normalized to a monthly figure regardless of frequency); a suggestion only shows when it's actually non-zero, and none show once a budget is already set
- gripr fix (also applied to gainr): every centred dialog now closes on a click anywhere outside it, not just its Cancel button — pulled into one shared `ModalOverlay` component so all of them (gainr's add/edit transaction; gripr's new account, add/edit transaction, add/edit recurring, new category, the account detail dialog) get this consistently; gainr's position detail slide-over already had this behavior and was left as-is
- gripr fix: Recurring's Category column now always resolves to the top-level category, matching Transactions, instead of showing the subcategory a rule happened to be tagged at
- gripr: accounts can now have their own colour (a small dot on the account card opens the same swatch picker Categories uses, including reset-to-default), defaulting to a colour derived from the account's type until overridden; that colour now renders as a badge wherever the account name shows in a table row (Transactions, Recurring) instead of plain text. Also fixed a pre-existing bug where resetting a category's colour to default silently did nothing (the repo layer was re-filtering out the explicit null the schema layer had already let through) — fixed for both categories and the new account colours
- gripr fix: the colour swatch picker (Categories and account colours) often closed the instant you moved the mouse toward it — it closed on mouse-leave, but the popover sits a few pixels below its trigger and hovering across that gap fired mouseleave before the click landed; now closes on an outside click instead
- both: the header (gainr/gripr toggle, the page tabs, the theme switcher) now stays pinned to the top of the screen while scrolling, instead of scrolling away with the page
- both: added grey and dark grey to the colour picker's swatches (Categories, accounts) — a separate picker-only palette, so the categorical palette every chart's automatic colour assignment relies on stays untouched
- both: row-level Edit and Delete are now a pencil/trash icon instead of text, everywhere they appear (both apps' transaction tables, gripr's Recurring list and account detail dialog, the position notes journal) — still labelled for a tooltip and screen readers, Archive/Unarchive and Pause/Resume next to them untouched
- both: performance — the Home page, its value chart, and switching chart ranges were all slow from replaying the entire transaction ledger on every request, plus a live Yahoo Finance call whenever the day's price cache was cold; the daily series is now computed once and reused until the ledger changes, prices refresh on a daily background schedule instead of on the first page load, and per-position valuation batches its queries instead of one round-trip per holding (see `docs/adr/0001-performance-series-cache.md`)
- both: light mode is a shade darker — pure white and near-white surfaces read as too bright; every step on that scale (page background, cards, borders) now sits one Tailwind slate stop darker, via the same override-sheet mechanism dark mode already uses
- gainr: the News section on a position's detail card can now be folded away, remembered per holding like every other collapsible section
- gainr: a transaction for a holding that doesn't exist yet no longer needs a separate step first — pick "+ Add new asset…" from the asset dropdown, fill in ticker/name/asset class/currency, and the transaction saves against it directly
- gainr: a target allocation weight per holding, and for cash — editable inline from the active positions table (a new Target column) or a holding's detail card, with a running check that the targets across everything, cash included, never add up to more than 100% (see `docs/adr/0002-target-weight-allocation.md`)
- gripr: a small repeat icon marks transactions booked automatically by a recurring rule, in the Transactions table
- gripr: an "Upcoming recurring" section at the top of Transactions, folded away by default, listing what's still due this month
- gripr: recurring rules can repeat every N weeks/months/years, not just every one
- gripr: categories can be linked to a loan account — an expense filed under one automatically nudges that loan's balance toward zero, kept in sync across edits and deletes (see `docs/adr/0003-loan-linked-category-balance-adjustment.md`)
- gainr: notes now clamp to 3 lines with a "Show more" that opens the full note in a dialog (only shown when it actually overflows), and support more formatting — headings, bullet/numbered lists, strikethrough — alongside bold/italic/code
- gripr: periods no longer have to start on the 1st of the month — Budget, Categories, and Overview each show a period switcher (Overview didn't have one before) with a gear icon to set which day of the month a period starts on, e.g. the 25th to align with payday; defaults to the 1st (a plain calendar month), so nothing changes unless it's set, and changing it doesn't retroactively move budgets already set (see `docs/adr/0004-gripr-period-boundary.md`)
- gripr: income categories can now be budgeted too, not just expense — Budget and Categories both show an Income section with "Target"/"Received" wording, and the progress bar flags falling short of the target rather than reusing the expense over-budget framing
- listr: a third module, for grocery lists and recipes, in Dutch — Lijsten (named, saved shopping lists you can check off, clear, and duplicate to reuse as a template), Recepten (recipes whose ingredients link to a real product catalog, with a "Toevoegen aan boodschappenlijst" action that adds some or all of them to a list, merging quantities onto a matching existing line), and Producten (the catalog itself, seeded with ~220 common Dutch groceries across 12 categories and extendable by hand) (see `docs/adr/0005-listr-module.md`)
- gripr: category view — clicking a category (or subcategory) opens a dialog listing every transaction filed under it for the period currently shown, same rollup Budget's "spent" figure uses; the link-to-loan, archive, and delete actions on a category tile are now icon buttons clustered together instead of spread across separate text-labelled rows, and tiles are the same size as Accounts' — Accounts' own Archive button and listr's Producten/Lijsten archive buttons were switched from text to icons too, for consistency
- listr: recipes can now be tagged with categories (Italiaans, Aziatisch, etc, multiple per recipe), filterable as chips on Recepten; a new Weekplanner tab plans which recipe gets cooked on which day in a week or month grid, with an explicit "Ik heb dit gekookt" step (planning a day isn't itself the record of eating it) driving a "Populairste recepten" ranking by times actually cooked (see `docs/adr/0006-listr-meal-planning.md`)
- listr: a "Boodschappenlijst van [period]" button in the Weekplanner adds every planned recipe's ingredients across the currently viewed week or month into one grocery list at once (per-day checkboxes to drop specific days), merging across recipes the same way a single recipe's own "Toevoegen aan boodschappenlijst" already does
- Android app — a Capacitor wrapper (`frontend/android/`) whose WebView loads the live site directly, so it's the same app rather than a second codebase to keep in sync; adds a biometric/PIN lock (Android-only, the web app still has no login), sideloaded rather than published to the Play Store (see `docs/adr/0009-android-capacitor-wrapper.md`)
- gripr: account and category names are now editable inline (read-only with a pencil icon until clicked, same pattern Budget's amount cells already used — categories couldn't be renamed before this); an account tile's balance source (manual vs. from transactions) is now a small icon instead of text; an account can carry a bank/broker icon (ING, Trading 212, Trade Republic, Revolut) picked from a popover, fetched once from the bank's own site like gainr's asset logos (see `docs/adr/0010-gripr-inline-rename-and-bank-logos.md`)
- gripr: Accounts, Categories, and Budget tiles are noticeably more compact (less padding, smaller icons, tighter type) and the grid packs more columns per row (2 on a phone up to 4 on desktop, previously 1/2/3) — significantly more fits on screen at once without scrolling, especially on mobile
- gripr: Budget view fix — a category tile with no budget set now renders at exactly the same height as one with a budget (a subtle CSS line-box-vs-flex-row mismatch made it a hair taller); Expenses and Income are now individually collapsible, remembering the choice across reloads, and still show their "Remaining"/"Behind by" total even when folded; the Budgeted/Spent/Remaining summary tiles now use the same 2/3/4-column breakpoints as the category grid below them instead of a fixed 3 columns, so their edges line up
- Rewrote the README to be far more concise (609 → ~215 lines) and added an Architecture section (stack, module-boundary convention, non-negotiables, deployment topology, and a table of every ADR)
- gainr: Home's summary tiles are noticeably more compact (less padding, smaller type) and pack up to 6 per row on desktop instead of 3, so all of them fit on one row; the whole section is now collapsible, remembering the choice across reloads, and still shows the total portfolio value even when folded
