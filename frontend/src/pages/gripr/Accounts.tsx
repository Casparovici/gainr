import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Landmark, Pencil } from "lucide-react";
import { useState } from "react";

import { griprApi } from "../../api/griprClient";
import type { GriprAccount, GriprCategory } from "../../api/griprTypes";
import CollapsibleCard from "../../components/CollapsibleCard";
import OwedToYou from "../../components/gripr/OwedToYou";
import AccountDetailDialog from "../../components/gripr/AccountDetailDialog";
import AccountForm, { type AccountFormInput } from "../../components/gripr/AccountForm";
import BankLogo from "../../components/gripr/BankLogo";
import GriprButton from "../../components/gripr/GriprButton";
import GriprSettingsButton from "../../components/gripr/GriprSettingsButton";
import MobileFab from "../../components/MobileFab";
import { ModuleTopRow, PageTitle, secondaryButtonClass } from "../../components/ui/kit";
import { ACCOUNT_TYPE_LABELS, ACCOUNT_TYPE_ORDER, resolveAccountColor } from "../../utils/accountColor";
import { decimalInputToApi, formatEur, toNumber } from "../../utils/format";

/** A balance reads in the ordinary text colour: money held isn't a gain, so only a negative
 * figure (an overdrawn pot, a loan) is marked, in red. */
function balanceClass(value: string | number | null | undefined): string {
  const n = typeof value === "number" ? value : toNumber(value ?? null);
  return n !== null && n < 0 ? "text-error" : "text-on-surface";
}

function BalanceCell({ account, onSave }: { account: GriprAccount; onSave: (value: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  if (account.balance_mode !== "manual") {
    return (
      <span className={`text-sm font-medium tabular-nums ${balanceClass(account.balance)}`}>{formatEur(account.balance)}</span>
    );
  }

  if (!editing) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setDraft(String(toNumber(account.manual_balance) ?? 0).replace(".", ","));
          setEditing(true);
        }}
        className={`group/balance inline-flex items-center gap-1.5 text-sm font-medium tabular-nums hover:underline ${balanceClass(account.balance)}`}
        title="Typed-in balance — click to update"
      >
        {formatEur(account.balance)}
        {/* Marks a balance that's typed in (a house, a car) rather than added up from
            transactions -- and is where you click to update it. */}
        <Pencil className="h-3 w-3 text-outline group-hover/balance:text-on-surface-variant" strokeWidth={2} />
      </button>
    );
  }

  return (
    <input
      autoFocus
      inputMode="decimal"
      value={draft}
      onClick={(e) => e.stopPropagation()}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => {
        setEditing(false);
        const value = decimalInputToApi(draft);
        if (value !== null) onSave(value);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape") setEditing(false);
      }}
      className="w-28 rounded-md border border-outline px-2 py-1 text-right text-sm"
    />
  );
}

function AccountRow({
  account,
  onSaveBalance,
  onSelect,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDrop,
  isDragTarget,
  heldInName,
}: {
  account: GriprAccount;
  onSaveBalance: (value: string) => void;
  onSelect: () => void;
  onDragStart: () => void;
  onDragEnd: () => void;
  onDragOver: (e: React.DragEvent) => void;
  onDrop: () => void;
  isDragTarget: boolean;
  /** The account this one is a virtual pot inside, if any. */
  heldInName?: string;
}) {
  return (
    <li
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault();
          onSelect();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label={`${account.name}: details and transactions`}
      className={`group relative flex min-h-[44px] cursor-pointer items-center gap-3 py-2 pl-4 pr-4 transition-colors ${
        isDragTarget ? "bg-primary-container" : "hover:bg-surface-container"
      }`}
    >
      {/* The account's own colour, as a thin strip rather than a border, dot and badge. */}
      <span aria-hidden className="absolute bottom-2 left-1 top-2 w-[3px] rounded-full" style={{ backgroundColor: resolveAccountColor(account) }} />
      <span className="flex h-6 w-6 shrink-0 items-center justify-center" title="Drag to reorder">
        {account.bank_logo_key ? (
          <BankLogo bankKey={account.bank_logo_key} size={24} />
        ) : (
          <Landmark className="h-4 w-4 text-on-surface-variant" strokeWidth={2} />
        )}
      </span>
      <span className="min-w-0 flex-1 truncate text-sm text-on-surface">
        {account.name}
        {heldInName && <span className="ml-1.5 text-xs text-on-surface-variant">in {heldInName}</span>}
      </span>
      {account.is_archived && (
        <span className="shrink-0 rounded-full bg-surface-container-high px-2 py-0.5 text-[10px] text-on-surface-variant">archived</span>
      )}
      <span className="shrink-0" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
        <BalanceCell account={account} onSave={onSaveBalance} />
      </span>
    </li>
  );
}

