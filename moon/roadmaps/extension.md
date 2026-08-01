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
- [7.13 Duplicate Tab Highlighter](#713-duplicate-tab-highlighter)
- [7.14 App-Powered CV Operations](#714-app-powered-cv-operations)
- [7.15 Media Capture Suite](#715-media-capture-suite)
- [7.16 Image Analysis Utilities](#716-image-analysis-utilities)
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

**Status: ✅ Shipped (S208, 2026-07-04).** `extension/webpack/` builds all four targets; the three hand-written manifests were deleted; `just build-extension` added.

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

**Status: ✅ Shipped (S208, 2026-07-04).** `extension/src/` TS sources with `shared/{api,settings,messages}.ts`; strict mode; `npm run typecheck` clean.

**Pain point:** The `typeof browser !== 'undefined'` adapter and the Promise/callback storage shim are copy-pasted in all three JS files; no types, no shared constants; message payloads are stringly-typed.

**Approach (selected):**
- Move `background/content/options` to TypeScript under `extension/src/`, compiled by the §7.1 webpack setup (`ts-loader`, `@types/webextension-polyfill`).
- `shared/api.ts` — single browser-API adapter (or adopt `webextension-polyfill` so everything is Promise-based on Chrome too).
- `shared/messages.ts` — discriminated-union message types (`DownloadImage`, `DupCheckRequest`, `DupCheckResult`, `IngestImage`, …) shared by background/content/options — this becomes the contract §7.5–§7.8 build on.
- `shared/settings.ts` — typed `storage.local` schema with defaults (`targetFolder`, `turboMode`, per-site rules from §7.10, bridge URL from §7.5).

**Effort:** ~2d · **Impact:** Medium-High (correctness + velocity for the feature work below)

---

## 7.3 Unified Manifest V3

**Status: ✅ Shipped (S208, 2026-07-04).** MV3 everywhere; Firefox overlay swaps `service_worker` for event-page `scripts` + gecko id (min 115).

**Pain point:** Firefox manifest is MV2 (`background.scripts`, `browser_action`) while Chrome is MV3; behaviour and permissions diverge.

**Approach (selected):** Target MV3 everywhere. Firefox 109+ supports MV3; the remaining differences are captured in the §7.1 overlays:
- Firefox MV3 uses `background.scripts` (event page) instead of `service_worker` — expressed in `manifest.firefox.json` overlay only.
- `host_permissions` unified; `browser_specific_settings.gecko` kept in the Firefox overlay with a real add-on ID (replace `save-to-folder@example.com`).
- Verify `storage.onChanged`, `contextMenus`, `downloads` parity under Firefox MV3; add `optional_host_permissions` where Firefox requires opt-in.

**Effort:** ~1d (folded into §7.1 overlays) · **Impact:** Medium (one API surface, MV2 EOL-proof)

---

## 7.4 Options Page Redesign

**Status: 🔄 Core shipped (S208, 2026-07-04).** Sectioned page (General / Site Rules / Connection / Duplicate Tabs) with template + sidecar + bridge URL/token fields. Remaining: separate slim popup vs full tab split, profile switcher.

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

**Phase A — Local HTTP API (MVP): ✅ Shipped (S208, 2026-07-04)** — `extension_api/` Django app: `GET ping/` + `POST dup-check/`, Bearer-token auth (auto-generated `~/.image-toolkit/extension-bridge/token.txt`), CORS with preflight pass-through, `DirPhashIndex` SQLite-cached phash search (no PostgreSQL needed). `/ingest` and `/similar` remain planned. Original plan:
- New Django app `api/extension/` exposing a small, token-authenticated, localhost-bound surface:
  - `GET  /api/extension/ping` → `{version, features}` (drives the §7.4 status dot)
  - `POST /api/extension/dup-check` (§7.6)
  - `POST /api/extension/ingest` (§7.7)
  - `POST /api/extension/similar` (§7.8)
- Pairing: the app shows a one-time token in its settings ("Browser Extension" section); user pastes it into the §7.4 options page. Token sent as `Authorization: Bearer`. CORS restricted to the extension origin (`chrome-extension://<id>`, `moz-extension://…`).
- Documented via the existing drf-spectacular OpenAPI setup (§4.5).
- Failure mode: bridge unreachable → features degrade gracefully (context items disabled with tooltip "Image Toolkit is not running").

**Phase B — Native Messaging: ✅ Shipped (2026-07-27, issue #50).**
- **Extracted shared handler logic** first: `extension_api/bridge_handlers.py` — transport-agnostic `handle_ping`/`handle_dup_check`/`handle_ingest`/`handle_similar`, each a plain `(payload: dict) -> (status_code, body_dict)` function with no DRF/HTTP dependency. `views.py`'s `PingView`/`DupCheckView`/`IngestView`/`SimilarView` became thin wrappers (bearer-token auth + CORS + DRF `Response` framing only) calling the same functions §7.5A already shipped — not a rewrite, a refactor verified byte-for-byte behavior-preserving against all 23 pre-existing `extension_api/tests.py` cases (still pass unmodified).
- **`extension_api/native_host.py`**: implements the Chrome/Firefox native-messaging wire protocol (4-byte native-order length prefix + UTF-8 JSON, both directions) in a `read_message`/`write_message`/`dispatch` loop over stdin/stdout. Dispatches `{"action": "ping"|"dup_check"|"ingest"|"similar", "payload": {...}}` to the same `bridge_handlers.HANDLERS` the HTTP views use, returning `{"ok": bool, "status": int, "body": {...}}` (status mirrors the HTTP code the same request would get over §7.5A, so client code can share result-handling across transports). Deliberately doesn't call `django.setup()` — `bridge_handlers`/`bridge_config`/`DirPhashIndex` have no Django ORM dependency, so the host starts fast without a settings module, which matters since browsers launch native hosts fresh per connection.
- **No token needed on this transport**, per the original plan: only extension IDs listed in the host's installed manifest (`allowed_origins` on Chromium, `allowed_extensions` on Firefox) may ever launch the process — the browser itself is the security boundary.
- **`desktop/linux/scripts/install_native_host.sh <extension-id> [browser...]`**: writes a `run_native_host.sh` launcher (activates `.venv`, execs `python -m extension_api.native_host`) plus per-browser host manifest JSON at the documented install locations (autodetects installed browsers from their config dirs if none specified; Brave correctly reads the Chrome location, matching the original plan's note).
- **Extension side — one interface, two transports**: `shared/api.ts` gained `sendNativeMessage()` (mirrors the existing `storageGet`/`storageSet` Firefox-Promise-vs-Chrome-callback pattern). `shared/bridge.ts`'s exported functions (`ping`/`dupCheck`/`ingest`/`findSimilar`) now dispatch on `settings.bridgeTransport` ("http" default | "native") via one internal `bridgeCall()` — callers never branch on transport, exactly per the original plan. New `ExtensionSettings.bridgeTransport`/`nativeHostName` fields (default `"http"`/`"com.imagetoolkit.bridge"`, fully backward compatible). Options page gained a transport `<select>` + native host name field with an inline install-command hint.
- `manifest.base.json` gained the `nativeMessaging` permission.
- **Tests**: `extension_api/test_native_host.py` (new) — 10 cases covering wire-protocol framing round-trips/truncation and `dispatch()` routing (unknown action, successful ping/dup-check reusing the real shared handlers via the existing `BridgeTestCase` isolated-bridge-dir fixture, handler-exception → 500 not a crash). All 33 `extension_api` tests pass (`python manage.py test extension_api`). Extension side: `npm run typecheck` clean for all touched files (two pre-existing, unrelated type errors in `storageGet`/`dupTabs.ts` remain — not introduced by this change, not this issue's scope).
- **Not verified end-to-end against a real browser** (no browser automation available in this environment) — the wire protocol and dispatch logic are unit-tested against the real shared handlers, but installing a manifest and actually launching the host from a loaded extension needs a human with a browser to confirm.

**Effort:** Phase A ~3d, Phase B ~1w (spent ~1 session) · **Impact:** Very High (unlocks §7.6–§7.8)

---

## 7.6 In-Browser Duplicate Search

*The headline integration feature: "have I already downloaded this image?"*

**Status: ✅ Core shipped (S208, 2026-07-04).** Context item → bridge dup-check → notification + popup match list with thumbnails; connection test in options. Verified end-to-end against a live server. Remaining: SHA-256 exact fast path, auto-check on turbo downloads (warn/skip modes).

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

**Status: ✅ Core shipped (S208, 2026-07-04).** `POST /api/extension/ingest/` saves into `ingest_dir` (fallback `dup_root/inbox`) with provenance JSON sidecar, uniquified names, implicit dup-check (409 with existing paths, `force` override); "Send to Image Toolkit" context item + notifications. Remaining: embedding/DB indexing at ingest, collection picker.

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

**Status: ✅ Shipped, pHash-degraded path (2026-07-27, issue #51).** Context-menu **"Find similar in my library"** → `POST /api/extension/similar/` `{url|data_b64, top_k=12}` → `SimilarView` (`extension_api/views.py`) ranks the configured directory tree by perceptual-hash Hamming distance (`DirPhashIndex.query_topk`/`query_topk_bytes`, `backend/src/core/dir_phash_index.py`) and returns ranked `{path, score, hamming, width, height, thumb_b64}` (`score` = `1 - hamming/64`). Results render in the extension options popup (`similar-results` panel, `extension/src/options/options.ts`), reusing the §7.6 duplicate-check row renderer (`renderThumbResults`, generalized to take both features' item shapes + a `labelFor` callback) rather than a new grid. `bridge.ts::findSimilar()` is the client; `background.ts::runSimilar()` wires the context-menu action and stores `lastSimilar` for the popup.

**Why pHash and not the embedding path described below:** verified before implementing that the Unified DB roadmap's [DB.7 Semantic Search & CBIR](unified_database.md#db7-semantic-search--cbir) — the phase that would populate `embeddings` with real MetaCLIP/BGE-M3 vectors and add a "find similar" action app-side — carries no shipped marker (unlike DB.1–DB.4) and is still listed `:::planned` in that roadmap's dependency graph. The C++ `base.database` cosine-`knn` primitive exists and is unit-tested, but nothing outside its own test calls it — no embedding worker fills the `embeddings` table for any real image. The standalone `Recommendation-Engine` submodule's BGE-M3/SQLite store is a different domain (media listings/entities) and isn't wired to the image library either. Per this section's own explicit fallback clause, the pHash-only degraded path was implemented instead — not a shortfall, the sanctioned outcome when the embedding index isn't ready. The response shape (`path, score, thumb_b64`, plus `method` discriminator) is designed so a future embedding-based `SimilarView` body swap doesn't require client changes.

**Original approach (kept for when §DB.7 ships):**
- App embeds the query image (BGE-M3 visual / CLIP per §5.1 semantic-search infrastructure) and queries the Unified DB embedding index; returns ranked `{path, score, thumb_b64}` with `method: "embedding"`.
- Clicking a result can open the app's gallery at that image (deep-link handled app-side) — not yet implemented on either path.

**Effort:** ~4d (after §7.6; embedding index availability gates quality) · **Impact:** High

---

## 7.9 Bulk Page Grabber

**Pain point:** Saving N images from a gallery/thread page is N right-clicks. Competing extensions (Imageye, Fatkun, Image Downloader) make page-level capture table stakes.

**Status: 🔄 Modes A+B shipped (S208, 2026-07-04).** Popup "⬇ Download all media" + "🖱 Select images…" buttons; `shared/pageMedia.ts` collection (images via §7.11 extractor, ≥64px filter, video src/source, blob: skipped); `contentOverlay.ts` click-to-select overlay with floating bar + Esc; batch download via `download_batch` message (§7.10 rules apply). Grid-preview page with filters + dup badges remains planned.

**Approach (selected — two capture modes, per user direction 2026-07-04):**
- **A — One-click "Download all"**: popup/toolbar button → content script collects **all images and videos** on the page (§7.11 extractor for full-res image candidates; `<video src>` / `<video><source>` for videos), dedupes by URL, filters out tiny icons (< 64px rendered, configurable), and batch-downloads through the existing background downloader (§7.10 folder rules + templating apply). Completion notification with count.
- **B — In-page selection overlay**: popup button "Select images on page…" → content script enters overlay mode: page dims slightly, images highlight on hover, **click toggles selection** (colored outline + count badge); a floating action bar (top-center, max z-index) shows the live selection count with **Download selected** / **Cancel** buttons; Esc cancels. Selected items download via mode A's path. Overlay leaves site DOM/styles untouched apart from the injected root node.
- Later (kept planned): grid-preview page with size/format/URL filters and per-item dup-check badges (§7.6 integration: "3 of 41 already in library"); progress UI with per-file status and retry.

**Effort:** ~3d (A+B) + ~3d (grid/filters) · **Impact:** High

---

## 7.10 Per-Site Folder Rules, Filename Templating & Metadata Sidecar

**Status: ✅ Shipped (S208 core 2026-07-04; folder profiles 2026-08-01, issue #103).** `shared/naming.ts`: wildcard hostname rules (first match wins), `{name}/{ext}/{site}/{date}/{time}` template with subfolders, JSON provenance sidecar toggle.

**Folder profiles + quick-switch, shipped:** `ExtensionSettings.folderProfiles: string[]` (new, default `["data"]`) — a named list of target folders managed in a new "Folder Profiles" options section (`options.html`/`options.ts`), each row with an "Activate" button that immediately sets `targetFolder` to that profile (no separate "Save Settings" click needed for the quick-switch case) and a remove button. The same list doubles as the context-menu's "Save to profile ▸" submenu (`background.ts`, `SAVE_PROFILE_MENU_ID`, only rendered once ≥2 profiles exist) — picking one downloads *that* image into the chosen folder via a new `downloadImage(..., overrideFolder?)` parameter that bypasses site-rule resolution for a one-off save without touching the active default. The submenu rebuilds live via `api.storage.onChanged` on `folderProfiles` changes, so editing the list in options doesn't need an extension reload. Site rules already mapped `domain-pattern → folder` directly (`resolveFolder()`, pre-existing) with a fallback to `targetFolder` — since `targetFolder` *is* the active profile now, "fallback to active profile" was already the existing behavior once profiles and `targetFolder` were unified rather than adding a separate indirection layer.

Verified via `npm run typecheck` (clean) and `npm run build:chrome` (compiles). No test framework is configured for this package (no jest/vitest in `package.json`) — verification is typecheck + build, matching how `§7.1`–`§7.9` were verified.

**Pain point:** One global `targetFolder` for every site; filenames are whatever the URL had; provenance is lost for plain downloads (when not using §7.7 ingest).

**Approach (selected):**
- **Folder profiles:** named profiles (e.g. "wallpapers", "refs"), quick-switchable from the popup and a context-menu submenu ("Save to ▸ wallpapers / refs / …").
- **Site rules table** (§7.4 editor): ordered `domain-pattern → profile` rules (`*.pixiv.net → art`, first match wins); fallback to active profile.
- **Filename templating:** `{site}`, `{page_title}`, `{alt}`, `{date}`, `{seq}`, `{name}`, `{ext}` tokens, e.g. `{site}/{date}_{name}.{ext}` (subfolders allowed — `downloads.download` supports relative paths). Sanitisation preserved from current `options.js`.
- **Metadata sidecar (optional toggle):** for plain downloads, also emit `<filename>.json` `{source_url, page_url, page_title, alt, saved_at}` via a second `downloads.download` of a data: URL. The app's scanner can ingest sidecars to backfill provenance — bridging the gap for users who don't run the §7.5 bridge.

**Effort:** ~4d · **Impact:** High (most-requested QoL category for this class of extension)

---

## 7.11 Full-Resolution Extraction

**Status: 🔄 Core shipped (S208, 2026-07-04).** `shared/extractor.ts`: srcset/`<picture>` scoring, lazy-load attrs, CSS background fallback; wired into turbo mode. Remaining: per-site URL upgrade table, canvas `toDataURL` fallback, context-menu correlation.

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

**Status: 🔄 Partial (S208, 2026-07-04).** Capture outline-flash feedback shipped. Remaining: badge counter, modifier-key mode, per-site enable list, history panel.

**Pain point:** Turbo mode gives no feedback (was the click captured? downloaded?), is all-or-nothing (global toggle intercepts every left-click on every site), and its event blocking can break sites.

**Approach (selected):**
- **Capture feedback:** brief outline flash + ✓ overlay on the captured `IMG`; badge counter on the toolbar icon; failure toast when the download errors.
- **Modifier-key mode:** alternative to the global toggle — hold a configurable modifier (default Alt) + click to capture without enabling interception globally; pointer cursor changes while held.
- **Per-site enable list:** turbo active only on allowlisted domains (or "everywhere except denylist"), managed in §7.4 and via a popup "enable on this site" toggle.
- **Download history panel:** last N captures (URL, filename, status, dup-check result) in the popup with re-download and "open folder" actions; backed by `storage.session`/`storage.local` ring buffer.
- Uses the §7.11 extractor so turbo captures full-res candidates instead of `img.src`.

**Effort:** ~3d · **Impact:** Medium-High (turbo is the extension's signature interaction; make it trustworthy)

---

## 7.13 Duplicate Tab Highlighter

**Status: ✅ Shipped (S208, 2026-07-04).** `shared/dupTabs.ts` + popup UI; colored `dup ×N` tab groups on Chromium (clear only dissolves our own groups), badge + popup set list everywhere; keep-first/close-rest wired.

**Pain point:** Long browsing/collection sessions accumulate dozens of tabs; the same gallery page or image URL often ends up open in several tabs of the same window, wasting memory and causing double-downloads. Nothing surfaces which tabs are duplicates.

**Approach (selected):**
- **Scan:** popup/toolbar action **"Scan tabs for duplicates"** (plus optional auto-scan on `tabs.onUpdated`/`onCreated`, default off). `tabs.query({currentWindow: true})`, group by **normalized URL** — strip `#fragment` always; strip common tracking params (`utm_*`, `fbclid`, `gclid`, …) optionally (configurable); protocol/host case-folded. Groups with ≥ 2 tabs are duplicates.
- **Highlight (Chromium — chrome/edge/brave):** move each duplicate set into a **colored tab group** via `chrome.tabs.group()` + `chrome.tabGroups.update(groupId, {color, title: "dup ×N"})` — cycling through distinct colors per set; this is the strongest native visual signal available. "Clear highlights" ungroups (`chrome.tabs.ungroup`).
- **Highlight (Firefox):** no `tabGroups` API — fallback: badge shows total duplicate count; popup lists duplicate sets (favicon + title + URL) with per-tab *switch-to* / *close* buttons and a per-set *close others* action; duplicates are additionally marked by `tabs.highlight` multi-selection when the user hovers a set in the popup.
- **Actions:** per-set "Keep first, close rest"; "close all duplicates" button with count preview; never auto-closes without explicit click.
- **Permissions:** `tabs` (and `tabGroups` on Chromium) added via the §7.1 per-browser manifest overlays — a concrete first payoff of the overlay architecture.
- **Implementation home:** background service worker owns scan/group state (`shared/dupTabs.ts`); popup renders results via the §7.2 typed message contract.

**Effort:** ~2d · **Impact:** Medium-High (immediate daily QoL; zero app-bridge dependency)

---

## 7.14 App-Powered CV Operations

*Right-click an image → the desktop app's ML stack processes it → result saved or returned to the browser. All items ride the §7.5 bridge and reuse models the app already ships.*

**Pain point:** The app's CV capabilities (BiRefNet, Real-ESRGAN, WD14) are only reachable after a manual download → open-app → find-file → process loop.

**Approach (selected):**
- **A — Background removal:** context item **"Remove background"** → `POST /api/extension/cv/bg-remove` `{url|data_b64}` → app runs BiRefNet (`birefnet_wrapper.py`), returns/saves transparent PNG (`<name>_nobg.png`) into the active folder profile. Long-running: job-id + polling (or SSE) using the app's existing task queue; extension shows a progress badge and notification on completion.
- **B — Upscale before save:** context item **"Upscale & save"** → `POST /api/extension/cv/upscale` `{url|data_b64, scale: 2|4}` → Real-ESRGAN (anime_6B, shared upscaler module CG.2); auto-suggested when the §7.11 extractor reports the best candidate is small (< configurable threshold, e.g. 600px).
- **C — Auto-tag on save:** §7.7 ingest gains `auto_tag: bool` — WD14 (`wd_tagger_wrapper.py`, §4.4) tags computed server-side at ingest; tags stored in DB + optional sidecar; threshold + review-queue semantics reuse `tag_with_review()`.
- **D — OCR extraction + translation:** context item **"Extract text"** → `POST /api/extension/cv/ocr` `{url|data_b64, translate_to?: str}`; app runs OCR (manga-ocr for anime-style text, tesseract otherwise — new small app-side capability) and optional translation (local model, e.g. argos-translate/NLLB via the app; explicit non-cloud default). Result shown in a copyable popup panel with per-block layout; "copy all" + "save as .txt sidecar" actions.

**Effort:** A ~2d · B ~1d · C ~1d · D ~4d (OCR+translate is a new app capability) · **Impact:** High (turns the extension into a remote control for the app's ML)

---

## 7.15 Media Capture Suite

*Extends capture beyond static `<img>` elements to video, animations, and multi-image sequences.*

**Pain point:** Video frames, GIF frames, webtoon strips, and clips are un-capturable today; these are exactly the media types the app's extractor and Anime Stitch Pipeline consume.

**Approach (selected):**
- **A — Video frame grabber: 🔄 Core shipped (S208, 2026-07-04)** — `videoCapture.ts`: "Capture video frame" / "Capture 5-frame burst" context items, native-res canvas grab of the right-clicked video (context-target tracking, srcUrl fallback), suggestedName download path, clear CORS/DRM-taint error with partial-burst reporting. Remaining: configurable burst size/interval, paused-video seek-clone bursts. Original plan: context item on `<video>` **"Capture frame"** — draw current frame to canvas at `videoWidth×videoHeight` (native res), save as PNG; **burst mode** captures N frames at a configurable interval/step (seeking a cloned muted `<video>` when possible to avoid disturbing playback) and downloads as a numbered sequence — drag-ready input for the app's extractor/ASP tabs. DRM/cross-origin-tainted video degrades gracefully with a clear error toast.
- **B — GIF/animation frame extractor:** context item **"Extract frames…"** on GIF/APNG/animated-WebP → decode in an extension page (`ImageDecoder` WebCodecs API where available; `omggif`/`upng` fallbacks) → frame grid preview with scrubber → save selected/all frames or send-to-app.
- **C — Webtoon capture → ASP stitch:** on long vertical comic pages, **"Capture strip → stitch"** collects the ordered image sequence (§7.11 extractor, same container/class heuristics), sends the list to `POST /api/extension/stitch` → app runs the Anime Stitch Pipeline (or simple vertical concat for trivially-aligned strips) → returns one seamless long image saved to the library. The flagship crossover feature — no other extension can do this.
- **D — Video clip → GIF/WebP:** popup action **"Record clip"** → `MediaRecorder` on `captureStream()` of the target `<video>` for a user-set duration (≤ 30s) → WebM; optional app-side conversion to GIF/WebP via the bridge (ffmpeg already in the app stack) with palette optimization.
- **E — Video downloader with range finder:** context item **"Download video…"** on `<video>` → panel showing the source list (direct `src`, `<source>` variants, and network-sniffed media URLs via `webRequest` where permitted) + a **time-range slider** (start/end thumbnails scrubbed from the video): *full video* downloads directly; *selected range* is cut app-side via the bridge (`ffmpeg -ss … -to … -c copy` for stream-copy speed) or `MediaRecorder` re-capture fallback without the bridge. HLS/DASH streams: detect manifest and delegate segment download+mux to the app (yt-dlp/ffmpeg integration app-side); DRM content excluded.

**Effort:** A ~2d · B ~3d · C ~4d (app endpoint + sequence heuristics) · D ~3d · E ~1w (network sniffing + app-side cutting/muxing) · **Impact:** Very High (C and E are differentiators; A/B feed the app's core pipelines)

---

## 7.16 Image Analysis Utilities

**Pain point:** No way to inspect what an image *is* (metadata, provenance, generation parameters) or whether/where it exists elsewhere, before deciding to save it.

**Approach (selected):**
- **A — AI-metadata / EXIF inspector: ✅ Shipped (S208, 2026-07-04)** — `shared/imageMeta.ts` (PNG tEXt/iTXt/zTXt with DecompressionStream inflate, JPEG SOF/COM/XMP + compact EXIF IFD0 reader, a1111/ComfyUI/NovelAI/InvokeAI detection) + `inspect.html` popup window opened from the "Inspect image metadata" context item; sidecar-save action still planned. Original plan: context item **"Inspect image"** → panel with EXIF/XMP/ICC basics plus **embedded AI-generation metadata**: a1111 `parameters` PNG text chunk, ComfyUI `workflow`/`prompt` JSON chunks, NovelAI/InvokeAI variants — prompt, negative prompt, model/LoRA, sampler, seed rendered in a readable card with copy buttons; "save metadata as sidecar" action. Parsing is pure client-side TS (PNG chunk + JPEG APP1 readers), no bridge needed.
- **B — Reverse-search shortcuts: ✅ Shipped (S208, 2026-07-04)** — "Search image on ▸" submenu (SauceNAO/trace.moe/Lens/IQDB/TinEye) in `background.ts`; custom URL templates in options still planned. Original plan: context submenu **"Search image on ▸"** SauceNAO / trace.moe / Google Lens / IQDB / TinEye (configurable set + custom URL templates in options); opens `service_url + encodeURIComponent(image_url)` in a background tab; data-URL images uploaded via the service's POST form where supported.
- **C — Client-side pHash pre-check: ✅ Shipped (2026-07-27, issue #54).** `extension/src/shared/clientPhash.ts` — a faithful TypeScript port of the server's exact algorithm (`imagehash.phash`: grayscale via PIL's ITU-R 601-2 luma formula, resize to 32×32, separable 2D DCT-II, top-left 8×8 low-freq block, median threshold), not a different dHash. `GET /api/extension/phash-snapshot` (`PhashSnapshotView`/`handle_phash_snapshot`, new `DirPhashIndex.export_hashes()`) exports a **sorted hex hash list**, not a bloom filter — a bloom filter only answers exact-membership queries, which would silently drop the near-duplicate tolerance perceptual hashing exists to provide, so it was rejected as a design choice rather than an oversight. Cached in `storage.local`, refreshed via a manual "Refresh snapshot" button in the options page (§7.16C's own "periodically" framing — an automatic/alarm-based refresh is a natural small follow-on, not done here). Deliberately excludes file paths from the exported snapshot (verified by test) since only the hash values are needed for the sweep. **Verified**: the DCT-II port produces output numerically identical (4+ decimal places) to `scipy.fftpack.dct` on a fixed test matrix — the exact math is confirmed correct, decoupled from the one remaining honest caveat: canvas's `drawImage` resampling isn't guaranteed bit-identical to PIL's `ANTIALIAS`/Lanczos resize, so a client-computed hash for the same image the server hashed may differ by a few bits rather than exactly zero — compensated with a slightly looser hint threshold (12 vs the server's own 10) and documented in the module as a hint, not an authority; §7.6 dup-check remains the real check. 56 total tests (18 `DirPhashIndex` incl. 4 new export tests, 38 `extension_api` incl. 5 new snapshot-endpoint tests) passing; `npm run typecheck` clean for all new/touched files. **Not wired into turbo/bulk-mode's own capture UI** — this ships the underlying capability (hash computation + snapshot infra + a manual refresh control), not the inline hint badge those features' own remaining scope (§7.9/§7.12) would consume it from; that integration is a natural next step, not attempted here to keep this change bounded.
- **D — Local-ML reverse search: primary path already satisfied by §7.8/issue #51 ("Find similar in my library"), checked 2026-07-27.** That feature already is D's specified "primary path = app bridge similarity search" — confirmed by reading `background.ts`'s existing context-menu wiring before considering building a duplicate. The **optional fully-in-browser ML fallback** (quantized MobileCLIP/SigLIP via `transformers.js`/ONNX-Runtime-Web, ~1 week per this section's own estimate) remains entirely unbuilt — genuinely out of scope for this pass, not attempted.

**Effort:** A ~3d · B ~1d · C ~3d (done) · D ~1w (browser-side model + snapshot infra; primary path already done via #51, only the in-browser fallback remains) · **Impact:** High (A/B inform the save decision; C/D extend dedup/similarity to offline)

---

## Phasing & Dependency Graph

**Phase E1 — Build & Language Foundation (~1w):** §7.1 webpack multi-manifest → §7.2 TypeScript → §7.3 unified MV3 → §7.4 options redesign.
**Phase E2 — App Bridge & Duplicate Search (~1.5w):** §7.5A HTTP bridge → §7.6 duplicate search → §7.7 send-to-app.
**Phase E3 — Capture Excellence (~2w):** §7.11 full-res extractor → §7.9 bulk grabber → §7.10 rules/templating/sidecar → §7.12 turbo polish.
**Phase E4 — Deep Integration (later):** §7.8 similarity search (needs §5.1 embedding index) → §7.5B native messaging.
**Phase E5 — CV & Media Suite (parallel to E3/E4 once E2 lands):** §7.16A metadata inspector + §7.16B reverse-search shortcuts (no bridge needed) → §7.15A/B frame grabbers → §7.14A/B/C bg-remove/upscale/auto-tag → §7.15C webtoon stitch → §7.15D/E clip recorder + range downloader → §7.14D OCR+translate → §7.16C/D offline hash/embedding search.

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
    E13["§7.13 Duplicate tab highlighter"]:::feature:::planned
    E14["§7.14 CV ops\n(bg-remove/upscale/tag/OCR)"]:::integration:::planned
    E15["§7.15 Media capture\n(video/GIF/webtoon/clip/range)"]:::feature:::planned
    E16["§7.16 Analysis utils\n(AI-meta/reverse/pHash/local-ML)"]:::feature:::planned

    E1 ==> E2 ==> E4
    E2 --> E13
    E5A ==> E14
    E2 --> E15
    E5A --> E15
    E2 --> E16
    E8 --- E16
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
| **Low–Medium (1–3d)** | §7.3 unified MV3 · §7.4 options redesign · §7.13 duplicate tab highlighter · §7.16B reverse-search shortcuts | §7.1 webpack builds · §7.2 TypeScript · §7.7 send-to-app · §7.12 turbo polish · §7.14A bg-remove · §7.14B upscale · §7.14C auto-tag · §7.15A frame grabber · §7.16A AI-metadata inspector | §7.5A HTTP bridge |
| **Medium–High (4d–1w)** | §7.16C client pHash | §7.9 bulk grabber · §7.10 rules/templating · §7.11 full-res extraction · §7.8 similarity search · §7.14D OCR+translate · §7.15B GIF frames · §7.15D clip→GIF | §7.6 duplicate search · §7.15C webtoon→ASP stitch |
| **High (1w+)** | §7.5B native messaging | §7.16D local-ML reverse search | §7.15E video range downloader |
