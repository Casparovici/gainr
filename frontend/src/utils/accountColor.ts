import type { GriprAccount, GriprAccountType } from "../api/griprTypes";
import { CATEGORICAL_COLORS } from "./palette";

// Roughly liquid-to-illiquid, and assets/liabilities last — the order a net-worth statement
// conventionally reads in, not alphabetical.
export const ACCOUNT_TYPE_ORDER: GriprAccountType[] = ["checking", "savings", "investment", "credit", "loan", "asset"];

export const ACCOUNT_TYPE_LABELS: Record<GriprAccountType, string> = {
  checking: "Checking & cash",
  savings: "Savings",
  investment: "Investment",
  credit: "Credit",
  loan: "Loans",
  asset: "Other assets",
};

// Fixed per type, not per rank — a checking account is always this colour whether it's the
// first or the fifth in its group. The default every account falls back to until it's given
// its own colour (e.g. a bank's real brand colour) via the account detail dialog's picker.
export const ACCOUNT_TYPE_COLORS: Record<GriprAccountType, string> = Object.fromEntries(
  ACCOUNT_TYPE_ORDER.map((type, i) => [type, CATEGORICAL_COLORS[i % CATEGORICAL_COLORS.length]]),
) as Record<GriprAccountType, string>;

/** The colour this account displays with everywhere — its own override if set, else its
 * type's default. */
export function resolveAccountColor(account: Pick<GriprAccount, "type" | "color">): string {
  return account.color ?? ACCOUNT_TYPE_COLORS[account.type];
}
