import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { api } from "../api/client";
import type { Asset, SymbolMatch, Transaction, TransactionInput, TransactionType } from "../api/types";
import { TRANSACTION_TYPES } from "../api/types";
import { apiToDecimalInput, decimalInputToApi, numberToDecimalInput, parseDecimalInput } from "../utils/format";
import AssetCombobox from "./AssetCombobox";
import AssetSymbolPicker from "./AssetSymbolPicker";
import ModalOverlay from "./ModalOverlay";
import TransactionAttachments from "./TransactionAttachments";
import { t as tr } from "../i18n";

const NEW_ASSET_CLASSES = ["equity", "crypto", "commodity"] as const;

type ComputedField = "local_value" | "value_eur" | "total_eur";
const COMPUTED_FIELDS: ComputedField[] = ["local_value", "value_eur", "total_eur"];

/** Which fields a transaction type actually uses. A dividend, for instance, is just
 * "this asset paid me this much" — quantity/price/FX are meaningless for it, so showing
 * (and submitting) them only invites junk data. */
interface TypeShape {
  asset: boolean; // asset selector
  quantity: boolean; // units changing hands
  trade: boolean; // full Qty × Price ÷ FX + Costs chain, with auto-calc
  amountLabel: string; // what `total_eur` is called for this type
  brokerLabel: string; // "Broker" for everything except a Transfer, which has two
  toBroker: boolean; // a second broker field -- only a Transfer moves cash between two
}

function shapeFor(type: TransactionType): TypeShape {
  switch (type) {
    case "Buy":
    case "Sell":
      return { asset: true, quantity: true, trade: true, amountLabel: tr("Total (EUR)"), brokerLabel: tr("Broker"), toBroker: false };
    case "Dividend":
      return {
        asset: true,
        quantity: false,
        trade: false,
        amountLabel: tr("Dividend amount (EUR)"),
        brokerLabel: tr("Broker"),
        toBroker: false,
      };
    case "Staking":
      // Reward units arriving at zero cost — quantity matters, money doesn't.
      return { asset: true, quantity: true, trade: false, amountLabel: tr("Value (EUR)"), brokerLabel: tr("Broker"), toBroker: false };
    case "Transfer":
      // Cash moving between two of the reader's own brokers -- not money entering or leaving
      // the portfolio, so it's shaped like Deposit/Withdraw (no asset, no quantity) plus a
      // second broker for where the cash lands.
      return {
        asset: false,
        quantity: false,
        trade: false,
        amountLabel: tr("Amount (EUR)"),
        brokerLabel: tr("From broker"),
        toBroker: true,
      };
    default: // Deposit, Withdraw, Interest, Broker Fee — pure cash movements
      return { asset: false, quantity: false, trade: false, amountLabel: tr("Amount (EUR)"), brokerLabel: tr("Broker"), toBroker: false };
  }
}

/** `new Date().toISOString()` is UTC, which lands on the wrong day for anyone east of
 * Greenwich in the hours after local midnight. */
function todayLocalISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

interface FormState {
  date: string;
  type: TransactionType;
  asset_id: string;
  quantity: string;
  price: string;
  local_value: string;
  fx_rate: string;
  value_eur: string;
  costs: string;
  total_eur: string;
  broker: string;
  to_broker: string;
  notes: string;
}

function toFormState(t: Transaction | undefined, defaultAssetId?: number, defaultType?: TransactionType): FormState {
  return {
    date: t?.date ?? todayLocalISO(),
    type: t?.type ?? defaultType ?? "Buy",
    // A new transaction opened from a position's card already knows which holding it's for.
    asset_id: t?.asset_id != null ? String(t.asset_id) : defaultAssetId != null ? String(defaultAssetId) : "",
    quantity: apiToDecimalInput(t?.quantity),
    price: apiToDecimalInput(t?.price),
    local_value: apiToDecimalInput(t?.local_value),
    fx_rate: apiToDecimalInput(t?.fx_rate),
    value_eur: apiToDecimalInput(t?.value_eur),
    costs: apiToDecimalInput(t?.costs),
    total_eur: apiToDecimalInput(t?.total_eur),
    broker: t?.broker ?? "",
    to_broker: t?.to_broker ?? "",
    notes: t?.notes ?? "",
  };
}

