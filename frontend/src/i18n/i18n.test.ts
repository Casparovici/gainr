import fs from "node:fs";
import path from "node:path";
import ts from "typescript";
import { afterEach, describe, expect, it } from "vitest";

import { dateLocale, setCurrentLanguage, t, tp } from "./index";
import { EN_FROM_NL, NL_FROM_EN } from "./messages";
import { nlToEn as SHARED_DUTCH } from "./messages/shared.nl";

const SRC = path.resolve(__dirname, "..");
// Modules written in Dutch; everything else is written in English, except a few files that speak
// for several modules (and so hold both).
const DUTCH_SOURCE = /listr|gardnr|trainr|taskr|vandaag/i;
const MIXED = new Set(["components/ModuleSwitcher.tsx", "i18n/dynamic.ts"]);
const CALLS = new Set(["t", "tr", "tp", "msg"]);

interface Found {
  file: string;
  line: number;
  text: string;
  /** Called while the module loads, so it would be frozen in whatever language was set then. */
  atModuleLevel: boolean;
}

function sourceFiles(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "test" ? [] : sourceFiles(full);
    return /\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name) ? [full] : [];
  });
}

/** Every literal handed to t(), tr(), tp() or msg() in the app. */
function translatedLiterals(): Found[] {
  const found: Found[] = [];
  for (const file of sourceFiles(SRC)) {
    if (file.includes(`${path.sep}i18n${path.sep}messages`)) continue;
    const source = ts.createSourceFile(file, fs.readFileSync(file, "utf8"), ts.ScriptTarget.Latest, true);
    const visit = (node: ts.Node, inFunction: boolean) => {
      if (ts.isCallExpression(node) && CALLS.has(node.expression.getText())) {
        const name = node.expression.getText();
        const literals = name === "tp" ? node.arguments.slice(1, 3) : node.arguments.slice(0, 1);
        for (const arg of literals) {
          if (ts.isStringLiteral(arg) || ts.isNoSubstitutionTemplateLiteral(arg)) {
            found.push({
              file: path.relative(SRC, file),
              line: source.getLineAndCharacterOfPosition(arg.getStart()).line + 1,
              text: arg.text,
              atModuleLevel: name !== "msg" && !inFunction,
            });
          }
        }
      }
      const fn = ts.isFunctionLike(node) || ts.isClassLike(node);
      ts.forEachChild(node, (child) => visit(child, inFunction || fn));
    };
    visit(source, false);
  }
  return found;
}

const literals = translatedLiterals();

describe("translations", () => {
  it("finds the app's strings", () => {
    expect(literals.length).toBeGreaterThan(500);
  });

  it("has a translation for every string, in the direction it's written", () => {
    const missing = literals
      .filter((l) => {
        if (MIXED.has(l.file.split(path.sep).join("/"))) return !(l.text in NL_FROM_EN || l.text in EN_FROM_NL);
        if (DUTCH_SOURCE.test(l.file)) return !(l.text in EN_FROM_NL);
        // A shared file may hold a Dutch label for a Dutch-written module (messages/shared.nl.ts).
        return !(l.text in NL_FROM_EN || l.text in SHARED_DUTCH);
      })
      .map((l) => `${l.file}:${l.line} ${JSON.stringify(l.text)}`);
    expect([...new Set(missing)]).toEqual([]);
  });

  it("keeps every placeholder in the translation", () => {
    const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    const broken = [...Object.entries(NL_FROM_EN), ...Object.entries(EN_FROM_NL)]
      .filter(([source, translated]) => placeholders(source).join() !== placeholders(translated).join())
      .map(([source]) => source);
    expect(broken).toEqual([]);
  });

  it("has no empty translations", () => {
    const empty = [...Object.entries(NL_FROM_EN), ...Object.entries(EN_FROM_NL)].filter(([, v]) => !v.trim());
    expect(empty).toEqual([]);
  });

  it("never translates while a module loads, where the language isn't set yet", () => {
    const early = literals.filter((l) => l.atModuleLevel).map((l) => `${l.file}:${l.line}`);
    expect(early).toEqual([]);
  });
});

describe("t", () => {
  afterEach(() => setCurrentLanguage("source"));

  it("shows a string as written until a language is chosen", () => {
    expect(t("Holdings")).toBe("Holdings");
    expect(t("{n} hidden", { n: 3 })).toBe("3 hidden");
  });

  it("translates English into Dutch and Dutch into English", () => {
    setCurrentLanguage("nl");
    expect(t("Holdings")).toBe(NL_FROM_EN.Holdings);
    expect(t("Boodschappen")).toBe("Boodschappen");
    setCurrentLanguage("en");
    expect(t("Holdings")).toBe("Holdings");
    expect(t("Boodschappen")).toBe(EN_FROM_NL.Boodschappen);
  });

  it("falls back to the source for a string without a translation", () => {
    setCurrentLanguage("nl");
    expect(t("not a known string {x}", { x: 1 })).toBe("not a known string 1");
  });

  it("fills placeholders in the translation", () => {
    setCurrentLanguage("nl");
    expect(t("{n} hidden", { n: 3 })).toBe(NL_FROM_EN["{n} hidden"].replace("{n}", "3"));
  });

  it("picks the singular or the plural form", () => {
    expect(tp(1, "{n} item", "{n} items")).toBe("1 item");
    expect(tp(2, "{n} item", "{n} items")).toBe("2 items");
    expect(tp(0, "{n} item", "{n} items")).toBe("0 items");
  });

  it("writes dates in the chosen language", () => {
    expect(dateLocale("nl-NL")).toBe("nl-NL");
    setCurrentLanguage("en");
    expect(dateLocale("nl-NL")).toBe("en-IE");
    setCurrentLanguage("nl");
    expect(dateLocale("en-IE")).toBe("nl-NL");
  });
});
