import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Deployed as the entire gh-pages site (see .github/workflows/docs.yml), i.e.
// https://acfharbinger.github.io/Image-Toolkit/ — override via SITE_BASE for
// other deploy targets (local preview under a subpath, forks).
const base = process.env.SITE_BASE || "/";

export default defineConfig({
  base,
  // The active documentation experience is now the React application. The
  // previous Vue portal remains archived in docs/website_old while the React
  // cutover is stabilized.
  plugins: [react()],
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
