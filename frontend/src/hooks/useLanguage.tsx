import { createContext, Fragment, useContext, useEffect, useState, type ReactNode } from "react";

import { LANGUAGE_STORAGE_KEY, LANGUAGES, setCurrentLanguage, type Language } from "../i18n";

function readStoredLanguage(): Language {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (LANGUAGES.some((l) => l.id === stored)) return stored as Language;
  } catch {
    // localStorage unavailable (private browsing, etc.) -- fall back to the browser's language.
  }
  return typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("nl") ? "nl" : "en";
}

interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

/** The app's language, a per-browser preference like the theme and the font: the stored choice,
 * else the browser's own language. It's set for `t()` before anything below renders, and the tree
 * below remounts when it changes, so every string -- in components, formatters and labels alike --
 * comes back in the new language at once. */
export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readStoredLanguage);
  setCurrentLanguage(language);

  useEffect(() => {
    document.documentElement.lang = language;
    try {
      localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    } catch {
      // Nothing to persist to -- the choice just won't survive a reload.
    }
  }, [language]);

  return (
    <LanguageContext.Provider value={{ language, setLanguage: setLanguageState }}>
      <Fragment key={language}>{children}</Fragment>
    </LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used within a LanguageProvider");
  return ctx;
}
