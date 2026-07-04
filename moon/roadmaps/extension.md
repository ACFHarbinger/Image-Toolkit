# Browser Extension Roadmap — Capture, Build System, and Desktop-App Integration

*Created: 2026-07-04. Covers the `extension/` WebExtension ("Save Image to Folder") — its build infrastructure, capture/UX upgrades, and integration with the Image Toolkit desktop app (Django API `api/`, `PhashDeduplicator`, BGE-M3/Qdrant vector search).*

---

## Table of Contents

- [Current State](#current-state)
- [7.1 Webpack Multi-Browser Build System](#71-webpack-multi-browser-build-system)
- [7.2 TypeScript Migration & Shared Core](#72-typescript-migration--shared-core)
- [7.3 Unified Manifest V3](#73-unified-manifest-v3)
- [7.4 Options Page Redesign](#74-options-page-redesign)
- [7.5 Local App Bridge (HTTP → Native Messaging)](#75-local-app-bridge-http--native-messaging)
- [7.6 In-Browser Duplicate Search](#76-in-browser-duplicate-search)
- [7.7 Send to Image Toolkit](#77-send-to-image-toolkit)
- [7.8 Visual Similarity Search from Browser](#78-visual-similarity-search-from-browser)
- [7.9 Bulk Page Grabber](#79-bulk-page-grabber)
- [7.10 Per-Site Folder Rules, Filename Templating & Metadata Sidecar](#710-per-site-folder-rules-filename-templating--metadata-sidecar)
- [7.11 Full-Resolution Extraction](#711-full-resolution-extraction)
- [7.12 Turbo Mode Polish](#712-turbo-mode-polish)
- [Phasing & Dependency Graph](#phasing--dependency-graph)
- [Effort × Impact Matrix](#effort--impact-matrix)

---

## Current State

The extension is a minimal image-saving helper:

- **`background.js`** — creates a "Save to selected directory" context-menu item on images; downloads `info.srcUrl` into `Downloads/<targetFolder>/` via `downloads.download` with `conflictAction: "uniquify"`; also receives `download_image` messages from the content script.
- **`content.js`** — "Turbo Mode": when enabled, intercepts click/pointer/touch events in capture phase, finds an `IMG` under the cursor via `elementsFromPoint`, blocks the site's handlers, and messages the background to download `img.src`.
- **`options.html/js`** — popup with target-folder text field + turbo checkbox, persisted in `storage.local`.
- **Manifests** — three hand-maintained copies: `manifest.json` (MV3), `manifest_chrome.json` (MV3), `manifest_firefox.json` (MV2, `browser_specific_settings.gecko`). `extension/webpack/` exists but is empty.
- Browser API differences handled ad-hoc via `typeof browser !== 'undefined'` + duplicated Promise/callback wrappers in every file.

Untapped app-side capabilities: `PhashDeduplicator` (`backend/src/core/phash_deduplicator.py`, shipped §4.6), pgvector/Qdrant + BGE-M3 vector search, the Django REST API (`api/`, OpenAPI-documented since §4.5), and the C++ `base` image core.

---

## 7.1 Webpack Multi-Browser Build System

**Pain point:** Three hand-maintained manifest copies (`manifest.json`, `manifest_chrome.json`, `manifest_firefox.json`) drift apart; there is no build step, no minification, no way to emit per-browser packages for Chrome, Firefox, Edge, and Brave.

**Approach (selected):** Webpack 5 build in `extension/webpack/`:

```
extension/
├── src/                       # source of truth (TS after §7.2)
│   ├── background.ts
│   ├── content.ts
│   ├── options/{options.html,options.ts}
│   └── shared/                # api adapter, storage, types
├── webpack/
│   ├── webpack.common.js      # entries, ts-loader, CopyPlugin (icons, html)
│   ├── webpack.chrome.js      # merge(common) + manifest for chrome
│   ├── webpack.firefox.js
│   ├── webpack.edge.js
│   ├── webpack.brave.js
│   └── manifest/
│       ├── manifest.base.json         # shared keys (name, version, icons, …)
│       ├── manifest.chrome.json       # MV3 service_worker, host_permissions
│       ├── manifest.firefox.json      # gecko id, background.scripts fallback
│       ├── manifest.edge.json         # chrome-compatible; store-specific keys
│       └── manifest.brave.json        # chrome-compatible
└── dist/{chrome,firefox,edge,brave}/  # unpacked builds + zips
```

- A small `GenerateManifestPlugin` (or `webpack.DefinePlugin` + `CopyPlugin.transform`) deep-merges `manifest.base.json` with the per-browser overlay and stamps `version` from `package.json`, emitting a single generated `manifest.json` per target — the three hand-written manifests in `extension/` are deleted.
- npm scripts: `build:chrome`, `build:firefox`, `build:edge`, `build:brave`, `build:all`, `watch:<browser>`; `just` recipes `build-extension` / `build-extension-all` mirroring the existing `build-frontend` pattern.
- Edge and Brave are Chromium-based: their overlays start as `{}` + store metadata, but having explicit targets keeps store-specific divergence (e.g. Edge `update_url`, future Brave rewards keys) tractable.
- Output zips named `image-toolkit-extension-<browser>-<version>.zip` for store upload.

**Effort:** ~2d · **Impact:** High (unblocks everything else; kills manifest drift)

---

## 7.2 TypeScript Migration & Shared Core

**Pain point:** The `typeof browser !== 'undefined'` adapter and the Promise/callback storage shim are copy-pasted in all three JS files; no types, no shared constants; message payloads are stringly-typed.

**Approach (selected):**
- Move `background/content/options` to TypeScript under `extension/src/`, compiled by the §7.1 webpack setup (`ts-loader`, `@types/webextension-polyfill`).
- `shared/api.ts` — single browser-API adapter (or adopt `webextension-polyfill` so everything is Promise-based on Chrome too).
- `shared/messages.ts` — discriminated-union message types (`DownloadImage`, `DupCheckRequest`, `DupCheckResult`, `IngestImage`, …) shared by background/content/options — this becomes the contract §7.5–§7.8 build on.
- `shared/settings.ts` — typed `storage.local` schema with defaults (`targetFolder`, `turboMode`, per-site rules from §7.10, bridge URL from §7.5).

**Effort:** ~2d · **Impact:** Medium-High (correctness + velocity for the feature work below)

---

## 7.3 Unified Manifest V3

**Pain point:** Firefox manifest is MV2 (`background.scripts`, `browser_action`) while Chrome is MV3; behaviour and permissions diverge.

**Approach (selected):** Target MV3 everywhere. Firefox 109+ supports MV3; the remaining differences are captured in the §7.1 overlays:
- Firefox MV3 uses `background.scripts` (event page) instead of `service_worker` — expressed in `manifest.firefox.json` overlay only.
- `host_permissions` unified; `browser_specific_settings.gecko` kept in the Firefox overlay with a real add-on ID (replace `save-to-folder@example.com`).
- Verify `storage.onChanged`, `contextMenus`, `downloads` parity under Firefox MV3; add `optional_host_permissions` where Firefox requires opt-in.

**Effort:** ~1d (folded into §7.1 overlays) · **Impact:** Medium (one API surface, MV2 EOL-proof)

---

## 7.4 Options Page Redesign

**Pain point:** The popup is a single folder field + turbo checkbox; upcoming features (folder profiles, per-site rules, app-bridge status) have nowhere to live.

**Approach (selected):**
- Split **popup** (quick actions: current folder profile switcher, turbo toggle, bridge status dot, "scan this page" launcher for §7.9) from a full **options page** (`options_ui.open_in_tab: true`).
- Options page tabs: *General* (default folder, filename template), *Folder Profiles & Site Rules* (§7.10 editor: domain pattern → folder/profile table), *Image Toolkit Connection* (§7.5: bridge URL/port, token, "Test connection", duplicate-search root directory display), *Advanced* (turbo behaviour, notification prefs).
- Keep it dependency-free (no framework) or Preact-via-webpack if the rules editor gets complex; styled to match the app's dark theme.

**Effort:** ~2–3d · **Impact:** Medium (prerequisite UX surface for §7.5/§7.9/§7.10)

---

## 7.5 Local App Bridge (HTTP → Native Messaging)

**Pain point:** The extension cannot reach any of the app's intelligence (dedup, vector search, ingestion). All integration features need a transport.

**Approach (selected — phased "Both"):**

**Phase A — Local HTTP API (MVP):**
- New Django app `api/extension/` exposing a small, token-authenticated, localhost-bound surface:
  - `GET  /api/extension/ping` → `{version, features}` (drives the §7.4 status dot)
  - `POST /api/extension/dup-check` (§7.6)
  - `POST /api/extension/ingest` (§7.7)
  - `POST /api/extension/similar` (§7.8)
- Pairing: the app shows a one-time token in its settings ("Browser Extension" section); user pastes it into the §7.4 options page. Token sent as `Authorization: Bearer`. CORS restricted to the extension origin (`chrome-extension://<id>`, `moz-extension://…`).
- Documented via the existing drf-spectacular OpenAPI setup (§4.5).
- Failure mode: bridge unreachable → features degrade gracefully (context items disabled with tooltip "Image Toolkit is not running").

**Phase B — Native Messaging (hardening, later):**
- `com.imagetoolkit.bridge` native host (thin Python script reusing the same handlers) + per-browser host manifests installed by the app (`~/.mozilla/native-messaging-hosts/`, `~/.config/google-chrome/NativeMessagingHosts/`, Edge/Brave equivalents — Brave reads the Chrome location).
- Advantages once done: no open port, no token UX, browser-mediated authentication; can launch the backend on demand.
- The §7.2 message contract is transport-agnostic so background code switches transports behind one interface.

**Effort:** Phase A ~3d, Phase B ~1w · **Impact:** Very High (unlocks §7.6–§7.8)

---

## 7.6 In-Browser Duplicate Search

*The headline integration feature: "have I already downloaded this image?"*

**Pain point:** Users re-download images they already have. The app has `PhashDeduplicator` (§4.6) but it is unreachable from the browser, where the decision happens.

**Approach (selected):**
- **App side:** user configures a **duplicate-search root directory** in the desktop app's settings (persisted app-side, shown read-only in the extension options). `POST /api/extension/dup-check` accepts `{url}` or `{data_b64}`; the handler:
  1. Fetches the image bytes (server-side fetch avoids CORS/auth cookies issues for most cases; falls back to extension-supplied bytes for login-gated content).
  2. Computes pHash via `compute_phash()`.
  3. Searches the configured root **and its subdirectories**: first against the PostgreSQL phash index (`find_near_duplicates_by_phash`, Hamming threshold ≤ 8) for already-indexed dirs; falls back to an on-demand `PhashDeduplicator.index_directory()` scan (C++ `base.scan_files` + thumbnail decode make cold scans fast; results cached/indexed for next time).
  4. Returns `{matches: [{path, hamming, width, height, thumb_b64}], scanned: n, cold_scan: bool}`.
- **Extension side:** context-menu item **"Check if already downloaded"** on images → badge/notification with result; popup shows match list with thumbnails, path copy button, and (later) "Reveal in Image Toolkit". Optional **auto-check mode**: turbo-mode downloads first call dup-check and skip/warn on hit (configurable: *warn* / *skip* / *save anyway*).
- Exact-duplicate fast path: SHA-256 of bytes compared against an app-side content-hash index before pHash.

**Effort:** ~4d (after §7.5A) · **Impact:** Very High (differentiator; no store extension can do local-library dedup)

---

## 7.7 Send to Image Toolkit

**Pain point:** Downloads land as bare files in `Downloads/<folder>` with no provenance; the app later has no source URL, page context, or tags, and the vector index only learns about files when a directory is rescanned.

**Approach (selected):**
- Context-menu **"Send to Image Toolkit"** → `POST /api/extension/ingest` with `{url | data_b64, source_page_url, page_title, alt_text, target_collection?}`.
- App saves into its managed library location (or the mapped folder), writes provenance to the DB (source URL, page title, capture timestamp), computes pHash + embedding, and indexes into vector search immediately.
- Dup-check (§7.6) runs implicitly before ingest; duplicate hits return `409 {existing_path}` so the extension can tell the user it's already in the library.
- Later: collection picker submenu fed from `GET /api/extension/collections`.

**Effort:** ~3d (after §7.6) · **Impact:** High

---

## 7.8 Visual Similarity Search from Browser

**Pain point:** "Do I have images *like* this?" — near-duplicates with different crops/resolutions and stylistically similar images are invisible to pHash.

**Approach (selected):**
- Context-menu **"Find similar in my library"** → `POST /api/extension/similar` `{url | data_b64, top_k=12}`.
- App embeds the query image (BGE-M3 visual / CLIP per §5.1 semantic-search infrastructure) and queries Qdrant/pgvector; returns ranked `{path, score, thumb_b64}`.
- Results rendered in an extension popup grid (reuses §7.6 result UI); clicking a result can open the app's gallery at that image (deep-link handled app-side).
- Depends on the app's embedding index covering the library (piggybacks on §5.1 OpenCLIP semantic search work; degrade to pHash-only §7.6 when no embedding index exists).

**Effort:** ~4d (after §7.6; embedding index availability gates quality) · **Impact:** High

---

## 7.9 Bulk Page Grabber

**Pain point:** Saving N images from a gallery/thread page is N right-clicks. Competing extensions (Imageye, Fatkun, Image Downloader) make page-level capture table stakes.

**Approach (selected):**
- Popup/toolbar action **"Scan this page"** → content script collects all image candidates (§7.11 extractor), including dimensions and source element info.
- Grid preview overlay (extension page, not injected UI): thumbnails with checkboxes; filters — min width/height, format (jpg/png/webp/gif), URL substring, "hide icons/tracking pixels" (< 64px default-off); select-all/none; live count + total size estimate where known.
- Batch download through the existing background downloader into the active folder profile (§7.10 rules apply); per-item dup-check badges when the bridge is up (§7.6 integration: "3 of 41 already in library").
- Progress UI with per-file status; failed items retryable.

**Effort:** ~1w · **Impact:** High

---

## 7.10 Per-Site Folder Rules, Filename Templating & Metadata Sidecar

**Pain point:** One global `targetFolder` for every site; filenames are whatever the URL had; provenance is lost for plain downloads (when not using §7.7 ingest).

**Approach (selected):**
- **Folder profiles:** named profiles (e.g. "wallpapers", "refs"), quick-switchable from the popup and a context-menu submenu ("Save to ▸ wallpapers / refs / …").
- **Site rules table** (§7.4 editor): ordered `domain-pattern → profile` rules (`*.pixiv.net → art`, first match wins); fallback to active profile.
- **Filename templating:** `{site}`, `{page_title}`, `{alt}`, `{date}`, `{seq}`, `{name}`, `{ext}` tokens, e.g. `{site}/{date}_{name}.{ext}` (subfolders allowed — `downloads.download` supports relative paths). Sanitisation preserved from current `options.js`.
- **Metadata sidecar (optional toggle):** for plain downloads, also emit `<filename>.json` `{source_url, page_url, page_title, alt, saved_at}` via a second `downloads.download` of a data: URL. The app's scanner can ingest sidecars to backfill provenance — bridging the gap for users who don't run the §7.5 bridge.

**Effort:** ~4d · **Impact:** High (most-requested QoL category for this class of extension)

---

## 7.11 Full-Resolution Extraction

**Pain point:** `img.src` is often a thumbnail: `srcset`/`<picture>` variants, lazy-load attributes (`data-src`, `data-original`), CSS `background-image`, and `<canvas>` renders are all missed; sites like Twitter/Pixiv serve downscaled defaults.

**Approach (selected):**
- Shared extractor in `content.ts` used by turbo mode, context menu (via `info.srcUrl` correlation), and the §7.9 grabber:
  - Parse `srcset`/`sizes` and `<picture><source>` to pick the largest candidate by descriptor.
  - Check lazy-load attributes (`data-src`, `data-original`, `data-lazy-src`, common gallery attrs) when present and larger.
  - Resolve CSS `background-image: url(...)` on the hit-tested element chain (extends the existing `elementsFromPoint` walk, which already handles overlay layers).
  - `<canvas>` fallback: `toDataURL()` capture (subject to taint), routed through the message channel as `data_b64`.
  - Optional per-site URL upgrades table (e.g. strip `/thumb/`, `name=small` → `name=orig`) maintained as data, not code.
- Picker returns `{best_url, width?, height?, origin_element}` so the UI can show "1200×1600 (upgraded from 300×400)".

**Effort:** ~4d · **Impact:** High (quality of every saved image; core to the toolkit's purpose)

---

## 7.12 Turbo Mode Polish

**Pain point:** Turbo mode gives no feedback (was the click captured? downloaded?), is all-or-nothing (global toggle intercepts every left-click on every site), and its event blocking can break sites.

**Approach (selected):**
- **Capture feedback:** brief outline flash + ✓ overlay on the captured `IMG`; badge counter on the toolbar icon; failure toast when the download errors.
- **Modifier-key mode:** alternative to the global toggle — hold a configurable modifier (default Alt) + click to capture without enabling interception globally; pointer cursor changes while held.
- **Per-site enable list:** turbo active only on allowlisted domains (or "everywhere except denylist"), managed in §7.4 and via a popup "enable on this site" toggle.
- **Download history panel:** last N captures (URL, filename, status, dup-check result) in the popup with re-download and "open folder" actions; backed by `storage.session`/`storage.local` ring buffer.
- Uses the §7.11 extractor so turbo captures full-res candidates instead of `img.src`.

**Effort:** ~3d · **Impact:** Medium-High (turbo is the extension's signature interaction; make it trustworthy)

---

## Phasing & Dependency Graph

**Phase E1 — Build & Language Foundation (~1w):** §7.1 webpack multi-manifest → §7.2 TypeScript → §7.3 unified MV3 → §7.4 options redesign.
**Phase E2 — App Bridge & Duplicate Search (~1.5w):** §7.5A HTTP bridge → §7.6 duplicate search → §7.7 send-to-app.
**Phase E3 — Capture Excellence (~2w):** §7.11 full-res extractor → §7.9 bulk grabber → §7.10 rules/templating/sidecar → §7.12 turbo polish.
**Phase E4 — Deep Integration (later):** §7.8 similarity search (needs §5.1 embedding index) → §7.5B native messaging.

```mermaid
flowchart TD
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef integration fill:#9d174d,color:#fff
    classDef planned     stroke:#64748b,stroke-width:2px

    E1["§7.1 Webpack multi-manifest\n(chrome/firefox/edge/brave)"]:::infra:::planned
    E2["§7.2 TypeScript + shared core"]:::infra:::planned
    E3["§7.3 Unified MV3"]:::infra:::planned
    E4["§7.4 Options redesign"]:::augment:::planned
    E5A["§7.5A HTTP app bridge"]:::integration:::planned
    E5B["§7.5B Native messaging host"]:::integration:::planned
    E6["§7.6 Duplicate search"]:::integration:::planned
    E7["§7.7 Send to Image Toolkit"]:::integration:::planned
    E8["§7.8 Similarity search"]:::integration:::planned
    E9["§7.9 Bulk page grabber"]:::feature:::planned
    E10["§7.10 Site rules + templating\n+ metadata sidecar"]:::feature:::planned
    E11["§7.11 Full-res extraction"]:::feature:::planned
    E12["§7.12 Turbo polish"]:::augment:::planned

    E1 ==> E2 ==> E4
    E1 --> E3
    E2 ==> E5A ==> E6 ==> E7
    E6 --> E8
    E5A -.-> E5B
    E2 --> E11 --> E9
    E4 --> E10
    E11 --> E12
    E6 --- E9
```

## Effort × Impact Matrix

| **Effort ↓ / Impact →** | Medium | High | Very High |
|---|---|---|---|
| **Low–Medium (1–3d)** | §7.3 unified MV3 · §7.4 options redesign | §7.1 webpack builds · §7.2 TypeScript · §7.7 send-to-app · §7.12 turbo polish | §7.5A HTTP bridge |
| **Medium–High (4d–1w)** | — | §7.9 bulk grabber · §7.10 rules/templating · §7.11 full-res extraction · §7.8 similarity search | §7.6 duplicate search |
| **High (1w+)** | §7.5B native messaging | — | — |
