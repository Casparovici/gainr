import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { briefrApi } from "../../api/briefrClient";
import type { BriefrAttention, BriefrReport } from "../../api/briefrTypes";
import ReportCard from "../../components/briefr/ReportCard";
import InfoHeading from "../../components/ui/InfoTip";
import { ModuleTopRow, secondaryButtonClass } from "../../components/ui/kit";
import { agentLabel, ATTENTION_LABELS, ATTENTIONS } from "../../utils/briefr";
import { t } from "../../i18n";

const cardClass = "rounded-2xl border border-ui-border bg-ui-surface px-4 py-6 text-center text-sm text-ui-muted";

/** briefr's inbox (or, with `archived`, its archive): the reports agents committed overnight,
 * newest first, filtered by agent and by how much they ask of you. A report opens in place to its
 * findings and write-up, which marks it read; archiving takes it out of the inbox. `now` is
 * injectable so tests don't depend on the clock. */
export default function BriefrInbox({ archived = false, now: nowOverride }: { archived?: boolean; now?: Date } = {}) {
  const now = nowOverride ?? new Date();
  const queryClient = useQueryClient();
  const [agent, setAgent] = useState<string | null>(null);
  const [attention, setAttention] = useState<BriefrAttention | null>(null);
  const [openId, setOpenId] = useState<number | null>(null);

  const reportsQuery = useQuery({
    queryKey: ["briefr-reports", { archived, agent, attention }],
    queryFn: () => briefrApi.listReports({ archived, agent, attention }),
  });
  const agentsQuery = useQuery({ queryKey: ["briefr-agents"], queryFn: briefrApi.listAgents });

  const refresh = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["briefr-reports"] }),
      queryClient.invalidateQueries({ queryKey: ["briefr-agents"] }),
    ]);
  const setRead = useMutation({
    mutationFn: ({ id, isRead }: { id: number; isRead: boolean }) => briefrApi.setRead(id, isRead),
    onSuccess: refresh,
  });
  const setArchived = useMutation({
    mutationFn: ({ id, isArchived }: { id: number; isArchived: boolean }) => briefrApi.setArchived(id, isArchived),
    onSuccess: () => {
      setOpenId(null);
      return refresh();
    },
  });

  const toggle = (report: BriefrReport) => {
    if (openId === report.id) {
      setOpenId(null);
      return;
    }
    setOpenId(report.id);
    if (!report.is_read) setRead.mutate({ id: report.id, isRead: true });
  };

  const reports = reportsQuery.data;
  const unread = reports?.filter((r) => !r.is_read).length ?? 0;
  const toAct = reports?.filter((r) => r.attention === "act").length ?? 0;
  const filtered = agent !== null || attention !== null;
  const title = archived ? t("Archive") : t("Inbox");

  return (
    <div className="flex flex-col gap-4">
      <ModuleTopRow />

      <div className="flex flex-col gap-1 pt-2">
        <InfoHeading
          title={<h1 className="m-0 font-display text-4xl font-bold leading-[1.05] tracking-[-0.025em] text-ui-ink">{title}</h1>}
          label="briefr"
          textClassName="m-0 text-sm text-ui-ink-soft"
          buttonClassName="text-ui-muted hover:text-ui-ink"
        >{t("Reports from your agents. Each agent runs on its own schedule, commits its report to the agents repository, and the server picks it up within ten minutes. A report is marked Act, Watch or Info by its most urgent finding. Opening one marks it read; archive it once you're done with it. Agents only report: nothing here trades or changes anything.")}</InfoHeading>
        {!archived && reports && reports.length > 0 && (
          <p className="m-0 text-[15px] text-ui-ink-soft">
            {t("{n} unread", { n: unread })}{toAct > 0 && ` · ${t("{n} to act on", { n: toAct })}`}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        {(agentsQuery.data?.length ?? 0) > 1 && (
          <select
            value={agent ?? ""}
            onChange={(e) => setAgent(e.target.value || null)}
            aria-label={t("Agent")}
            className="h-11 rounded-xl border border-ui-line bg-ui-surface px-3 text-[15px] text-ui-ink sm:w-56"
          >
            <option value="">{t("All agents")}</option>
            {agentsQuery.data?.map((a) => (
              <option key={a.agent} value={a.agent}>
                {agentLabel(a.agent)}
              </option>
            ))}
          </select>
        )}
        <div className="flex h-11 items-stretch gap-1 rounded-xl border border-ui-border bg-ui-surface p-1 sm:w-fit" role="group" aria-label={t("Attention")}>
          {[null, ...ATTENTIONS].map((level) => (
            <button
              key={level ?? "all"}
              type="button"
              onClick={() => setAttention(level)}
              aria-pressed={attention === level}
              className={`flex-1 rounded-lg px-4 text-sm font-semibold transition-colors ${
                attention === level ? "bg-ui-brand-soft text-ui-brand-strong" : "text-ui-muted hover:text-ui-ink"
              }`}
            >
              {level === null ? t("All") : t(ATTENTION_LABELS[level])}
            </button>
          ))}
        </div>
      </div>

      {(setRead.isError || setArchived.isError) && (
        <p className="m-0 text-sm text-ui-late" role="alert">
          {setArchived.isError ? t("Couldn't archive the report — try again.") : t("Couldn't mark the report — try again.")}</p>
      )}

      {reportsQuery.isPending ? (
        <div className={cardClass} role="status">{t("Loading reports…")}</div>
      ) : reportsQuery.isError || !reports ? (
        <div className={cardClass} role="alert">{t("Couldn't load the reports.")}{" "}
          <button type="button" onClick={() => reportsQuery.refetch()} className={`${secondaryButtonClass} mt-3 flex w-full sm:mx-auto sm:w-auto`}>{t("Try again")}</button>
        </div>
      ) : reports.length === 0 ? (
        <div className={cardClass}>
          <p className="m-0 font-display text-lg font-bold text-ui-ink">
            {filtered ? t("Nothing matches") : archived ? t("Nothing archived") : t("Inbox zero")}
          </p>
          <p className="m-0 mt-1">
            {filtered
              ? t("No reports match these filters.")
              : archived
                ? t("Reports you archive from the inbox are kept here.")
                : t("No reports waiting. New ones appear here after the agents' nightly runs.")}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {reports.map((report) => (
            <ReportCard
              key={report.id}
              report={report}
              now={now}
              open={openId === report.id}
              onToggle={() => toggle(report)}
              onMarkUnread={() => setRead.mutate({ id: report.id, isRead: false })}
              onArchive={(isArchived) => setArchived.mutate({ id: report.id, isArchived })}
              isBusy={setRead.isPending || setArchived.isPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}
