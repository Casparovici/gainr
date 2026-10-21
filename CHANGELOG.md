<!-- markdownlint-configure-file { "MD024": { "siblings_only": true } } -->

# Changelog

What changed in the app, newest first. Every push to `main` is deployed, so entries are grouped
by the day they went live. **Added** is new, **Changed** works differently, **Fixed** was wrong.
The reasoning behind bigger changes is in [`docs/adr/`](docs/adr/README.md).

## 2026-10-21

### Added

- briefr: a home chef. Every Friday morning an agent suggests five recipes for the coming week, preferably from Dutch sites like Leuke Recepten and delicious., in a report in briefr. Each recipe shows why it was picked, its servings and time, the ingredients and steps, and a link to the page. "Plan in listr" shows the next two weeks with what's already planned, and puts the recipe on the day you pick (asking first if that day has something). The first time, the recipe is added to listr's recipes, with the ingredients that match a product as recipe lines and the rest in its notes; the report then shows the days it's planned on.
- listr: a recipe planned from briefr links to the page it came from.

## 2026-10-20

### Added

- gripr: the Savings tab of the budget shows how much you can save this period: the income you budgeted minus the expenses you budgeted, and how much of that your savings goals already plan (or plan too much of). It says so when the budgeted expenses are higher than the budgeted income, and updates as you change a budget.
- listr: the categories on a shopping list fold away. Tap a category's header to collapse or expand it (a category that's fully ticked shows a check), or "Alles inklappen" / "Alles uitklappen" for all at once; what you folded is remembered per list on this device.
- gainr: a position's detail shows its price chart, over 1 day, 1 week, 1 month, year to date or 3 years, with the change over that range. The day view shows the last session's prices within the day; when Yahoo has none right now it shows the last week's closes and says so.
- listr: supermarkets. Add the shops you use and arrange their categories in the order you walk through them (with arrows, in a sheet opened from a list's "Winkel" picker). A list set to a store shows its groups in that order, so you can follow it through the shop; a list without a store follows one standard order, which you can also arrange. Duplicating a list keeps its store. Categories used to be shown alphabetically; they now follow the standard order (the order they were made in, until you arrange them).
- notr, a new module for notes. Write in Markdown (headings, lists, quotes, code, tables, links) with a toolbar and a preview, and put **pictures** in a note by pasting, dropping or picking one (a phone offers its camera). Checklists tick off in place. Notes have labels, a pin and archiving, and can be searched. A note can be about positions, plants and recipes, and then shows there too (a Notes section on each, and for positions in gainr's Journal); a note about nothing is a plain note. Vandaag has a "+ Notitie" button and lists your pinned notes, and briefr's "Save as note" turns a report into a note.
- All modules: a language setting. Settings > Language shows the whole app in English or Dutch, from gainr's figures to listr's shopping list and trainr's workouts. It starts in your browser's language and is remembered on this device, like the font. Text the server writes (agenda titles, notifications, reports) stays as it was written.
- Vandaag, the app's new start screen: what needs you today across all modules in one place. Late garden care and tasks, payments without a category and unread reports, each linking to where you deal with it; your portfolio's value and today's move; what's safe to move out of your current account; today's agenda, where your own tasks are ticked off; and tonight's meal. Buttons to add a task, an expense, a grocery or a workout. gainr Home moved to its own address (old position links still work).
- All modules: the module switcher shows what waits in each module (payments to categorise, garden care, today's workout, unread reports), with a dot when something waits elsewhere. On a phone it opens as a sheet of tiles, with the theme switch. taskr has no tile of its own any more: its agenda is on Vandaag, with a link to the full agenda.

### Changed

- listr: ticking off on a shopping list is easier: tap anywhere on a line's name, not only the small box. The product search above the list, its suggestions and the Picnic code box now match the rest of the app (and follow dark mode, at a size that doesn't zoom the page on a phone).
- gainr: the money-weighted return is now the headline performance figure. It is the big number in the performance chart's header (per year for a year or longer), with the euros and the time-weighted return beside it, and it is the figure in the "This year" and "Since start" tiles ("Since start" is now a yearly rate). The chart's line and the benchmark comparison stay time-weighted. For one day, or when there is no rate, the time-weighted return is shown and labelled as such.
- gainr: the Journal and a position's Notes now use notr's editor and Markdown, so journal notes get lists, links, checklists and pictures too. Your existing journal notes and labels moved to notr unchanged.
- listr: you can move a planned meal to another day. Open the day in the Weekplanner and change its date; the recipe, note and cooked tick go with it. A day that is already planned can't be moved onto.
- gainr: Home starts with what the portfolio is worth and how much it moved today, with the time of the prices. The six summary tiles became four smaller ones (this year, since start, unrealized and realized, cash and invested), and on a wide screen they sit beside the chart with the allocation.
- gainr: every holding shows today's move, in percent and euros, and its weight as a bar with its target marked. On a phone the holdings are a list you can sort by value, today's move, unrealized result or distance from target, instead of a table that scrolled sideways. The allocation donut became one bar by kind of holding (stocks and ETFs, crypto, cash).
- gainr: Transactions groups the list by month on a phone, with what happened in each month. Filtering is a search box, chips for buys, sells, dividends and deposits, and a Filter button for broker and dates, instead of a block of fields at the top. Tapping a transaction opens it with Edit, Duplicate (a copy dated today) and Delete, and a link to its position; the rows no longer carry edit and delete buttons.
- gripr: transaction rows no longer carry their own "got money back", edit and delete buttons; tap a transaction to open it, where "Got money back" and now "Delete transaction…" are.
- listr: each item on a shopping list is one line to tick off. Tap its amount to change it with − and +, pick its Picnic product or take it off the list.

### Fixed

- listr: the Producten page's categories fold away too, like a shopping list's (tap a header, or "Alles inklappen" / "Alles uitklappen"); with a couple of hundred products that makes the catalog manageable. What you folded is remembered on this device.
- gainr: on a phone, Home no longer scrolls sideways because of the chart's return line, and Transactions' settings gear is no longer cut off at the edge (trainr's Historie had the same problem).
- gainr: the Cash row in Active positions no longer shows a DLT "Neutral" badge.
- All modules: on a wider screen, pages no longer start with an empty strip above the title; the settings gear sits in the header next to the theme switch.

## 2026-10-19

### Added

- gainr: live prices, refreshed once an hour. Your total value, positions, weights and P&L, and the chart's today point and 1D change, now follow the market during the day instead of showing yesterday's close. Active positions shows when the prices were taken, the position panel shows the time of its quote, and Home updates itself every 15 minutes. Most European listings are about 15 minutes behind at Yahoo; history and returns still use daily closes.
- trainr: a gym plan every Sunday at noon. From your last three weeks of gym sessions, next week's three sessions of about 45 minutes are planned for muscle growth (8 to 12 reps; more weight once you reach 12) around your padel, football, runs and rides, and appear in the planner ready to do. A report in briefr explains the week: what you trained, which muscle groups are behind, and what changed per exercise.
- briefr: performance reports on your portfolios every morning: daily (Tuesday to Saturday), weekly on Saturday and monthly on the 1st. Each shows the time-weighted return per portfolio next to the S&P 500, Nasdaq and MSCI World, and per holding its price change and what it contributed in euros and in percentage points. Big moves, holdings without a current price and, weekly and monthly, holdings far from their target weight are flagged and link to the position.
- trainr: Historie has a Week period next to Maand and Jaar: the done workouts of one Monday-to-Sunday week, with its totals per activity, headed by the week number and its dates.

### Changed

- briefr: the portfolio performance reports come one per portfolio instead of all portfolios in one report, so Main, Kids and the others can each be read, marked and archived on their own. Each title names its portfolio, and the benchmarks are in every report.
- briefr: the performance reports list and flag only the positions you still hold. A position you sold out of, or an old one that paid a late dividend, no longer shows up in the tables, findings or summary; the portfolio's return and change still include what it earned.
- briefr: reports can show tables. The performance reports show one table per portfolio (price change, contribution in euros and points, weight and target per holding, the biggest drag at the top), the gym plan shows each session as a table (this time, last time, what changed), and the holdings scan opens with a table of every position and what's new.
- briefr: the agents now start from the same news you see on a position's News card, including the extra sources you set on it (a sector, an industry, gold futures), so ETFs and gold get covered too. homecloud exports each holding's headlines of the last 3 days with the nightly context.

### Fixed

- gainr: Home failed to load ("Could not load portfolio summary") from the second page load onwards after today's live-prices change. The summary, chart and positions load again.

## 2026-10-18

### Added

- briefr: a new module for the reports your AI agents write overnight. The Inbox lists them newest first, each marked Act, Watch or Info by its most urgent finding; open one to see its findings (with links to the position and the sources) and the write-up, which marks it read. Filter by agent or level, mark a report unread, or archive it once you're done. Reports arrive from the private agents repository within about ten minutes of an agent pushing them.
- gainr: an Income page with your dividends: received per month and year, per holding, and what your holdings are expected to pay over the next 12 months (last year's payments per share times what you hold now), with the yield on market value and on cost.
- gainr: the money-weighted return (XIRR) next to the time-weighted one in the chart's header, for the same range (per year for ranges of a year or more). It includes the timing of your deposits, which the time-weighted figure leaves out on purpose.
- gainr: a Rebalance button on Active positions. Enter an amount, either new money or cash already in the portfolio, and see what to buy to move towards your target weights: split over the holdings below target, the furthest behind getting the most, with the approximate number of shares. Nothing is sold.
- taskr: your own tasks, for to-dos that don't belong to a module. Add one at the top of the agenda with a title and a day, which starts as the first day on screen. It shows on the agenda next to gardnr's and trainr's items. Tick it off with its circle, with an undo in case of a mis-tap, or tap it to change its title, day or notes, or delete it. An open task stays overdue until you tick it off.
- trainr: how-to demos for gym exercises. In a guided workout, each exercise shows how it's done: its start and end photo flip like a short GIF, with the steps folded underneath. The next exercise's demo shows during the rest, and "Voorbeeld verbergen" hides them on that device. The suggested exercises come with a demo already (all but Burpee). On the Oefeningen page, "Voorbeeld kiezen" links a demo to any exercise, or changes or unlinks one.
- listr: recipes can have a photo. Add one when you create or edit a recipe (take it with the camera or pick one), and it shows in the recipe list and at the top of the recipe. "Ophalen uit Mealie" brings Mealie's picture along.

### Changed

- gainr: the rebalance helper only buys holdings DLT rates Attractive or Neutral, and shows each purchase's rating. A holding rated Critical or not rated at all gets nothing and is listed with the reason, as one without a target already was.

## 2026-10-16

### Added

- trainr: football and padel. Log a match with its time, total calories, average heart rate and maximum heart rate. History, the planner and the overview show them: totals and averages per period (the average heart rate weighted by time), and records for the longest session, most calories and highest heart rate.

### Changed

- trainr: the activity picker is a dropdown instead of a row of buttons, in the overview, the history filter and the workout form, so it keeps working now there are five activities.

## 2026-10-14

### Added

- taskr: a new module with one agenda of everything that's due across the other modules: gardnr's care actions and trainr's planned workouts. Look at a day, a week or 30 days ahead (or page back and forward); anything that slipped is listed first under "Achterstallig", then each day with what's on it. taskr only shows: each line links to the module where you tick it off or change it.
- trainr: a guided gym session now times each exercise too. The time you actually spent on an exercise's sets (rests left out) is saved in that exercise's time field and shown in the workout, e.g. "3 × 10 · 12,5 kg · 2:10"; a live set stopwatch runs while you train.
- trainr: run a planned gym session step by step. Tap the play button on a planned home gym workout in the planner and trainr walks you through it set by set: the target reps and weight (adjustable with +/−), a countdown for timed holds, a rest timer between sets, and skip or tick off a set or a whole exercise. When you finish, the workout is saved as done with the reps and weights you actually did and the time it took.

### Changed

- All modules: the app starts faster, on the phone especially. It used to download every module's pages and the chart library before showing anything (1.3 MB); now it loads about a quarter of that up front and each page the first time you open it.
- gripr: a budget's "Year avg" suggestion is now your average actual spend per month over the past twelve months (income received, for an income category) instead of the average of the budgets you set, so a budget you never stuck to no longer suggests itself. A savings goal's "Year avg" is likewise what you actually moved into the account per month (net of withdrawals) rather than the average of the goals you set.

### Fixed

- gripr: deleting a category no longer leaves recurring rules filed under a category that doesn't exist; they keep running, uncategorised, like the transactions they booked.
- gainr, gripr, listr: when a list can't be loaded (transactions, positions, accounts, budget, recurring, lists, recipes, products, stock, the weekplanner, the portfolio switcher, list and recipe pickers), the page now says so with a retry button, instead of showing an empty "No transactions" or "Nog geen lijsten" as if there were nothing there.

## 2026-10-12

### Added

- trainr: an Overzicht page with a dashboard per activity. Cycling and running show km this week, this month, this year and in total (each against the same point in the previous period), distance and average speed (or pace) per month or year, and records; home gym shows sessions and volume, weight progress per exercise and sets per muscle group.
- trainr: import your rides and runs from a Strava account export (the archive from Strava's "Download or delete your account"). Each becomes a done workout with distance, moving time, top speed and the activity's name; re-importing a newer export only adds what's new.
- trainr: a new module for workouts. Log or plan home gym sessions, runs and rides in a week/month planner and tick them off when done; runs and rides record distance, time and top speed and show average speed and pace; a gym session lists exercises with sets, reps and weight (kg), starting from what you did last time. Historie shows done workouts per month or year with totals per activity, and Oefeningen holds 43 suggested dumbbell, barbell, pull-up bar and bodyweight exercises you can add to, rename or archive.
- All modules: a settings gear at the end of every page's top row (it was only on gainr's pages and gripr's Accounts); listr and gardnr get one too, with the font choice. Choose the font there: the current look, Manrope + Inter, Fraunces + DM Sans or Space Grotesk + IBM Plex Sans. Applies at once and is remembered in that browser.
- gainr: the Cash card's Transactions tab lists every deposit, withdrawal, dividend, interest payment, fee and transfer behind the balance (read-only; buys and sells stay on their positions).

## 2026-10-11

### Added

- listr: leftovers. Keep cooked meals under Voorraad > Restjes (freezer or fridge, how many meals, for how many people, use-by date). Marking a recipe cooked in the meal planner offers to store the leftovers, and a day can eat a leftover instead of a recipe: ticking it off takes one meal off.

## 2026-10-10

### Changed

- All modules: dropdown fields have a clean chevron, a bit more room and a hover state instead of the stock Android/browser look; the list that opens is still the system picker.

## 2026-10-09

### Added

- gripr: search on Transactions: notes, category, account or an amount.
- gripr: select several transactions to file them under a (sub)category, move them to another account, or delete them at once.
- gripr: after you categorise a bank transaction, gripr offers to file the other uncategorised ones from the same counterparty too.
- gripr: each category is compared with its usual: "+18%" next to the spending bars on Overview, and a line in the category dialog. While a period is running, it compares with the same point in the 3 periods before.

### Changed

- gripr: a bank payment recognises a counterparty however the bank spells it (branch numbers, cities, card terminals, "via Rabo Smart Pay"), so the category you gave it last time sticks more often.

## 2026-10-07

### Added

- gripr: Overview shows your savings rate (how much of what came in was kept, with the 3 periods before it) and your runway (how many months your checking and savings would cover at a typical month's spending).
- gripr: the balance chart says what is safe to move out of checking today (the forecast's lowest point minus a week of everyday spending), and spreads the remaining budget over the weekdays you tend to spend on instead of evenly.
- gripr: Overview has a "Needs attention" list: budgets overspent, or under 75%, three periods in a row, with a budget that would have fitted.

- gainr: a Metrics tab in a position's detail for the holdings you track closely (ABN AMRO, Alphabet, Amazon, ServiceNow, MercadoLibre, Nu, tonies, the four thematic ETFs, gold, Bitcoin, Ethereum): the figures that decide how each is judged, from Yahoo where it has them (margins and trends, free cash flow and capex, cost/income, ETF concentration, holdings' P/E and TER, correlation with the Nasdaq), and the rest listed as not on Yahoo with where to look.
- gripr: a category's dialog and Overview's Spending by category (tap a bar) show where the money went by subcategory, with shares; tapping a subcategory in the dialog narrows its transactions.
- gripr: an ING payment takes the category, or subcategory, you last gave a payment to the same counterparty, like Trading 212's merchants.

### Changed

- gripr: Overview's Budget vs. actual is a list of progress bars per expense category (spent of budget, what's left or over, over-budget in red) instead of an unreadable bar chart; Money put aside's axis has round values including €0; charts without data say so, and a failed load offers a retry.
- gripr: Overview draws the unfinished period dashed, uses straight lines instead of smoothed curves, shows the expected balance at the end of the period above the balance chart (with the lowest point if it dips below), and hides that chart when you page to another period.
- gripr: Overview's spending bars and category chart use each category's own colour (as on Budget), the budget list shows two columns with a colour dot per category, spending bars carry their amounts, and Reservations has its own colour instead of sharing Income's.

### Added

- gripr: Overview has a balance chart for the current period -- your checking balance day by day, actual up to today, then a forecast for the rest of the period from known recurring payments/income and each category's remaining budget.

## 2026-10-06

### Changed

- gripr: Trade Republic payments now appear on the next morning run instead of two days later. One you haven't entered yet shows up uncategorised ("not entered by hand"); when you then enter that payment (same account, same amount, within a week), it takes over that row instead of adding a second one. A row you've already categorised is never taken over.

### Fixed

- gripr: a Trading 212 card payment could be lost when you'd entered a payment of the same amount a few days earlier: the sync took your older row for it. Card payments now only match a row within two days.

## 2026-10-05

### Added

- gainr: attach files such as invoices or contract notes (PDF, PNG, JPEG or WebP, up to 10 MB) to a transaction; a paperclip marks the transactions that have some, and opening one shows it in the browser.
- gripr: attach files such as invoices or receipts to a transaction, the same way as in gainr.
- gripr: a monthly transfer into a fund can be an asset's depreciation: when it books, the car's value drops by its share, and Accounts compares each car's value and monthly depreciation with the fund it feeds.

### Changed

- gripr: the MCP server for adding transactions from a chat assistant is removed.
- gainr: Trading 212's weekly batch tells interest and cashback apart: the interest is an Interest row in gainr's cash, the cashback a Deposit there (it pays for the pie's TDIV buys) and income in the gripr account you pick in gainr's settings.
- Settings sections (Period, Banks in gripr; Trading 212 in gainr) start folded: tap a title to open it. They open themselves when something needs you, such as a sync result or an instrument to link.
- Sync is an icon everywhere (circular arrows, spinning while it runs), and in Banks it sits in the section's header instead of at the bottom.
- gainr: the Trading 212 sync moved from the Transactions page into a settings gear in the top row, like gripr's.
- gainr: Home's title reads "Home (Main)" instead of a separate portfolio line underneath.
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
