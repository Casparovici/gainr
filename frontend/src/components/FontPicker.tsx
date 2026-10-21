import { useFont } from "../hooks/useFont";
import { FONT_PACKAGES } from "../utils/fontPackages";
import { t } from "../i18n";

/** Settings > Appearance: pick one of the font packages, each previewed in its own faces. Applies
 * at once and is remembered in this browser (see hooks/useFont.ts). */
export default function FontPicker({ tone = "gainr" }: { tone?: "gainr" | "gripr" }) {
  const { font, setFont } = useFont();
  const gripr = tone === "gripr";
  return (
    <div role="radiogroup" aria-label={t("Font")} className="grid grid-cols-1 gap-2 sm:grid-cols-2">
      {FONT_PACKAGES.map((pkg) => {
        const selected = font === pkg.id;
        return (
          <button
            key={pkg.id}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => setFont(pkg.id)}
            className={`flex flex-col gap-1 rounded-xl border p-3 text-left transition-colors ${
              selected
                ? gripr
                  ? "border-primary bg-primary-container"
                  : "border-ui-brand bg-ui-brand-soft"
                : gripr
                  ? "border-outline-variant hover:bg-surface-container"
                  : "border-slate-200 hover:bg-slate-50"
            }`}
          >
            <span className="text-xl font-bold leading-tight tracking-[-0.02em]" style={{ fontFamily: `${pkg.display}, sans-serif` }}>{t("Portfolio €12.345,67")}</span>
            <span className="text-sm" style={{ fontFamily: `${pkg.text}, sans-serif` }}>
              {pkg.label}
            </span>
            <span className="text-xs opacity-70" style={{ fontFamily: `${pkg.text}, sans-serif` }}>
              {t(pkg.note)}
            </span>
          </button>
        );
      })}
    </div>
  );
}
