import { useQuery } from "@tanstack/react-query";
import { Landmark } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { griprApi } from "../../api/griprClient";
import BankLogo from "./BankLogo";
import { QueryError } from "../ui/QueryError";
import { t } from "../../i18n";

/** A small popover listing the fixed bank/broker catalog (see gripr_bank_logo_service.py) --
 * same interaction shape as ColorPicker: an outside click closes it, and picking (or "None")
 * both selects and closes in one action. The trigger shows the account's current logo, or a
 * generic bank icon placeholder when none is set. */
export default function BankLogoPicker({
  value,
  onSelect,
  size = 22,
}: {
  value: string | null;
  onSelect: (key: string | null) => void;
  size?: number;
}) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { data: banks, isError, refetch } = useQuery({ queryKey: ["gripr-bank-logos"], queryFn: () => griprApi.listBankLogos() });

  useEffect(() => {
    if (!open) return;
    function handlePointerDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen((o) => !o);
        }}
        title={t("Set bank/broker icon")}
        className="flex items-center justify-center rounded-md text-on-surface-variant/50 hover:text-on-surface-variant"
        style={{ width: size, height: size }}
      >
        {value ? <BankLogo bankKey={value} size={size} /> : <Landmark className="h-full w-full" strokeWidth={1.5} />}
      </button>
      {open && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute right-0 top-full z-20 mt-1 w-44 rounded-lg border border-outline-variant bg-surface-container-high p-1.5 shadow-lg"
        >
          {isError && <QueryError className="px-2 py-1.5 text-sm" message={t("Couldn't load bank icons.")} onRetry={() => refetch()} />}
          {(banks ?? []).map((bank) => (
            <button
              key={bank.key}
              type="button"
              onClick={() => {
                onSelect(bank.key);
                setOpen(false);
              }}
              className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-on-surface/5 ${
                value === bank.key ? "bg-secondary-container font-medium text-on-secondary-container" : "text-on-surface"
              }`}
            >
              <BankLogo bankKey={bank.key} size={18} />
              {bank.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() => {
              onSelect(null);
              setOpen(false);
            }}
            className="mt-1 w-full rounded-md border-t border-outline-variant px-2 py-1.5 pt-2 text-left text-xs text-on-surface-variant hover:text-on-surface"
          >{t("No icon")}</button>
        </div>
      )}
    </div>
  );
}
