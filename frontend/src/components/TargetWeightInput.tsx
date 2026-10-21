import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Position } from "../api/types";
import { usePortfolio } from "../hooks/usePortfolio";
import { apiToDecimalInput, decimalInputToApi, formatWeight } from "../utils/format";
import { t } from "../i18n";

/** The backend's `{"detail": "..."}` body, buried in the generic `request()` error message
 * (`"400 Bad Request: {\"detail\": \"...\"}"`) — pulled out so a rejected write can show the
 * actual reason (e.g. "would total 110%") instead of a raw HTTP error string. */
function extractDetail(err: unknown): string {
  if (err instanceof Error) {
    const braceIndex = err.message.indexOf("{");
    if (braceIndex !== -1) {
      try {
        const parsed = JSON.parse(err.message.slice(braceIndex));
        if (typeof parsed?.detail === "string") return parsed.detail;
      } catch {
        // fall through to the generic message below
      }
    }
  }
  return t("Couldn't save that value.");
}

/** Editable target-weight cell shared by the active positions table and a position's detail
 * card — one mutation and one error-formatting path for both, so the 100%-cap rejection reads
 * identically wherever it's edited from.
 *
 * `asText` is for the positions table: the value reads as plain "1,0%" like every other row's
 * target until clicked (pencil on hover), rather than an always-open input box standing out in
 * a column of text. */
export default function TargetWeightInput({
  position,
  className,
  asText = false,
}: {
  position: Position;
  className?: string;
  asText?: boolean;
}) {
  const queryClient = useQueryClient();
  const { portfolioId } = usePortfolio();
  const isCash = position.ticker === "CASH";
  const [value, setValue] = useState(apiToDecimalInput(position.target_weight_pct));
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  // The row's own value can change from elsewhere (a refetch after another edit) — follow it
  // as long as this field isn't mid-edit-with-an-error the user hasn't dismissed yet.
  useEffect(() => {
    setValue(apiToDecimalInput(position.target_weight_pct));
    setError(null);
     
  }, [position.target_weight_pct]);

  const mutation = useMutation({
    mutationFn: (next: string | null) =>
      isCash
        ? api.updateCashTargetWeight(portfolioId!, next)
        : api.updateAssetTargetWeight(position.asset_id, portfolioId!, next),
    onSuccess: () => {
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["positions"] });
    },
    onError: (err: unknown) => {
      setError(extractDetail(err));
      setValue(apiToDecimalInput(position.target_weight_pct)); // revert the input to the last saved value
    },
  });

  const commit = () => {
    setEditing(false);
    // Comma or dot decimals both accepted; compared as numbers so "1,0" against a stored "1.00"
    // isn't mistaken for a change.
    const next = value.trim() === "" ? null : decimalInputToApi(value);
    const current = position.target_weight_pct;
    if (next === null ? current === null : current !== null && Number(next) === Number(current)) return;
    if (next === null && value.trim() !== "") {
      setError(t("Enter a number, e.g. 2,5."));
      return;
    }
    mutation.mutate(next);
  };

  const errorLine = error && (
    <span className="max-w-[10rem] text-right text-[11px] leading-tight text-red-600">{error}</span>
  );

  if (asText && !editing) {
    return (
      <div className={`flex flex-col items-end gap-0.5 ${className ?? ""}`}>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setEditing(true);
          }}
          className="group inline-flex items-center gap-1 tabular-nums"
          title={t("Edit target weight")}
          aria-label={t("Edit target weight")}
        >
          <Pencil className="h-3 w-3 shrink-0 text-slate-300 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100" strokeWidth={2} />
          {formatWeight(position.target_weight_pct)}
        </button>
        {errorLine}
      </div>
    );
  }

  return (
    <div className={`flex flex-col items-end gap-0.5 ${className ?? ""}`}>
      <div className="flex items-center gap-1">
        <input
          autoFocus={asText}
          type="text"
          inputMode="decimal"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={commit}
          onKeyDown={(e) => {
            if (e.key === "Enter") e.currentTarget.blur();
            if (e.key === "Escape" && asText) {
              setValue(apiToDecimalInput(position.target_weight_pct));
              setEditing(false);
            }
          }}
          onClick={(e) => e.stopPropagation()}
          placeholder="—"
          className={`w-14 rounded border px-1.5 py-0.5 text-right text-sm tabular-nums focus:outline-none focus:ring-1 ${
            error
              ? "border-red-400 text-red-700 focus:ring-red-400"
              : "border-slate-200 focus:border-slate-400 focus:ring-slate-400"
          }`}
        />
        <span className="text-xs text-slate-400">%</span>
      </div>
      {errorLine}
    </div>
  );
}
