import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { griprApi } from "../../api/griprClient";
import type { GriprAccount, GriprBankConnection, GriprBankRule, GriprBankStatus, GriprBankSyncResult } from "../../api/griprTypes";
import { decimalInputToApi, formatDate, formatEur, formatRelativeTime } from "../../utils/format";
import InfoHeading from "../ui/InfoTip";
import { inputClass } from "../ui/kit";
import SettingsSection from "../ui/SettingsSection";
import SyncButton from "../ui/SyncButton";
import GriprButton from "./GriprButton";
import { useConfirmDialog } from "./useConfirmDialog";
import { msg, t } from "../../i18n";

// A consent this close to its end gets a "reconnect" nudge -- ING allows 180 days, Trade
// Republic 90.
const RECONNECT_WARNING_DAYS = 14;

const CALLBACK_MESSAGES: Record<string, string> = {
  connected: msg("Connected. Check which gripr account each bank account books into, then switch syncing on."),
  cancelled: msg("Connecting was cancelled — nothing changed."),
  failed: msg("Connecting didn't work. Try again from here."),
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
    r.booked && t("{n} booked", { n: r.booked }),
    r.fulfilled && t("{n} filed under a recurring rule", { n: r.fulfilled }),
    r.matched && t("{n} already in gripr", { n: r.matched }),
  ].filter(Boolean);
  const problems = Object.entries(r.problems).map(([bank, problem]) => `${bank}: ${problem}`);
  return [parts.length ? `${parts.join(", ")}.` : t("Nothing new from your banks."), ...problems].join(" ");
}

function ruleLabel(rule: GriprBankRule): string {
  const size = rule.amount !== null ? formatEur(rule.amount) : rule.amount_max !== null ? t("up to {amount}", { amount: formatEur(rule.amount_max) }) : "";
  const amount = size
    ? [
        rule.direction === "out" ? t("money out") : rule.direction === "in" ? t("money in") : "",
        size,
        rule.day_of_month !== null ? t("around the {day}", { day: ordinal(rule.day_of_month) }) : "",
      ]
        .filter(Boolean)
        .join(" ")
    : "";
  const parts = [rule.iban ?? "", rule.text_contains ? `“${rule.text_contains}”` : "", amount].filter(Boolean);
  return parts.join(" + ");
}

function ordinal(day: number): string {
  if (day % 10 === 1 && day !== 11) return t("{day}st", { day });
  if (day % 10 === 2 && day !== 12) return t("{day}nd", { day });
  if (day % 10 === 3 && day !== 13) return t("{day}rd", { day });
  return t("{day}th", { day });
}

/** The bank connections (docs/adr/0029), as the Banks section of gripr's settings dialog: per
 * bank, connect/reconnect through Enable Banking, which gripr account each of its accounts books
 * into, and on/off from a start date; shared across banks, which counterparties are the reader's
 * own accounts (booked as transfers). On a server without the Enable Banking settings it says so
 * instead -- there's nothing the reader could do with it there. */
