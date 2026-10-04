# gainr brand assets — module logos

Logos for the four modules of the gainr app: **gainr** (portfolio), **gripr** (personal finance),
**listr** (groceries & recipes), **gardnr** (garden). One family: a coloured rounded tile, a white
line glyph on a 48×48 grid (round caps/joins, stroke 3.4, or 4.2 at ≤32 px), and a lowercase
wordmark whose final "r" carries the module colour.

## Colours

| Module | Light | Dark mode | Label (NL) |
|---|---|---|---|
| gainr  | `#3F3AC4` | `#9D9AF2` | Beleggingsportefeuille |
| gripr  | `#B7790A` | `#EDB94A` | Persoonlijke financiën |
| listr  | `#D4502A` | `#F08A66` | Boodschappen & recepten |
| gardnr | `#2F7D3A` | `#7FC486` | Tuin & verzorging |

Also in `tokens.json`. Wordmark font: **Bricolage Grotesque 700** (Google Fonts), letter-spacing −0.02em.

## What's in here

```
react/ModuleLogo.tsx     ModuleGlyph (currentColor, Lucide-style), ModuleIcon (tile), ModuleWordmark, MODULE_BRAND
svg/<m>-glyph.svg        glyph only, stroke=currentColor
svg/<m>-icon.svg         square tile (rx 12.5/48)
svg/<m>-icon-round.svg   circular tile
svg/<m>-icon-small.svg   tile with heavier stroke, for ≤32 px / favicons
png/<m>-{16..512}.png    rendered tiles (16/32 use the small variant)
android/                 launcher icon for the Capacitor app (uses the gainr mark)
tokens.json              colours + labels
```

## Suggested integration (for Claude Code)

1. Copy `react/ModuleLogo.tsx` → `frontend/src/components/ModuleLogo.tsx`.
2. Copy `svg/` and `png/` → `frontend/public/brand/`.
3. Add the Bricolage Grotesque 700 font (Google Fonts `<link>` in `frontend/index.html`, or self-host).
4. Module switcher pill in the header: show `<ModuleIcon module={current} size={32} />` +
   `<ModuleWordmark module={current} />` when collapsed; each row of the expanded list gets
   `ModuleIcon size={28}` + wordmark. Pass `dark` to `ModuleWordmark` when the `.dark` class is active.
   Keys match the module list in `config/moduleNav.ts` (gainr/gripr/listr/gardnr).
5. Favicon: `png/<m>-32.png` / `svg/<m>-icon-small.svg`; optionally swap it per active module.
6. Android: copy `android/mipmap-*` and `android/values/ic_launcher_background.xml` into
   `frontend/android/app/src/main/res/` (overwrite Capacitor's default launcher icons), then
   `npx cap sync android`. The `android/drawable/ic_launcher_foreground.svg` is the source for
   the adaptive-icon foreground if you prefer a vector drawable via Android Studio's Image Asset tool.
