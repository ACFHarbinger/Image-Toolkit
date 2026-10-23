# S-05 spike — file drag-and-drop in and out of the webview (#891)

— Kimi, 2026-10-22. Branch `feat/s05-dragdrop-spike` (`a53c298a2` on `origin/main` `d609e1a5d`). PR: opened against main. Codex reviews; Harbinger decides go/no-go.

## Recommendation

**Go, with a scoped follow-up.** Inbound drag-and-drop is fully feasible with zero new dependencies, zero capability changes, and full jsdom/vitest coverage — ship it. Outbound works today via the Chromium `DownloadURL` mechanism for the Linux/Windows file managers that honor it, but true native drag-out (`tauri-plugin-drag` or a custom Rust command behind the `NativeDragOut` seam) is a required follow-up for macOS Finder and Wayland targets. A no-go is not warranted: inbound is the higher-value half (library import) and is production-ready in shape.

## What was measured

**Inbound (OS → webview).** Tauri 2's webview raises native `tauri://drag-enter/over/drop/leave` events carrying absolute filesystem paths; `Webview.onDragDropEvent` consumes them via the core event system. Verified against the installed `@tauri-apps/api` 2.12.0 and `frontend/src-tauri/schemas/desktop-schema.json`: listening needs only `core:event:allow-listen`, already inside `core:default` (granted in `capabilities/default.json`) — **no capability edit required**. The only config gate is `dragDropEnabled` (default true, not overridden). The DOM `drop` event does not reliably expose `File.path` (Chromium-only, absent on Linux WebKitGTK), so the spike ships a DOM fallback accepting `File.path` or `file://` `text/uri-list` entries — this is what the Vite build + Playwright per-PR gate can exercise.

**Outbound (webview → OS).** `DownloadURL` (`mime:filename:url`) + `text/uri-list` is the only web-standard mechanism; support observed in the field: Dolphin and most Linux file managers copy the file, Windows Explorer synthesizes CF_HDROP, macOS Finder and Wayland compositors ignore it (need promised-file native drags). The spike implements the web path and leaves a typed `registerNativeDragOut` seam for the native plugin; no Rust shipped.

**Validation.** `validateDropPath`/`planDrop` (`frontend/src/shell/dragdrop/paths.ts`): absolute-POSIX-only, NUL/traversal rejection, `.` collapse, extension allowlist mirroring `SUPPORTED_IMG_FORMATS` (`middleware/src/constants/app.py:5` — note `frontend/src/constants.ts` is stale, lacking tiff/avif), regular-file-only via injected stat, 512 MiB/file default, symlink resolution with re-validation of the target (extension-flip rejected, depth ≤ 8), batch cap 256, 2 GiB total-bytes budget with latch-on-exhaustion. Windows drive-letter paths are POSIX-rejected and flagged as a production decision.

## Evidence (targeted only, per RESOURCE RULE)

On `a53c298a2`: `vitest run src/shell/dragdrop` 62/62 (3 files); `tsc --noEmit` clean; `vite build` green. No package/lockfile/Cargo edits; no `src-tauri` edits; no `App.tsx` wiring (spike module only); no `gui/src` edits (W0-20 freeze).

## Production follow-ups (post go)

1. Wire `useFileDropTarget` into the import surface; feed accepted batches to the middleware import queue over the bridge.
2. Inject `@tauri-apps/plugin-fs` (or bridge) `stat`/`realpath` as `DropFs`; spike fakes disappear.
3. Implement `NativeDragOut` with `tauri-plugin-drag` / custom Rust command — mandatory for Finder + Wayland.
4. Decide Windows path normalization before the Windows shell ships.
5. Render `rejected` reasons in the UI.

## Update 2026-10-23 (review fixes, PR #968)

Two P2s from review of the landed spike, both fixed:

- Native drops are now hit-tested against the mounted target's rect
  (`positionHitsTarget`, physical→CSS pixels via `devicePixelRatio`);
  previously the whole-webview subscription imported drops outside the
  target and fanned every batch out to all mounted targets.
- `DownloadURL` carries exactly one `mime:filename:url` tuple (first
  item); all items remain on `text/uri-list`. This strengthens the
  follow-up case for the `NativeDragOut` seam: multi-file drag-out is
  web-impossible, not just Finder/Wayland-limited.

Verification: 68/68 vitest (6 new), tsc/eslint/vite build clean.
