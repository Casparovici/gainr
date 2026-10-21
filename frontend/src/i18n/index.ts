/** The app's two languages. Every visible string is written once, in the language its module
 * started in (English for gainr, gripr and briefr; Dutch for listr, gardnr, trainr, taskr and
 * Vandaag), wrapped in `t()`; `messages/` holds its translation into the other language. A string
 * with no translation shows as written -- `i18n.test.ts` keeps that from happening unnoticed.
 *
 * The chosen language is module state rather than a React context, so `t()` works in plain
 * functions and formatters too: LanguageProvider sets it before rendering and remounts the app
 * when it changes, so every component re-renders in the new language. */
import { EN_FROM_NL, NL_FROM_EN } from "./messages";

export type Language = "en" | "nl";

export const LANGUAGES: { id: Language; label: string; native: string }[] = [
  { id: "en", label: "English", native: "English" },
  { id: "nl", label: "Dutch", native: "Nederlands" },
];

export const LANGUAGE_STORAGE_KEY = "pdt-language";

// "source" shows every string as written, in whichever language that is: what tests see unless
// they pick a language, so each module's own tests read its own words. The app always sets one.
let current: Language | "source" = "source";

export function getLanguage(): Language | "source" {
  return current;
}

export function setCurrentLanguage(language: Language | "source"): void {
  current = language;
}

/** The locale dates are written in: the language's, or `asWritten` -- the one the call site was
 * written for -- while showing strings as written. Numbers keep the European notation in both
 * languages: the amount fields read "1.234,56", and the figures should look the way they're typed. */
export function dateLocale(asWritten = "en-IE"): string {
  if (current === "source") return asWritten;
  return current === "nl" ? "nl-NL" : "en-IE";
}

type Vars = Record<string, string | number>;

function fill(text: string, vars?: Vars): string {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in vars ? String(vars[name]) : whole));
}

/** `source` in the current language, with `{name}` placeholders filled from `vars`. */
export function t(source: string, vars?: Vars): string {
  const translated = current === "nl" ? NL_FROM_EN[source] : current === "en" ? EN_FROM_NL[source] : undefined;
  return fill(translated ?? source, vars);
}

/** One or many: `tp(n, "{n} transaction", "{n} transactions")`, with `n` among the vars. */
export function tp(n: number, one: string, many: string, vars?: Vars): string {
  return t(n === 1 ? one : many, { n, ...vars });
}

/** Marks a string defined outside a render (a constant, a table of labels) as one to translate,
 * without translating it there and then: pass it through `t()` where it's shown. */
export function msg(source: string): string {
  return source;
}
