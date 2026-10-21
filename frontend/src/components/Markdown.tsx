import { createContext, useContext, useMemo, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { taskLineNumbers } from "../utils/markdownEditing";
import { t } from "../i18n";

/** Only the pictures notr itself stores are shown; a picture from anywhere else is left out, so
 * a note can't make the page fetch from a third-party server just by being opened. */
const OWN_IMAGE = /^\/api\/notr\/images\/\d+$/;
const SAFE_LINK = /^(https?:|mailto:|tel:|\/|#)/i;

/** Which `- [ ]` line of the note the list item being rendered is (-1 when it isn't one the
 * server would find). The checkbox itself carries no source position, so its list item says. */
const TaskIndex = createContext(-1);

/** What a checklist item needs from the whole text: where the `- [ ]` lines are, and what to do when
 * one is ticked. */
const TaskContext = createContext<{ lines: number[]; onToggle?: (index: number, checked: boolean) => void }>({ lines: [] });

function safeUrl(url: string): string {
  return OWN_IMAGE.test(url) || SAFE_LINK.test(url) ? url : "";
}

function ListItem({ line, task, children }: { line?: number; task: boolean; children?: ReactNode }) {
  const { lines } = useContext(TaskContext);
  if (!task) return <li className="my-0.5">{children}</li>;
  return (
    <li className="my-0.5 flex list-none items-start gap-2">
      <TaskIndex.Provider value={line === undefined ? -1 : lines.indexOf(line)}>{children}</TaskIndex.Provider>
    </li>
  );
}

/** One stable set of element renderers: a new object on every render would make React remount
 * every element (and lose a checkbox's focus) each time a box is ticked. What they need from the
 * text comes through TaskContext. */
const COMPONENTS: Components = {
  h1: ({ children }) => <h3 className="mb-2 mt-4 font-display text-xl font-bold tracking-[-0.01em] text-ui-ink first:mt-0">{children}</h3>,
  h2: ({ children }) => <h4 className="mb-1.5 mt-4 font-display text-lg font-bold text-ui-ink first:mt-0">{children}</h4>,
  h3: ({ children }) => <h5 className="mb-1 mt-3 text-base font-semibold text-ui-ink first:mt-0">{children}</h5>,
  h4: ({ children }) => <h6 className="mb-1 mt-3 text-base font-semibold text-ui-ink-soft first:mt-0">{children}</h6>,
  h5: ({ children }) => <h6 className="mb-1 mt-3 text-sm font-semibold text-ui-ink-soft first:mt-0">{children}</h6>,
  h6: ({ children }) => <h6 className="mb-1 mt-3 text-sm font-semibold text-ui-muted first:mt-0">{children}</h6>,
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children, className: c }) => (
    <ul className={`my-2 pl-5 ${c?.includes("contains-task-list") ? "list-none pl-0" : "list-disc"}`}>{children}</ul>
  ),
  ol: ({ children }) => <ol className="my-2 list-decimal pl-5">{children}</ol>,
  li: ({ node, children, className }) => (
    <ListItem line={node?.position?.start.line} task={Boolean(className?.includes("task-list-item"))}>
      {children}
    </ListItem>
  ),
  input: ({ checked, type }) => (type === "checkbox" ? <TaskCheckbox checked={Boolean(checked)} /> : null),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-4 border-ui-line pl-3 text-ui-ink-soft">{children}</blockquote>
  ),
  hr: () => <hr className="my-4 border-ui-line" />,
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-xl bg-ui-tile p-3 text-[13px] leading-snug text-ui-ink">{children}</pre>
  ),
  code: ({ children, className: c }) =>
    c ? (
      <code className={c}>{children}</code>
    ) : (
      <code className="rounded bg-ui-tile px-1 py-0.5 text-[0.9em]">{children}</code>
    ),
  a: ({ href, children }) => <SafeLink href={href}>{children}</SafeLink>,
  img: ({ src, alt }) => {
    if (typeof src !== "string" || !OWN_IMAGE.test(src)) return alt ? <span className="text-ui-muted">{alt}</span> : null;
    return (
      <a href={src} target="_blank" rel="noopener noreferrer" className="my-2 block w-fit max-w-full">
        <img src={src} alt={alt ?? ""} loading="lazy" className="max-h-[28rem] max-w-full rounded-xl border border-ui-line object-contain" />
      </a>
    );
  },
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children, style }) => <th style={style} className="border-b border-ui-line px-2 py-1.5 text-left font-semibold">{children}</th>,
  td: ({ children, style }) => <td style={style} className="border-b border-ui-line/60 px-2 py-1.5">{children}</td>,
};

/** A note's Markdown, rendered: headings, lists, checklists, quotes, code, tables, links and
 * pictures. Nothing here touches innerHTML, and raw HTML in the text is shown as text, so a note
 * can't run anything. With `onToggleTask`, a checkbox in the text can be ticked in place (it gets
 * the index of the checkbox among the note's `- [ ]` lines, which is what the server wants).
 *
 * The one renderer for every note -- notr, gainr's Journal and the Notes sections on a position,
 * a plant and a recipe -- in place of MarkdownLite's small subset. */
export default function Markdown({
  text,
  onToggleTask,
  className = "",
}: {
  text: string;
  onToggleTask?: (index: number, checked: boolean) => void;
  className?: string;
}) {
  const taskLines = useMemo(() => taskLineNumbers(text), [text]);
  const tasks = useMemo(() => ({ lines: taskLines, onToggle: onToggleTask }), [taskLines, onToggleTask]);


  return (
    <div className={`text-[15px] leading-relaxed text-ui-ink-soft [overflow-wrap:anywhere] ${className}`}>
      <TaskContext.Provider value={tasks}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS} urlTransform={safeUrl}>
          {text}
        </ReactMarkdown>
      </TaskContext.Provider>
    </div>
  );
}

function SafeLink({ href, children }: { href?: string; children?: ReactNode }) {
  if (!href) return <>{children}</>;
  const external = /^https?:/i.test(href);
  return (
    <a
      href={href}
      {...(external ? { target: "_blank", rel: "noopener noreferrer nofollow" } : {})}
      className="font-medium text-ui-brand-strong underline underline-offset-2"
    >
      {children}
    </a>
  );
}

function TaskCheckbox({ checked }: { checked: boolean }) {
  const index = useContext(TaskIndex);
  const { onToggle } = useContext(TaskContext);
  const canToggle = onToggle !== undefined && index >= 0;
  return (
    <input
      type="checkbox"
      checked={checked}
      disabled={!canToggle}
      readOnly={!canToggle}
      aria-label={t("Done")}
      onChange={(e) => canToggle && onToggle(index, e.target.checked)}
      className="mt-1 h-4 w-4 shrink-0 accent-[rgb(var(--ui-brand-rgb))]"
    />
  );
}
