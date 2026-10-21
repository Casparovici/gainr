import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { griprApi } from "../../api/griprClient";
import { listrApi } from "../../api/listrClient";
import type { ListrPicnicSyncSettingsInput } from "../../api/listrTypes";
import { todayIsoDate } from "../../utils/format";
import { inputClass, primaryButtonClass, secondaryButtonClass } from "../ui/kit";
import { dateLocale, t, tp } from "../../i18n";

// Labels above are small caps; the controls themselves read as plain text.
const controlClass = `${inputClass} font-normal normal-case tracking-normal`;

/** "Automatisch verwerken": whether a delivered Picnic order is booked as a gripr expense (on
 * the chosen account and category) and restocks Voorraad. Off until switched on; `since` keeps
 * it from reaching back further than the reader chooses. The backend matches orders already
 * booked by hand, so switching it on alongside manual booking doesn't double-count (see
 * picnic_sync_service). */
export default function PicnicSyncCard() {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({ queryKey: ["listr-picnic-sync-settings"], queryFn: () => listrApi.picnicSyncSettings() });
  const accountsQuery = useQuery({ queryKey: ["gripr-accounts", false], queryFn: () => griprApi.listAccounts() });
  const categoriesQuery = useQuery({ queryKey: ["gripr-categories"], queryFn: () => griprApi.listCategories() });

  const [draft, setDraft] = useState<ListrPicnicSyncSettingsInput | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  useEffect(() => {
    if (settingsQuery.data && draft === null) {
      const { last_synced_at: _lastSynced, ...rest } = settingsQuery.data;
      setDraft(rest);
    }
  }, [settingsQuery.data, draft]);

  const refreshAfterSync = () => {
    queryClient.invalidateQueries({ queryKey: ["listr-picnic-sync-settings"] });
    queryClient.invalidateQueries({ queryKey: ["listr-picnic-orders"] });
    queryClient.invalidateQueries({ queryKey: ["listr-inventory"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-transactions"] });
    queryClient.invalidateQueries({ queryKey: ["gripr-accounts"] });
  };
  const saveMutation = useMutation({
    mutationFn: (input: ListrPicnicSyncSettingsInput) => listrApi.updatePicnicSyncSettings(input),
    onSuccess: (saved) => {
      const { last_synced_at: _lastSynced, ...rest } = saved;
      setDraft(rest);
      setFeedback(saved.enabled ? t("Opgeslagen.") : t("Uitgeschakeld."));
      refreshAfterSync();
    },
    onError: () => setFeedback(t("Opslaan is mislukt.")),
  });
  const syncMutation = useMutation({
    mutationFn: () => listrApi.runPicnicSync(),
    onSuccess: (r) => {
      setFeedback(
        r.deliveries === 0
          ? t("Geen nieuwe leveringen.")
          : tp(
              r.deliveries,
              "{n} levering verwerkt: {booked} geboekt, {matched} al geboekt, {restocked} op voorraad.",
              "{n} leveringen verwerkt: {booked} geboekt, {matched} al geboekt, {restocked} op voorraad.",
              { booked: r.orders_booked, matched: r.orders_matched, restocked: r.items_restocked },
            ),
      );
      refreshAfterSync();
    },
    onError: () => setFeedback(t("Verwerken is mislukt. Is Picnic nog verbonden?")),
  });

  if (settingsQuery.isError) {
    return <div className="rounded-2xl bg-ui-late-soft px-4 py-3.5 text-sm font-semibold text-ui-late">{t("Instellingen laden is mislukt.")}</div>;
  }
  if (!draft) {
    return <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">{t("Laden…")}</div>;
  }

  const accounts = (accountsQuery.data ?? []).filter((a) => !a.is_archived);
  const categories = categoriesQuery.data ?? [];
  const byId = new Map(categories.map((c) => [c.id, c]));
  const expenseCategories = categories
    .filter((c) => c.kind === "expense" && !c.is_archived)
    .map((c) => ({ id: c.id, label: c.parent_id !== null ? `${byId.get(c.parent_id)?.name ?? ""} › ${c.name}` : c.name }))
    .sort((a, b) => a.label.localeCompare(b.label, "nl"));
  const saved = settingsQuery.data;
  const dirty =
    !!saved &&
    (saved.enabled !== draft.enabled ||
      saved.gripr_account_id !== draft.gripr_account_id ||
      saved.gripr_category_id !== draft.gripr_category_id ||
      saved.since !== draft.since);
  const set = (fields: Partial<ListrPicnicSyncSettingsInput>) => {
    setFeedback(null);
    setDraft({ ...draft, ...fields });
  };

  return (
    <section className="flex flex-col gap-3 rounded-[20px] border border-ui-border bg-ui-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h2 className="m-0 font-display text-xl font-bold tracking-[-0.02em] text-ui-ink">{t("Automatisch verwerken")}</h2>
          <p className="m-0 text-sm text-ui-ink-soft">{t("Een bezorgde bestelling wordt een uitgave in gripr (wat Picnic afschrijft, met statiegeld), en producten die je in Voorraad bijhoudt worden aangevuld. Al zelf geboekt? Een uitgave van precies dat bedrag op die rekening, rond de besteldatum, wordt herkend en niet dubbel geboekt.")}</p>
        </div>
        <label className="flex shrink-0 cursor-pointer items-center gap-2 pt-1 text-sm font-semibold text-ui-ink">
          <input
            type="checkbox"
            className="h-5 w-5 accent-ui-brand"
            checked={draft.enabled}
            onChange={(e) => set({ enabled: e.target.checked, since: draft.since ?? (e.target.checked ? todayIsoDate() : null) })}
          />{t("Aan")}</label>
      </div>

      {draft.enabled && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{t("Rekening")}<select
              className={controlClass}
              value={draft.gripr_account_id ?? ""}
              onChange={(e) => set({ gripr_account_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">{t("Niet boeken in gripr")}</option>
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{t("Categorie")}<select
              className={controlClass}
              value={draft.gripr_category_id ?? ""}
              onChange={(e) => set({ gripr_category_id: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">{t("Kies een categorie")}</option>
              {expenseCategories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-[0.06em] text-ui-muted">{t("Leveringen vanaf")}<input
              type="date"
              className={controlClass}
              value={draft.since ?? ""}
              max={todayIsoDate()}
              onChange={(e) => set({ since: e.target.value || null })}
            />
          </label>
        </div>
      )}
      {draft.enabled && (draft.gripr_account_id === null || draft.gripr_category_id === null) && (
        <p className="m-0 text-xs text-ui-muted">{t("Zonder rekening en categorie wordt alleen Voorraad aangevuld.")}</p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => saveMutation.mutate(draft)}
          disabled={!dirty || saveMutation.isPending}
          className={`${primaryButtonClass} h-11`}
        >
          {saveMutation.isPending ? t("Opslaan…") : t("Opslaan")}
        </button>
        {saved?.enabled && (
          <button type="button" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending || dirty} className={secondaryButtonClass}>
            {syncMutation.isPending ? t("Bezig…") : t("Nu verwerken")}
          </button>
        )}
        {saved?.last_synced_at && (
          <span className="text-xs text-ui-muted">{t("Laatst:")}{" "}{new Date(saved.last_synced_at).toLocaleString(dateLocale("nl-NL"), { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
          </span>
        )}
      </div>
      {feedback && <p className="m-0 text-sm text-ui-ink-soft">{feedback}</p>}
    </section>
  );
}
