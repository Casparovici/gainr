import { useEffect, useState } from "react";

import { FONT_PACKAGES, FONT_STORAGE_KEY, type FontPackageId } from "../utils/fontPackages";

function readStoredFont(): FontPackageId {
  try {
    const stored = localStorage.getItem(FONT_STORAGE_KEY);
    if (FONT_PACKAGES.some((f) => f.id === stored)) return stored as FontPackageId;
  } catch {
    // localStorage unavailable (private browsing, etc.) -- fall back to the default.
  }
  return "default";
}

/** The font package, as a per-browser preference like the theme. The choice is `data-font` on
 * <html>, which index.css turns into the `--font-display` / `--font-text` variables; the inline
 * script in index.html applies the stored one before first paint, so this hook only has to apply
 * changes. */
export function useFont(): { font: FontPackageId; setFont: (font: FontPackageId) => void } {
  const [font, setFontState] = useState<FontPackageId>(readStoredFont);

  useEffect(() => {
    if (font === "default") document.documentElement.removeAttribute("data-font");
    else document.documentElement.setAttribute("data-font", font);
    try {
      localStorage.setItem(FONT_STORAGE_KEY, font);
    } catch {
      // Nothing to persist to -- the choice just won't survive a reload.
    }
  }, [font]);

  return { font, setFont: setFontState };
}
