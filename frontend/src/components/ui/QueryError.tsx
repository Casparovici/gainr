import { t } from "../../i18n";
/** What a widget shows when its data couldn't be loaded, instead of the empty state it would
 * otherwise fall through to ("No transactions" when the request actually failed). The retry
 * refetches the failed query; the label follows the module's language. */
export function QueryError({
  message,
  onRetry,
  retryLabel = t("Try again"),
  className = "",
}: {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}) {
  return (
    <div role="alert" className={`text-ui-late ${className}`}>
      {message}
      {onRetry && (
        <>
          {" "}
          <button type="button" onClick={onRetry} className="font-semibold underline underline-offset-2">
            {retryLabel}
          </button>
        </>
      )}
    </div>
  );
}
