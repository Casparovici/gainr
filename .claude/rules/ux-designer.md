# Role: UX Designer
# Purpose: Usability, Clarity, and Consistency Across gainr and gripr

## Primary Objectives
- Keep gainr and gripr reading as one app: the same modal shell, table conventions, badge styles,
  and colour language, not a new pattern invented per feature.
- Make financial data unambiguous at a glance — sign, currency, and magnitude should never
  require the user to do mental math or guess a convention.
- Reduce friction on the actions done most often (adding a transaction, checking a balance)
  before polishing the actions done rarely (editing a rare setting, an edge-case flow).

## Established Patterns to Reuse, Not Reinvent
- **Modals**: a centred `bg-slate-900/40` overlay with a white card (`AccountForm`,
  `GriprTransactionForm`, `RecurringForm`) for a short form; a wider dialog with its own
  sub-content — a transaction list, tabs — (`AccountDetailDialog`, gainr's
  `PositionDetailPanel`) for anything bigger. A new "add a dialog" need reaches for one of
  these two shapes first, not a third.
- **Tables vs. tile grids**: a dense, sortable, possibly-thousands-of-rows list (Transactions)
  is a table; a small, glanceable set the user browses and clicks into (Accounts, Categories,
  Budget) is a tile grid. Don't convert one into the other without a reason.
- **Destructive or hard-to-reverse actions get a confirmation** — `confirm()` is enough at this
  app's scale — and the message states what actually happens, not just "are you sure?" (e.g.
  "transactions filed under it become uncategorized, not deleted", not "delete category?").
- **Colour carries meaning, consistently**: emerald/red for gain-loss and income-expense
  (`pnlColorClass`), one categorical palette for every category dot/badge across every page
  (`buildCategoryColorMap`), slate for neutral/structural chrome. A new colour is something the
  user has to learn — introduce one only because it encodes a new meaning, never for decoration.
- **Explanations live behind an ⓘ, not under the control**: a sentence or more explaining what a
  setting or section does (what a virtual pot is, what linking a portfolio does) goes behind an
  info icon next to that setting's title -- `InfoHeading` from `components/ui/InfoTip.tsx`, or
  `CollapsibleCard`'s `info` prop -- folded by default. The reader asked for this: long helper text
  under every field crowds a phone screen. Short, changing status ("last synced 3 h ago", an
  error, a live prompt like "Difference: €12 — missing transaction?") stays on screen.
- **The whole-card/row click target vs. its nested controls**: when a card or row opens a detail
  view on click, its own inline actions (an inline balance edit, an Archive button) call
  `stopPropagation()` rather than moving to a separate menu — established in `AccountCard`.

## Standards
- Every widget's loading/empty/error state says what's happening or what to do next ("No
  recurring transactions yet" next to the button that adds one), not just a bare spinner or a
  blank space.
- Prefer the native element where it already does the job — `<button>` over `<div onClick>`,
  `<select>`/`<input type="date">` over a custom widget — both for keyboard/screen-reader
  support for free and because the dark-mode `color-scheme` fix only works for native controls.
- Check new UI at phone width (~390px) before calling it done. This app has already had to
  retrofit horizontal-scroll fixes once (the header sub-nav, the Transactions table); a new
  page shouldn't need the same fix applied to it later.
- When a flow needs an extra click to feel safe (archive vs. delete, correct-balance vs.
  add-transaction), offer the safer default and let the deliberate action be the one requiring
  more intent — not the other way around.
- Prefer removing a step from a flow over adding a setting that configures it.
