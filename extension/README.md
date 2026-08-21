# Image-Toolkit Browser Extension

The `extension/` directory contains the Image-Toolkit companion WebExtension. It captures images and video, organizes downloads, inspects metadata, and optionally connects browser actions to the Image-Toolkit desktop application.

It is a TypeScript/Webpack Manifest V3 project with separate builds for Chrome, Brave, Edge, and Firefox.

## Functionality

- Save a right-clicked image to a selected subfolder under the browser's `Downloads/` directory.
- Use filename templates containing `{name}`, `{ext}`, `{site}`, `{date}`, and `{time}`.
- Define folder profiles and per-site wildcard rules such as `*.pixiv.net`.
- Turbo Mode: capture images by clicking them, with optional modifier-key and site allowlist/denylist controls.
- Bulk-capture page images in a filterable grid preview.
- Check for duplicates or find visually similar images in the Image-Toolkit library.
- Inspect EXIF, XMP, PNG text chunks, and common AI-generation metadata.
- Remove backgrounds and upscale images through the Image-Toolkit CV bridge.
- Extract animated GIF/APNG/WebP frames where the browser supports `ImageDecoder`.
- Capture a video frame or five-frame burst.
- Record fixed five-second WebM or animated-WebP clips.
- Open SauceNAO, trace.moe, Google Lens, IQDB, or TinEye reverse-search actions.
- Optionally save a JSON provenance sidecar next to downloads.
- Scan the current browser window for duplicate tabs.

The extension can use an HTTP bridge (default) or native messaging to communicate with Image-Toolkit. HTTP uses a local Django API and bearer token. Native messaging launches `api.extension.native_host` through a browser-installed host manifest.

## Requirements

- Node.js 20+ and npm.
- Chrome, Brave, Edge, or Firefox.
- For integration: a running Image-Toolkit backend.
- For Linux native messaging: the repository `.venv/` environment.

## Build

From the repository root:

```bash
cd extension
npm install
npm run build:chrome
npm run build:brave
npm run build:edge
npm run build:firefox
```

Build every target:

```bash
npm run build:all
```

Outputs:

```text
extension/dist/chrome/
extension/dist/brave/
extension/dist/edge/
extension/dist/firefox/
```

Each output directory is a complete unpacked extension containing its generated `manifest.json`. Do not edit `dist/`; edit the TypeScript, HTML, or manifest sources and rebuild.

Development commands:

```bash
npm run typecheck
npm run watch:chrome
npm run watch:firefox
```

Run `npm install` before typechecking so the local TypeScript compiler and browser types are available.

## Install as an unpacked extension

### Chrome

1. Run `npm run build:chrome`.
2. Open `chrome://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked** and select `extension/dist/chrome/`.
5. Click **Reload** after each rebuild.

### Brave

1. Run `npm run build:brave`.
2. Open `brave://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked** and select `extension/dist/brave/`.

### Microsoft Edge

1. Run `npm run build:edge`.
2. Open `edge://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked** and select `extension/dist/edge/`.

### Firefox

1. Run `npm run build:firefox`.
2. Open `about:debugging#/runtime/this-firefox`.
3. Click **Load Temporary Add-on…**.
4. Select `extension/dist/firefox/manifest.json`.

Firefox temporary add-ons are removed when Firefox closes. A persistent Firefox installation must be packaged and signed through the normal Firefox Add-ons process.

## Initial configuration

Open the extension options page from the browser's extension-management page or toolbar menu. Configure:

- **Target folder**: default subfolder below `Downloads/`; default is `data`.
- **Filename template**: default is `{name}.{ext}`.
- **Folder profiles**: named folders available from the popup/context menu.
- **Site rules**: wildcard hostname-to-folder mappings.
- **Turbo Mode**: direct-click capture, modifier key, and site policy.
- **Save sidecar**: writes provenance JSON beside each download.
- **Duplicate-tab parameter stripping**: ignores common tracking parameters when scanning tabs.
- **Bridge URL/token/transport**.

Default bridge settings:

```text
URL:       http://127.0.0.1:8000/api/extension
Transport: http
Host name: com.imagetoolkit.bridge
```

## Using the context menus

Right-click an image to access:

