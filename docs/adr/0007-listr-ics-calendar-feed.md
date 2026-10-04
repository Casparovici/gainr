# 7. listr: read-only ICS feed for the Weekplanner, published via Tailscale Funnel

## Status

Accepted

## Context

The user wants their listr Weekplanner to show up (read-only) in Google Calendar. Google
Calendar has two ways to pull in external data: the full Calendar API (OAuth2, a Google Cloud
project, a stored refresh token, near-instant sync) or "subscribe by URL" to a plain iCalendar
(.ics) feed (no OAuth, Google polls the URL on its own schedule — typically every several
hours, not instant). For a single-user app that has never needed to store a third-party secret
before (yfinance needs no key), and where near-real-time sync isn't a requirement the user
asked for, the ICS route is the much smaller addition.

The harder part turned out not to be generating the feed but reaching it: gainr's homecloud
deployment listens only on the box's LAN/Tailscale interface (`0.0.0.0:80`, no reverse proxy,
no public DNS) — reachable via Tailscale today, never designed to be reachable from the public
internet Google's servers poll from.

## Decisions

**A token-gated `GET /api/listr/meal-plan.ics?token=...` endpoint**, not the Calendar API.
Renders every `ListrMealPlan` row as an all-day `VEVENT` (✓-prefixed when `is_cooked`), using
the `icalendar` library rather than hand-formatting ICS text — line-folding, escaping, and
`DTSTART;VALUE=DATE` formatting are easy to get subtly wrong by hand, and a malformed feed is a
worse failure mode (a calendar client silently drops or mangles entries) than one more small,
well-established dependency.

**The token is a plain shared secret, read from `GAINR_LISTR_ICS_TOKEN`** (`app/config.py`),
never committed — the same env-var-only pattern `GAINR_DATABASE_URL`/`GAINR_CORS_ORIGINS`
already use. Unset (the default everywhere except homecloud) means the endpoint always 404s,
so the feature is off by default rather than needing to be explicitly disabled. A wrong token
also 404s (not 401/403), so an unauthenticated prober can't distinguish "wrong token" from
"page doesn't exist."

**Public reachability is scoped to a dedicated port, via Tailscale Funnel, not by opening the
app itself to the internet.** Funnel turns out to be an on/off switch for an entire
`hostname:port` listener, not per-path — enabling it on port 443 (where the app's own
`tailscale serve` root mount also lives, added later for the household-access setup, see
below) would have funneled the whole app to the public internet regardless of a `--set-path`
flag, since that flag only adds a mount to the serve config, it doesn't scope *which* mounts on
that port get funneled. This was caught live (a `tailscale funnel status` check showed `/` and
`/listr.ics` both listed as "Funnel on" after adding the app's root mount) and fixed by moving
the feed to its own port:
- **`:443`** — `tailscale serve` (no funnel) proxying `/` to the app (`127.0.0.1:80`) —
  tailnet-only, reachable to the account owner and anyone the `gainr` device is explicitly
  shared with (see [ADR 0008](0008-household-tailscale-access.md)).
- **`:8443`** — `tailscale funnel --set-path=/listr.ics` proxying only that one URL to
  `127.0.0.1:80/api/listr/meal-plan.ics` — the only thing reachable from the public internet,
  and still token-gated by the app itself underneath.

No new reverse proxy process was needed either way; `tailscale serve`/`funnel`'s own mounting
covers it, as long as anything meant to stay private lives on a port Funnel is never turned on
for, rather than trusting per-path scoping on a port that's also funneled.

## Alternatives considered

- **Google Calendar API + OAuth2**: near-instant sync, but needs a Google Cloud project, an
  OAuth consent flow, and secure storage for a refresh token — real new complexity and the
  app's first stored third-party secret, for a want ("see it in Google Calendar") that doesn't
  need to be instant.
- **Opening the whole app to the public internet** (funnel the main port, or a reverse proxy
  with no path scoping): the app has no authentication at all today, so this would publish
  portfolio and personal-finance data to the internet to solve a problem that only needed one
  read-only, already-token-gated path exposed.
- **A reverse-proxy process (Caddy/nginx) in front of Tailscale Funnel**: unnecessary — Tailscale
  `serve`/`funnel`'s built-in `--set-path` mounting does the same scoping without adding and
  operating a new service.
- **Sharing port 443 between the app's tailnet-only root mount and the funneled ICS path**: this
  was the first attempt, and it's wrong — Funnel enables the whole port's listener to the
  internet, not just the path it was invoked with. A dedicated funnel-only port is the only way
  to keep one mount genuinely private while another on the same node is public.

## Consequences

- Google Calendar's refresh cadence for subscribed URLs isn't controllable from this app — a
  same-day edit to the weekplanner may take hours to appear in Google Calendar. Acceptable for
  a "see my plan on my phone's calendar too" want, not for anything time-sensitive.
- The subscription URL (path + token) is a bearer secret: anyone who has it can read the whole
  meal-plan history (never anything else — the feed is read-only and carries no other app data).
  It isn't surfaced anywhere in the app's UI; it's handed to the user directly once, the same
  way the homecloud SSH deploy key is handled outside the app.
- If the token ever needs to be rotated (leaked, or just periodic hygiene), it's one env var
  change + a service restart on homecloud, and the previous Google Calendar subscription needs
  re-adding with the new URL — there's no in-app token-rotation flow, matching the app's
  existing no-secrets-in-the-app posture.

## Bug found after the fact: Google accepted the calendar but showed no events

The first shipped version of `_build_meal_plan_ics` (`app/routers/listr.py`) never set
`DTSTAMP` on any `VEVENT` — RFC 5545 requires it, and while `icalendar`'s writer doesn't enforce
that, Google Calendar's reader does: it happily parsed and added the `VCALENDAR` itself (hence
the "Weekplanner" calendar showing up at all), then silently dropped every event inside it for
failing validation, with no error surfaced anywhere. Fixed by stamping every event with the
feed's generation time (`datetime.now(timezone.utc)`) — correct per spec for a dynamically
generated feed, and simpler than trying to derive one from `ListrMealPlan.updated_at`. Worth
remembering for any future feed/export format: a "the container looks right but the contents
are missing" report is a validation-dropped-silently symptom, not a routing/auth one — check
the actual generated payload against the format's required fields before assuming the plumbing
is broken.
