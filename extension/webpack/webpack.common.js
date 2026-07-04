/**
 * Shared webpack configuration for all browser targets (§7.1).
 *
 * Per-browser configs call `makeConfig("<browser>")`, which:
 *   - bundles the TypeScript entries (background, content, options),
 *   - copies static assets (icons, options.html),
 *   - generates dist/<browser>/manifest.json by deep-merging
 *     manifest/manifest.base.json with manifest/manifest.<browser>.json
 *     and stamping `version` from package.json.
 */
const path = require("path");
const fs = require("fs");
const CopyPlugin = require("copy-webpack-plugin");

const ROOT = path.resolve(__dirname, "..");

// Top-level manifest keys that per-browser overlays replace wholesale instead
// of merging (e.g. Firefox swaps service_worker for scripts — a merged object
// with both keys would be ambiguous).
const REPLACE_KEYS = ["background"];

function deepMerge(base, overlay, depth = 0) {
  const out = { ...base };
  for (const [key, value] of Object.entries(overlay)) {
    const replace =
      (depth === 0 && REPLACE_KEYS.includes(key)) ||
      Array.isArray(value) ||
      typeof value !== "object" ||
      value === null ||
      typeof out[key] !== "object" ||
      Array.isArray(out[key]);
    out[key] = replace ? value : deepMerge(out[key], value, depth + 1);
  }
  return out;
}

function generateManifest(browser) {
  const read = (p) => JSON.parse(fs.readFileSync(p, "utf-8"));
  const base = read(path.join(__dirname, "manifest", "manifest.base.json"));
  const overlay = read(
    path.join(__dirname, "manifest", `manifest.${browser}.json`),
  );
  const pkg = read(path.join(ROOT, "package.json"));
  const merged = deepMerge(base, overlay);
  merged.version = pkg.version;
  return JSON.stringify(merged, null, 2);
}

function makeConfig(browser) {
  return {
    mode: "production",
    devtool: false,
    context: ROOT,
    entry: {
      background: "./src/background.ts",
      content: "./src/content.ts",
      options: "./src/options/options.ts",
      inspect: "./src/inspect/inspect.ts",
    },
    output: {
      path: path.join(ROOT, "dist", browser),
      filename: "[name].js",
      clean: true,
    },
    resolve: {
      extensions: [".ts", ".js"],
    },
    module: {
      rules: [
        {
          test: /\.ts$/,
          loader: "ts-loader",
          exclude: /node_modules/,
        },
      ],
    },
    optimization: {
      // Keep each entry self-contained: MV3 workers/content scripts cannot
      // load shared runtime chunks.
      splitChunks: false,
      runtimeChunk: false,
    },
    plugins: [
      new CopyPlugin({
        patterns: [
          { from: "icons", to: "icons" },
          { from: "src/options/options.html", to: "options.html" },
          { from: "src/inspect/inspect.html", to: "inspect.html" },
          {
            from: "webpack/manifest/manifest.base.json",
            to: "manifest.json",
            transform: () => generateManifest(browser),
          },
        ],
      }),
    ],
  };
}

module.exports = { makeConfig };
