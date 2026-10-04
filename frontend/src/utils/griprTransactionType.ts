import type { GriprCategoryKind, GriprTransactionType } from "../api/griprTypes";

/** One place for how each gripr transaction type looks and signs, shared by every list that
 * shows transactions or recurring rules. A refund reuses income's colours: both are money
 * coming in, and the badge text already says which. */
export const GRIPR_TYPE_BADGE: Record<GriprTransactionType, string> = {
  expense: "bg-error-container text-on-error-container",
  income: "bg-tertiary-container text-on-tertiary-container",
  refund: "bg-tertiary-container text-on-tertiary-container",
  transfer: "bg-secondary-container text-on-secondary-container",
};

export const GRIPR_TYPE_OPTIONS: { value: GriprTransactionType; label: string }[] = [
  { value: "expense", label: "Expense" },
  { value: "income", label: "Income" },
  { value: "refund", label: "Refund" },
  { value: "transfer", label: "Transfer" },
];

/** Which category kind a type is filed under -- a refund nets against an expense category.
 * Null for a transfer, which has no category. */
export function griprCategoryKindFor(type: GriprTransactionType): GriprCategoryKind | null {
  if (type === "transfer") return null;
  return type === "income" ? "income" : "expense";
}

/** The amount as it affects the account it's booked on: negative for money leaving. */
export function griprSignedAmount(t: { type: GriprTransactionType; amount: string }): number {
  const n = parseFloat(t.amount);
  return t.type === "expense" ? -n : n;
}
