import { useLanguage } from "../hooks/useLanguage";
import { LANGUAGES, t } from "../i18n";

/** Settings > Language: English or Dutch, for the whole app. Applies at once and is remembered in
 * this browser (see hooks/useLanguage.tsx). Each option is written in its own language, so it can
 * be found whichever one is showing. */
export default function LanguagePicker({ tone = "gainr" }: { tone?: "gainr" | "gripr" }) {
  const { language, setLanguage } = useLanguage();
  const gripr = tone === "gripr";
  return (
    <div role="radiogroup" aria-label={t("Language")} className="grid grid-cols-2 gap-2">
      {LANGUAGES.map((option) => {
        const selected = language === option.id;
        return (
          <button
            key={option.id}
            type="button"
            role="radio"
            aria-checked={selected}
            lang={option.id}
            onClick={() => setLanguage(option.id)}
            className={`flex flex-col gap-0.5 rounded-xl border p-3 text-left transition-colors ${
              selected
                ? gripr
                  ? "border-primary bg-primary-container"
                  : "border-ui-brand bg-ui-brand-soft"
                : gripr
                  ? "border-outline-variant hover:bg-surface-container"
                  : "border-slate-200 hover:bg-slate-50"
            }`}
          >
            <span className="text-base font-semibold">{option.native}</span>
            {/* Its name in the other language, so it reads the same whichever one is showing. */}
            <span className="text-xs opacity-70" lang={option.id === "en" ? "nl" : "en"}>{option.id === "en" ? "Engels" : "Dutch"}</span>
          </button>
        );
      })}
    </div>
  );
}
