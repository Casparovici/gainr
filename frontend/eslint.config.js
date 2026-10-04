import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "android", "node_modules", "design"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Seeding a form or a selection from data that just loaded is done in an effect throughout
      // this app, deliberately: it's a re-render, not a bug. The rest of the hooks rules stay on.
      "react-hooks/set-state-in-effect": "off",
      // Fast-refresh granularity in the dev server only; many modules export a helper next to
      // their component on purpose.
      "react-refresh/only-export-components": "off",
      // An `_unused` argument documents a callback's shape without using it.
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
);
