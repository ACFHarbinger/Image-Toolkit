import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import react from "@vitejs/plugin-react";

// Deployed as the entire gh-pages site (see .github/workflows/docs.yml), i.e.
// https://acfharbinger.github.io/Image-Toolkit/ — override via SITE_BASE for
// other deploy targets (local preview under a subpath, forks).
const base = process.env.SITE_BASE || "/";

export default defineConfig({
  base,
  plugins: [
    vue(),
    // The React island (src/frameworks/react/) is mounted client-side into
    // a Vue-owned DOM node via ReactDOM.createRoot — this plugin only
    // transforms its .tsx files; it never touches .vue SFCs.
    react({ include: /frameworks\/react\/.*\.tsx?$/ }),
  ],
  server: {
    fs: {
      // Allow importing markdown from the repo root (three levels up from
      // this file: website/ -> docs/ -> repo root) — useDocs.ts bundles
      // docs/**/*.md plus a curated set of repo-wide guides that live
      // outside docs/. Also allow ../../frontend/src so the React island
      // (src/frameworks/react/) can import Image-Toolkit's real
      // frontend/src/components/common/*.tsx directly.
      allow: ["../..", "../../frontend/src"],
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    chunkSizeWarningLimit: 1024,
  },
});
