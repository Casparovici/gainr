import { Fragment, type ReactNode } from "react";

// Longest/most-specific delimiters first in the alternation — "**x**" must never be read as
// italic wrapping a literal asterisk, and "~~x~~" must never fall through to anything else.
// Deliberately not a full markdown parser (no links, no nested emphasis): this is a journal
// entry field, not a document editor. Never touches innerHTML, so nothing here needs sanitizing.
const INLINE_PATTERN = /(\*\*[^*]+?\*\*|~~[^~]+?~~|\*[^*]+?\*|`[^`]+?`)/g;

function renderInline(text: string): ReactNode[] {
  return text.split(INLINE_PATTERN).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("~~") && part.endsWith("~~")) {
      return <del key={i}>{part.slice(2, -2)}</del>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={i} className="rounded bg-slate-100 px-1 py-0.5 text-[0.9em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    return part;
  });
}

function renderLines(text: string): ReactNode {
  const lines = text.split("\n");
  return lines.map((line, li) => (
    <Fragment key={li}>
      {renderInline(line)}
      {li < lines.length - 1 && <br />}
    </Fragment>
  ));
}

type Block =
  | { kind: "heading"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "paragraph"; text: string };

const HEADING_RE = /^#\s+(.*)$/;
const UL_ITEM_RE = /^-\s+(.*)$/;
const OL_ITEM_RE = /^\d+\.\s+(.*)$/;

/** Groups raw lines into block-level chunks — a heading line, a run of bullet/numbered list
 * items, or a paragraph (itself possibly multi-line, blank lines separating one from the
 * next) — so each can get its own element instead of every line becoming a `<br>`-joined run. */
function parseBlocks(text: string): Block[] {
  const lines = text.split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ kind: "paragraph", text: paragraph.join("\n") });
      paragraph = [];
    }
  };

  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const heading = line.match(HEADING_RE);
    if (heading) {
      flushParagraph();
      blocks.push({ kind: "heading", text: heading[1] });
      i++;
      continue;
    }
    if (UL_ITEM_RE.test(line)) {
      flushParagraph();
      const items: string[] = [];
      while (i < lines.length && UL_ITEM_RE.test(lines[i])) {
        items.push(lines[i].match(UL_ITEM_RE)![1]);
        i++;
      }
      blocks.push({ kind: "ul", items });
      continue;
    }
    if (OL_ITEM_RE.test(line)) {
      flushParagraph();
      const items: string[] = [];
      while (i < lines.length && OL_ITEM_RE.test(lines[i])) {
        items.push(lines[i].match(OL_ITEM_RE)![1]);
        i++;
      }
      blocks.push({ kind: "ol", items });
      continue;
    }
    if (line.trim() === "") {
      flushParagraph();
      i++;
      continue;
    }
    paragraph.push(line);
    i++;
  }
  flushParagraph();
  return blocks;
}

/** Renders a journal note body. Blank lines separate paragraphs, single newlines break lines
 * within one; `# heading` lines, `- ` bullet lists and `1. ` numbered lists become their own
 * block; `**bold**`, `*italic*`, `~~strikethrough~~` and `` `code` `` render inline. */
export default function MarkdownLite({ text }: { text: string }) {
  const blocks = parseBlocks(text);
  return (
    <>
      {blocks.map((block, bi) => {
        const spacing = bi > 0 ? "mt-2" : undefined;
        if (block.kind === "heading") {
          return (
            <div key={bi} className={`${spacing ?? ""} text-sm font-semibold`}>
              {renderInline(block.text)}
            </div>
          );
        }
        if (block.kind === "ul") {
          return (
            <ul key={bi} className={`${spacing ?? ""} list-disc space-y-0.5 pl-5`}>
              {block.items.map((item, ii) => (
                <li key={ii}>{renderInline(item)}</li>
              ))}
            </ul>
          );
        }
        if (block.kind === "ol") {
          return (
            <ol key={bi} className={`${spacing ?? ""} list-decimal space-y-0.5 pl-5`}>
              {block.items.map((item, ii) => (
                <li key={ii}>{renderInline(item)}</li>
              ))}
            </ol>
          );
        }
        return (
          <p key={bi} className={spacing}>
            {renderLines(block.text)}
          </p>
        );
      })}
    </>
  );
}
