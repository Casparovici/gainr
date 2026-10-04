# 33. gripr is euro-only

## Status

Accepted

## Context

gripr accounts had a `currency` field, defaulting to EUR, that nothing read. Balances, net worth,
budgets and the bank syncs all add amounts up as euros, and the bank sync already skips
non-euro entries. A non-euro account would have been summed into net worth as if its balance
were in euros. Every account the reader has is in euros.

## Decision

Drop `pefi_accounts.currency`. gripr amounts are euros, full stop. gainr keeps per-transaction
currencies and point-in-time FX, because a portfolio genuinely holds USD assets.

## Consequences

- A foreign-currency account (a USD card, a holiday account) can't be represented correctly.
  If one is ever needed, it gets a currency again, with balances converted at the day's rate,
  the way gainr does, rather than a label that changes nothing.
- The MCP server's account list no longer reports a currency.
