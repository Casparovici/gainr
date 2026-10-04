import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Listens on every interface, not just loopback, so the dev server is reachable from a
    // phone on the same tailnet/LAN -- needed to actually test the mobile nav/FAB at real
    // touch scale instead of a resized desktop window.
    host: true,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