```text
Save to selected directory
Save to profile ▸ …
Check if already downloaded
Send to Image Toolkit
Find similar in my library
Inspect image metadata
Remove background
Upscale & save
Extract frames…
Search image on ▸ …
```

Right-click a video to access:

```text
Capture video frame
Capture 5-frame burst
Record 5s clip (WebM)
Record 5s clip → Animated WebP
```

Cross-origin or DRM-protected media may prevent canvas capture. The extension reports those failures and does not bypass browser/site protections.

## HTTP desktop bridge

Start the Image-Toolkit backend, then configure the extension with the bridge URL and token. Requests use:

```http
Authorization: Bearer <token>
```

Available endpoints are mounted under `/api/extension/`:

```text
GET  /ping/
POST /dup-check/
POST /ingest/
POST /similar/
GET  /phash-snapshot/
POST /cv/bg-remove/
POST /cv/upscale/
GET  /cv/status/<job-id>/
```

The bridge provides liveness, duplicate search, ingest, similarity search, pHash snapshots, background removal, and upscaling/job status. Keep this API bound to localhost unless you have explicitly secured any wider deployment.

## Native messaging on Linux

Native messaging avoids the HTTP bearer token. The browser only launches the host when its installed manifest allows the extension ID.

1. Build and load the extension.
2. Copy its ID from the browser extension page.
3. Ensure the repository has `.venv/bin/python`.
4. From the repository root, run one or more commands:

```bash
desktop/linux/scripts/install_native_host.sh <extension-id> chrome
desktop/linux/scripts/install_native_host.sh <extension-id> brave
desktop/linux/scripts/install_native_host.sh <extension-id> edge
desktop/linux/scripts/install_native_host.sh <extension-id> firefox
```

Autodetect installed browsers:

```bash
desktop/linux/scripts/install_native_host.sh <extension-id>
```

The installer creates the `com.imagetoolkit.bridge` host manifest and launcher. Brave intentionally uses Chrome's native-messaging directory. Reload the extension, then select **Native** transport and the matching host name in options.

The generated launcher expects the repository virtual environment at `.venv/`. If it is elsewhere, update the generated launcher or create the expected environment.

**Current manifest caveat:** Firefox inherits the `nativeMessaging` permission from the base manifest. The Chrome, Brave, and Edge overlays replace the permissions array without that permission, so use HTTP for those builds unless their overlays are updated.

## Source layout

```text
extension/
├── src/background.ts       Service worker and context menus
├── src/content.ts          Page capture, Turbo Mode, and media handling
├── src/gallery/            Bulk image grid
├── src/frames/             Animated-image frame extraction
├── src/inspect/            Metadata inspector
├── src/options/             Settings/options page
├── src/shared/              API, bridge, settings, naming, and messages
├── src/videoCapture.ts      Video frame/burst capture
├── src/videoClip.ts         WebM/animated-WebP recording
├── webpack/manifest/        Base manifest and browser overlays
├── webpack/webpack.*.js     Browser build configurations
├── dist/                    Generated builds; do not edit
└── package.json             Build and verification commands
```

The server-side bridge lives in `api/extension/`. Its transport-independent handlers are shared by HTTP views and the native host.

## Troubleshooting

- **No extension appears:** verify that the selected build directory contains `manifest.json`, and use the build matching the browser.
- **No context menu:** reload the extension and right-click an actual image/video element.
- **Downloads fail:** check the target folder, filename template, browser download settings, and the service-worker console.
- **Bridge unreachable:** start the backend, verify the URL ends at `/api/extension`, check the token, and use the options-page connection test.
- **Native messaging unreachable:** verify the host name, current extension ID, executable launcher, `.venv/bin/python`, and installed browser host manifest.
- **Frame extraction unavailable:** Firefox currently lacks the WebCodecs `ImageDecoder` path used by the frame extractor; use a Chromium-family browser for that feature.

## Security and privacy

The extension requests broad page access because it must inspect media on arbitrary websites. Captures remain browser downloads unless an explicit bridge action sends them to Image-Toolkit. The HTTP bridge is bearer-token protected and should remain local during development. Native messaging is restricted by browser-managed extension-ID allowlists. Review permissions and source code before loading an unpacked build in a sensitive browser profile.

