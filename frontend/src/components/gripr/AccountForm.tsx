import { useState } from "react";

import { GRIPR_ACCOUNT_TYPES, type GriprAccountType, type GriprBalanceMode } from "../../api/griprTypes";
import { decimalInputToApi } from "../../utils/format";
import ModalOverlay from "../ModalOverlay";

const inputClass =
  "rounded-md border border-outline px-2.5 py-1.5 text-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary";

function field(label: string, input: React.ReactNode) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">{label}</span>
      {input}
    </label>
  );
}

// Loans and net-worth-only trackers (a car's value, home equity) have no transaction feed of
// their own in this app — their balance is just a number the user updates by hand.
const MANUAL_TYPES: GriprAccountType[] = ["loan", "credit", "asset"];

export interface AccountFormInput {
  name: string;
  type: GriprAccountType;
  balance_mode: GriprBalanceMode;
  opening_balance: string;
  manual_balance: string;
}

export default function AccountForm({
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  onCancel: () => void;
  onSubmit: (input: AccountFormInput) => void;
  isSubmitting: boolean;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState<GriprAccountType>("checking");
  const [balance, setBalance] = useState("0");

  const manual = MANUAL_TYPES.includes(type);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const amount = decimalInputToApi(balance) ?? "0";
    onSubmit({
      name,
      type,
      balance_mode: manual ? "manual" : "transactional",
      opening_balance: manual ? "0" : amount,
      manual_balance: manual ? amount : "0",
    });
  };

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-sm rounded-[28px] bg-surface p-6 shadow-xl">
      <h2 className="text-lg font-medium text-on-surface">New account</h2>
      <form onSubmit={handleSubmit} className="mt-4 flex flex-col gap-3">
        {field("Name", <input required autoFocus value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />)}
        {field(
          "Type",
          <select value={type} onChange={(e) => setType(e.target.value as GriprAccountType)} className={inputClass}>
            {GRIPR_ACCOUNT_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>,
        )}
        {field(
          manual ? "Current balance" : "Opening balance",
          <input inputMode="decimal" value={balance} onChange={(e) => setBalance(e.target.value)} className={inputClass} />,
        )}
        {!manual && (
          <p className="text-xs text-on-surface-variant">
            This account tracks its balance from transactions — the opening balance is what it held before its
            first booked transaction.
          </p>
        )}

        <div className="mt-2 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-full border border-outline px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-full bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:opacity-90 disabled:opacity-50"
          >
            {isSubmitting ? "Saving…" : "Create"}
          </button>
        </div>
      </form>
    </ModalOverlay>
  );
}