export default function BankSettings({ defaultOpen = false }: { defaultOpen?: boolean } = {}) {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const { confirm, dialog } = useConfirmDialog();
  const statusQuery = useQuery({ queryKey: ["gripr-banks"], queryFn: () => griprApi.getBanks() });
  const accountsQuery = useQuery({ queryKey: ["gripr-accounts", false], queryFn: () => griprApi.listAccounts() });

  // A bank's redirect lands here with ?bank=connected|cancelled|failed -- shown once, then
  // dropped from the URL so a reload doesn't repeat it.
  const callback = searchParams.get("bank");
  // Folded away like every settings section, but open when a bank's redirect brought the reader
  // here (the outcome is in it) and after a sync (so is its result).
  const [open, setOpen] = useState(defaultOpen || !!callback);
  const [feedback, setFeedback] = useState<{ text: string; link?: boolean } | null>(
    callback && CALLBACK_MESSAGES[callback] ? { text: t(CALLBACK_MESSAGES[callback]) } : null,
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
    onError: onFailure(t("Couldn't start connecting. Try again in a moment.")),
  });
  const settingsMutation = useMutation({
    mutationFn: ({ id, enabled, since }: { id: number; enabled: boolean; since: string | null }) =>
      griprApi.updateBank(id, { enabled, since }),
    onSuccess: (status) => {
      setStatus(status);
      // Recurring rules on bank-fed accounts stop or resume booking with this switch.
      queryClient.invalidateQueries({ queryKey: ["gripr-recurring"] });
    },
    onError: onFailure(t("Saving didn't work.")),
  });
  const mapMutation = useMutation({
    mutationFn: ({ iban, accountId }: { iban: string; accountId: number | null }) => griprApi.mapBankAccount(iban, accountId),
    onSuccess: setStatus,
    onError: onFailure(t("Saving the account didn't work.")),
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
    onError: onFailure(t("That rule wasn't saved — check the IBAN (or leave it empty and use the text).")),
  });
  const deleteRuleMutation = useMutation({
    mutationFn: (id: number) => griprApi.deleteBankRule(id),
    onSuccess: setStatus,
    onError: onFailure(t("Removing the rule didn't work.")),
  });
  const syncMutation = useMutation({
    mutationFn: () => griprApi.syncBanks(),
    onSuccess: (result) => {
      setFeedback({ text: describeResult(result), link: result.booked > 0 });
      setOpen(true);
      queryClient.invalidateQueries({ queryKey: ["gripr-banks"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-transactions"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-receivables"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-accounts"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-recurring"] });
      queryClient.invalidateQueries({ queryKey: ["gripr-notifications"] });
    },
    onError: () => {
      setFeedback({ text: t("Syncing didn't work. Try again in a moment.") });
      setOpen(true);
      queryClient.invalidateQueries({ queryKey: ["gripr-banks"] });
    },
  });
  const disconnectMutation = useMutation({
    mutationFn: (id: number) => griprApi.disconnectBank(id),
    onSuccess: (status) => {
      setStatus(status);
      setFeedback({ text: t("Disconnected.") });
      queryClient.invalidateQueries({ queryKey: ["gripr-recurring"] });
    },
    onError: onFailure(t("Disconnecting didn't work.")),
  });

  async function handleDisconnect(connection: GriprBankConnection) {
    const ok = await confirm({
      title: t("Disconnect {name}?", { name: connection.name }),
      description: t(
        "This ends the consent at {name} and stops booking its new transactions. Everything already booked stays, and recurring rules on its accounts go back to booking their own rows. Your account choices are kept for when you reconnect.",
        { name: connection.name },
      ),
      confirmLabel: t("Disconnect"),
      destructive: true,
    });
    if (ok) disconnectMutation.mutate(connection.id);
  }

  const section = (body: ReactNode, actions?: ReactNode) => (
    <SettingsSection title={t("Banks")} open={open} onOpenChange={setOpen} actions={actions}>
      {body}
    </SettingsSection>
  );

  if (statusQuery.isLoading) {
    return section(<p className="text-sm text-on-surface-variant">{t("Loading your bank connections…")}</p>);
  }
  if (statusQuery.isError || !statusQuery.data) {
    return section(
      <p className="rounded-xl bg-error-container px-3 py-2 text-sm text-on-error-container">{t("Couldn't load your bank connections. Close and reopen settings to try again.")}</p>,
    );
  }
  const status = statusQuery.data;
  if (!status.configured && !status.connections.some((c) => c.connected)) {
    return section(
      <p className="text-sm text-on-surface-variant">{t("Bank connections aren't set up on this server, so transactions are entered by hand.")}</p>,
    );
  }

  const accounts: GriprAccount[] = (accountsQuery.data ?? []).filter((a) => !a.is_archived);
  const accountName = (id: number | null) => accounts.find((a) => a.id === id)?.name ?? "—";
  const syncing = status.connections.filter((c) => c.enabled && c.connected);

  const syncAction =
    syncing.length > 0 ? <SyncButton pending={syncMutation.isPending} onClick={() => syncMutation.mutate()} /> : null;

  return section(
    <>
      <div className="flex flex-col gap-4">
        {feedback && (
          <p role="status" className="rounded-xl bg-surface-container px-3 py-2 text-sm text-on-surface">
            {feedback.text}{" "}
            {feedback.link && (
              <Link to="/gripr/transactions?category=uncategorized" className="font-medium text-primary hover:underline">{t("Categorise them")}</Link>
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

        <section aria-label={t("Your own accounts")} className="flex flex-col gap-2 border-t border-outline-variant pt-3">
          <InfoHeading label={t("Your own accounts")} title={<h3 className="text-sm font-medium text-on-surface">{t("Your own accounts")}</h3>}>{t("Money to or from these is booked as a transfer, not spending, at every bank. Accounts synced above are recognised by themselves; add the rest here. Match on the IBAN, on text in the description (an Oranje Spaarrekening's number, like B 145-58977), or both — use both for a payment processor whose IBAN other shops share too. For a bank that sends amounts only, match on an amount around a day of the month — exactly (a €121 savings plan on the 2nd) or up to a ceiling (a saveback of at most €15), and only money going out.")}</InfoHeading>
          {status.rules.length > 0 && (
            <ul className="divide-y divide-outline-variant rounded-xl border border-outline-variant">
              {status.rules.map((rule) => (
                <li key={rule.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                  <span className="min-w-0 break-words text-on-surface">
                    {ruleLabel(rule)} <span className="text-on-surface-variant">→ {accountName(rule.gripr_account_id)}</span>
                  </span>
                  <button
                    type="button"
                    aria-label={t("Remove {rule}", { rule: ruleLabel(rule) })}
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
            <input aria-label={t("IBAN")} placeholder={t("IBAN")} value={ruleIban} onChange={(e) => setRuleIban(e.target.value)} className={`${inputClass} col-span-2`} />
            <input
              aria-label={t("Description contains")}
              placeholder={t("Description contains")}
              value={ruleText}
              onChange={(e) => setRuleText(e.target.value)}
              className={`${inputClass} col-span-2`}
            />
            <select aria-label={t("Amount is")} value={ruleAmountKind} onChange={(e) => setRuleAmountKind(e.target.value === "max" ? "max" : "exact")} className={inputClass}>
              <option value="exact">{t("Exactly")}</option>
              <option value="max">{t("Up to")}</option>
            </select>
            <input aria-label={t("Amount")} placeholder={t("€ amount")} inputMode="decimal" value={ruleAmount} onChange={(e) => setRuleAmount(e.target.value)} className={inputClass} />
            <input aria-label={t("Day of month")} placeholder={t("Around day")} inputMode="numeric" value={ruleDay} onChange={(e) => setRuleDay(e.target.value)} className={inputClass} />
            <select
              aria-label={t("Direction")}
              value={ruleDirection}
              onChange={(e) => setRuleDirection(e.target.value === "out" ? "out" : e.target.value === "in" ? "in" : "")}
              className={inputClass}
            >
              <option value="">{t("In or out")}</option>
              <option value="out">{t("Money out")}</option>
              <option value="in">{t("Money in")}</option>
            </select>
            <select aria-label={t("Transfer with")} value={ruleAccount} onChange={(e) => setRuleAccount(e.target.value)} className={`${inputClass} col-span-2 sm:col-span-3`}>
              <option value="">{t("Transfer with…")}</option>
              {accounts.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  {acc.name}
                </option>
              ))}
            </select>
            <GriprButton type="submit" variant="outlined" disabled={!ruleValid || addRuleMutation.isPending} className="col-span-2 sm:col-span-1">{t("Add")}</GriprButton>
          </form>
        </section>

      </div>
      {dialog}
    </>,
    syncAction,
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
      ? t(
          "Card payments arrive with the shop's name and take the category you last gave that shop. Top-ups are matched to the transfer from your bank a couple of days later. Interest and cashback go to gainr instead, as a weekly deposit.",
        )
      : c.amount_only
        ? t(
            "{name} sends only dates and amounts — no shop names. Keep entering its payments yourself; the sync checks them off and books anything you missed, uncategorised, a couple of days after {name} does. It's read once a day in the morning run, not on Sync now: {name} allows only a few reads a day.",
            { name: c.name },
          )
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
                  <span>{t("Read with the API key set on the server")}</span>
                  {c.last_synced_at && <span> {t("· last synced {when}", { when: formatRelativeTime(c.last_synced_at) })}</span>}
                </>
              ) : (
                t("{name} isn't set up on this server — it needs an API key there first.", { name: c.name })
              )
            ) : c.connected ? (
              <>
                <span className={soon ? "font-medium text-error" : undefined}>
                  {t("Connected until {date}", { date: c.valid_until ? formatDate(isoDay(c.valid_until)) : "—" })}
                </span>
                {c.last_synced_at && <span> {t("· last synced {when}", { when: formatRelativeTime(c.last_synced_at) })}</span>}
              </>
            ) : c.accounts.length > 0 ? (
              t("Not connected — your account choices are kept.")
            ) : (
              t("Connect {name} and its transactions are booked here automatically — you only categorise them.", { name: c.name })
            )}
          </p>
          {c.last_error && <p className="text-xs text-error">{c.last_error}</p>}
        </div>
        {c.kind === "consent" && (!c.connected || soon) && (
          <GriprButton variant={c.connected ? "tonal" : "filled"} onClick={onConnect} disabled={busy} className="shrink-0">
            {c.accounts.length > 0 ? t("Reconnect {name}", { name: c.name }) : t("Connect {name}", { name: c.name })}
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
            />{t("Book new transactions automatically")}</label>
          <label className="flex items-center gap-2 text-sm text-on-surface-variant">{t("from")}<input
              type="date"
              aria-label={t("{name} start date", { name: c.name })}
              value={c.since ?? ""}
              disabled={busy}
              onChange={(e) => e.target.value && onSettings(c.enabled, e.target.value)}
              className={inputClass}
            />
          </label>
        </div>
      )}

      {c.accounts.length > 0 && (
        <ul aria-label={t("{name} accounts", { name: c.name })} className="divide-y divide-outline-variant rounded-xl border border-outline-variant">
          {c.accounts.map((a) => (
            <li key={a.iban} className="flex flex-col gap-2 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 text-sm">
                <div className="truncate text-on-surface">
                  {a.product || c.name} <span className="text-on-surface-variant">{lastFour(a.iban)}</span>
                </div>
                <div className="truncate text-xs text-on-surface-variant">
                  {a.holder_name}
                  {!a.in_consent && ` · ${t("not in the current consent")}`}
                </div>
              </div>
              <select
                aria-label={t("gripr account for {account}", { account: `${a.product || c.name} ${lastFour(a.iban)}` })}
                value={a.gripr_account_id ?? ""}
                disabled={busy}
                onChange={(e) => onMap(a.iban, e.target.value === "" ? null : Number(e.target.value))}
                className={`${inputClass} sm:w-56`}
              >
                <option value="">{t("Skip this account")}</option>
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
          <GriprButton variant="text" onClick={onDisconnect} className="-ml-3">{t("Disconnect {name}", { name: c.name })}</GriprButton>
        </div>
      )}
    </section>
  );
}
