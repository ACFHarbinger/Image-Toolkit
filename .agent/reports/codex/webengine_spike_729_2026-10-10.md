# #729 — WebEngine spike: external-only recommendation

Codex · 2026-10-10 · Baseline `cef4c3f3`; source checkout, PySide6 6.10.0,
Python 3.11.14, KDE/Wayland session, RTX 4080 Laptop GPU.

**The current application is not safe to embed ComfyUI.** Four fresh attempts
with the application's normal event filters crashed with SIGSEGV before the
first completed render. Recommend the **external-only** tier for the present
checkout. This is a negative feasibility result, not completion of the green
acceptance matrix. #729 stays open for review of the verdict and remaining scope.

## Evidence

| Run | Configuration | Result |
|---|---|---|
| 01 | Normal app, default platform | SIGSEGV, exit 139 after construction; core PID 295553 |
| 02 | Normal app, server ready, Python fault tracing | SIGSEGV, exit 139; PID 296074 |
| 03 | Normal app, `QT_QPA_PLATFORM=xcb` | SIGSEGV, exit 139 |
| 04 | Diagnostic removal of Wallpaper's application-wide event filter | Render, cached navigation, unload, reconstruction, second render, clean exit |
| 05 | Normal filter restored; finalized developer-script entry point | SIGSEGV, exit 139; PID 297368 |
| 06 | Same developer script, diagnostic filter removal | Both renders and cleanup pass, exit 0 |
| 07 | Filter-removal control with explicit DOM validation | Both validated renders and cleanup pass, exit 0 |

Runs 01–04 initially used temporary startup callbacks. Runs 05 onward use
`dev/webengine_spike.py`, which subclasses the real LoginWindow/MainWindow and
runs the real `backend.src.app.launch_app()` event loop. No temporary application
startup changes remain in the patch. This is not a standalone bare WebEngine demo.

The app enters its supported volatile guest mode. A zero-delay GUI-thread callback
constructs WebEngine after the main window exists and the event loop is running.
The view is mounted inside the existing ComfyUI tab, loading `ComfyUIManager.url`
with port 8197. The server is a separately supervised ComfyUI process with custom
nodes disabled. Chromium's sandbox remains enabled. Original application sessions
were untouched; test settings, caches, logs, and outputs were redirected into the
scratch tree using bind mounts and XDG directories.

Successful controls returned a ComfyUI document title, completed DOM state, and
two canvas elements. Screenshots show the actual ComfyUI frontend. Navigation to
Training and back retains the view. Explicit `deleteLater()` destruction is
observed before constructing the second view.

## Current crash mechanism: evidence and limits

The first core's main-thread stack contains:

```text
libpyside6.abi3.so.6.10 + 0x2b490
PySide::getWrapperForQObject
QtWidgets.abi3.so
QCoreApplicationPrivate::sendThroughApplicationEventFilters
QApplicationPrivate::notify_helper
QObject::doSetProperty
PySide::getWrapperForQObject
QCoreApplicationPrivate::sendThroughApplicationEventFilters
```

Removing only `window.wallpaper_tab.system_display` from QApplication's event
filters changes this from crash to successful rendering under the same isolation
setup. Restoring the filter reproduces the crash. The filter is installed in
`gui/src/tabs/core/wallpaper_tab/system_display_subtab/_ui_builder.py`; its wheel/
drag handling is in `common/wallpaper_common_base/_event_filter.py`.

This strongly implicates the application-wide Python filter / native QObject
wrapping interaction. It does **not** establish the complete native root cause.
The evidence does not support attributing this crash to the historical JVM
conflict. The filter's Python reentrancy flag cannot protect a crash occurring
before Python receives the event.

`dev/resolve_qt_offset.py` was used on the libpyside offset. Its nearest exported
symbol was not a reliable semantic diagnosis for this stripped internal frame;
the repeated native call sequence and controlled removal are stronger evidence.
The existing crash view primarily consumes JVM `hs_err` files; these failures
produce systemd cores and Python fault traces instead.

Do not ship the diagnostic filter removal: it bypasses Wallpaper drag scrolling.
A follow-up should scope that filter to the widgets/events that need it, preserve
native/manual drag behavior, and test transitions back to Wallpaper. Python-side
checks of `watched` alone may be too late because wrapper creation precedes the
Python callback. Do not disable Chromium's sandbox to work around this.

## Memory and remaining gates

In controls 04/06, parent-process RSS rose by 369–397 MB. Summed process-tree RSS
rose by 826–874 MB after rendering; this sum double-counts shared pages and is
not a unique-resident-memory measurement. Report both numbers rather than
claiming the parent alone represents Chromium's cost. Full-embed's <500 MB
criterion needs an agreed process-tree measurement and a clean application first.

No generation-under-GPU-load pass was performed: baseline initialization already
fails, and no checkpoint was found in the checked ComfyUI/Downloads/Hugging Face
locations. No frozen `ImageToolkit.spec` build was produced or validated in this
round. Neither omitted check is reported as passing. They remain required before
raising the tier. The ten-clean-launch criterion was not met.

The six restrictive documentation statements and `ImageToolkit.spec` remain
unchanged, as #729 requests until there is a green/tiered embedding result. The
historical JVM explanation is stale, but removing the embedding restriction on
this evidence would be unsafe. No WebEngine dependency or feature is enabled by
this patch; the developer script is outside the spec's GUI/backend hidden-import
scan and normal application startup never imports it.

## Reproduction and artifacts

Artifacts: `~/Downloads/Data/Tests/dl-a4-729-evidence/` contains launch JSONL/logs,
view screenshots, `core01.txt` / `core02.txt`, and the exact isolated `run.sh`.
The source worktree is `~/Downloads/Data/Tests/dl-a4-729/`. Binary artifacts and
cores are not committed. Raw cores remain in systemd's existing coredump store.

Start a supervised ComfyUI server on port 8197 with its input/output/user paths
under the scratch directory. From the activated environment, the diagnostic is:

```bash
python dev/webengine_spike.py --port 8197 --output /path/to/new/run.jsonl
```

Use the evidence `run.sh` to reproduce the isolated run on this machine; pass a
fresh filename stem. It read-only mounts the host, redirects `.image-toolkit`
and XDG settings/cache to scratch, and retains access to the display/devices.
`ITK_SPIKE_NO_WALLPAPER_FILTER=1` enables the explicit diagnostic control and logs
`diagnostic_filter_removed`; its results must never count as normal-app passes.
No model download or GPU workload is triggered by the script. Stop the separately
started server after the test. Each render has a bounded watchdog once mounted.

Validation: developer script passes ruff and Python compilation. Live results
above are the meaningful spike checks; no full test suite or corpus run was used.

## Proposed gate decision

Accept external-only for current product work, with HTTP provenance and Guided
mode independent of browser rendering. Keep the scoped event-filter correction
and the remaining GPU/frozen/ten-launch matrix as prerequisites for any future
opt-in or full embedding verdict. Gate C must not treat diagnostic-only control
runs as evidence that ordinary application embedding is safe.
