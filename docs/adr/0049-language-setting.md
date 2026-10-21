# 49. A language setting: English or Dutch, for every module

## Status

Accepted

## Context

The app has been written in two languages. gainr, gripr and briefr are in English; listr, gardnr,
trainr, taskr and Vandaag are in Dutch. Each page held its text directly, and there was no
translation layer (README, "Run your own copy"). The reader wants one language throughout,
chosen in Settings the way the font is chosen.

## Decision

**A per-browser preference, like the font and the theme.** Settings (in gainr, gripr and the
other modules' settings) has a Language section with English and Nederlands. The choice is stored
in `localStorage` (`pdt-language`). Without a stored choice, the browser's language decides:
Dutch if it starts with `nl`, otherwise English. A pre-paint script in `index.html` sets
`<html lang>`. There is no server setting, because the app has one reader and the font works the
same way.

**No i18n library: a small `t()` keyed by the source string** (`frontend/src/i18n/`).
- Every user-visible string in the code is written as before, in its module's language, and
  wrapped in a call:
  - `t("Holdings")`, with `{name}` placeholders: `t("{n} hidden", { n })`.
  - `tp(n, one, many)` for plurals.
  - `msg()` to mark a string in a module-level constant, translated with `t()` where it's shown.
- The dictionaries go one way per module, keyed by what the code says:
  - English to Dutch for the English modules (`messages/*.en.ts`).
  - Dutch to English for the Dutch ones (`messages/*.nl.ts`).
- A string in its own language needs no entry, so a module's text stays readable in its source
  file, and no rename into message ids was needed.
- `dateLocale()` turns a hard-coded date locale into the chosen language's. Numbers and amounts
  keep the European format (`€ 1.234,56`) in both languages: that's how the reader reads money.
- We considered `react-i18next` with message ids. It would have meant renaming about 2,500 strings
  into ids and adding a dependency, for two languages and one reader.

**The language is set before render, and changing it remounts the app.** `LanguageProvider` sets
the module-level current language that `t()` reads, then keys its subtree on the language. So
strings built outside components (formatters, label maps, toasts) switch together with the JSX,
and nothing threads a hook through helpers. Remounting drops open dialogs and local state. That's
acceptable for a setting changed once. Server data stays in TanStack Query's cache, so nothing is
refetched.

**Tests run in "source" mode.** Until a language is set, `t()` returns the string as written. So
the existing tests, which assert the text each module was written in, are unchanged.
`i18n.test.ts` scans the code with the TypeScript parser and fails when:
- a literal handed to `t`/`tp`/`msg` has no entry in its direction's dictionary;
- a translation loses or renames a placeholder;
- `t()` runs at module level, where the language isn't set yet.

## Consequences

- New UI text goes through `t()`, and the i18n test fails until both languages have it. This is a
  frontend convention (`.claude/rules/frontend-engineer.md`).
- Text the server writes stays in the language it's written in. That covers:
  - agenda item titles from gardnr and trainr;
  - gripr notifications;
  - briefr's reports, which agents and the performance job write;
  - error details from the API;
  - listr's product catalogue.
  Translating these would mean either a language on the server or keys instead of sentences in
  the API. Neither is worth it yet.
- Names from data (accounts, categories, plants, exercises, recipes) are the reader's own and are
  never translated.
