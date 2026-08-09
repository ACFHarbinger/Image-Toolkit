// @ts-check
import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";
import vueParser from "vue-eslint-parser";
import vuePlugin from "eslint-plugin-vue";
import globals from "globals";

export default [
  js.configs.recommended,
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parser: tsParser,
      parserOptions: { sourceType: "module", ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { "@typescript-eslint": tseslint },
    rules: {
      ...tseslint.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["**/*.vue"],
    languageOptions: {
      parser: vueParser,
      parserOptions: { parser: tsParser, sourceType: "module" },
      globals: { ...globals.browser },
    },
    plugins: { vue: vuePlugin },
    rules: {
      ...vuePlugin.configs["flat/recommended"].map((c) => c.rules).reduce((a, b) => ({ ...a, ...b }), {}),
    },
  },
  {
    ignores: [
      "dist/**",
      "public/**",
      "astro-public/**",
      "**/nav.generated.ts",
      "node_modules/**",
      "storybook-static/**",
    ],
  },
];
