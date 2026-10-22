// @ts-check
import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import boundaries from "eslint-plugin-boundaries";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["**/*.{js,mjs,cjs}"],
    languageOptions: { globals: { ...globals.node } },
  },
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    languageOptions: {
      parser: tsParser,
      parserOptions: { sourceType: "module", ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: {
      "@typescript-eslint": tseslint,
      "react-hooks": reactHooks,
      boundaries,
    },
    settings: {
      "import/resolver": {
        node: {
          extensions: [".js", ".jsx", ".ts", ".tsx"],
        },
      },
      "boundaries/include": ["src/**/*"],
      "boundaries/elements": [
        {
          type: "shell",
          pattern: "src/shell/**",
          partialMatch: false,
        },
        {
          type: "eventhub",
          pattern: "src/eventhub/**",
          partialMatch: false,
        },
        {
          type: "store",
          pattern: "src/store/**",
          partialMatch: false,
        },
        {
          type: "shared",
          pattern: ["src/components/**", "src/hooks/**", "src/math/**"],
          partialMatch: false,
        },
        {
          type: "feature",
          pattern: "src/features/*/**",
          capture: ["feature"],
          partialMatch: false,
        },
        {
          type: "tab",
          pattern: "src/tabs/*/**",
          capture: ["domain"],
          partialMatch: false,
        },
      ],
    },
    rules: {
      "no-undef": "off",
      "no-unused-vars": "off",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "boundaries/dependencies": [
        "error",
        {
          default: "allow",
          policies: [
            {
              from: { element: { type: "shared" } },
              disallow: { to: { element: { type: ["shell", "feature", "tab"] } } },
              message:
                "Shared components/hooks/math must not import from shell, features, or tabs.",
            },
            {
              from: { element: { type: "eventhub" } },
              disallow: {
                to: { element: { type: ["shell", "feature", "tab", "shared", "store"] } },
              },
              message: "EventHub must remain independent of UI features, tabs, and shell.",
            },
            {
              from: { element: { type: "store" } },
              disallow: { to: { element: { type: ["feature", "tab"] } } },
              message: "Store must not import directly from feature or tab views.",
            },
            {
              from: { element: { type: "feature" } },
              disallow: {
                to: [
                  { element: { type: "tab" } },
                  {
                    element: {
                      type: "feature",
                      captured: { feature: "!{{ from.captured.feature }}" },
                    },
                  },
                ],
              },
              message:
                "Features under src/features/<x>/ are isolated and cannot import other features or tabs directly (route via shell/eventhub/store).",
            },
            {
              from: { element: { type: "tab" } },
              disallow: {
                to: [
                  {
                    element: {
                      type: "tab",
                      captured: { domain: "!{{ from.captured.domain }}" },
                    },
                  },
                ],
              },
              message:
                "Tab domains under src/tabs/<domain>/ cannot import across sibling tab domains directly.",
            },
          ],
        },
      ],
    },
  },
  {
    ignores: [
      "build/**",
      "dist/**",
      "node_modules/**",
      "src-tauri/**",
    ],
  },
];