/** What it all adds up to, closing the page like a statement's bottom line. Owned is every
 * positive balance plus what others still owe you for expenses you fronted, owed every negative
 * balance (loans, an overdrawn pot); the bar shows their proportion. */
function NetWorthSummary({ accounts, owedToYou }: { accounts: GriprAccount[]; owedToYou: number }) {
  const balances = accounts.map((a) => toNumber(a.balance) ?? 0);
  const owned = balances.filter((b) => b > 0).reduce((sum, b) => sum + b, 0) + owedToYou;
  const owed = -balances.filter((b) => b < 0).reduce((sum, b) => sum + b, 0);
  const net = owned - owed;
  const ownedShare = owned + owed > 0 ? (owned / (owned + owed)) * 100 : 100;

  return (
    <section className="rounded-2xl border border-outline-variant bg-surface px-4 py-3" aria-label="Net worth">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-sm text-on-surface-variant">Net worth</span>
        <span className={`text-xl font-semibold tabular-nums ${balanceClass(net)}`}>{formatEur(net)}</span>
      </div>
      <div className="mt-2 flex h-1.5 overflow-hidden rounded-full bg-error-container" aria-hidden>
        <div className="h-full rounded-full bg-primary" style={{ width: `${ownedShare}%` }} />
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-on-surface-variant">
        <span>Owned {formatEur(owned)}</span>
        <span>Owed {formatEur(owed)}</span>
      </div>
    </section>
  );
}

