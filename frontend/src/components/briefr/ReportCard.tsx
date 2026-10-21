import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ExternalLink } from "lucide-react";
import { useId } from "react";
import { Link } from "react-router-dom";

import { briefrApi } from "../../api/briefrClient";
import type { BriefrItem, BriefrReport, BriefrReportDetail } from "../../api/briefrTypes";
import { NOTR_KEYS, notrApi } from "../../api/notrClient";
import type { NotrNote } from "../../api/notrTypes";
import { agentLabel, ATTENTION_LABELS, countsLabel, LEVEL_CHIP, runLabel, sourceLabel, VERDICT_LABELS } from "../../utils/briefr";
import MarkdownLite from "../MarkdownLite";
import RecipeSuggestion from "./RecipeSuggestion";
import { QueryError } from "../ui/QueryError";
import { secondaryButtonClass } from "../ui/kit";
import { positionPath } from "../../config/modules";
import { t } from "../../i18n";

const chipClass = "inline-flex h-6 items-center rounded-full px-2.5 text-xs font-semibold";

function Finding({ item }: { item: BriefrItem }) {
  return (
    <li className="flex flex-col gap-1 py-3 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`${chipClass} ${LEVEL_CHIP[item.verdict]}`}>{t(VERDICT_LABELS[item.verdict])}</span>
        {item.symbol &&
          (item.asset_id !== null ? (
            <Link to={positionPath(item.asset_id)} className="text-sm font-semibold text-ui-brand-strong hover:underline">
              {item.symbol}
            </Link>
          ) : (
            <span className="text-sm font-semibold text-ui-ink">{item.symbol}</span>
          ))}
        <span className="text-[15px] text-ui-ink">{item.headline}</span>
      </div>
      {item.detail && <p className="m-0 whitespace-pre-line text-sm text-ui-ink-soft">{item.detail}</p>}
      {item.sources.length > 0 && (
        <div className="flex flex-wrap gap-x-3 gap-y-1">
          {item.sources.map((url) => (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[13px] text-ui-muted hover:text-ui-ink hover:underline"
            >
              {sourceLabel(url)}
              <ExternalLink size={12} aria-hidden />
            </a>
          ))}
        </div>
      )}
    </li>
  );
}

/** The report as a note's Markdown: where it came from, the findings as a list, then the write-up. */
export function reportAsNoteBody(report: BriefrReportDetail): string {
  const run = new Date(report.run_at);
  const date = `${run.getFullYear()}-${String(run.getMonth() + 1).padStart(2, "0")}-${String(run.getDate()).padStart(2, "0")}`;
  const parts = [`*${t("Saved from briefr report of {date}", { date })}*`];
  if (report.items.length > 0) {
    parts.push(
      report.items
        .map((item) => `- ${item.symbol ? `**${item.symbol}** ` : ""}${item.headline}${item.detail ? `: ${item.detail.replace(/\s*\n\s*/g, " ")}` : ""}`)
        .join("\n"),
    );
  }
  if (report.body.trim()) parts.push(report.body.trim());
  return parts.join("\n\n");
}

/** Keeps the report in notr: a note with the report's title and text, linked to the positions its
 * findings are about (the ones the server could resolve to a gainr asset). */
function SaveAsNote({ report }: { report: BriefrReportDetail }) {
  const queryClient = useQueryClient();
  const save = useMutation<NotrNote>({
    mutationFn: () =>
      notrApi.createNote({
        title: report.title,
        body: reportAsNoteBody(report),
        asset_ids: [...new Set(report.items.flatMap((i) => (i.asset_id !== null ? [i.asset_id] : [])))],
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTR_KEYS.all }),
  });
  if (save.isSuccess) {
    return (
      <p className="m-0 flex flex-wrap items-center gap-x-2 text-sm text-ui-ink-soft" role="status">
        {t("Saved")}
        <Link to={`/notr/${save.data.id}`} className="font-semibold text-ui-brand-strong hover:underline">{t("Open note")}</Link>
      </p>
    );
  }
  return (
    <div className="flex flex-col items-start gap-2">
      <button type="button" onClick={() => save.mutate()} disabled={save.isPending} className={secondaryButtonClass}>
        {save.isPending ? t("Saving…") : t("Save as note")}
      </button>
      {save.isError && (
        <p className="m-0 text-sm text-ui-late" role="alert">{t("Couldn't save the note. Try again.")}</p>
      )}
    </div>
  );
}

