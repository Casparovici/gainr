# 8. Household access via Tailscale device sharing, not a login system

## Status

Accepted

## Context

The user wants his wife to be able to use gainr/gripr/listr too. Two questions decided the
shape of this: does she need her own separate data (her own portfolio, her own budget
categories), or the same shared household data; and does she need to reach the app from
anywhere, or is being on the home network enough. Both answers came back on the simple side:
shared data, and network-only access is fine.

## Decisions

**No account system, no per-user data model.** The app stays exactly what CLAUDE.md already
describes it as — local and single-user, in the sense that there's one dataset, not one dataset
per login. Adding `user_id` throughout gainr/gripr/listr's schemas, filtering every query by
it, and building a login flow would be a substantial change to solve a problem the user doesn't
have: this is a household finance app for a household, not a multi-tenant product.

**Access is a Tailscale device share, not an app-level login.** The homecloud box's tailnet is
a personal one under the user's own account — there's no "invite a second user to my network"
option on a personal tailnet, but Tailscale's **share a device** feature covers exactly this:
the wife gets her own (separate) Tailscale account, the `gainr` node is shared to her
specifically from the [admin console](https://login.tailscale.com/admin/machines), and once
accepted her devices can reach it — without merging the two tailnets, so she doesn't get access
to the user's other devices (personal laptop, phone, etc.) and vice versa.

**The app is reachable over HTTPS on the tailnet, not just plain HTTP.** `tailscale serve`
(no funnel) proxies port 443 to the app's existing `127.0.0.1:80` — tailnet peers now get a
trusted, browser-clean `https://ipper.tailf12cf8.ts.net/` instead of only plain HTTP, which
matters because modern browsers increasingly try HTTPS first for a bare-typed domain and fail
outright (rather than falling back) when nothing answers on 443. This surfaced directly: before
this mount existed, the wife's browser produced an SSL protocol error trying
`finance.tijssen-hq.nl` over HTTPS, because nothing was listening there.

**The custom domain (`finance.tijssen-hq.nl`, in Cloudflare DNS) only resolves to the box's
Tailscale address, not a public one** — it works over plain `http://` for anyone already on the
tailnet, but not over `https://`, since Tailscale only issues certificates for its own
`*.ts.net` names, not arbitrary domains pointed at a tailnet IP. `https://ipper.tailf12cf8
.ts.net/` is the one that actually gets a valid, browser-trusted certificate, so it's the URL
handed out for real use; the custom domain over HTTPS would need its own reverse proxy with its
own ACME certificate (e.g. Caddy) to work, which isn't justified for what's otherwise a fully
solved problem via the `.ts.net` name.

## Alternatives considered

- **A real login system** (shared household password, or per-user accounts): more work than the
  actual requirement (shared data) calls for, and the household is already gated by something
  stronger than a password — Tailscale network membership, which nobody outside the two of them
  has.
- **A multi-user Tailscale plan / migrating to an org tailnet**: would let her join as a full
  tailnet member rather than a single shared device, but is a bigger, harder-to-reverse account
  change for a household of two who only need access to one box.
- **Terminate TLS for the custom domain directly** (Caddy + Let's Encrypt on the box, fronting
  both the app and the ICS feed under `finance.tijssen-hq.nl` with a real cert): would make the
  custom domain fully work over HTTPS too, but adds and operates a new service for a cosmetic
  win — the `.ts.net` HTTPS URL already works cleanly.

## Consequences

- Two URLs exist for the same app depending on protocol: `https://ipper.tailf12cf8.ts.net/`
  (works, trusted cert) and `http://finance.tijssen-hq.nl` (works, no cert involved) — but
  `https://finance.tijssen-hq.nl` does not, since nothing holds a certificate for that name.
  Worth remembering if a browser's HTTPS-upgrade behavior causes this to resurface.
- Onboarding a household member is a manual, one-time admin-console action (share the device,
  she accepts in the Tailscale app) rather than a self-serve signup — appropriate at this scale
  (a household of two), reconsider if that ever changes.