export default function GriprAccounts() {
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [draggedId, setDraggedId] = useState<number | null>(null);
  const [dragOverId, setDragOverId] = useState<number | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);

  const receivablesQuery = useQuery({ queryKey: ["gripr-receivables"], queryFn: () => griprApi.listReceivables() });
  const accountsKey = ["gripr-accounts", showArchived] as const;
  const { data: accounts, isLoading } = useQuery({
    queryKey: accountsKey,
    queryFn: () => griprApi.listAccounts(showArchived),
  });
  const { data: categories } = useQuery<GriprCategory[]>({
    queryKey: ["gripr-categories"],
    queryFn: () => griprApi.listCategories(),
  });
  const selectedAccount = (accounts ?? []).find((a) => a.id === selectedAccountId) ?? null;

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["gripr-accounts"] });

  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: number; input: Partial<GriprAccount> }) => griprApi.updateAccount(id, input),
    onSuccess: invalidate,
  });
  const createMutation = useMutation({
    mutationFn: (input: AccountFormInput) => griprApi.createAccount(input),
    onSuccess: () => {
      invalidate();
      setShowForm(false);
    },
  });
  // Applied optimistically to the cache below so a drag feels instant; on failure the
  // invalidate falls back to whatever order the server actually has.
  const reorderMutation = useMutation({
    mutationFn: (accountIds: number[]) => griprApi.reorderAccounts(accountIds),
    onError: invalidate,
  });

  function handleDrop(groupAccounts: GriprAccount[], targetId: number) {
    const sourceId = draggedId;
    setDraggedId(null);
    setDragOverId(null);
    if (sourceId === null || sourceId === targetId) return;

    const ids = groupAccounts.map((a) => a.id);
    const fromIdx = ids.indexOf(sourceId);
    const toIdx = ids.indexOf(targetId);
    if (fromIdx === -1 || toIdx === -1) return;
    ids.splice(toIdx, 0, ids.splice(fromIdx, 1)[0]);

    const groupType = groupAccounts[0].type;
    queryClient.setQueryData<GriprAccount[]>(accountsKey, (old) => {
      if (!old) return old;
      const byId = new Map(old.map((a) => [a.id, a]));
      const reordered = ids.map((id) => byId.get(id)!);
      let cursor = 0;
      return old.map((a) => (a.type === groupType ? reordered[cursor++] : a));
    });
    reorderMutation.mutate(ids);
  }

  const groups = ACCOUNT_TYPE_ORDER.map((type) => {
    const groupAccounts = (accounts ?? []).filter((a) => a.type === type);
    return {
      type,
      accounts: groupAccounts,
      subtotal: groupAccounts.reduce((sum, a) => sum + (toNumber(a.balance) ?? 0), 0),
    };
  }).filter((g) => g.accounts.length > 0);

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow>
        <label className={`${secondaryButtonClass} cursor-pointer text-sm font-medium`}>
          <input type="checkbox" className="h-4 w-4 accent-ui-brand" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          Archived
        </label>
        {/* On mobile this is the FAB's job instead (MobileFab, below). */}
        <GriprButton onClick={() => setShowForm(true)} className="hidden sm:inline-flex">
          New account
        </GriprButton>
        <GriprSettingsButton />
      </ModuleTopRow>
      <PageTitle>Accounts</PageTitle>

      {isLoading ? (
        <div className="rounded-2xl border border-outline-variant bg-surface px-4 py-6 text-center text-on-surface-variant">
          Loading…
        </div>
      ) : groups.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-outline-variant px-4 py-6 text-center text-sm text-on-surface-variant">
          No accounts yet — add your first one to start tracking balances.
        </div>
      ) : (
        <>
          {/* Two columns from lg up, flowing top-to-bottom, so ~20 accounts fit one screen;
              one column on a phone, where each group can be folded away. */}
          <div className="gap-4 lg:columns-2">
            {groups.map((group) => (
              <div key={group.type} className="mb-4 break-inside-avoid">
                <CollapsibleCard
                  storageKey={`gripr-accounts-${group.type}`}
                  cardClassName="overflow-hidden rounded-2xl border border-outline-variant bg-surface"
                  bodyClassName="border-t border-outline-variant"
                  title={
                    <span className="text-on-surface">
                      {ACCOUNT_TYPE_LABELS[group.type]}
                      <span className="ml-1.5 font-normal text-on-surface-variant">{group.accounts.length}</span>
                    </span>
                  }
                  meta={
                    <span className={`text-sm font-medium tabular-nums ${balanceClass(group.subtotal)}`}>
                      {formatEur(group.subtotal)}
                    </span>
                  }
                >
                  <ul className="divide-y divide-outline-variant">
                    {group.accounts.map((account) => (
                      <AccountRow
                        key={account.id}
                        account={account}
                        onSaveBalance={(value) => updateMutation.mutate({ id: account.id, input: { manual_balance: value } })}
                        onSelect={() => setSelectedAccountId(account.id)}
                        onDragStart={() => setDraggedId(account.id)}
                        onDragEnd={() => {
                          setDraggedId(null);
                          setDragOverId(null);
                        }}
                        onDragOver={(e) => {
                          e.preventDefault();
                          if (dragOverId !== account.id) setDragOverId(account.id);
                        }}
                        onDrop={() => handleDrop(group.accounts, account.id)}
                        isDragTarget={dragOverId === account.id && draggedId !== account.id}
                        heldInName={(accounts ?? []).find((a) => a.id === account.held_in_account_id)?.name}
                      />
                    ))}
                  </ul>
                </CollapsibleCard>
              </div>
            ))}
          </div>
          <button
            type="button"
            onClick={() => setShowForm(true)}
            className="hidden self-start text-sm font-medium text-primary hover:underline sm:inline"
          >
            + New account
          </button>
          {/* At the bottom, as the sum of everything above it -- the way a statement reads. */}
          <NetWorthSummary accounts={accounts ?? []} owedToYou={toNumber(receivablesQuery.data?.total) ?? 0} />
          <OwedToYou />
        </>
      )}

      <MobileFab label="New account" onClick={() => setShowForm(true)} />

      {showForm && (
        <AccountForm
          isSubmitting={createMutation.isPending}
          onCancel={() => setShowForm(false)}
          onSubmit={(input) => createMutation.mutate(input)}
        />
      )}

      {selectedAccount && (
        <AccountDetailDialog
          key={selectedAccount.id}
          account={selectedAccount}
          accounts={accounts ?? []}
          categories={categories ?? []}
          onClose={() => setSelectedAccountId(null)}
        />
      )}
    </div>
  );
}
