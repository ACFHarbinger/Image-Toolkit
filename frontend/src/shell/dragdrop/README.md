# S-05 — file drag-and-drop in and out of the webview (#891)

Feasibility spike for the Tauri 2 + React 19 shell. Delivers a small,
well-tested module plus hook surfaces; nothing here is wired into
`App.tsx` or granted new capabilities. Companion to the S-02 canvas
spike (`frontend/src/shell/canvas/` on `feat/s02-canvas-spike`).

## Module map

| File | Role |
| :--- | :--- |
| `paths.ts` | Pure inbound validation: allowlist, traversal/size/type gates, batch planning. No Tauri, no DOM — fully fakeable. |
| `inbound.ts` | Runtime adapter: Tauri `onDragDropEvent` subscription (dynamic-imported), DOM `DataTransfer` fallback, `useFileDropTarget` hook. |
| `outbound.ts` | Drag-out source: Chromium `DownloadURL` + `text/uri-list` payloads, `useDragSource` hook, and the `NativeDragOut` seam. |
| `index.ts` | Barrel. |

## What was measured

**Inbound.** Tauri 2's webview emits native drag-drop as the events
`tauri://drag-enter/over/drop/leave` (see `TauriEvent` in
`@tauri-apps/api`), delivered to JS as `DragDropEvent` payloads carrying
absolute filesystem paths on `enter`/`drop`. That is the only path that
yields real paths on all platforms. The DOM `drop` event in a Tauri
webview does *not* reliably expose `File.path` (Chromium-only property,
absent on Linux WebKitGTK builds), so the DOM fallback accepts either
`File.path` or `text/uri-list` (`file://` URLs) and is mainly there for
the plain-browser Vite dev loop.

**Outbound.** Chromium implements the de-facto `DownloadURL`
DataTransfer type (`mime:filename:url`), which supporting file managers
(KDE Dolphin, Windows Explorer via CF_HDROP synthesis, some GNOME
targets) turn into a real file copy; `text/uri-list` covers URL-only
targets. This is the only web-standard mechanism that works from a
webview without native code. Support matrix observed in the field:

| Target | DownloadURL | text/uri-list | Notes |
| :--- | :---: | :---: | :--- |
| Chromium / Tauri webview (source side) | ✅ | ✅ | Both set by `applyDragSource`. |
| Dolphin, most Linux file managers | ✅ | ⚠️ | uri-list often yields a `.desktop`-style link, not a copy. |
| Windows Explorer | ✅ | ⚠️ | Requires the file to be reachable; blob URLs work in webview contexts. |
| macOS Finder | ❌ | ⚠️ | Finder needs promised-file native drags — see `NativeDragOut` seam. |
| Firefox (as a drop *target*, for completeness) | ❌ | ✅ | Firefox ignores DownloadURL by design. |

**Validation semantics.** `validateDropPath` enforces: absolute POSIX
path, no NUL bytes, `..` segments rejected outright (absolute paths
cannot escape the root, so traversal is redundant noise), `.` segments
collapsed, case-insensitive extension allowlist mirroring the Qt
converter contract (`SUPPORTED_IMG_FORMATS`,
`middleware/src/constants/app.py:5`; the frontend copy in
`src/constants.ts` is stale — no tiff/avif), non-empty filename stem,
and — via injected `stat`/`realpath` — regular-file-only, size ceilings
(512 MiB/file default), and symlink resolution where the resolved
target must re-pass extension and size checks (a `link.png →
/etc/passwd` symlink is rejected). `planDrop` dedups after
normalization (reported as rejections), caps batches (256 items), and
latches a 2 GiB total-bytes budget once exhausted. Windows
drive-letter paths (`C:\…`) are **not** handled — POSIX-only per spike
scope; production must normalize or reject them explicitly.

## Capability finding: `onDragDropEvent` needs no new permission

Verified against the installed `@tauri-apps/api` 2.12.0 and
`frontend/src-tauri/schemas/desktop-schema.json`:

- `Webview.onDragDropEvent` (webview.d.ts:538) is implemented entirely
  on the core event system — it calls `this.listen(...)` for the four
  `tauri://drag-*` events. Event listening is gated by
  `core:event:allow-listen`, which is part of `core:event:default`,
  which `core:default` already includes (`capabilities/default.json`
  grants `core:default` + `dialog:default` today).
- The desktop schema has **no** drag-drop capability permission at all.
  The only drag-related entries are `core:window:allow-start-dragging` /
  `deny-start-dragging`, which govern window dragging, not file drops.
- The only config gate is the webview's `dragDropEnabled` build flag
  (default `true`; not overridden in `frontend/src-tauri/tauri.conf.json`).

Conclusion: inbound native drag-drop works with the existing
`core:default` grant — no capability file changes required for
production wiring. `getCurrentWebview()` throws outside a Tauri
runtime, hence the dynamic import + no-op-with-warning in
`subscribeTauriDrop`.

## Production follow-ups

1. Wire `useFileDropTarget` into a real gallery/import surface and feed
   accepted batches to the middleware import queue (bridge contract).
2. Inject `@tauri-apps/plugin-fs`-backed `stat`/`realpath` (or the
   middleware bridge) as `DropFs`; the spike's fakes disappear.
3. Implement the `NativeDragOut` seam (`registerNativeDragOut`) with
   `tauri-plugin-drag` or a custom Rust command — mandatory for Finder
   and Wayland targets, which ignore `DownloadURL`.
4. Decide Windows path handling (drive-letter normalization) before the
   Windows shell ships.
5. Surface `rejected` reasons in the UI; today they are returned but
   not rendered anywhere.