function ReportDetail({ id, now }: { id: number; now: Date }) {
  const detail = useQuery({ queryKey: ["briefr-report", id], queryFn: () => briefrApi.getReport(id) });
  if (detail.isPending) {
    return (
      <p className="m-0 text-sm text-ui-muted" role="status">{t("Loading report…")}</p>
    );
  }
  if (detail.isError) {
    return <QueryError message={t("Couldn't load this report.")} onRetry={() => detail.refetch()} className="text-sm" />;
  }
  const report = detail.data;
  return (
    <div className="flex flex-col gap-4">
      {report.items.length > 0 && (
        <ul className="m-0 list-none divide-y divide-ui-border p-0">
          {report.items.map((item) =>
            item.recipe ? (
              <RecipeSuggestion key={item.id} item={item} recipe={item.recipe} now={now} />
            ) : (
              <Finding key={item.id} item={item} />
            ),
          )}
        </ul>
      )}
      {report.body && (
        <div className="text-[15px] leading-relaxed text-ui-ink">
          <MarkdownLite text={report.body} />
        </div>
      )}
      {report.items.length === 0 && !report.body && <p className="m-0 text-sm text-ui-muted">{t("This report has no write-up.")}</p>}
      <SaveAsNote report={report} />
    </div>
  );
}

/** One report: a tappable summary row that opens to its findings and write-up, with the reader's
 * actions underneath. Opening an unread report is up to the page (it marks it read). */
export default function ReportCard({
  report,
  now,
  open,
  onToggle,
  onMarkUnread,
  onArchive,
  isBusy,
}: {
  report: BriefrReport;
  now: Date;
  open: boolean;
  onToggle: () => void;
  onMarkUnread: () => void;
  onArchive: (archived: boolean) => void;
  isBusy: boolean;
}) {
  const panelId = useId();
  return (
    <article className="rounded-2xl border border-ui-border bg-ui-surface">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-start gap-3 rounded-2xl p-4 text-left"
      >
        <span
          className={`mt-2 h-2 w-2 shrink-0 rounded-full ${report.is_read ? "bg-transparent" : "bg-ui-brand"}`}
          aria-label={report.is_read ? undefined : t("Unread")}
          role={report.is_read ? undefined : "img"}
        />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[13px] text-ui-muted">
            <span className={`${chipClass} ${LEVEL_CHIP[report.attention]}`}>{t(ATTENTION_LABELS[report.attention])}</span>
            <span className="font-semibold text-ui-ink-soft">{agentLabel(report.agent)}</span>
            <span>{runLabel(report.run_at, now)}</span>
          </span>
          <span className={`text-[17px] leading-snug text-ui-ink ${report.is_read ? "font-medium" : "font-bold"}`}>{report.title}</span>
          {report.summary && <span className="text-sm text-ui-ink-soft">{report.summary}</span>}
          <span className="text-[13px] text-ui-muted">{countsLabel(report.counts)}</span>
        </span>
        <ChevronDown size={20} className={`mt-1 shrink-0 text-ui-muted transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>
      {open && (
        <div id={panelId} className="flex flex-col gap-4 border-t border-ui-border px-4 pb-4 pt-4 sm:pl-9">
          <ReportDetail id={report.id} now={now} />
          <div className="flex flex-wrap gap-2">
            {report.is_archived ? (
              <button type="button" onClick={() => onArchive(false)} disabled={isBusy} className={secondaryButtonClass}>{t("Move to inbox")}</button>
            ) : (
              <button type="button" onClick={() => onArchive(true)} disabled={isBusy} className={secondaryButtonClass}>{t("Archive")}</button>
            )}
            {report.is_read && !report.is_archived && (
              <button type="button" onClick={onMarkUnread} disabled={isBusy} className={secondaryButtonClass}>{t("Mark unread")}</button>
            )}
          </div>
        </div>
      )}
    </article>
  );
}
