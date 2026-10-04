import { useState } from "react";

/** A bank/broker's cached brand icon (see gripr_bank_logo_service.py) -- unlike AssetLogo there's
 * no initials-badge fallback, since a bank logo is optional by nature (most accounts have none
 * set): nothing renders at all until a real image has actually loaded. */
export default function BankLogo({ bankKey, size = 22 }: { bankKey: string; size?: number }) {
  const [loaded, setLoaded] = useState(false);

  return (
    <span
      className="inline-flex shrink-0 items-center justify-center overflow-hidden rounded-md bg-white ring-1 ring-outline-variant"
      style={{ width: size, height: size, display: loaded ? undefined : "none" }}
    >
      {/* No `loading="lazy"` -- the wrapper starts `display: none` until loaded, and a lazy
          image inside a hidden ancestor never enters the viewport, so it would never load in
          the first place. These are a handful of small, already-cached-after-first-fetch icons
          per page, so eager loading costs nothing. */}
      <img
        src={`/api/gripr/bank-logos/${bankKey}/logo`}
        alt=""
        onLoad={() => setLoaded(true)}
        onError={() => setLoaded(false)}
        className="h-full w-full object-contain"
      />
    </span>
  );
}
