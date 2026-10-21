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

type Align = "left" | "right";

type Block =
  | { kind: "heading"; text: string }
  | { kind: "ul"; items: string[] }
  | { kind: "ol"; items: string[] }
  | { kind: "table"; header: string[]; align: Align[]; rows: string[][] }
  | { kind: "paragraph"; text: string };

const HEADING_RE = /^#{1,3}\s+(.*)$/;
const UL_ITEM_RE = /^-\s+(.*)$/;
const OL_ITEM_RE = /^\d+\.\s+(.*)$/;
// A pipe table: a "| a | b |" header, then a "|---|--:|" separator, then rows. A colon on the
// right of a separator cell right-aligns that column (numbers).
const TABLE_ROW_RE = /^\s*\|.*\|\s*$/;
const TABLE_SEPARATOR_RE = /^\s*\|(\s*:?-{3,}:?\s*\|)+\s*$/;

function tableCells(line: string): string[] {
  return line.trim().slice(1, -1).split("|").map((cell) => cell.trim());
}

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
    if (TABLE_ROW_RE.test(line) && i + 1 < lines.length && TABLE_SEPARATOR_RE.test(lines[i + 1])) {
      flushParagraph();
      const header = tableCells(line);
      const align = tableCells(lines[i + 1]).map((cell): Align => (cell.endsWith(":") ? "right" : "left"));
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && TABLE_ROW_RE.test(lines[i])) {
        rows.push(tableCells(lines[i]));
        i++;
      }
      blocks.push({ kind: "table", header, align, rows });
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

/** Renders a journal note body (and a briefr report's write-up). Blank lines separate paragraphs,
 * single newlines break lines within one; pipe tables render as a table that scrolls sideways on a
 * narrow screen; `# heading` lines (`##` and `###` too, rendered alike), `- ` bullet lists and `1. ` numbered lists become their own
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
        if (block.kind === "table") {
          const cellClass = (col: number) => `px-2 py-1.5 ${block.align[col] === "right" ? "text-right tabular-nums" : "text-left"}`;
          return (
            <div key={bi} className={`${spacing ?? ""} overflow-x-auto`}>
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-slate-200">
                    {block.header.map((cell, ci) => (
                      <th key={ci} scope="col" className={`${cellClass(ci)} whitespace-nowrap font-semibold`}>
                        {renderInline(cell)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, ri) => (
                    <tr key={ri} className="border-b border-slate-100 last:border-0">
                      {block.header.map((_, ci) => (
                        <td key={ci} className={cellClass(ci)}>
                          {renderInline(row[ci] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
