import { TRAINR_ACTIVITY_LABELS, TRAINR_ACTIVITY_TYPES, type TrainrActivityType } from "../../api/trainrTypes";
import { t } from "../../i18n";

const selectClass =
  "h-11 w-full rounded-xl border border-ui-border bg-ui-surface px-3 text-sm font-semibold text-ui-ink focus:border-ui-brand focus:outline-none";

/** The activity picker as a native dropdown -- five activities no longer fit side by side on a
 * phone. With `allLabel` it also offers an "all activities" choice (the history filter), whose
 * value is "all". */
export default function ActivitySelect<Value extends TrainrActivityType | "all" = TrainrActivityType>({
  value,
  onChange,
  options = TRAINR_ACTIVITY_TYPES as TrainrActivityType[],
  allLabel,
  label = t("Activiteit"),
  className = selectClass,
}: {
  value: Value;
  onChange: (value: Value) => void;
  options?: TrainrActivityType[];
  allLabel?: string;
  label?: string;
  className?: string;
}) {
  return (
    <select aria-label={label} value={value} onChange={(e) => onChange(e.target.value as Value)} className={className}>
      {allLabel && <option value="all">{allLabel}</option>}
      {options.map((type) => (
        <option key={type} value={type}>
          {t(TRAINR_ACTIVITY_LABELS[type])}
        </option>
      ))}
    </select>
  );
}
