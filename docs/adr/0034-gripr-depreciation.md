# 34. gripr: a transfer into a fund can be an asset's depreciation

## Status

Accepted

## Context

The reader's cars are manually valued asset accounts (a Ford Focus, a Peugeot 107). Every month a
transfer goes from Trade Republic into "Afschrijving Auto", an account tracking the Auto portfolio
in gainr, where it's invested. That transfer is meant to equal what the cars lose in value that
month, so the fund can eventually replace them. But nothing linked the two: the car's value only
moved when the reader edited it, so there was no view of whether the fund kept up.

## Decision

A recurring transfer can say which assets it is the depreciation of, and how much of the transfer
each is (`pefi_depreciations`): €96 of the monthly transfer is the Focus, €25 the Peugeot. When an
occurrence books, each asset's manual value drops by its share. The fund follows the market; the
asset follows the plan, which is the contrast the reader wants to see.

- **Applied with the other side effects** of a transaction (loan balances, the portfolio mirror):
  a pre-booked occurrence waits for its due date, and an edit or delete reverses what was
  applied. A booked transfer keeps a snapshot of its depreciation rows, so changing the rule
  later doesn't change what an earlier month is reversed by.
- **Net worth is unchanged on that day**: the asset loses what the fund gains. Only the fund's
  market movement and a manual revaluation move it afterwards.
- **Only a manually valued asset account**, only on a transfer, and never more than the transfer
  itself (validated).
- **Every path that books the rule's transfer carries it**: the recurring job, a pre-booked
  occurrence, and a bank entry the sync books or files under the rule.
- **A view**: Accounts shows each asset's value, monthly depreciation and months left at that
  pace, and each fund's balance as a share of the value depreciating into it ("covers 24,7%").

Nothing is back-filled: months already booked before the rule said so did not touch the car.

## Alternatives considered

- **The asset loses value on its own schedule** (a monthly depreciation on the account). Needs no
  transfer rule, but net worth drops by the depreciation with nothing offsetting it until the
  transfer lands, and the two numbers can drift apart when one is changed.
- **An expense category linked to the asset**, like loan-linked categories (ADR 0003). A
  transfer has no category, and the depreciation isn't spending, so it would put an expense in
  the budget that was never paid.
- **One rule per asset.** Simpler to model, but the bank's single €121 entry would no longer match
  one booked row, and it would be booked twice (ADR 0029).

## Consequences

- Splitting the transfer between several assets is one rule with several rows, keeping one booked
  transfer to match the bank's entry.
- The asset's value follows the plan, not the market; a revaluation (Correct balance) is still the
  reader's call.
- A rule that stops (ends, is paused) stops the depreciation.
