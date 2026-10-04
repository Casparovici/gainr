/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Headings in gardnr's redesign and the module wordmarks (ModuleLogo.tsx).
        display: ['"Bricolage Grotesque"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      // Material 3 tonal roles for gripr's redesign -- each resolves through a CSS custom
      // property defined per-theme under `.module-gripr` in index.css, the same
      // ancestor-class-scoping technique the app's other per-module accents already use.
      // Outside gripr these variables are unset, so these utilities are only meaningful
      // there -- deliberately not a global recolour of the other three modules.
      colors: {
        primary: "rgb(var(--md-primary-rgb) / <alpha-value>)",
        "on-primary": "rgb(var(--md-on-primary-rgb) / <alpha-value>)",
        "primary-container": "rgb(var(--md-primary-container-rgb) / <alpha-value>)",
        "on-primary-container": "rgb(var(--md-on-primary-container-rgb) / <alpha-value>)",
        secondary: "rgb(var(--md-secondary-rgb) / <alpha-value>)",
        "on-secondary": "rgb(var(--md-on-secondary-rgb) / <alpha-value>)",
        "secondary-container": "rgb(var(--md-secondary-container-rgb) / <alpha-value>)",
        "on-secondary-container": "rgb(var(--md-on-secondary-container-rgb) / <alpha-value>)",
        tertiary: "rgb(var(--md-tertiary-rgb) / <alpha-value>)",
        "on-tertiary": "rgb(var(--md-on-tertiary-rgb) / <alpha-value>)",
        "tertiary-container": "rgb(var(--md-tertiary-container-rgb) / <alpha-value>)",
        "on-tertiary-container": "rgb(var(--md-on-tertiary-container-rgb) / <alpha-value>)",
        error: "rgb(var(--md-error-rgb) / <alpha-value>)",
        "on-error": "rgb(var(--md-on-error-rgb) / <alpha-value>)",
        "error-container": "rgb(var(--md-error-container-rgb) / <alpha-value>)",
        "on-error-container": "rgb(var(--md-on-error-container-rgb) / <alpha-value>)",
        surface: "rgb(var(--md-surface-rgb) / <alpha-value>)",
        "on-surface": "rgb(var(--md-on-surface-rgb) / <alpha-value>)",
        "surface-variant": "rgb(var(--md-surface-variant-rgb) / <alpha-value>)",
        "on-surface-variant": "rgb(var(--md-on-surface-variant-rgb) / <alpha-value>)",
        "surface-container-low": "rgb(var(--md-surface-container-low-rgb) / <alpha-value>)",
        "surface-container": "rgb(var(--md-surface-container-rgb) / <alpha-value>)",
        "surface-container-high": "rgb(var(--md-surface-container-high-rgb) / <alpha-value>)",
        outline: "rgb(var(--md-outline-rgb) / <alpha-value>)",
        // The page kit's tokens (gardnr, listr) -- see the page-kit block in index.css; each module
        // sets its own brand/warning values.
        "ui-bg": "rgb(var(--ui-bg-rgb) / <alpha-value>)",
        "ui-surface": "rgb(var(--ui-surface-rgb) / <alpha-value>)",
        "ui-border": "rgb(var(--ui-border-rgb) / <alpha-value>)",
        "ui-ink": "rgb(var(--ui-ink-rgb) / <alpha-value>)",
        "ui-ink-soft": "rgb(var(--ui-ink-soft-rgb) / <alpha-value>)",
        "ui-muted": "rgb(var(--ui-muted-rgb) / <alpha-value>)",
        "ui-faint": "rgb(var(--ui-faint-rgb) / <alpha-value>)",
        "ui-line": "rgb(var(--ui-line-rgb) / <alpha-value>)",
        "ui-brand": "rgb(var(--ui-brand-rgb) / <alpha-value>)",
        "ui-brand-strong": "rgb(var(--ui-brand-strong-rgb) / <alpha-value>)",
        "ui-brand-soft": "rgb(var(--ui-brand-soft-rgb) / <alpha-value>)",
        "ui-late": "rgb(var(--ui-late-rgb) / <alpha-value>)",
        "ui-late-soft": "rgb(var(--ui-late-soft-rgb) / <alpha-value>)",
        "ui-late-ink": "rgb(var(--ui-late-ink-rgb) / <alpha-value>)",
        "ui-late-line": "rgb(var(--ui-late-line-rgb) / <alpha-value>)",
        "ui-today": "rgb(var(--ui-today-rgb) / <alpha-value>)",
        "ui-today-soft": "rgb(var(--ui-today-soft-rgb) / <alpha-value>)",
        "ui-today-dot": "rgb(var(--ui-today-dot-rgb) / <alpha-value>)",
        "ui-field": "rgb(var(--ui-field-rgb) / <alpha-value>)",
        "ui-field-dot": "rgb(var(--ui-field-dot-rgb) / <alpha-value>)",
        "ui-zone-ink": "rgb(var(--ui-zone-ink-rgb) / <alpha-value>)",
        "ui-tile": "rgb(var(--ui-tile-rgb) / <alpha-value>)",
        "ui-disabled": "rgb(var(--ui-disabled-rgb) / <alpha-value>)",
        "ui-edit-bar": "rgb(var(--ui-edit-bar-rgb) / <alpha-value>)",
        "ui-edit-bar-label": "rgb(var(--ui-edit-bar-label-rgb) / <alpha-value>)",
        "outline-variant": "rgb(var(--md-outline-variant-rgb) / <alpha-value>)",
      },
    },
  },
  plugins: [],
};
