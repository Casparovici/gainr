import { inputClass, primaryButtonClass } from "../ui/kit";
import type { usePicnicConnect } from "../../hooks/usePicnicConnect";
import { t } from "../../i18n";

/** "Connect to Picnic" (login, then the SMS code if Picnic asks for one) -- the not-connected
 * state of every page that needs a live Picnic session. `picnic` is that page's own
 * usePicnicConnect, so connecting chains straight into whatever the page wanted to do. */
export default function PicnicConnectCard({
  picnic,
  reason,
}: {
  picnic: ReturnType<typeof usePicnicConnect>;
  reason: string;
}) {
  if (picnic.status && !picnic.status.configured) {
    return (
      <div className="rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center text-ui-muted">{t("Picnic is niet ingesteld op deze server (GAINR_PICNIC_EMAIL en GAINR_PICNIC_PASSWORD ontbreken).")}</div>
    );
  }
  return (
    <div className="flex flex-col items-center gap-3 rounded-[20px] border border-ui-border bg-ui-surface px-4 py-6 text-center">
      <p className="m-0 text-ui-ink-soft">{reason}</p>
      {picnic.awaiting2FA ? (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (picnic.code.trim()) picnic.verify();
          }}
          className="flex w-full max-w-xs flex-col gap-2"
        >
          <label className="text-sm text-ui-muted" htmlFor="picnic-code">{t("Picnic heeft je een sms gestuurd met een code.")}</label>
          <input
            id="picnic-code"
            autoFocus
            inputMode="numeric"
            value={picnic.code}
            onChange={(e) => picnic.setCode(e.target.value)}
            placeholder="123456"
            className={inputClass}
          />
          {picnic.verifyError && <p className="m-0 text-sm text-ui-late">{t("Code niet geaccepteerd, probeer opnieuw.")}</p>}
          <button type="submit" disabled={!picnic.code.trim() || picnic.isVerifying} className={primaryButtonClass}>{t("Bevestigen")}</button>
        </form>
      ) : (
        <button type="button" onClick={picnic.connect} disabled={picnic.isConnecting} className={primaryButtonClass}>
          {picnic.isConnecting ? t("Bezig…") : t("Verbinden met Picnic")}
        </button>
      )}
      {picnic.connectError && <p className="m-0 text-sm text-ui-late">{t("Verbinden met Picnic is mislukt. Probeer het later opnieuw.")}</p>}
    </div>
  );
}
