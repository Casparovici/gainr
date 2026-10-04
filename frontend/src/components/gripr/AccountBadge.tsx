import type { GriprAccount } from "../../api/griprTypes";
import { resolveAccountColor } from "../../utils/accountColor";

/** A colour-coded pill for an account name, so which account a transaction or recurring rule
 * sits on reads at a glance instead of blending into the row's plain text — same idea as the
 * type/category badges next to it. Falls back to neutral slate if the account can't be
 * resolved (shouldn't happen, but a row's own `account_name`/`counter_account_name` is a
 * static snapshot that could theoretically outlive an account rename this list hasn't
 * refetched yet). */
export default function AccountBadge({ name, account }: { name: string; account: GriprAccount | undefined }) {
  const color = account ? resolveAccountColor(account) : "#94a3b8";
  return (
    <span className="rounded-full px-2 py-0.5 text-xs font-medium" style={{ backgroundColor: `${color}1a`, color }}>
      {name}
    </span>
  );
}