/** Mirrors the source spreadsheet's formulas: Local Value = Qty × Price, Value (EUR) = Local
 * Value / FX, Total = Value + Costs on a Buy (costs are money paid out, on top of the trade)
 * but Value - Costs on a Sell (costs are deducted from what the broker pays out, same as they
 * always are on a real contract note) -- `total_eur` is the net cash the ledger actually moves,
 * per `position_service.py`'s cost-basis/realized-P&L math and `cash_balance_eur`, both of which
 * treat it as already net of costs rather than adding/subtracting costs themselves. Only fields
 * still in `auto` get overwritten, so a field the user has directly edited keeps its value even
 * as upstream fields keep changing. */
function recompute(f: FormState, auto: Set<ComputedField>): FormState {
  const next = { ...f };

  if (auto.has("local_value")) {
    const q = parseDecimalInput(next.quantity);
    const p = parseDecimalInput(next.price);
    next.local_value = q !== null && p !== null ? numberToDecimalInput(q * p) : "";
  }
  if (auto.has("value_eur")) {
    const lv = parseDecimalInput(next.local_value);
    const fx = parseDecimalInput(next.fx_rate);
    next.value_eur = lv !== null ? numberToDecimalInput(fx ? lv / fx : lv) : "";
  }
  if (auto.has("total_eur")) {
    const v = parseDecimalInput(next.value_eur);
    const c = parseDecimalInput(next.costs) ?? 0;
    const costSign = next.type === "Sell" ? -1 : 1;
    next.total_eur = v !== null ? numberToDecimalInput(v + costSign * c) : "";
  }
  return next;
}

function subtract(set: Set<ComputedField>, key: ComputedField): Set<ComputedField> {
  const next = new Set(set);
  next.delete(key);
  return next;
}

function field(label: string, input: React.ReactNode, resetButton?: React.ReactNode) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
        {resetButton}
      </span>
      {input}
    </label>
  );
}

const inputClass =
  "rounded-md border border-slate-300 px-2.5 py-1.5 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";
const OTHER_BROKER = "__other__";

interface NewAssetState {
  ticker: string;
  name: string;
  asset_class: string;
  native_currency: string;
  /** The Yahoo listing prices come from, picked in AssetSymbolPicker; null = the ticker as typed. */
  yahoo_symbol: string | null;
}

const EMPTY_NEW_ASSET: NewAssetState = { ticker: "", name: "", asset_class: "equity", native_currency: "EUR", yahoo_symbol: null };

