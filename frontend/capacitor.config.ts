import type { CapacitorConfig } from "@capacitor/cli";

// The WebView loads the live site directly rather than a bundled copy of `dist/` -- see
// docs/adr/0009-android-capacitor-wrapper.md. This means the app has no UI code of its own:
// every web deploy is instantly what the Android app shows, with nothing to rebuild or
// resubmit for ordinary feature work. `webDir` still has to point at a real built directory
// for the Capacitor CLI's own tooling (`cap sync`), even though nothing in it is ever loaded.
const config: CapacitorConfig = {
  appId: "nl.tijssenhq.gainr",
  appName: "gainr",
  webDir: "dist",
  server: {
    // The one URL that gets a valid, browser-trusted cert (see docs/adr/0008) -- never the
    // finance.tijssen-hq.nl custom domain, which only resolves over plain HTTP. The Tailscale
    // machine is still named "ipper" (not "gainr"): the module rename didn't rename the box, and
    // a "gainr.tailf12cf8.ts.net" URL simply doesn't exist (ERR_NAME_NOT_RESOLVED in the app).
    url: "https://ipper.tailf12cf8.ts.net",
    cleartext: false,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 400,
      launchAutoHide: true,
      backgroundColor: "#0f172aff",
      androidScaleType: "CENTER_CROP",
      showSpinner: false,
    },
  },
};

export default config;
