# 9. Android app: a Capacitor wrapper around the live site

## Status

Accepted

## Context

The user wants gainr/gripr/listr available as an Android app with the same features and a
UI/UX close to the web app, and asked explicitly how the website and Android app can be kept in
sync going forward.

## Decisions

**Capacitor, in `server.url` mode, not a bundled build.** `frontend/capacitor.config.ts` points
the native WebView straight at `https://ipper.tailf12cf8.ts.net` (the one URL with a valid,
browser-trusted cert — see [ADR 0008](0008-household-tailscale-access.md); the
`finance.tijssen-hq.nl` custom domain only resolves over plain HTTP). The Android app therefore
has **no UI code of its own** — it's the same React app, loaded live, wrapped in a native shell
(own launcher icon, own task-switcher entry, real installable `.apk`). This is the direct answer
to "how do we keep them in sync": there's nothing to keep in sync, because there's only one
frontend. Every web deploy is instantly what the Android app shows, with no separate release
step for ordinary feature work — only a native-shell change (a new plugin, a permission) needs a
new APK built and reinstalled.

**Confirmed with the user over a PWA "Add to Home Screen" and a full native (Kotlin/Compose)
rewrite** — both considered and rejected:
- A PWA install needs no new project at all, but isn't a distinct installable app (opens through
  Chrome's engine, no home-screen-icon identity beyond what Chrome grants any installed site,
  can't add native plugins like a biometric lock without migrating to Capacitor anyway).
- A native rewrite gives the deepest platform integration, but is a second codebase that has to
  be manually kept in feature-parity with the web app forever — the opposite of an automatic
  sync answer, and a permanent 2x cost on every future feature for a household app built by one
  person.

**Zero backend or existing-frontend changes were needed for the app to function.** Every API
client (`frontend/src/api/{client,griprClient,listrClient}.ts`) already calls a same-origin
relative path (`fetch("/api${path}")`), and in `server.url` mode the WebView's origin genuinely
*is* `https://ipper.tailf12cf8.ts.net` — so `/api/...` resolves correctly with no CORS change,
exactly as it would in a mobile browser tab. This was the strongest practical argument for this
approach beyond the sync question alone.

**A biometric/PIN lock, Android-only, behind `Capacitor.isNativePlatform()`.** The web app has no
login and that's unchanged — but a phone icon is a more exposed entry point than a browser
bookmark, so `frontend/src/components/AppLockGate.tsx` wraps the whole app (wired once, in
`main.tsx`) and requires the phone's own biometric or device-credential (PIN/pattern/password)
check via `@capgo/capacitor-native-biometric` before rendering anything, re-checking every time
the app returns from the background (the same convention banking apps use). On web, this
component renders `children` immediately and never touches the plugin — verified by keeping the
gate check as the very first line of the component, not a fallback path.
This is explicitly a **convenience layer against a casual glance or someone else's hands on an
unlocked phone, not the app's real security boundary** — the plugin's own documentation is
explicit that `verifyIdentity()` can be bypassed on a rooted/jailbroken device via a hooked JS
bridge, and this app has no server-side session to actually gate. The real security boundary
remains Tailscale network membership (ADR 0008): nobody without a shared device connection can
reach the site at all, biometric lock or not.

**Distribution is a sideloaded `.apk`, not the Play Store**, signed with a dedicated release
keystore kept out of git entirely (same convention `GAINR_LISTR_ICS_TOKEN` already follows —
secrets live in the environment/local filesystem, never committed; `frontend/android/.gitignore`
was updated to actually exclude `*.jks`/`*.keystore`, which Capacitor's template ships
commented-out by default). This matches the app's existing posture: no login, not public, only
reachable to Tailscale-shared devices — a Play Store listing would need a privacy policy, a
public-facing store presence, and review, none of which fits a two-person household app.

**Plugin choice**: `@capgo/capacitor-native-biometric` (a maintained fork of the long-standing
`capacitor-native-biometric`, versioned to track Capacitor's own major version, actively
published) over the original package (last published 2023, stale relative to Capacitor 8) or
`@aparajita/capacitor-biometric-auth` (viable, but less directly matched to the exact
`isAvailable`/`verifyIdentity` + `DEVICE_CREDENTIAL`-fallback shape already familiar from the
original plugin's wide documentation).

## Toolchain note

`@capacitor/cli` v8 requires Node ≥22; this machine runs Node 20, so `@capacitor/cli` is pinned
to `^7.6.9` (the version npm's own engine-aware resolution picked) while `@capacitor/core`,
`@capacitor/android`, and every plugin stay on their current 8.x releases — `cap add android` /
`cap sync android` / `capacitor-assets generate` all ran cleanly against that combination.
Building the actual APK needs a JDK + Android SDK/Gradle, unavailable in this environment
(no `java` on `PATH`, no passwordless `sudo` to install one) — the project is fully scaffolded
and synced, but the first real build/sign/install happens in Android Studio (see README), the
standard tool for this anyway and useful to have installed for any future native-shell change.

## Alternatives considered

- **PWA "Add to Home Screen"**: see above — rejected for not being a distinct installable app
  and no path to native plugins like the biometric lock without migrating to Capacitor regardless.
- **Full native rewrite (Kotlin + Jetpack Compose)**: see above — rejected for turning the sync
  question into a permanent manual-parity burden.
- **Bundling `dist/` into the APK instead of `server.url`**: would need introducing an actual
  configurable API base URL across three client files (today hardcoded relative paths) plus
  CORS changes, for a benefit — offline access — the app doesn't otherwise support (no
  service worker, no local data cache); not worth the added surface for a feature nobody asked
  for.

## Consequences

- The Android app requires network connectivity (Tailscale reachable) to do anything at all, by
  design — identical to the web app's existing requirement, not a regression.
- A future feature ships to the Android app automatically the moment it's deployed to homecloud;
  only a native-shell change (a new Capacitor plugin, an Android permission, an icon change)
  needs `npx cap sync android` and a new signed APK.
- The biometric lock is convenience-only, explicitly documented as such rather than presented as
  a real access-control boundary — future work involving actual sensitive actions (irreversible
  deletes, etc.) should not assume the app is "protected" by it.

## Addendum: biometric lock removed (2026-10-04)

The biometric/PIN lock kept re-prompting right after a successful unlock and was switched off on
2026-09-14. It's now deleted, with its plugins (`@capgo/capacitor-native-biometric`,
`@capacitor/app`, `@capacitor/status-bar`). Access control is Tailscale membership (ADR 0008),
as it always was; the lock only guarded against someone holding an unlocked phone.

