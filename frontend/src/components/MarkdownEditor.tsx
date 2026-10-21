import {
  Bold,
  Heading2,
  Image as ImageIcon,
  Italic,
  Link as LinkIcon,
  List,
  ListChecks,
  ListOrdered,
  Quote,
  type LucideIcon,
} from "lucide-react";
import { useLayoutEffect, useRef, useState, type ClipboardEvent, type DragEvent, type KeyboardEvent } from "react";

import { notrApi } from "../api/notrClient";
import { continueList, insertBlock, prefixLines, wrapSelection, type Edit } from "../utils/markdownEditing";
import Markdown from "./Markdown";
import { t } from "../i18n";

const IMAGE_TYPES = "image/png,image/jpeg,image/webp";

type Tool = "heading" | "bold" | "italic" | "bullets" | "numbers" | "checklist" | "quote" | "link" | "picture";

/** The Markdown editor every note is written in -- notr, gainr's Journal and the Notes sections on
 * a position, a plant and a recipe. A plain text box (native, so it's right on a phone) with a
 * Write / Preview switch and a small toolbar. Pictures come in by pasting, dropping or picking a
 * file (a phone offers its camera) and land in the text as `![](url)`, which is all a picture
 * is: the note's Markdown stays plain text you can read anywhere. Enter continues a list. */
