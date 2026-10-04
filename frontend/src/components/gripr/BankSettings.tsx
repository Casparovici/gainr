import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { griprApi } from "../../api/griprClient";
import type { GriprAccount, GriprBankConnection, GriprBankRule, GriprBankStatus, GriprBankSyncResult } from "../../api/griprTypes";
import { decimalInputToApi, formatDate, formatEur, formatRelativeTime } from "../../utils/format";
import InfoHeading from "../ui/InfoTip";
import { inputClass } from "../ui/kit";
import GriprButton from "./GriprButton";
import { useConfirmDialog } from "./useConfirmDialog";

// A consent this close to its end gets a "reconnect" nudge -- ING allows 180 days, Trade
// Republic 90.
const RECONNECT_WARNING_DAYS = 14;

const CALLBACK_MESSAGES: Record<string, string> = {
  connected: "Connected. Check which gripr account each bank account books into, then switch syncing on.",
  cancelled: "Connecting was cancelled — nothing changed.",
  failed: "Connecting didn't work. Try again from here.",
};

function lastFour(iban: string): string {
  return `•••• ${iban.slice(-4)}`;
}

function daysUntil(iso: string): number {
  return Math.floor((new Date(iso).getTime() - Date.now()) / 86_400_000);
}

function isoDay(iso: string): string {
  const d = new Date(iso);
  return [d.getFullYear(), String(d.getMonth() + 1).padStart(2, "0"), String(d.getDate()).padStart(2, "0")].join("-");
}

function expiringSoon(c: GriprBankConnection): boolean {
  return c.kind === "consent" && c.connected && c.valid_until !== null && daysUntil(c.valid_until) <= RECONNECT_WARNING_DAYS;
}

function describeResult(r: GriprBankSyncResult): string {
  const parts = [
    r.booked && `${r.booked} booked`,
    r.fulfilled && `${r.fulfilled} filed under a recurring rule`,
    r.matched && `${r.matched} already in gripr`,
  ].filter(Boolean);
  const problems = Object.entries(r.problems).map(([bank, problem]) => `${bank}: ${problem}`);
  return [parts.length ? `${parts.join(", ")}.` : "Nothing new from your banks.", ...problems].join(" ");
}

function ruleLabel(rule: GriprBankRule): string {
  const size = rule.amount !== null ? formatEur(rule.amount) : rule.amount_max !== null ? `up to ${formatEur(rule.amount_max)}` : "";
  const amount = size
    ? [
        rule.direction === "out" ? "money out" : rule.direction === "in" ? "money in" : "",
        size,
        rule.day_of_month !== null ? `around the ${ordinal(rule.day_of_month)}` : "",
      ]
        .filter(Boolean)
        .join(" ")
    : "";
  const parts = [rule.iban ?? "", rule.text_contains ? `“${rule.text_contains}”` : "", amount].filter(Boolean);
  return parts.join(" + ");
}

function ordinal(day: number): string {
  const suffix = day % 10 === 1 && day !== 11 ? "st" : day % 10 === 2 && day !== 12 ? "nd" : day % 10 === 3 && day !== 13 ? "rd" : "th";
  return `${day}${suffix}`;
}

/** The bank connections (docs/adr/0029), as the Banks section of gripr's settings dialog: per
 * bank, connect/reconnect through Enable Banking, which gripr account each of its accounts books
 * into, and on/off from a start date; shared across banks, which counterparties are the reader's
 * own accounts (booked as transfers). On a server without the Enable Banking settings it says so
 * instead -- there's nothing the reader could do with it there. */