export default function TransactionForm({
  assets,
  brokers,
  initial,
  template,
  defaultAssetId,
  defaultType,
  portfolioId,
  onCancel,
  onSubmit,
  isSubmitting,
}: {
  assets: Asset[];
  brokers: string[];
  initial: Transaction | undefined;
  /** A new transaction pre-filled from an existing one ("Duplicate"), dated today. Ignored when
   * editing. Its figures are kept as they were rather than recomputed. */
  template?: Transaction;
  defaultAssetId?: number;
  defaultType?: TransactionType;
  /** Which portfolio a new transaction is created in -- always the currently-selected one, not
   * a field the form itself exposes. Ignored when editing (`initial` already has its own). */
  portfolioId: number;
  onCancel: () => void;
  /** `files` are the attachments picked on a new transaction, to upload once it exists; always
   * empty when editing, where attachments are added and removed on the spot. */
  onSubmit: (input: TransactionInput, files: File[]) => void;
  isSubmitting: boolean;
}) {
  const queryClient = useQueryClient();
  const source = initial ?? (template ? { ...template, date: todayLocalISO() } : undefined);
  const [form, setForm] = useState<FormState>(toFormState(source, defaultAssetId, defaultType));
  // New transactions start fully auto-calculated; editing an existing one (or duplicating it)
  // respects its stored values until the user explicitly changes an upstream field or hits reset.
  const [autoFields, setAutoFields] = useState<Set<ComputedField>>(new Set(source ? [] : COMPUTED_FIELDS));
  const [brokerIsOther, setBrokerIsOther] = useState(() => !!form.broker && !brokers.includes(form.broker));
  const [toBrokerIsOther, setToBrokerIsOther] = useState(() => !!form.to_broker && !brokers.includes(form.to_broker));
  const [assetIsNew, setAssetIsNew] = useState(false);
  const [newAsset, setNewAsset] = useState<NewAssetState>(EMPTY_NEW_ASSET);
  const [isCreatingAsset, setIsCreatingAsset] = useState(false);
  const [assetError, setAssetError] = useState<string | null>(null);
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  // Picking a listing also fills in its name -- unless the reader typed one: a name filled in from
  // an earlier pick follows the new pick, so switching TDIV -> TDIV.AS doesn't keep First Trust's.
  const autoName = useRef<string | null>(null);
  const pickSymbol = useCallback((symbol: string | null, match: SymbolMatch | null) => {
    setNewAsset((a) => {
      const typedByReader = a.name.trim() !== "" && a.name !== autoName.current;
      if (typedByReader || !match?.name) return { ...a, yahoo_symbol: symbol };
      autoName.current = match.name;
      return { ...a, yahoo_symbol: symbol, name: match.name };
    });
  }, []);

  const shape = shapeFor(form.type);
  // Auto-calculation is only meaningful for the Qty × Price chain, i.e. Buy/Sell.
  const effectiveAuto = shape.trade ? autoFields : new Set<ComputedField>();

  const update = (patch: Partial<FormState>) => setForm((f) => recompute({ ...f, ...patch }, effectiveAuto));

  /** Switching type also drops values the new type has no use for, so a half-filled Buy
   * can't leave a phantom quantity, FX rate — or a Qty × Price total — behind on a dividend.
   * A total the user typed by hand is kept, since that's a real amount they entered. */
  const changeType = (type: TransactionType) => {
    const next = shapeFor(type);
    const totalWasDerived = shape.trade && autoFields.has("total_eur");
    setForm((f) =>
      recompute(
        {
          ...f,
          type,
          asset_id: next.asset ? f.asset_id : "",
          quantity: next.quantity ? f.quantity : "",
          price: next.trade ? f.price : "",
          local_value: next.trade ? f.local_value : "",
          fx_rate: next.trade ? f.fx_rate : "",
          value_eur: next.trade ? f.value_eur : "",
          costs: next.trade ? f.costs : "",
          total_eur: next.trade || !totalWasDerived ? f.total_eur : "",
          to_broker: next.toBroker ? f.to_broker : "",
        },
        next.trade ? autoFields : new Set<ComputedField>(),
      ),
    );
  };

  const editComputed = (key: ComputedField, value: string) => {
    setForm((f) => recompute({ ...f, [key]: value }, subtract(effectiveAuto, key)));
    setAutoFields((prev) => subtract(prev, key));
  };

  const resetToAuto = (key: ComputedField) => {
    const next = new Set(autoFields).add(key);
    setAutoFields(next);
    setForm((f) => recompute(f, shape.trade ? next : new Set<ComputedField>()));
  };

  const resetButton = (key: ComputedField) =>
    !effectiveAuto.has(key) && (
      <button
        type="button"
        onClick={() => resetToAuto(key)}
        className="font-normal normal-case text-slate-400 hover:text-slate-700"
        title={tr("Recalculate automatically")}
      >{tr("↺ auto")}</button>
    );

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAssetError(null);

    let assetId = form.asset_id ? Number(form.asset_id) : null;
    if (shape.asset && assetIsNew) {
      if (!newAsset.ticker.trim() || !newAsset.name.trim()) {
        setAssetError(tr("Ticker and name are required for a new asset."));
        return;
      }
      setIsCreatingAsset(true);
      try {
        const created = await api.createAsset({
          ticker: newAsset.ticker.trim(),
          name: newAsset.name.trim(),
          asset_class: newAsset.asset_class,
          native_currency: newAsset.native_currency.trim().toUpperCase(),
          yahoo_symbol: newAsset.yahoo_symbol,
        });
        assetId = created.id;
        queryClient.invalidateQueries({ queryKey: ["assets"] });
      } catch {
        setAssetError(tr("Couldn't create that asset — check the fields and try again."));
        return;
      } finally {
        setIsCreatingAsset(false);
      }
    }

    const payload: TransactionInput = {
      date: form.date,
      type: form.type,
      portfolio_id: initial?.portfolio_id ?? portfolioId,
      asset_id: assetId,
      quantity: decimalInputToApi(form.quantity),
      price: decimalInputToApi(form.price),
      local_value: decimalInputToApi(form.local_value),
      fx_rate: decimalInputToApi(form.fx_rate),
      value_eur: decimalInputToApi(form.value_eur) ?? "0",
      costs: decimalInputToApi(form.costs) ?? "0",
      total_eur: decimalInputToApi(form.total_eur) ?? "0",
      broker: form.broker || null,
      to_broker: shape.toBroker ? form.to_broker || null : null,
      notes: form.notes || null,
    };
    onSubmit(payload, initial ? [] : pendingFiles);
  };

  return (
    <ModalOverlay onClose={onCancel} cardClassName="w-full max-w-lg rounded-lg bg-white p-5 shadow-lg">
        <h2 className="text-base font-semibold text-slate-900">{initial ? tr("Edit transaction") : tr("Add transaction")}</h2>

        <form onSubmit={handleSubmit} className="mt-4 grid grid-cols-2 gap-3">
          {field(
            tr("Date"),
            <input
              type="date"
              required
              value={form.date}
              onChange={(e) => update({ date: e.target.value })}
              className={inputClass}
            />,
          )}
          {field(
            tr("Type"),
            <select value={form.type} onChange={(e) => changeType(e.target.value as TransactionType)} className={inputClass}>
              {TRANSACTION_TYPES.map((t) => (
                <option key={t} value={t}>
                  {tr(t)}
                </option>
              ))}
            </select>,
          )}

          {shape.asset &&
            field(
              tr("Asset"),
              assetIsNew ? (
                <div className="flex flex-col gap-1.5">
                  <div className="flex gap-1">
                    <input
                      autoFocus
                      value={newAsset.ticker}
                      onChange={(e) => setNewAsset((a) => ({ ...a, ticker: e.target.value.toUpperCase() }))}
                      className={`${inputClass} min-w-0 flex-1`}
                      placeholder={tr("Ticker (e.g. AAPL)")}
                    />
                    <button
                      type="button"
                      onClick={() => {
                        setAssetIsNew(false);
                        setNewAsset(EMPTY_NEW_ASSET);
                        setAssetError(null);
                      }}
                      className="px-1 text-xs text-slate-400 hover:text-slate-700"
                      title={tr("Choose an existing asset instead")}
                    >
                      ✕
                    </button>
                  </div>
                  <AssetSymbolPicker ticker={newAsset.ticker} value={newAsset.yahoo_symbol} onChange={pickSymbol} />
                  <input
                    value={newAsset.name}
                    onChange={(e) => setNewAsset((a) => ({ ...a, name: e.target.value }))}
                    className={inputClass}
                    placeholder={tr("Name")}
                  />
                  <div className="flex gap-1">
                    <select
                      value={newAsset.asset_class}
                      onChange={(e) => setNewAsset((a) => ({ ...a, asset_class: e.target.value }))}
                      className={`${inputClass} flex-1`}
                    >
                      {NEW_ASSET_CLASSES.map((c) => (
                        <option key={c} value={c}>
                          {c[0].toUpperCase() + c.slice(1)}
                        </option>
                      ))}
                    </select>
                    <input
                      value={newAsset.native_currency}
                      onChange={(e) => setNewAsset((a) => ({ ...a, native_currency: e.target.value.toUpperCase() }))}
                      className={`${inputClass} w-20`}
                      placeholder="EUR"
                      maxLength={8}
                    />
                  </div>
                  {assetError && <span className="text-xs text-red-600">{assetError}</span>}
                </div>
              ) : (
                <AssetCombobox
                  assets={assets}
                  value={form.asset_id ? Number(form.asset_id) : null}
                  onChange={(assetId) => update({ asset_id: String(assetId) })}
                  onAddNew={() => {
                    setAssetIsNew(true);
                    update({ asset_id: "" });
                  }}
                />
              ),
            )}

          {field(
            shape.brokerLabel,
            brokerIsOther ? (
              <div className="flex gap-1">
                <input
                  autoFocus
                  value={form.broker}
                  onChange={(e) => update({ broker: e.target.value })}
                  className={`${inputClass} flex-1`}
                  placeholder={tr("New broker name")}
                />
                <button
                  type="button"
                  onClick={() => {
                    setBrokerIsOther(false);
                    update({ broker: "" });
                  }}
                  className="px-1 text-xs text-slate-400 hover:text-slate-700"
                  title={tr("Choose from list instead")}
                >
                  ✕
                </button>
              </div>
            ) : (
              <select
                value={form.broker}
                onChange={(e) => {
                  if (e.target.value === OTHER_BROKER) {
                    setBrokerIsOther(true);
                    update({ broker: "" });
                  } else {
                    update({ broker: e.target.value });
                  }
                }}
                className={inputClass}
              >
                <option value="">{tr("— select —")}</option>
                {brokers.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
                <option value={OTHER_BROKER}>{tr("Other…")}</option>
              </select>
            ),
          )}

          {shape.toBroker &&
            field(
              tr("To broker"),
              toBrokerIsOther ? (
                <div className="flex gap-1">
                  <input
                    autoFocus
                    required
                    value={form.to_broker}
                    onChange={(e) => update({ to_broker: e.target.value })}
                    className={`${inputClass} flex-1`}
                    placeholder={tr("New broker name")}
                  />
                  <button
                    type="button"
                    onClick={() => {
                      setToBrokerIsOther(false);
                      update({ to_broker: "" });
                    }}
                    className="px-1 text-xs text-slate-400 hover:text-slate-700"
                    title={tr("Choose from list instead")}
                  >
                    ✕
                  </button>
                </div>
              ) : (
                <select
                  required
                  value={form.to_broker}
                  onChange={(e) => {
                    if (e.target.value === OTHER_BROKER) {
                      setToBrokerIsOther(true);
                      update({ to_broker: "" });
                    } else {
                      update({ to_broker: e.target.value });
                    }
                  }}
                  className={inputClass}
                >
                  <option value="">{tr("— select —")}</option>
                  {brokers
                    .filter((b) => b !== form.broker)
                    .map((b) => (
                      <option key={b} value={b}>
                        {b}
                      </option>
                    ))}
                  <option value={OTHER_BROKER}>{tr("Other…")}</option>
                </select>
              ),
            )}

          {shape.quantity &&
            field(
              tr("Quantity"),
              <input
                inputMode="decimal"
                value={form.quantity}
                onChange={(e) => update({ quantity: e.target.value })}
                className={inputClass}
              />,
            )}

          {shape.trade && (
            <>
              {field(
                tr("Price (native ccy)"),
                <input inputMode="decimal" value={form.price} onChange={(e) => update({ price: e.target.value })} className={inputClass} />,
              )}
              {field(
                tr("Local value"),
                <input
                  inputMode="decimal"
                  value={form.local_value}
                  onChange={(e) => editComputed("local_value", e.target.value)}
                  className={inputClass}
                />,
                resetButton("local_value"),
              )}
              {field(
                tr("FX rate"),
                <input inputMode="decimal" value={form.fx_rate} onChange={(e) => update({ fx_rate: e.target.value })} className={inputClass} />,
              )}
              {field(
                tr("Value (EUR)"),
                <input
                  inputMode="decimal"
                  value={form.value_eur}
                  onChange={(e) => editComputed("value_eur", e.target.value)}
                  className={inputClass}
                />,
                resetButton("value_eur"),
              )}
              {field(
                tr("Costs (EUR)"),
                <input inputMode="decimal" value={form.costs} onChange={(e) => update({ costs: e.target.value })} className={inputClass} />,
              )}
            </>
          )}

          {field(
            shape.amountLabel,
            <input
              inputMode="decimal"
              required
              value={form.total_eur}
              onChange={(e) => editComputed("total_eur", e.target.value)}
              className={inputClass}
            />,
            shape.trade && resetButton("total_eur"),
          )}

          <div className="col-span-2">
            {field(tr("Notes"), <input value={form.notes} onChange={(e) => update({ notes: e.target.value })} className={inputClass} />)}
          </div>

          <div className="col-span-2">
            <TransactionAttachments source={api.transactionAttachments} transactionId={initial?.id ?? null} pending={pendingFiles} onPendingChange={setPendingFiles} />
          </div>

          <div className="col-span-2 mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >{tr("Cancel")}</button>
            <button
              type="submit"
              disabled={isSubmitting || isCreatingAsset}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
            >
              {isCreatingAsset ? tr("Creating asset…") : isSubmitting ? tr("Saving…") : tr("Save")}
            </button>
          </div>
        </form>
    </ModalOverlay>
  );
}
