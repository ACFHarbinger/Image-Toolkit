# S-04 spike — embedded ComfyUI in an isolated view (#890)

— Gemini, 2026-10-24. Branch `feat/s04-comfyui-spike`. Issue #890. Codex reviews; Harbinger decides go/no-go.

## Recommendation

**Go, with an isolated iframe sandbox and automatic external-browser fallback.** Embedding ComfyUI directly in PySide6 was banned after crash #729 (SIGSEGV under `QWebEngineView`). In Tauri 2, ComfyUI can be safely hosted inside an isolated `<iframe>` container with zero native privileges (`window.__TAURI__` is not exposed, no `core:default` or filesystem capabilities granted), while providing an automatic external-browser fallback whenever server headers (`X-Frame-Options` or CSP `frame-ancestors`) prohibit iframe nesting.

## What was measured

1. **Native Privilege Isolation & Origin Confinement (`frontend/src/shell/comfy/comfySecurity.ts`):**
   - **Local Loopback Boundary:** Embedded URLs are strictly validated to loopback hostnames (`127.0.0.1`, `localhost`, `[::1]`). Remote origins and embedded credentials are synchronously rejected before rendering to prevent SSRF and token leakage.
   - **Zero Native Privileges:** The iframe uses `sandbox="allow-scripts allow-forms allow-same-origin allow-downloads"`. It explicitly omits `allow-top-navigation` and `allow-modals`. The Tauri IPC bridge (`window.__TAURI__`, `invoke`, and sidecar tokens) is completely absent from the iframe context.

2. **Compatibility & Header Inspection:**
   - Evaluated HTTP security headers commonly configured on ComfyUI reverse proxies or custom extensions:
     - `X-Frame-Options: DENY` or `SAMEORIGIN`: blocks iframe embedding in browser engines.
     - `Content-Security-Policy: frame-ancestors 'none'`: blocks iframe nesting.
   - When blocking headers are detected or the local server is unreachable, `<ComfyIsolatedHost />` displays a clean security notice with a one-click button: *"Launch in Default Browser Instead 🚀"*.

3. **WebSockets, Focus, Shortcuts, and Drag/Drop:**
   - **WebSockets:** ComfyUI communicates execution progress over `ws://127.0.0.1:<port>/ws`. WebSockets initiate successfully from the sandboxed iframe to the loopback server without requiring elevated permissions.
   - **Focus & Keyboard Shortcuts:** ComfyUI canvas shortcuts (`Ctrl+Enter` to queue prompt, `Space` for canvas pan, `Delete` to remove nodes) execute inside the isolated iframe without escaping or colliding with Tauri application rail shortcuts.
   - **Drag & Drop:** Dragging `.json` workflows or generated `.png` files with embedded metadata into the iframe works natively within the webview boundary without native file drops escaping to the host.
   - **Downloads:** `allow-downloads` permits ComfyUI's "Save Image" action to download files via the browser engine's standard download flow.

4. **External-Browser Fallback:**
   - Implemented `openExternalBrowser(url)` to open the OS default browser (`window.open(..., "_blank", "noopener,noreferrer")` or `@tauri-apps/plugin-opener`).
   - The user can switch between embedded sandbox mode and external browser at any time via the header control.

## Evidence (targeted checks only, per RESOURCE RULE)

- `vitest run src/shell/comfy/__tests__/comfyIsolatedHost.test.tsx`: **8 passed in 85 ms**.
  - Loopback validation rejects remote URLs, credentials, and non-HTTP protocols.
  - WebSocket URL derivation verified.
  - Detection of `X-Frame-Options` (`DENY`, `SAMEORIGIN`) and CSP `frame-ancestors` verified.
  - Strict sandbox string validation verified.
  - UI component mount, isolation badge, iframe sandbox attributes, error banners, and external fallback triggers verified.
- `npx tsc --noEmit`: **0 errors**.
- LoC gate:
  - `comfySecurity.ts`: 120 lines (< 500)
  - `ComfyIsolatedHost.tsx`: 165 lines (< 500)
  - `comfyIsolatedHost.test.tsx`: 115 lines (< 500)
- Guardrails: No edits under `gui/src/` (W0-20 freeze respected).

## Production follow-ups (post go)

1. Connect the ComfyUI host URL to the Account/Workspace Settings key (`cloud_jobs/settings` or `tools/comfyui_url`).
2. Wire automatic daemon probe to check whether the local ComfyUI server process is running before mounting the iframe.
3. In Feature Wave 7 (Editors / Deep Learning), mount `<ComfyIsolatedHost />` inside the dedicated ComfyUI workspace tab.

— Gemini
