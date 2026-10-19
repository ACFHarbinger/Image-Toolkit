# Tauri migration and architecture refactor — Grok proposal

— Grok, 2026-10-19. Proposal only. Builds on Harbinger's recorded
answers (Claude Q0a–Q0d, Codex R1–R7). Does not re-open them. Does not
propose PostgreSQL. The library stays on the encrypted SQLCipher store.

## 1. What this adds

Codex R1 is the bridge: a supervised Python sidecar on versioned
JSON-RPC/stdio, Django as a second adapter for remote clients, Rust
only for native integration. The gaps below are the ones that still
change the desktop design.

### Bounded media, not a webview decode path

`gui/src/utils/cache/lru_image_cache.py` exists because the Qt gallery
decoded full frames into a process-wide `PixmapBudget` (800 resident
entries, #568). Huge animated GIFs crashed browse before that. A Tauri
`<img>` pointed at the original file through the asset protocol repeats
that failure inside the webview, which has no equivalent budget.

Extract thumbnail generation out of
`gui/src/elements/database/common/listings_common.py` into a Qt-free
service the sidecar owns:

- Grid cells receive a still preview: max edge from the existing
  thumbnail setting, first frame only for animations, written under the
  app cache directory.
- The focused item may request an animated preview with a frame cap.
  Changing the selection cancels it.
- The webview never receives the original path of a multi-frame or
  oversized file. It receives a cache path the asset scope allows.

Rust does not grow a second decoder. `db.rs` and the convert/merge
commands stay on the deletion list from the brief.

### Lock the asset protocol before new UI

`frontend/src-tauri/tauri.conf.json` sets `"csp": null` and
`assetProtocol.scope` to `["**"]`. Cloud Jobs Gate D is the first new
Tauri UI. Shipping it on a scope that can read any path makes the
webview a file browser.

Wave 0 should set a real CSP and a default-deny asset scope. Each
feature declares roots: library cache, thumbnail cache, job output
collections, and an explicit import drop. Originals stay behind the
sidecar. A drop gives the sidecar a path and gets back an id.

### One serializable catalog

`gui/src/modules/catalog.py` already models page, workspace, and route
without owning widgets. `gui/src/modules/descriptor.py` still imports
`QWidget` and stores `view_factory`. That is why the React app cannot
share the navigation model.

Split a frozen dataclass (id, parent workspace, route key, title,
category, order, capability flags, search terms) from the Qt factory.
Both shells read it. The Qt factory map stays in `gui/` until that
row is deleted. OpenCode's migration ledger tracks parity and
ownership. This catalog tracks navigation. They should reference the
same ids, not become two inventories.

### One workspace window

`tauri.conf.json` declares a single 800×600 window. PySide6 spreads
preview, compare, slideshow, settings, and Cloud Compute across
windows. Recreating that as one webview per window multiplies the
sidecar session and the asset scope.

Recommend one main webview. Preview, compare, settings, and Cloud Jobs
are routes or panels in that window. Extra native windows are only for
surfaces the webview cannot be: the tray, a wallpaper/slideshow
presenter, and a file dialog. Child windows do not get the
`**` asset scope.

### Sibling processes, not a window-owned tree

Codex R2 says durable local jobs survive closing every window, and
Cloud Jobs already has its own daemon. The wallpaper slideshow daemon
(`backend/src/utils/display/monitor_slideshow_daemon.py`, controlled
from `gui/src/tabs/core/wallpaper_tab/.../_slideshow_daemon`) is the
same kind of process. If the Tauri shell starts the sidecar, and the
sidecar starts the daemons, closing the shell or crashing the sidecar
takes the watchers down. That contradicts both R2 and the Cloud Jobs
lifetime decision.

Recommend one supervisor, outside the webview:

- it starts the sidecar, the cloud-jobs daemon, and the slideshow
  daemon;
- the UI sends intents over the sidecar;
- window close stops session requests only;
- the supervisor restarts a dead sidecar without tearing down daemons
  that still hold leases.

The webview does not spawn `externalBin` children itself.

### The vault password stays out of the webview

`backend/src/core/vault_manager.py` is the credential boundary. Cloud
Jobs already decided the daemon receives a key lease and never the
vault password. The same rule should cover Tauri. The React tree is
the least trustworthy place to hold a SQLCipher key: devtools, logs,
and the current null CSP.

Unlock happens in the sidecar. The webview holds a session handle.
Daemons hold leases. Rust may store an OS-keychain wrapped secret only
if the sidecar is what unwraps it. The webview never sees the password
or the database key.

### Editors share one canvas host

Stitch, merge, and frame-slice are the canvas features called out in
the brief. Porting three canvases independently will fork hit-testing,
zoom, and undo. A Wave 0 spike should prove one canvas host (input,
camera, layer list, undo) with a fake document. Stitch is the first
real document, after the seam-first Convert pilot the other proposals
already recommend. If the spike fails the performance budget from
Codex R5, that area uses the case-specific deferral. It does not keep
a private Qt editor forever by default.

### Remaining Deep Learning UI

Milestone #11 still has UI that has not started. The training contract
is already files: `record.json` and `events.jsonl` from
`backend/src/core/training_runs.py`. New panels should be Tauri clients
of that contract. Finishing them in Qt creates a surface that the
deletion gate immediately has to port again.

## 2. Shape

- `backend/src/services/media/thumbnails.py` — still and capped
  animation requests. No PySide6 import.
- `backend/src/services/catalog/export.py` — JSON catalog emitted from
  the serializable descriptors. Qt factories are not in the file.
- `frontend/src-tauri/tauri.conf.json` — CSP and scoped
  `assetProtocol` in the same change as the Vite cutover, before Gate D
  UI.
- Supervisor config lists sidecar, `cloud_jobs` daemon, and slideshow
  daemon as siblings.
- Vault unlock RPC returns a handle. Logs redact it.

Targeted tests: thumbnail bounds on a huge GIF fixture, catalog JSON
round-trip without importing PySide6, asset-scope rejection of a path
outside the declared roots, supervisor restart that keeps a daemon
lease. No full suite. No live cloud spend.

## 3. Questions for Harbinger

Recommendation first.

### Grok T1 — Where do gallery pixels come from?

- **A (recommended).** A Qt-free thumbnail service writes bounded
  stills (first frame, max edge). The webview displays those cache
  files only. Animated preview is a separate, cancellable request for
  the focused item.
- **B.** A Rust thumbnail command decodes for the grid, so the grid
  does not wait on the Python sidecar.
- **C.** The webview decodes original files directly through the asset
  protocol.
- **D.** Keep today's Rust `db.rs` / image commands as the thumbnail
  path until the library wave.

### Grok T2 — When do we close the open asset scope and null CSP?

- **A (recommended).** Wave 0, before Cloud Jobs Gate D or any other
  new UI. Default deny. Each feature declares roots. Originals are not
  in the scope.
- **B.** Tighten the scope as each feature migrates. Gate D may ship
  on the current `**` scope.
- **C.** Leave `csp: null` and `scope: ["**"]` until PySide6 is gone.

### Grok T3 — What is the navigation source of truth while both shells ship?

- **A (recommended).** One serializable catalog, split out of
  `descriptor.py` so it does not import `QWidget`. Qt and Tauri both
  render it. Ids match the migration ledger.
- **B.** Tauri routes are handwritten. `ModuleCatalog` stays Qt-only
  until that area is deleted.
- **C.** The React router becomes the source of truth now. The Qt
  registry is frozen and edited only to delete rows.

### Grok T4 — How many native windows does the desktop have?

- **A (recommended).** One main webview. Preview, compare, settings,
  and Cloud Jobs are routes or panels. Extra native windows only for
  the tray, the slideshow/wallpaper presenter, and OS file dialogs.
- **B.** One Tauri window for each current PySide6 window.
- **C.** Several webviews inside one native frame, one per major area.

### Grok T5 — Who starts the sidecar and the long-lived daemons?

- **A (recommended).** A supervisor outside the webview starts the
  sidecar, the cloud-jobs daemon, and the slideshow daemon as
  siblings. Closing the window does not stop them. A sidecar crash
  does not drop daemon leases.
- **B.** The sidecar parents the daemons. The supervisor only restarts
  the sidecar, which then reattaches.
- **C.** The Tauri shell starts all of them as `externalBin` children.
  Their lifetime follows the shell.

### Grok T6 — Where may the vault password and database key live?

- **A (recommended).** Unlock stays in the sidecar. The webview holds a
  session handle only. Daemons hold leases, as Cloud Jobs already
  requires. Logs never contain the password or the SQLCipher key.
- **B.** The Tauri shell stores the password in the OS keychain and
  passes it to the sidecar at launch.
- **C.** Rust holds the unwrapped database key for the process
  lifetime and proxies queries itself.

### Grok T7 — How should stitch, merge, and frame-slice canvases be ported?

- **A (recommended).** One shared canvas host. A Wave 0 spike uses a
  fake document. Stitch is the first real editor after the Convert
  pilot. A failed budget uses the Codex R5 case-specific deferral.
- **B.** Each editor keeps its own canvas. No shared host.
- **C.** Leave the editor canvases on PySide6 until every other area
  has been deleted.

### Grok T8 — What happens to Deep Learning UI that has not been built yet?

- **A (recommended).** Freeze new Qt panels. Build the remaining Deep
  Learning UI in Tauri against the existing `record.json` /
  `events.jsonl` contract.
- **B.** Finish the open Qt issue first, then freeze `gui/` Deep
  Learning panels.
- **C.** Make the Deep Learning workspace the migration pilot, ahead
  of Convert.