export default function BankSettings() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const { confirm, dialog } = useConfirmDialog();
  const statusQuery = useQuery({ queryKey: ["gripr-banks"], queryFn: () => griprApi.getBanks() });
  const accountsQuery = useQuery({ queryKey: ["gripr-accounts", false], queryFn: () => griprApi.listAccounts() });

  // A bank's redirect lands here with ?bank=connected|cancelled|failed -- shown once, then
  // dropped from the URL so a reload doesn't repeat it.
  const callback = searchParams.get("bank");
  const [feedback, setFeedback] = useState<{ text: string; link?: boolean } | null>(
    callback && CALLBACK_MESSAGES[callback] ? { text: CALLBACK_MESSAGES[callback] } : null,
  );
  useEffect(() => {
    if (callback) {
      const next = new URLSearchParams(searchParams);
      next.delete("bank");
      setSearchParams(next, { replace: true });
    }
  }, [callback, searchParams, setSearchParams]);

  const [ruleIban, setRuleIban] = useState("");
  const [ruleText, setRuleText] = useState("");
  const [ruleAmount, setRuleAmount] = useState("");
  const [ruleAmountKind, setRuleAmountKind] = useState<"exact" | "max">("exact");
  const [ruleDay, setRuleDay] = useState("");
  const [ruleDirection, setRuleDirection] = useState<"" | "out" | "in">("");
  const [ruleAccount, setRuleAccount] = useState("");
  const ruleAmountApi = ruleAmount.trim() ? decimalInputToApi(ruleAmount) : null;
  const ruleDayNumber = ruleDay.trim() ? Number(ruleDay) : null;
  const ruleValid =
    !!ruleAccount &&
    (!!ruleIban.trim() || !!ruleText.trim() || ruleAmountApi !== null) &&
    (!ruleAmount.trim() || ruleAmountApi !== null) &&
    (ruleDayNumber === null || (ruleAmountApi !== null && Number.isInteger(ruleDayNumber) && ruleDayNumber >= 1 && ruleDayNumber <= 31));

  const setStatus = (status: GriprBankStatus) => queryClient.setQueryData(["gripr-banks"], status);
  const onFailure = (text: string) => () => setFeedback({ text });

  const connectMutation = useMutation({
    mutationFn: (id: number) => griprApi.connectBank(id),
    onSuccess: ({ url }) => window.location.assign(url),
    onError: onFailure("Couldn't start connecting. Try again in a moment."),
  });
  const settingsMutation = useMutation({
    mutationFn: ({ id, enabled, since }: { id: number; enabled: boolean; since: string | null }) =>
      griprApi.updateBank(id, { enabled, since }),
    onSuccess: (status) => {
      setStatus(status);
      // Recurring rules on bank-fed accounts stop or resume booking with this switch.
      queryClient.invalidateQueries({ queryKey: ["gripr-recurring"] });
    },
    onError: onFailure("Saving didn't work."),
  });
  const mapMutation = useMutation({
    mutationFn: ({ iban, accountId }: { iban: string; accountId: number | null }) => griprApi.mapBankAccount(iban, accountId),
    onSuccess: setStatus,
    onError: onFailure("Saving the account didn't work."),
  });
  const addRuleMutation = useMutation({
    mutationFn: () =>
      griprApi.createBankRule({
        iban: ruleIban.trim() || null,
        text_contains: ruleText.trim() || null,
        amount: ruleAmountKind === "exact" ? ruleAmountApi : null,
        amount_max: ruleAmountKind === "max" ? ruleAmountApi : null,
        day_of_month: ruleDayNumber,
        direction: ruleDirection || null,
        gripr_account_id: Number(ruleAccount),
      }),
    onSuccess: (status) => {
      setStatus(status);
      setRuleIban("");
      setRuleText("");
      setRuleAmount("");
      setRuleAmountKind("exact");
      setRuleDay("");
      setRuleDirection("");
      setRuleAccount("");
    },
    onError: onFailure("That rule wasn't saved — check the IBAN (or leave it empty and use the text)."),
  });
  const deleteRuleMutation = useMutation({
    mutationFn: (id: number) => griprApi.deleteBankRule(id),
    onSuccess: setStatus,
    onError: onFailure("Removing the rule didn't work."),
  });
  const syncMutation = useMutation({
    mutationFn: () => griprApi.syncBanks(),
    onSuccess: (result) => {
      setFeedback({ text: describeResult(result), link: result.booked > 0 });
      queryClient.invalidateQueries({ queryKey: ["gripr-banks"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-receivables"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-recurring"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-notifications"] });
    },
    onError: () => {
      setFeedback({ text: "Syncing didn't work. Try again in a moment." });
      queryClient.invalidateQueries({ queryKey: ["gripr-banks"] });
    },
  });
  const disconnectMutation = useMutation({
    mutationFn: (id: number) => griprApi.disconnectBank(id),
    onSuccess: (status) => {
      setStatus(status);
      setFeedback({ text: "Disconnected." });
      queryClient.invalidateQueries({ queryKey: ["gripr-recurring"] });
    },
    onError: onFailure("Disconnecting didn't work."),
  });

  async function handleDisconnect(connection: GriprBankConnection) {
    const ok = await confirm({
      title: `Disconnect ${connection.name}?`,
      description:
        `This ends the consent at ${connection.name} and stops booking its new transactions. Everything already booked ` +
        "stays, and recurring rules on its accounts go back to booking their own rows. Your account choices are kept " +
        "for when you reconnect.",
      confirmLabel: "Disconnect",
      destructive: true,
    });
    if (ok) disconnectMutation.mutate(connection.id);
  }

  if (statusQuery.isLoading) {
    return <p className="text-sm text-on-surface-variant">Loading your bank connections…</p>;
  }
  if (statusQuery.isError || !statusQuery.data) {
    return (
      <p className="rounded-xl bg-error-container px-3 py-2 text-sm text-on-error-container">
        Couldn't load your bank connections. Close and reopen settings to try again.
      </p>
    );
  }
  const status = statusQuery.data;
  if (!status.configured && !status.connections.some((c) => c.connected)) {
    return (
      <p className="text-sm text-on-surface-variant">
        Bank connections aren't set up on this server, so transactions are entered by hand.
      </p>
    );
  }

  const accounts: GriprAccount[] = (accountsQuery.data ?? []).filter((a) => !a.is_archived);
  const accountName = (id: number | null) => accounts.find((a) => a.id === id)?.name ?? "—";
  const syncing = status.connections.filter((c) => c.enabled && c.connected);

  return (
    <>
      <div className="flex flex-col gap-4">
        {feedback && (
          <p role="status" className="rounded-xl bg-surface-container px-3 py-2 text-sm text-on-surface">
            {feedback.text}{" "}
            {feedback.link && (
              <Link to="/gripr/transactions?category=uncategorized" className="font-medium text-primary hover:underline">
                Categorise them
              </Link>
            )}
          </p>
        )}

        {status.connections.map((connection) => (
          <BankSection
            key={connection.id}
            connection={connection}
            accounts={accounts}
            busy={connectMutation.isPending || settingsMutation.isPending || mapMutation.isPending}
            onConnect={() => connectMutation.mutate(connection.id)}
            onSettings={(enabled, since) => settingsMutation.mutate({ id: connection.id, enabled, since })}
            onMap={(iban, accountId) => mapMutation.mutate({ iban, accountId })}
            onDisconnect={() => handleDisconnect(connection)}
          />
        ))}

        <section aria-label="Your own accounts" className="flex flex-col gap-2 border-t border-outline-variant pt-3">
          <InfoHeading label="Your own accounts" title={<h3 className="text-sm font-medium text-on-surface">Your own accounts</h3>}>
            Money to or from these is booked as a transfer, not spending, at every bank. Accounts synced above are recognised
            by themselves; add the rest here. Match on the IBAN, on text in the description (an Oranje Spaarrekening's number,
            like B 145-58977), or both — use both for a payment processor whose IBAN other shops share too. For a bank that
            sends amounts only, match on an amount around a day of the month — exactly (a €121 savings plan on the 2nd) or up to a
            ceiling (a saveback of at most €15), and only money going out.
          </InfoHeading>
          {status.rules.length > 0 && (
            <ul className="divide-y divide-outline-variant rounded-xl border border-outline-variant">
              {status.rules.map((rule) => (
                <li key={rule.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                  <span className="min-w-0 break-words text-on-surface">
                    {ruleLabel(rule)} <span className="text-on-surface-variant">→ {accountName(rule.gripr_account_id)}</span>
                  </span>
                  <button
                    type="button"
                    aria-label={`Remove ${ruleLabel(rule)}`}
                    onClick={() => deleteRuleMutation.mutate(rule.id)}
                    disabled={deleteRuleMutation.isPending}
                    className="shrink-0 rounded-md p-1 text-on-surface-variant hover:bg-on-surface/5 hover:text-error"
                  >
                    <Trash2 className="h-4 w-4" strokeWidth={2} />
                  </button>
                </li>
              ))}
            </ul>
          )}
          <form
            className="grid grid-cols-2 gap-2 sm:grid-cols-4"
            onSubmit={(e) => {
              e.preventDefault();
              addRuleMutation.mutate();
            }}
          >
            <input aria-label="IBAN" placeholder="IBAN" value={ruleIban} onChange={(e) => setRuleIban(e.target.value)} className={`${inputClass} col-span-2`} />
            <input
              aria-label="Description contains"
              placeholder="Description contains"
              value={ruleText}
              onChange={(e) => setRuleText(e.target.value)}
              className={`${inputClass} col-span-2`}
            />
            <select aria-label="Amount is" value={ruleAmountKind} onChange={(e) => setRuleAmountKind(e.target.value === "max" ? "max" : "exact")} className={inputClass}>
              <option value="exact">Exactly</option>
              <option value="max">Up to</option>
            </select>
            <input aria-label="Amount" placeholder="€ amount" inputMode="decimal" value={ruleAmount} onChange={(e) => setRuleAmount(e.target.value)} className={inputClass} />
            <input aria-label="Day of month" placeholder="Around day" inputMode="numeric" value={ruleDay} onChange={(e) => setRuleDay(e.target.value)} className={inputClass} />
            <select
              aria-label="Direction"
              value={ruleDirection}
              onChange={(e) => setRuleDirection(e.target.value === "out" ? "out" : e.target.value === "in" ? "in" : "")}
              className={inputClass}
            >
              <option value="">In or out</option>
              <option value="out">Money out</option>
              <option value="in">Money in</option>
            </select>
            <select aria-label="Transfer with" value={ruleAccount} onChange={(e) => setRuleAccount(e.target.value)} className={`${inputClass} col-span-2 sm:col-span-3`}>
              <option value="">Transfer with…</option>
              {accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.name}
                </option>
              ))}
            </select>
            <GriprButton type="submit" variant="outlined" disabled={!ruleValid || addRuleMutation.isPending} className="col-span-2 sm:col-span-1">
              Add
            </GriprButton>
          </form>
        </section>

        {syncing.length > 0 && (
          <div>
            <GriprButton variant="tonal" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
              {syncMutation.isPending ? "Syncing…" : "Sync now"}
            </GriprButton>
          </div>
        )}
      </div>
      {dialog}
    </>
  );
}

