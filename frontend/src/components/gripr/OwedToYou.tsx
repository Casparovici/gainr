import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { griprApi } from "../../api/griprClient";
import type { GriprReceivable } from "../../api/griprTypes";
import { formatDate, formatEur } from "../../utils/format";
import InfoHeading from "../ui/InfoTip";
import { useConfirmDialog } from "./useConfirmDialog";

/** What the reader fronted and is still owed (docs/adr/0032): one row per expense, oldest first,
 * with a write-off for money that isn't coming. Counted in net worth until repaid or written off.
 * Hidden while nothing is owed. */
export default function OwedToYou() {
  const queryClient = useQueryClient();
  const { confirm, dialog } = useConfirmDialog();
  const query = useQuery({ queryKey: ["gripr-receivables"], queryFn: () => griprApi.listReceivables() });
  const writeOff = useMutation({
    mutationFn: (id: number) => griprApi.writeOffReceivable(id),
    onSuccess: (data) => {
      queryClient.setQueryData(["gripr-receivables"], data);
      for (const key of ["gripr-transactions", "gripr-budgets", "gripr-overview", "gripr-accounts"]) {
        queryClient.invalidateQueries({ queryKey: [key] });
      }
    },
  });

  async function handleWriteOff(r: GriprReceivable) {
    const ok = await confirm({
      title: `Stop expecting ${formatEur(r.outstanding)} back?`,
      description:
        `What hasn't come back for “${r.notes || r.category_name || "this expense"}” counts as your own spending from now on. ` +
        "The expense and any money that did come back stay as they are.",
      confirmLabel: "Write off",
      destructive: true,
    });
    if (ok) writeOff.mutate(r.id);
  }

  if (query.isLoading) return null;
  if (query.isError || !query.data) {
    return <p className="text-sm text-error">Couldn't load what you're owed. Reload the page to try again.</p>;
  }
  if (query.data.items.length === 0) return null;

  return (
    <section className="rounded-2xl border border-outline-variant bg-surface px-4 py-3" aria-label="Owed to you">
      <div className="flex items-baseline justify-between gap-3">
        <div className="flex flex-col gap-1">
          <InfoHeading label="Owed to you" title={<span className="text-sm text-on-surface-variant">Owed to you</span>}>
            Money you fronted for others and expect back. Your spending already counts only your share; this closes as their
            repayments come in. It counts in net worth until it's repaid or you write it off.
          </InfoHeading>
        </div>
        <span className="text-xl font-semibold tabular-nums text-on-surface">{formatEur(query.data.total)}</span>
      </div>
      <ul className="mt-2 divide-y divide-outline-variant">
        {query.data.items.map((r) => (
          <li key={r.id} className="flex items-center justify-between gap-3 py-2 text-sm">
            <div className="min-w-0">
              <div className="truncate text-on-surface">
                {r.notes || r.category_name || "Expense"}
                {r.expected_from && <span className="text-on-surface-variant"> · {r.expected_from}</span>}
              </div>
              <div className="text-xs text-on-surface-variant">
                {formatDate(r.date)} · {formatEur(r.received)} of {formatEur(r.expected_back)} back
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span className="tabular-nums text-on-surface">{formatEur(r.outstanding)}</span>
              <button
                type="button"
                onClick={() => handleWriteOff(r)}
                disabled={writeOff.isPending}
                className="text-xs font-medium text-primary hover:underline disabled:opacity-50"
              >
                Write off
              </button>
            </div>
          </li>
        ))}
      </ul>
      {dialog}
    </section>
  );
}
