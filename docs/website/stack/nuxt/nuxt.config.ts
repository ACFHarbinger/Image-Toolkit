// Nuxt 3 config — not the primary framework here (that's the plain Vite +
// Vue Router setup in vite.config.ts / src/router.ts), kept as an
// alternative SSR-capable surface over the same src/ tree, the same way
// stack/next/ is kept for a possible React/Next surface. Not part of the
// default `npm run build` — only reachable via `npm run nuxt:*`.
import { defineNuxtConfig } from "nuxt/config";

export default defineNuxtConfig({
  srcDir: "../../src",
  rootDir: "../..",
  compatibilityDate: "2025-01-01",
  css: ["~/styles/theme.css", "~/styles/markdown.css", "~/styles/hub.css"],
  typescript: { typeCheck: false },
  postcss: {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  },
});