function BankSection({
  connection,
  accounts,
  busy,
  onConnect,
  onSettings,
  onMap,
  onDisconnect,
}: {
  connection: GriprBankConnection;
  accounts: GriprAccount[];
  busy: boolean;
  onConnect: () => void;
  onSettings: (enabled: boolean, since: string | null) => void;
  onMap: (iban: string, accountId: number | null) => void;
  onDisconnect: () => void;
}) {
  const c = connection;
  const soon = expiringSoon(c);
  const explanation =
    c.kind === "api_key"
      ? "Card payments arrive with the shop's name and take the category you last gave that shop. Top-ups are matched to the " +
        "transfer from your bank a couple of days later. Interest and cashback go to gainr instead, as a weekly deposit."
      : c.amount_only
        ? `${c.name} sends only dates and amounts — no shop names. Keep entering its payments yourself; the sync checks them ` +
          `off and books anything you missed, uncategorised, a couple of days after ${c.name} does. It's read once a ` +
          `day in the morning run, not on Sync now: ${c.name} allows only a few reads a day.`
        : null;
  return (
    <section aria-label={c.name} className="flex flex-col gap-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          {explanation ? (
            <InfoHeading label={c.name} title={<h3 className="text-sm font-medium text-on-surface">{c.name}</h3>}>
              {explanation}
            </InfoHeading>
          ) : (
            <h3 className="text-sm font-medium text-on-surface">{c.name}</h3>
          )}
          <p className="text-xs text-on-surface-variant">
            {c.kind === "api_key" ? (
              c.connected ? (
                <>
                  <span>Read with the API key set on the server</span>
                  {c.last_synced_at && <span> · last synced {formatRelativeTime(c.last_synced_at)}</span>}
                </>
              ) : (
                `${c.name} isn't set up on this server — it needs an API key there first.`
              )
            ) : c.connected ? (
              <>
                <span className={soon ? "font-medium text-error" : undefined}>
                  Connected until {c.valid_until ? formatDate(isoDay(c.valid_until)) : "—"}
                </span>
                {c.last_synced_at && <span> · last synced {formatRelativeTime(c.last_synced_at)}</span>}
              </>
            ) : c.accounts.length > 0 ? (
              "Not connected — your account choices are kept."
            ) : (
              `Connect ${c.name} and its transactions are booked here automatically — you only categorise them.`
            )}
          </p>
          {c.last_error && <p className="text-xs text-error">{c.last_error}</p>}
        </div>
        {c.kind === "consent" && (!c.connected || soon) && (
          <GriprButton variant={c.connected ? "tonal" : "filled"} onClick={onConnect} disabled={busy} className="shrink-0">
            {c.accounts.length > 0 ? `Reconnect ${c.name}` : `Connect ${c.name}`}
          </GriprButton>
        )}
      </div>

      {c.connected && (
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
          <label className="flex items-center gap-2 text-sm text-on-surface">
            <input
              type="checkbox"
              className="h-4 w-4 accent-ui-brand"
              checked={c.enabled}
              disabled={busy}
              onChange={(e) => onSettings(e.target.checked, c.since)}
            />
            Book new transactions automatically
          </label>
          <label className="flex items-center gap-2 text-sm text-on-surface-variant">
            from
            <input
              type="date"
              aria-label={`${c.name} start date`}
              value={c.since ?? ""}
              disabled={busy}
              onChange={(e) => e.target.value && onSettings(c.enabled, e.target.value)}
              className={inputClass}
            />
          </label>
        </div>
      )}

      {c.accounts.length > 0 && (
        <ul aria-label={`${c.name} accounts`} className="divide-y divide-outline-variant rounded-xl border border-outline-variant">
          {c.accounts.map((a) => (
            <li key={a.iban} className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 text-sm">
                <div className="truncate text-on-surface">
                  {a.product || c.name} <span className="text-on-surface-variant">{lastFour(a.iban)}</span>
                </div>
                <div className="truncate text-xs text-on-surface-variant">
                  {a.holder_name}
                  {!a.in_consent && " · not in the current consent"}
                </div>
              </div>
              <select
                aria-label={`gripr account for ${a.product || c.name} ${lastFour(a.iban)}`}
                value={a.gripr_account_id ?? ""}
                disabled={busy}
                onChange={(e) => onMap(a.iban, e.target.value === "" ? null : Number(e.target.value))}
                className={`${inputClass} sm:w-56`}
              >
                <option value="">Skip this account</option>
                {accounts.map((acc) => (
                  <option key={acc.id} value={acc.id}>
                    {acc.name}
                  </option>
                ))}
              </select>
            </li>
          ))}
        </ul>
      )}

      {c.connected && c.kind === "consent" && (
        <div>
          <GriprButton variant="text" onClick={onDisconnect} className="-ml-3">
            Disconnect {c.name}
          </GriprButton>
        </div>
      )}
    </section>
  );
}