export default function MarkdownEditor({
  value,
  onChange,
  placeholder,
  rows = 10,
  autoFocus = false,
  ariaLabel,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  autoFocus?: boolean;
  ariaLabel?: string;
}) {
  const [mode, setMode] = useState<"write" | "preview">("write");
  const [uploading, setUploading] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  // The text as it is right now, for an upload that finishes after more typing (or another upload).
  const latest = useRef(value);
  useLayoutEffect(() => {
    latest.current = value;
  }, [value]);
  const pendingSelection = useRef<[number, number] | null>(null);

  // A toolbar edit changes the text and then puts the selection where the edit says; the text
  // box only has the new text once React has rendered it.
  useLayoutEffect(() => {
    const selection = pendingSelection.current;
    if (selection && area.current) {
      area.current.focus();
      area.current.setSelectionRange(selection[0], selection[1]);
      pendingSelection.current = null;
    }
  }, [value]);

  const apply = (edit: Edit) => {
    latest.current = edit.value;
    pendingSelection.current = [edit.start, edit.end];
    onChange(edit.value);
  };
  // Until the reader has put the caret somewhere, an edit goes at the end: a text box that was
  // never focused reports its caret at the start, which is the wrong place for a picture.
  const touched = useRef(false);
  const selection = (): [number, number] => {
    const end = latest.current.length;
    if (!touched.current || !area.current) return [end, end];
    return [area.current.selectionStart, area.current.selectionEnd];
  };

  const upload = async (files: File[]) => {
    const pictures = files.filter((f) => f.type.startsWith("image/"));
    if (pictures.length === 0) return;
    setError(null);
    for (const file of pictures) {
      setUploading((n) => n + 1);
      try {
        const stored = await notrApi.uploadImage(file);
        const alt = file.name.replace(/\.[^.]+$/, "").replace(/^image$/i, "").replace(/[[\]]/g, "");
        const [start, end] = selection();
        apply(insertBlock(latest.current, start, end, `![${alt}](${stored.url})`));
      } catch (e) {
        setError(t("Couldn't add that picture: {reason}", { reason: e instanceof Error ? e.message : String(e) }));
      } finally {
        setUploading((n) => n - 1);
      }
    }
  };

  const wrap = (before: string, after: string, placeholderText: string) => {
    const [start, end] = selection();
    apply(wrapSelection(latest.current, start, end, before, after, placeholderText));
  };
  const prefix = (marker: string) => {
    const [start, end] = selection();
    apply(prefixLines(latest.current, start, end, marker));
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.ctrlKey && !e.metaKey && !e.altKey && !e.nativeEvent.isComposing) {
      const [start, end] = selection();
      const edit = start === end ? continueList(latest.current, start) : null;
      if (edit) {
        e.preventDefault();
        apply(edit);
      }
    } else if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey && (e.key === "b" || e.key === "i")) {
      e.preventDefault();
      if (e.key === "b") wrap("**", "**", t("bold"));
      else wrap("*", "*", t("italic"));
    }
  };

  const onPaste = (e: ClipboardEvent<HTMLTextAreaElement>) => {
    const files = Array.from(e.clipboardData.files);
    if (files.some((f) => f.type.startsWith("image/"))) {
      e.preventDefault();
      void upload(files);
    }
  };
  const onDrop = (e: DragEvent<HTMLTextAreaElement>) => {
    const files = Array.from(e.dataTransfer.files);
    if (files.some((f) => f.type.startsWith("image/"))) {
      e.preventDefault();
      void upload(files);
    }
  };

  const runTool = (tool: Tool) => {
    switch (tool) {
      case "heading":
        return prefix("## ");
      case "bold":
        return wrap("**", "**", t("bold"));
      case "italic":
        return wrap("*", "*", t("italic"));
      case "bullets":
        return prefix("- ");
      case "numbers":
        return prefix("1. ");
      case "checklist":
        return prefix("- [ ] ");
      case "quote":
        return prefix("> ");
      case "link":
        return wrap("[", "](https://)", t("link text"));
      case "picture":
        return fileInput.current?.click();
    }
  };
  const tools: { tool: Tool; label: string; icon: LucideIcon }[] = [
    { tool: "heading", label: t("Heading"), icon: Heading2 },
    { tool: "bold", label: t("Bold"), icon: Bold },
    { tool: "italic", label: t("Italic"), icon: Italic },
    { tool: "bullets", label: t("Bulleted list"), icon: List },
    { tool: "numbers", label: t("Numbered list"), icon: ListOrdered },
    { tool: "checklist", label: t("Checklist"), icon: ListChecks },
    { tool: "quote", label: t("Quote"), icon: Quote },
    { tool: "link", label: t("Link"), icon: LinkIcon },
    { tool: "picture", label: t("Add picture"), icon: ImageIcon },
  ];

  return (
    <div className="overflow-hidden rounded-xl border border-ui-line bg-ui-surface focus-within:border-ui-brand">
      <div className="flex flex-col gap-1 border-b border-ui-line bg-ui-tile/50 px-1.5 py-1">
        <div role="tablist" aria-label={t("Note text")} className="flex w-fit shrink-0 rounded-lg bg-ui-tile p-0.5">
          {(["write", "preview"] as const).map((m) => (
            <button
              key={m}
              type="button"
              role="tab"
              aria-selected={mode === m}
              onClick={() => setMode(m)}
              className={`h-8 rounded-md px-3 text-[13px] font-semibold ${mode === m ? "bg-ui-surface text-ui-ink shadow-sm" : "text-ui-muted"}`}
            >
              {m === "write" ? t("Write") : t("Preview")}
            </button>
          ))}
        </div>
        {mode === "write" && (
          <div className="flex min-w-0 items-center gap-0.5 overflow-x-auto" role="toolbar" aria-label={t("Formatting")}>
            {tools.map(({ tool, label, icon: Icon }) => (
              <button
                key={label}
                type="button"
                title={label}
                aria-label={label}
                onClick={() => runTool(tool)}
                className="grid h-9 w-9 shrink-0 place-items-center rounded-lg text-ui-ink-soft hover:bg-ui-tile"
              >
                <Icon size={17} aria-hidden />
              </button>
            ))}
          </div>
        )}
      </div>

      {mode === "write" ? (
        <textarea
          ref={area}
          value={value}
          rows={rows}
          autoFocus={autoFocus}
          aria-label={ariaLabel ?? t("Note text")}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => {
            touched.current = true;
          }}
          onKeyDown={onKeyDown}
          onPaste={onPaste}
          onDrop={onDrop}
          onDragOver={(e) => e.dataTransfer.types.includes("Files") && e.preventDefault()}
          className="block w-full resize-y bg-transparent px-3 py-3 text-base leading-relaxed text-ui-ink outline-none placeholder:text-ui-faint"
        />
      ) : (
        <div className="min-h-[8rem] px-3 py-3" style={{ minHeight: `${rows * 1.6}rem` }}>
          {value.trim() ? <Markdown text={value} /> : <p className="m-0 text-sm text-ui-muted">{t("Nothing to preview yet.")}</p>}
        </div>
      )}

      <input
        ref={fileInput}
        type="file"
        accept={IMAGE_TYPES}
        multiple
        hidden
        aria-label={t("Add picture")}
        onChange={(e) => {
          void upload(Array.from(e.target.files ?? []));
          e.target.value = "";
        }}
      />
      {(uploading > 0 || error) && (
        <div className="border-t border-ui-line px-3 py-2 text-sm" aria-live="polite">
          {uploading > 0 && <span className="text-ui-muted">{t("Uploading picture…")}</span>}
          {error && (
            <p role="alert" className="m-0 text-ui-late">
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
