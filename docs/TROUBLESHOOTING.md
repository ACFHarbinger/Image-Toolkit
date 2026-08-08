# Troubleshooting Guide

*Last updated: 2026-07-27. Absorbed the full content of `docs/TROUBLESHOOT.md` (the older, SIGSEGV-only guide) and that file has been deleted — this is now the single troubleshooting doc. Covers PySide6/Qt crashes, Qt Multimedia video playback failures, ASP pipeline errors, C++/pybind11 build failures, Hydra CLI issues, mobile build failures, and database problems.*

---

## Table of Contents

- [PySide6 / Qt Crashes & Layout Bugs](#pyside6--qt-crashes-sigsegv)
  - [Benchmark Evaluation Inspector Window Geometry Overflow](#benchmark-evaluation-inspector-window-geometry-overflow--vertical-image-tiling)
- [Qt Multimedia / Video Playback Decode Failures](#qt-multimedia--video-playback-decode-failures)
- [External API Failures (Jikan / MyAnimeList Auto-Fill)](#external-api-failures-jikan--myanimelist-auto-fill)
- [ASP Pipeline Errors](#asp-pipeline-errors)
- [C++ / pybind11 Build Failures](#cpp-pybind11-build-failures)
- [Hydra CLI Configuration Errors](#hydra-cli-configuration-errors)
- [Database (PostgreSQL / pgvector)](#database-postgresql--pgvector)
- [Tauri / Frontend Build Failures](#tauri--frontend-build-failures)
- [Mobile Build Failures](#mobile-build-failures)
- [Test Suite Issues](#test-suite-issues)
- [Developer Best Practices](#developer-best-practices)

---

## <a id="pyside6--qt-crashes-sigsegv"></a>PySide6 / Qt Crashes & Layout Bugs

### Benchmark Evaluation Inspector Window Geometry Overflow & Vertical Image Tiling

**Symptom:** After maximizing, un-maximizing, or moving the Benchmark Evaluation Inspector window, right-hand UI controls (Settings button, Scoring panel toggles, Save button) expand beyond the right monitor/window boundary and get cut off. Additionally, images inside `ImagePanel` display split or tiled vertically with uncentered viewport scroll offsets.

**Root causes (full set — see also issue #153):**

1. Default `Expanding` horizontal size policies on `ImagePanel`, `_PanelCell`, `PanelGrid`, and `_GridHost` caused graphics view layout updates to propagate up the layout tree during viewport transforms, requesting 2080px+ width from parent `QSplitter` and `centralWidget` and forcing `QMainWindow` to expand past the 1920px screen width.
2. `QTimer.singleShot(0, self._fit_all)` calls in `_load_current`, `_on_layout_changed`, and `_on_visibility_changed` were left in place even after `_resize_timer` was introduced. These bypassed the 150 ms resize debounce, firing `_fit_all` while the window manager was still animating a maximize/move — causing `_compute_fit_scale()` to read transitional (mid-animation) viewport sizes and propagate an inflated width request up through the splitter.
3. `ImagePanel.resizeEvent` recalculated `_fit_scale` without re-anchoring `centerOn(...)`.
4. The two internal `QStackedWidget` instances inside `PanelGrid` (`_host_stack` and `_stack`) retained the default `Preferred` horizontal size policy. `QStackedWidget.sizeHint()` returns the **maximum** sizeHint of all contained widgets — which, during a re-layout triggered by a panel add/remove, could reflect the native pixel size of the largest image. Even with `PanelGrid` itself set to `Ignored`, `QLayout::minimumSize()` still queries children's `minimumSizeHint()`, which `QStackedWidget` derives from its children's `sizeHint()` when their own policy is `Ignored` but the stacked widget's is not.
5. `QGraphicsView.setTransform` / `centerOn` can trigger internal `QAbstractScrollArea` geometry updates that re-enter the Qt event loop and may re-invoke `_fit_all` mid-execution, compounding whichever of the above is the immediate trigger.
6. The footer key-hint crib sheet (`KEY_HINTS`, joined into one `QLabel` in `_build_ui`) and the header/footer status labels (`status_label`, `pixel_label`) used plain `QLabel`s with word-wrap off and no elision. A `QLabel` in that configuration reports its full unwrapped text width as its `minimumSizeHint` — for the joined `KEY_HINTS` string that's ~1680px — which propagates up through the footer row into `QMainWindow`'s own minimum size. This is independent of, and was not fixed by, root causes 1-5: it reproduced the exact same symptom (right-hand sidebar controls and footer text clipped at the screen edge) on a real window even with the size-policy and debounce fixes in place, because the window's *minimum* size itself was the thing exceeding the screen, not a transient viewport-driven expansion.

**Fix (issue #153 / `main_window.py`, `panel_grid.py`):**

1. Set `setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)` on `ImagePanel`, and `setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)` on `_PanelCell`, `PanelGrid`, `_GridHost`, `InspectorToolbar`, `_host_stack`, and `_stack`. Internal image viewport transforms now never force parent layouts or `QMainWindow` to expand horizontally.
2. Replaced all three `QTimer.singleShot(0, self._fit_all)` calls with `self._schedule_fit(0)`. `_schedule_fit(delay_ms)` routes every fit request through the single `_resize_timer` (`setSingleShot(True)`) and enforces a "don't shorten a longer active debounce" rule: if the 150 ms resize timer is already counting down, `_schedule_fit(0)` does nothing — the resize timer fires as originally scheduled, after the window manager has fully settled.
3. Updated `ImagePanel.resizeEvent` to re-center scene coordinates (`centerOn(...)`) whenever `_fit_scale` changes.
4. Added a `_fitting` boolean re-entrancy guard in `_fit_all`. If a `QGraphicsView` internal geometry propagation re-enters `_fit_all` while `grid.fit_all()` is running, the nested call returns immediately without applying a second conflicting transform.
5. Added `_ElidingLabel` (`main_window.py`) — a `QLabel` subclass with `QSizePolicy.Ignored` horizontal policy that elides its text with `QFontMetrics.elidedText(..., Qt.ElideRight, self.width())` on every `resizeEvent`, keeping the full untruncated string as the tooltip. `status_label`, `pixel_label`, and the footer `hints` label all use it now, so none of them can force the window wider than the screen regardless of how long their text gets (a long dataset path, a `Pinned:` multi-comparator pixel readout, or the full `KEY_HINTS` crib sheet).

**Debug instrumentation (issue #153):** `_DBG_INSPECTOR` in `main_window.py` and `_DBG_PANEL` in `image_panel.py` gate tagged stdout lines (`[DBG-INSPECTOR]`, `[DBG-PANEL]`) covering every resize event, `_fit_all` invocation (with call-stack origin), splitter sizes before/after fit, per-panel viewport+fit_scale+zoom, and a `window exceeds screen width` flag. Both are set to `False` now that the bug is confirmed resolved (46 regression tests in `backend/benchmark/evaluation/test/`); flip to `True` if it needs to be diagnosed again.

---

### `__dynamic_cast` failure in `libstdc++.so.6`

**Symptom:** Application terminates during directory browsing, gallery loading, or startup. Crash log (`hs_err_pid*.log`) shows:
```
C [libstdc++.so.6+0xc1e25] __dynamic_cast+0x35
```

**Root causes and fixes:**

**1 — Unsafe Signal Lifecycle in `QRunnable` (Shiboken)**

Context: `LoaderWorker` and `BatchLoaderWorker` use `setAutoDelete(True)` and own a `signals` `QObject` member.

When `run()` returns, the worker is immediately deleted by Qt. If `Signal.emit()` is in-flight, the `signals` object is destroyed before delivery completes.

Fix: Add `self.signals.deleteLater()` in a `finally` block at the end of `run()`. This schedules deletion *after* pending signals are handled.

**2 — QFileDialog with GTK portal + JPype JVM**

Context: `QFileDialog.getExistingDirectory()` without `DontUseNativeDialog` loads the GTK portal dialog on Linux.

Cause: GTK brings in its own `libstdc++`. Combined with JPype's JVM native bindings, RTTI symbol conflicts cause `__dynamic_cast` to segfault.

Fix: **Always** pass `QFileDialog.Option.DontUseNativeDialog` to all `QFileDialog` calls.

```python
# Correct
path = QFileDialog.getExistingDirectory(
    self, "Select folder", "",
    QFileDialog.Option.DontUseNativeDialog
)
```

**3 — `QWebEngineView` + JPype JVM**

Cause: Chromium initialises its Vulkan/GBM renderer lazily on first paint, loading native `libstdc++` that conflicts with JPype's JVM bindings. Log line just before crash: `"Fallback to Vulkan rendering in Chromium"`.

Fix: **Never** use `QWebEngineView` or any `QtWebEngine` widget. Open URLs with:

```python
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
QDesktopServices.openUrl(QUrl("https://example.com"))
```

**4 — `QPixmap` created in a worker thread**

Cause: `QPixmap` is not thread-safe. Creating it in a `QThreadPool` worker triggers Shiboken's internal type system crash.

Fix: Emit `QImage` from workers (thread-safe). Convert to `QPixmap` only in the main thread slot:

```python
# Worker thread — OK
self.signals.image_loaded.emit(QImage(path))

# Main thread slot — OK
pixmap = QPixmap.fromImage(q_image)
label.setPixmap(pixmap)
```

**5 — Incomplete Worker Cleanup during Tab Closure**

Context: Closing `ConvertTab` or `GalleryTab` while background workers are active.

Fix: Override `closeEvent` in every tab that uses long-running workers. Call `worker.wait()` or `QThreadPool.globalInstance().waitForDone()` before returning.

**6 — JNI/JPype Threading Race during Startup**

Context: Concurrent access to `VaultManager` (JPype JVM) from multiple threads at startup.

Fix: A `threading.RLock` in `VaultManager` serialises all JNI calls. If you see this crash, check that `VaultManager` is not being called from worker threads without acquiring the lock.

**7 — Widget Parent/Ownership Conflicts**

Context: Reusing a persistent widget (e.g. `MonitorDropWidget`) across transient layout containers.

Cause: Calling `deleteLater()` on a container implicitly deletes its children too, even if a child widget was meant to be reused elsewhere.

Fix: Explicitly call `setParent(None)` on the child widget *before* deleting/replacing the parent layout or container.

**8 — Starting new `QThread`s during the fragile pre-event-loop startup window**

Context: any code that starts a `QThread` (or constructs a `QAudioOutput`/other object that triggers Qt Multimedia's PipeWire backend probe) *synchronously* during `MainWindow`/tab construction — i.e., before `app.exec()` has started processing events. Confirmed: `ExtractorTab`'s originally-eager `QAudioOutput` construction, and the Wallpaper tab's directory-restore/browse actions starting `ImageScannerWorker`/`VideoScannerWorker` `QThread`s.

Symptom: `QSocketNotifier: Socket notifiers cannot be enabled or disabled from another thread`, immediately followed by either `free(): invalid pointer` (glibc heap corruption) and a SIGABRT, or a SIGSEGV inside `libQt6Core` (see the `deleteOrphaned` crash class below, which was originally misdiagnosed as this instance's root cause before the full startup stdout was available).

Cause: Qt Multimedia's PipeWire backend probes audio devices on its own thread the first time anything triggers it (constructing `QAudioOutput`, or sometimes just the plugin registration from importing `PySide6.QtMultimedia`). On Linux/glib, a `QThread` started around the same moment — before the main event loop is running — races that probe. With the JPype JVM already loaded in-process (started at login for `VaultManager`), this collision reliably corrupts the heap rather than failing safely. **Before assuming this is the cause, rule out the already-fixed, differently-triggered version**: `backend/main.py` preloads the system `libpulse.so.0` (via `ctypes.CDLL`, wrapped in `contextlib.suppress(OSError)`) to prevent a *different* mechanism from producing the identical warning — a SONAME-dedup mismatch where `import base`'s OpenCV/FFmpeg dependency transitively loads a pixi-built `libpulse.so.0` before Qt Multimedia's own `dlopen()` of the same SONAME, causing Qt to bind to a build it wasn't tested against. Test that preload in isolation (`ctypes.CDLL(path)` should not silently swallow an `OSError`) before spending time on the thread-timing race below — they produce the same warning text but need different fixes.

Fix that actually closed this (after a narrower per-call-site defer proved insufficient — see below): **gate the source, not individual callers.** `backend/src/app.py::launch_app()` now explicitly primes the backend (`QAudioOutput()`) immediately after `QApplication` is constructed, before the login window is even shown — giving the async probe the maximum possible head start, since vault authentication takes real, sequential time. It then defers the actual `MainWindow(...)` construction itself with `QTimer.singleShot(400, ...)`. Since no tab — and therefore no scanner `QThread` — can exist before `MainWindow` is constructed, this closes the race for *every* call path at once (auto-restore, a user's own manual action taken within seconds of launch, any future gallery), rather than requiring each individual call site to remember to defer itself.

**Why a per-call-site defer isn't enough on its own**: an earlier attempt deferred only the Wallpaper tab's startup auto-restore call (`QTimer.singleShot(250, ...)` on `SystemDisplaySubTab.set_config()`) and still recurred — the user's own manual "browse a new directory" action, taken within that same window, reaches the identical `QThread`-starting code through a completely different call path, entirely unprotected by a defer wrapping only the auto-restore. If you're tempted to fix a new instance of this crash class by wrapping one specific call in `QTimer.singleShot`, consider whether a user action could reach the same underlying thread-starting code some other way — if so, gate construction of whatever owns that code path instead (as done here for `MainWindow`), not the individual call.

**If you defer window/widget construction with `QTimer.singleShot` during a login/splash-to-main-window transition, watch for a zero-windows-open gap.** The fix above initially closed the login window synchronously while deferring `MainWindow` construction by 400ms — for that whole window, no top-level window was open, and `QApplication`'s default `quitOnLastWindowClosed=True` (never overridden anywhere in this codebase) silently quit the entire app right there. No crash log, no signal — just an app that "crashes immediately after login" with nothing in stdout past whatever was mid-flight. Always construct and show the *next* window before closing the *previous* one in any deferred transition, never the reverse.

**And check every place that `emit()`s the signal driving that deferred construction, not just the slot itself.** This exact bug recurred a second time from a completely different file: `LoginWindow` had its own `self.close()` immediately after `self.login_successful.emit(...)`, at three separate call sites. `login_successful` is a *direct* (same-thread) connection, so the connected slot runs synchronously inside `emit()` — but that slot only *schedules* `MainWindow` construction, it doesn't build it immediately. Once `emit()` returned, `LoginWindow`'s own next line (`self.close()`) ran instantly, long before the deferred construction, recreating the zero-windows-open state through a path the first fix never touched. When you fix a slot to defer its work, audit every `emit()` site for code that assumed the old synchronous behavior — a direct connection means the emitter's own subsequent statements are exactly as much a risk as the slot's.

**The 400ms `MainWindow` defer alone was still not a reliable enough margin.** The exact same crash (identical `libQt6Core.so.6` offset, `+0x1df7c9`) recurred with the simplest possible repro — auto-restore a directory, then one immediate manual browse — well after the `QAudioOutput` priming + 400ms defer above was already in place. The implicit assumption behind that fix was that login/vault-unlock (JVM start, keystore load, vault decrypt) reliably eats far more than 400ms, giving the probe a large real margin by the time `MainWindow` (and therefore any scanner `QThread`) can exist. That assumption fails whenever login happens quickly. Fixed by adding an explicit, elapsed-time-based gate: `gui/src/utils/guard/startup_probe_guard.py` records the probe's real start time (`mark_startup_probe_started()`, called from `app.py` right where the priming `QAudioOutput` is constructed) and exposes `startup_settle_remaining_ms()` — a 1.5s settle window measured from that timestamp, not from window-construction timing. Every scanner-thread call site (`WallpaperCommonBase.populate_scan_image_gallery()`, `VideoExtractorSubTab.scan_directory()`) checks this immediately before starting a thread and, if still within the window, reschedules its *entire own call* via `QTimer.singleShot()` — gating the actual danger point directly, rather than hoping enough time already passed by the time execution gets there.

**UPDATE — this whole root cause is now believed to be a misdiagnosis for the crash that motivated it.** Removing the `QAudioOutput` priming entirely, and separately making `ExtractorTab`'s `QGraphicsVideoItem()` construction lazy (the other, previously-unnoticed Qt Multimedia trigger — plain `QAudioOutput()` construction does *not* print Qt's `"Using Qt multimedia with FFmpeg..."` banner, but `QGraphicsVideoItem()` does), together eliminated every code path that could trigger Qt Multimedia's backend during a Wallpaper-only session. The crash **still recurred** — same warning text, same general `QSocketNotifier` internal-function crash class — in a run whose stdout contained *no* Qt Multimedia backend banner at all, proving the backend was never loaded. This crash was never a Qt Multimedia timing race; the warning text is apparently generic enough to also come from a completely different mechanism (see the `deleteOrphaned` section below, Addendum 15). The `startup_probe_guard.py` machinery described above is kept (it's harmless, tested, and may still matter for a genuine `ExtractorTab` video-preview-shortly-after-launch scenario), but do not spend further effort tuning it against *this* crash pattern — it was never the lever.

---

### `libpyside6.abi3.so.6.10` crash in `__dynamic_cast` on tab switch

**Symptom:** Fatal crash when switching to any tab that contains a `QWebEngineView` for the first time.

**Cause:** Same as root cause #3 above. See the fix there.

---

### `QObjectPrivate::ConnectionData::deleteOrphaned` crash switching directories or paging a gallery

**Symptom:** Fatal crash browsing/scanning a new directory (e.g. a video
directory right after an image directory) or navigating gallery pages
before the previous thumbnail batch finishes loading. Seen in the Extractor
and Wallpaper tabs; any tab built on `AbstractClassTwoGalleries` or
`AbstractClassSingleGallery` (Convert, Delete, Merge, Wallpaper, Extractor)
can hit it. Two different crash-log signatures have been observed for this
same underlying race (the exact frame depends on timing — whether the
delivery is caught cleanly inside Qt's own bookkeeping, or lands on already-
corrupted/reused memory further along):
```
SIGSEGV (0xb) ... si_code: 1 (SEGV_MAPERR), si_addr: 0x0000000000000001
C  [libQt6Core.so.6+0x1e73ae]  QObjectPrivate::ConnectionData::deleteOrphaned(...)
```
```
SIGSEGV (0xb) ... si_code: 2 (SEGV_ACCERR), si_addr matches RIP
Current thread: JavaThread "main"   [_thread_in_native, ...]
C  0x... (no resolved symbol)
```
The second form's "JavaThread main" label is JPype's embedded JVM (started
for `VaultManager`) reporting a crash on the thread that called
`startJVM()` — which is the same OS thread running the Qt event loop, not a
Java-code crash.

This is a different underlying bug from root cause #1 above (both involve a
`QRunnable` worker's `signals` `QObject`, but this one is a genuine Qt
connection-list race, not a premature-deletion-before-emit issue) — related
family, distinct root cause.

**Cause:** `cancel_loading()` (called on every directory switch, tab
switch, and page navigation via `clear_galleries()`/
`clear_gallery_widgets()`) only *best-effort* stops in-flight `QRunnable`
thumbnail workers — it sets a Python cancellation flag (checked at a few
points inside `run()`) and dequeues not-yet-started tasks, but does nothing
for a worker **already executing** on a pool thread. The caller then
immediately tears down the gallery's thumbnail widgets
(`deleteLater()` in a loop). A leftover worker from the previous scan can
still be mid-`run()`, delivering a queued cross-thread signal to a gallery
slot at the exact moment its connections/widgets are being destroyed,
corrupting Qt's connection bookkeeping.

**Fix:** `cancel_loading()` in both `AbstractClassTwoGalleries` and
`AbstractClassSingleGallery` now waits for the thread pool to actually
drain after clearing it, mirroring the fix already used in
`AbstractClassTwoGalleries.closeEvent()` for the tab-close case:

```python
if hasattr(self, "thread_pool"):
    self.thread_pool.clear()
    self.thread_pool.waitForDone(_WORKER_DRAIN_TIMEOUT_MS)  # -1: wait until
                                                             # actually idle
```

**Important — don't use a fixed millisecond timeout here.** The first
version of this fix used `waitForDone(500)`, which seemed to work but
crashed again after repeated directory switches, with a different signature
(`SEGV_ACCERR` on the main thread, no resolved symbol — the same underlying
race, just caught at a different point). Root cause: `waitForDone(msecs)`
returns after either all tasks finish *or* the timeout elapses, whichever
comes first — `VideoLoaderWorker` shells out to `ffmpegthumbnailer`/`ffmpeg`
subprocesses with their own 15s timeouts and up to three fallback attempts
chained (~45s worst case on a slow/corrupt video file), so any fixed bound
shorter than that reintroduces the exact same race, just needs a slower
worker and a few repeated attempts to hit it. Use `-1` (Qt's own sentinel
for "block until the pool is actually idle") instead of guessing a number —
workers are still asked to cooperatively cancel first (`.stop()`), so this
returns quickly in the overwhelming majority of cases; the tradeoff is a
rare, bounded-by-subprocess-timeout pause instead of a crash.

If you add a new gallery/tab with its own thumbnail-loading workers, make
sure any teardown path (directory switch, page change, tab close) routes
through `cancel_loading()` rather than clearing widgets directly — that's
what makes this wait apply automatically. And if any new worker type does
its own slow blocking I/O (subprocess calls, network requests), make sure
its `_is_cancelled` flag is actually checked *during* that blocking call
(e.g. polling a subprocess with a timeout loop), not just before/after it —
otherwise cancellation can't make the wait return quickly, only correctly.

**This bug recurred a third and fourth time from two separate code paths
that don't go through `cancel_loading()` at all.** `ExtractorTab.scan_directory()`
(the video-scan path) and `WallpaperCommonBase.populate_scan_image_gallery()`
each have their own bespoke `QThread` subclasses (`ImageScannerWorker`,
`VideoScannerWorker`) for directory-level scanning, with their own inline
stop/wait logic, entirely separate from `cancel_loading()`'s
`thread_pool`/`_active_workers` machinery. Both had the identical two bugs
independently: the stop-and-wait ran *after* widgets were already being torn
down (not before), and `VideoScannerWorker`'s wait used the same insufficient
bounded timeout. Fixed by moving the stop/wait to the *start* of each method
and using an unbounded `QThread.wait()` — same reasoning as above:
`VideoScannerWorker`'s internal `ThreadPoolExecutor` can't be force-killed
mid-subprocess, and its context-manager `__exit__` already blocks until
truly idle regardless of any earlier non-blocking `shutdown()` call, so an
unbounded `.wait()` accurately reflects genuine completion — it just can't
be given a timeout short enough to give up before that.

**If you're chasing a new instance of this crash class**: grep for
`deleteLater()` loops or widget-clearing code anywhere in a gallery/tab that
*doesn't* go through `cancel_loading()`/`clear_galleries()`/
`clear_gallery_widgets()`, and check whether it stops and waits (unbounded)
for every worker/thread that could still emit to those widgets — and that
the wait happens *before* the teardown, not after. This pattern (a bespoke
per-tab scanner thread with its own inline cleanup) is not guaranteed to be
fully audited across the whole codebase; only the instances that actually
produced a crash report have been fixed so far.

**A fourth recurrence came from a *linked-instance* variant of the same
bug, in the Wallpaper tab specifically.** `WallpaperTab` has two linked
gallery panels (`system_display`/`monitor_display`) that share a mutable
`_initial_pixmap_cache` dict (aliased, not copied — see `wallpaper_tab.py`)
and propagate scans to each other via a `directory_scanned` signal that
synchronously, recursively calls the *peer's own*
`populate_scan_image_gallery()`. The round-3 fix made each instance
correctly stop-and-wait for its **own** previous scanner threads before
touching its **own** widgets — correct for a single instance, but each
panel only guarded its own state, leaving the *peer's* still-running
scanner thread free to touch the shared cache/widgets while this instance
tore it down. Fixed by extracting the stop-and-drain logic into
`_stop_scanner_threads()` and calling it — at the very start of
`populate_scan_image_gallery()`, before even the `directory_scanned.emit()`
that triggers the peer's nested call — on **both `self` and every entry in
`self.linked_tabs`**. If you build another feature with linked/mirrored
gallery instances sharing mutable state, apply the same rule: stop and
drain *every* linked instance's workers before *any* of them touch shared
state or widgets, not just the instance that received the user's action.

**Important correction, round 5**: the *specific* crash log that motivated
rounds 3-4 above turned out, once the full startup stdout was available, to
actually be an instance of **root cause #8** above (a `QThread` started
during the fragile pre-event-loop startup window racing Qt Multimedia's
PipeWire probe) — not this `deleteOrphaned`/scanner-thread-ordering class at
all. Rounds 2-4's fixes address a real, separate race in their own right
(and are kept), but likely only reduced how often *that* crash class
surfaces, without being the actual trigger of the specific log that
prompted them. **If you're debugging a fresh instance of this crash and the
process's stdout is available, check it for `QSocketNotifier: ... another
thread` and `free(): invalid pointer` before assuming this section's fix
applies** — those two lines point at root cause #8 instead, which needs a
startup-deferral fix (`QTimer.singleShot`), not a worker-stop-ordering one.

**A fifth recurrence (round 9) came from an event-queue backlog on rapid,
repeated directory switches**, even with every wait above correctly
unbounded. `QThread.wait()`/`QThreadPool.waitForDone(-1)` block the
*calling* thread until the worker actually finishes, but they do not pump
that thread's own event loop while blocked. Any `deleteLater()` calls
already queued by an *earlier* switch's own teardown are therefore still
sitting unprocessed in the queue when a later wait returns — the wait says
nothing about whether the queue itself has been drained. With several
rapid switches in a row (e.g. restore previous session's directory, browse
a new directory immediately, switch back, then immediately browse again),
each teardown queues more deferred deletions before the previous batch has
ever run, since nothing in the chain yields back to the event loop. Fixed
by adding an explicit `QApplication.processEvents()` call immediately
after every unbounded wait in this file's teardown/cancel/close paths,
flushing the queue before the caller proceeds to tear down or rebuild
widgets again. If you add a new blocking wait anywhere in this crash
class's call chain, apply the same rule: a wait alone only proves the
*worker* is done, not that previously-queued *deletions* have actually
been processed — pair it with `processEvents()` before touching widgets
again.

**A sixth recurrence (round 10) turned out to be caused by round 9's own
fix.** `QApplication.processEvents()` doesn't just flush `deleteLater()`s —
it delivers *any* queued event, including a stale `ImageScannerWorker.scan_finished`
signal from the *previous* directory's scan, whose completion was itself
detected by the `.wait()` immediately before the `processEvents()` call.
That delivery happens reentrantly, in the middle of
`_stop_scanner_threads()`, *before* the caller has updated `self.scanned_dir`
to the new directory — so `_on_image_scan_finished()` runs for the old
directory and starts a brand-new `VideoScannerWorker` for it, with nothing
in that same call left to stop it. Fixed two ways: (1) narrowed every
round-9 flush from `QApplication.processEvents()` to
`QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` — same
`deleteLater()`-draining effect, without reentrantly delivering ordinary
signals; (2) hardened `_on_image_scan_finished()` (in
`wallpaper_common_base.py`) to reject a delivery that isn't from the
*current* image scanner — compared by Python object identity captured in
the signal connection's own closure, **not** `QObject.sender()` (a stale
sender's C++ object is frequently already destroyed by the time its
signal is processed, and `sender()` returns `None` for a destroyed
sender — the opposite of what a staleness check needs) — and to always
stop any existing `vid_scanner_worker` before starting a new one, even on
a legitimate completion.

If you're chasing a new instance of this crash class and considering a
`processEvents()`-style fix: **prefer the narrowest event type that solves
your actual gap** (`QCoreApplication.sendPostedEvents(None, <QEvent.Type>)`)
over a blanket `processEvents()`. A blanket flush can reentrantly run
*any* connected slot for *any* signal that happens to be queued at that
moment, including ones that assume they're only ever called from the
normal event loop, not mid-teardown.

This crash class now has an automated regression test:
`gui/test/core/test_wallpaper_scan_race.py` reproduces rapid
image/video directory switching against the real
`WallpaperCommonBase` scan path and asserts no spurious/orphaned
`VideoScannerWorker` gets created. Verified to fail against the
pre-round-10 code and pass against the fix — if you touch
`populate_scan_image_gallery()`/`_on_image_scan_finished()`/
`_stop_scanner_threads()` again, run this test first.

**This is now believed to be the actual mechanism behind a crash previously
misdiagnosed as the Qt Multimedia startup race (root cause #8) above** —
that theory was directly disproven (see the UPDATE note there): the crash
recurred with identical symptoms in a run where Qt Multimedia's backend
was never triggered at all. The real Wallpaper tab always runs **two
linked `WallpaperCommonBase` instances** (`system_display`/`monitor_display`,
wired in `wallpaper_tab.py`: mutual `linked_tabs`, a shared/aliased
`_initial_pixmap_cache` dict, `directory_scanned` cross-connected with
`emit_signal=False`) — a topology `test_wallpaper_scan_race.py` doesn't
cover (it only exercises one instance). A second test,
`gui/test/core/test_wallpaper_linked_panel_scan_race.py`, builds the same
two-instance topology and drives rapid switching through one panel — it
currently **passes** against the existing code, meaning this specific
interaction isn't reproducible by simulating the Python/Qt-signal call
sequence with a mocked scan delay. That's a real, useful negative result:
it points at something lower-level (genuine native thread-scheduling
timing, real subprocess spawning, or a Qt-internal event-dispatcher/
socket-notifier interaction) that only manifests under real OS thread
creation, not a logic bug reachable this way.

Fine-grained `[thread-lifecycle]` print instrumentation (tagged with
`panel={id(self):x}` and `tid={threading.get_ident()}`) was added at
every `QThread` start/stop/quit/wait/deleteLater transition in
`wallpaper_common_base.py`, and at `_on_image_scan_finished()`'s
stale-vs-proceed decision, specifically so the *next* live crash's stdout
pinpoints exactly which lifecycle operation was in flight — none of the
diagnosis up to this point could determine that from the coarser prints
that existed before. If a future crash's last instrumented line still
doesn't localize the problem, the next escalation is external process
tracing (`strace -f`, or GDB attached ahead of time), not more Python
print statements — that would mean the issue is below what this kind of
tracing can observe.

**Recurred again on 2026-08-01**, same repro shape (auto-restored
directory, then browsing a video directory), same `QSocketNotifier: ...
another thread` warning immediately followed this time by `corrupted size
vs. prev_size` (glibc's `malloc_consolidate()` catching heap corruption)
and SIGABRT — the same failure mode Addendum 13 already saw once. Rather
than another Python-level fix guess, this round built permanent,
toggleable tooling instead of another one-off print pass: see
[`debug/README.md`](../debug/README.md).
`backend/src/core/telemetry.py` is a structured, JSONL event logger
(`IMAGE_TOOLKIT_TELEMETRY=1 just python` to enable) wired into every
`[thread-lifecycle]`/`[startup-probe-guard]` call site already documented
above (additive only, none of the existing prints were touched) plus the
suspected native-crash boundary itself — `QImage().loadFromData()` in
`video_thumbnailer.py` and every `base.scan_files_multi()` call —
wrapped in `telemetry.span()` so a crash mid-decode leaves an unambiguous
"orphaned span" in the file instead of requiring inference from which
`print()` line happened to be last. `debug/telemetry_analyzer.py` parses
that file into a merged, time-ordered timeline and flags orphaned spans
and overlapping scanner-thread windows automatically.
`debug/run_with_gdb.sh` runs the app under `gdb -batch`, stopping only on
SIGABRT (SIGSEGV is deliberately passed through untouched — the JVM raises
it internally, on purpose, for implicit null-checks/safepoint polling, and
stopping there produces a misleading "crashes before login" false
positive; see Addendum 19) and dumping an all-thread backtrace before
re-delivering the signal so the JVM's own `hs_err_pid*.log` also gets
written — the actual "external process tracing" step this document has
called for since Addendum 15/round 16 of the underlying investigation but
never had a ready-made tool for.

**Update (2026-08-01, Addendum 20) — first hard confirmation of the actual
crash site.** With the fixed script, two live crashes produced real
`hs_err_pid*.log` files with the JVM's own diagnosis:
`libQt6Core.so.6+0x1e74d5` and `libQt6Core.so.6+0x1df7c9`. PySide6's
bundled Qt is stripped, but `debug/resolve_qt_offset.py` resolves both via
the surviving dynamic symbol table: `QObjectPrivate::ConnectionData::deleteOrphaned(...)`
and `QObjectPrivate::connect(...)` respectively — the first confirms this
is genuinely the same `deleteOrphaned` class documented throughout this
section (not a misdiagnosis), the second is new: a crash inside
`QObject::connect()` itself, most likely wiring up a freshly-constructed
scanner/loader worker's signals. Working theory: one underlying
cross-thread race corrupts a `QObject`'s connection-list bookkeeping once,
and every previously-reported offset (`deleteOrphaned`, `connect`,
`QSocketNotifier::setEnabled`/`::type()`, unresolved raw addresses) is
just wherever that already-damaged structure gets touched next — not 20
independent bugs. Not yet fixed: neither capture had telemetry enabled, so
there's no Python-level correlation for which specific `.connect()` call
site was involved. If you hit this again, reproduce with
`IMAGE_TOOLKIT_TELEMETRY=1 debug/run_with_gdb.sh` (now also captures a
core dump) and start from `debug/telemetry_analyzer.py`'s report before
writing another speculative fix.

**Update (2026-08-01, Addendum 23) — video-directory scanning removed
entirely; crash confirmed gone by live testing.** A further attempted fix
(disconnect worker signals before teardown) made the crash *more*
reliable, not less — first video-directory browse instead of needing
rapid switches. After 23 rounds, none of which closed this crash class,
the decision was made to stop patching and remove the feature instead:
`VideoScannerWorker` (directory scan + thumbnail generation for video
files) was deleted entirely, along with `VideoLoaderWorker`/
`BatchVideoLoaderWorker` (a separate, never-crash-implicated video
thumbnail loader used by every gallery tab) for consistency. Only image
directory scanning remains anywhere in the app. **Live-tested and
confirmed**: the user's exact original repro (browse a directory, then
immediately browse a different one) no longer crashes — first time in 23
rounds. Known accepted gap: video files are no longer discovered/
thumbnailed anywhere in the app until a from-scratch replacement is
built (a leading candidate: `VideoLoaderWorker`'s `QRunnable`/
`QThreadPool` architecture, which was never implicated in this crash
class, unlike `VideoScannerWorker`'s bespoke `QThread` + internal
executor). See Addendum 23 in the crash doc for full scope.

**Update (2026-08-01, Addendum 24) — video thumbnail scanning
re-implemented.** Directory *scanning* and thumbnail *generation* are now
separate concerns. `VideoScannerWorker` was rewritten as a scan-only
`QThread` modeled on `ImageScannerWorker` (no internal executor, no
decode work inside `run()`). Thumbnail generation reuses the restored
`VideoLoaderWorker`/`BatchVideoLoaderWorker` `QRunnable`/`QThreadPool`
workers, never implicated in this crash class. Wallpaper tab sequences
the video scan strictly after the image scan settles (never concurrent);
Extractor tab dispatches a single `BatchVideoLoaderWorker` per scan,
guarded by a generation counter instead of a persistent worker reference.
A second, unrelated segfault (`self.sender()` on an already-destroyed
gallery widget, same crash *class*, different code path) was found and
fixed with `Shiboken.isValid(self)` guards while verifying this change.
Not yet live-tested against a real directory-switch repro — see Addendum
24 in the crash doc.

Full diagnosis: `.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`.

---

## <a id="qt-multimedia--video-playback-decode-failures"></a>Qt Multimedia / Video Playback Decode Failures

### AV1 video shows a blank frame + `Failed to get pixel format` / `Get current frame error` spam

**Symptom:** Loading an AV1-encoded video in the Extractor tab's internal player shows a solid blank/black frame. The console repeats, once per frame:
```
[av1 @ 0x...] Failed to get pixel format.
[av1 @ 0x...] Get current frame error
```
Playback position still advances (the demuxer is fine), but nothing renders. Other codecs (H.264, HEVC, VP9) are unaffected. Not a crash — the process stays alive.

**Root cause:** `backend/main.py` sets `QT_FFMPEG_DECODING_HW_DEVICE_TYPES` to steer Qt's FFmpeg backend away from hardware video decode (originally added to keep VA-API's `iHD_drv_video.so` from loading next to JPype's JVM — see root cause #2/#3 above). Qt's own docs say an empty/`","` value should disable hardware decode entirely, but on this Qt/FFmpeg build that value does **not** reliably do that — VA-API context creation is still probed, and when it fails (or is skipped), the backend falls through to CUDA/NVDEC. This system's Qt-bundled FFmpeg has a broken `av1_cuvid` decoder for this content (10-bit "Main" profile `yuv420p10le` AV1), so every frame fails pixel-format negotiation. Confirmed empirically by toggling the env var across ~15 repeated loads: `""`/`","` failed on nearly every run; leaving the var unset, or restricting it to `"cuda"` explicitly, decoded correctly every time.

A related, separate failure mode was also reproduced during investigation: heavy **concurrent GPU video decode from other processes** (e.g. a browser with several video tabs open) can exhaust the GPU's limited hardware decode-session pool, causing the exact same symptom intermittently even with a healthy config. This is a real hardware/driver limit, not something the env var can fix — if it happens only occasionally and correlates with heavy concurrent GPU video use elsewhere, that's this second cause, not the config bug above.

**Fix:** In `backend/main.py`, set the decode restriction to `"cuda"` specifically, not `""` or `","`:
```python
os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "cuda")
```
This keeps VA-API from ever being the *selected* decode device (preserving the original JVM-safety intent) while avoiding the "fully disabled" code path that was actually broken. Verify with:
```bash
QT_LOGGING_RULES="qt.multimedia.ffmpeg.hwaccel=true" python backend/main.py
```
— the enumeration log line (`Checking HW context: vaapi ... Using above hw context.`) appears regardless of this setting in this Qt build (that step seems unconditional), but per-codec device *selection* does respect it, which is what actually matters here.

---

## <a id="external-api-failures-jikan--myanimelist-auto-fill"></a>External API Failures (Jikan / MyAnimeList Auto-Fill)

### "Auto-Fill from MAL" fails with `Network error: 504 Server Error: Gateway Time-out`

**Symptom:** Clicking "Auto-Fill from MAL" in the Series Listings detail panel shows a `QMessageBox.critical` with a message like:
```
Network error: 504 Server Error: Gateway Time-out for url: https://api.jikan.moe/v4/anime?q=<title>&limit=1
```
It may work for some titles and not others, and can persist across many manual retries over minutes.

**Root cause:** This is **not a bug in this codebase** — confirmed by bypassing `jikan_client.py` entirely and hitting the Jikan API directly with `curl`. `api.jikan.moe` is a caching proxy in front of MyAnimeList, not MAL itself: a title someone has searched recently is served instantly from cache, but a cache miss makes Jikan scrape MAL live, and *that* leg is what fails. Direct evidence gathered during investigation:
- `GET https://api.jikan.moe/v4/anime/1` (cached, by ID) → `200 OK`
- `GET` request to `api.jikan.moe/v4/anime?q=<uncached title>` → `504`, `{"message": "Jikan failed to connect to MyAnimeList. MyAnimeList may be down/unavailable or refuses to connect"}`, persisting across 6+ retries over 20+ seconds regardless of query params
- `GET` request to `myanimelist.net/anime.php?q=<same title>` (MAL directly, bypassing Jikan) → `200 OK`, title found fine

So MAL itself is reachable and has the title; Jikan's own scraper currently can't reach MAL for this specific (likely rarely-searched) query. Even mainstream titles 504'd if not already hot in Jikan's cache — this is a known, recurring pattern in Jikan's own issue tracker (e.g. `jikan-me/jikan#357`, `#381`), not something client-side retries can paper over.

**Fix:** No client-side fix removes the underlying Jikan↔MAL outage, but `jikan_client.py` now does two things:
1. Retries transient gateway errors (429/502/503/504, connection errors) with exponential backoff (`_get_with_retry`), which does help genuine short blips.
2. If the search call still fails, surfaces an accurate, actionable message instead of a bare `504 Gateway Time-out` — explicitly stating this is a Jikan↔MAL outage for this title, not a search or app problem, and suggesting the user try again later or search the title on myanimelist.net directly first (which sometimes "warms" Jikan's cache for the next lookup).

**Workaround — switch the Auto-Fill method:** Since Jikan's cache-miss path is the actual point of failure, switching to a different data source sidesteps it entirely. Go to **Settings > System and Logging > MyAnimeList Auto-Fill** and change "Auto-Fill Method" to:
- **Direct Website Scraping** — scrapes myanimelist.net directly (`mal_scrape_client.py`), no API key needed, gets full data including characters/staff. Slower (2-3 sequential page loads) and slightly more fragile to MAL markup changes, but bypasses Jikan entirely — confirmed working against titles that 504 on Jikan.
- **Official MyAnimeList API** — hits `api.myanimelist.net` directly (`mal_api_client.py`), needs a free client ID from https://myanimelist.net/apiconfig (set `MAL_CLIENT_ID` or `backend/config/api_keys.yaml` → `myanimelist.client_id`). No characters/staff data (not exposed by this API), but fast and reliable for core metadata.

Dispatched through `backend/src/web/clients/mal_dispatcher.py`; the chosen method persists via `AppSettings.mal_fetch_method()` (`QSettings`, key `preferences/mal_fetch_method`).

---

## ASP Pipeline Errors

### `ValueError: Not enough inliers` / `alignment_failed`

**Context:** Stage 7b (bundle adjustment / geometric filter) or Stage 8 (ECC refinement) rejects too many edges.

**Diagnosis:**
```bash
# Run with verbose logging
ASP_LOG_LEVEL=DEBUG python -m backend.src.animation.pipeline <args>

# Check the stage trace JSON (written to output dir)
cat output/trace.json | python -m json.tool | grep -A5 "stage_7"
```

**Common causes and fixes:**

| Cause | Fix |
|-------|-----|
| Animated hold frames not filtered | Enable dHash hold detection: `ASP_HOLD_DHASH_THRESH=4` |
| Horizontal scroll detected as vertical | Check `_detect_scroll_axis` output in trace; ensure frames are vertically scrolling content |
| Feature matching failed (blank areas, solid colour) | Lower `ASP_POSE_WINDOW_PX` or switch to phase-correlation-only mode |
| Too few adjacent edges survive quality gate | Lower `HIGH_CONF_EDGE_THRESH` from 0.65 to 0.55 in `asp_config.toml` |

---

### Pipeline falls back to SCANS on every test

**Symptom:** `fallback_reason` in benchmark results is always `alignment_failed:*` or `ratio=*`.

**Diagnosis:** Check `ASP_COV_MIN_MULTI_PCT` — if the canvas coverage gate is too strict, multi-frame coverage is below 30% and the pipeline falls back immediately.

```bash
# Relax coverage gate
ASP_COV_MIN_MULTI_PCT=0.15 python -m backend.src.animation.pipeline <args>
```

Other common causes:
- `STATIC_EDGE_MIN_DISP_PX=50` is too high for slow-scroll content → lower to 20.
- All frames are nearly identical (animation hold) → enable temporal variance filter: `ASP_TEMPORAL_VAR_THRESH=1e-3`.

---

### Ghost / double-image artifact in output

**Symptom:** Characters appear doubled or blurred at the seam boundary.

**Diagnosis:**
```bash
# Check ghosting score in benchmark output
python backend/benchmark/run_single.py --test-id <ID> | grep ghosting
```

**Fixes in priority order:**

1. Enable bg-mask-aware DSFN ramp (S20, default ON): `ASP_SGM_PROXY=0` to rule out SGM proxy interference.
2. Check `_seam_gate_vote_counts` in trace — if the ensemble gate is not firing, the seam cost map may be routing through foreground.
3. Try Poisson seam blending: `ASP_POISSON_SEAM=1` (adds 1–3 s/seam, CPU).
4. Increase minimum feather: set `FEATHER_MIN=120` in `asp_config.toml`.

---

### `RuntimeError: Canvas too large` / `CANVAS_MAX_DIM exceeded`

**Cause:** The computed panorama canvas exceeds `CANVAS_MAX_DIM` (set in `backend/src/constants/animation.py`).

**Fix:** Reduce the input image resolution before stitching, or increase the constant (memory-bound):

```python
# backend/src/constants/animation.py
CANVAS_MAX_DIM = 32768  # increase from default 16384
```

---

### `asp_config.toml` key not taking effect

**Cause:** Environment variables take precedence over TOML config by default (`setdefault` semantics in `load_asp_config`).

**Fix:** Unset the environment variable or use `override_env=True` in the loader:

```python
from backend.src.animation.config import load_asp_config
load_asp_config("backend/config/asp_config.toml", override_env=True)  # TOML wins over env
```

Or: set the value directly in the environment (env always wins by default):
```bash
unset ASP_HOLD_THRESHOLD
```

---

## <a id="cpp-pybind11-build-failures"></a>C++ / pybind11 Build Failures

### `ModuleNotFoundError: No module named 'base'`

**Cause:** The pybind11 C++ extension has not been compiled for the active Python environment.

**Fix:**
```bash
source .venv/bin/activate
just build-base
```

If CMake or pybind11 is not installed:
```bash
sudo apt install cmake libopencv-dev
pip install pybind11
```

---

### `cmake` fails: `Could not find pybind11`

**Cause:** pybind11 Python package is not installed in the active venv.

**Fix:** Activate the correct environment:
```bash
source .venv/bin/activate
pip install pybind11
just build-base
```

---

### `cmake` fails: `error: linking with cc failed`

**Ubuntu/Debian — missing system libraries:**
```bash
sudo apt install -y \
  libssl-dev pkg-config \
  libpqxx-dev \
  nlohmann-json3-dev \
  libopencv-dev
```

**macOS:**
```bash
brew install openssl@3 pkg-config opencv
export PKG_CONFIG_PATH="$(brew --prefix openssl@3)/lib/pkgconfig"
```

---

### `OpenMP` threads panic in tests

**Symptom:** Tests in `backend/test/animation/` hang with deadlock-like behaviour.

**Cause:** Multiple OpenMP thread pools being initialised in parallel test workers.

**Fix:** Run tests with `--skip-gpu` and the `pytest-xdist` work-steal distribution:
```bash
pytest backend/test/animation/ -n auto --dist=worksteal --skip-gpu
```

---

## Hydra CLI Configuration Errors

### `HydraException: Key 'command' not found in config`

**Cause:** The `command` key is missing from `backend/config/base.yaml` or was not passed on the CLI.

**Fix:** Pass the command explicitly:
```bash
python -m backend.dispatcher command=train
```

Or add a default in `backend/config/base.yaml`:
```yaml
defaults:
  - _self_

command: train
```

---

### `omegaconf.errors.ConfigAttributeError: Key 'xyz' is not in struct`

**Cause:** Hydra is in strict struct mode and you are trying to add an undeclared key.

**Fix:** Declare the key in the config schema or use `+` prefix to append:
```bash
python -m backend.dispatcher +new_key=value
```

---

### `config_path` resolution failure: `Expected config_path ... to be under ...`

**Cause:** The `config_path` in `@hydra.main` is relative to the Python file, not the working directory.

**Fix:** Always run the dispatcher from the project root, or use an absolute path:
```bash
# From project root
python -m backend.dispatcher

# NOT: python backend/dispatcher.py (wrong cwd)
```

---

### ComfyUI not starting (`command=comfyui`)

**Check 1:** Is ComfyUI installed?
```bash
ls ComfyUI/main.py
```

**Check 2:** Port conflict:
```bash
lsof -i :8188
python -m backend.dispatcher command=comfyui comfyui.port=8189
```

**Check 3:** GPU not available to ComfyUI:
```bash
python -m backend.dispatcher command=comfyui comfyui.cpu=true
```

---

## <a id="database-postgresql--pgvector"></a>Database (PostgreSQL / pgvector)

### "DB Offline" / red indicator in GUI header

**Check 1:** PostgreSQL is running:
```bash
sudo systemctl status postgresql   # Linux
brew services list                 # macOS
```

**Start if stopped:**
```bash
sudo systemctl start postgresql    # Linux
brew services start postgresql@14  # macOS
```

**Check 2:** Credentials in `.env` match the database:
```bash
psql postgresql://toolkit_user:your_password@localhost:5432/image_toolkit
```

**Check 3:** pgvector extension installed:
```sql
\c image_toolkit
SELECT * FROM pg_extension WHERE extname = 'vector';
-- If empty: CREATE EXTENSION IF NOT EXISTS vector;
```

---

### `pgvector` extension not found after install

```bash
# Rebuild pgvector against the running PostgreSQL version
cd /tmp
git clone --branch v0.5.0 https://github.com/pgvector/pgvector.git
cd pgvector
make PG_CONFIG=$(pg_config --bindir)/pg_config
sudo make install PG_CONFIG=$(pg_config --bindir)/pg_config
```

Then in psql:
```sql
\c image_toolkit
CREATE EXTENSION IF NOT EXISTS vector;
```

---

### Migration fails: `relation already exists`

**Cause:** A previous migration run was interrupted partway through.

**Fix:** Check which migrations have already been applied:
```bash
psql postgresql://toolkit_user:pass@localhost:5432/image_toolkit -c "SELECT * FROM _sqlx_migrations ORDER BY version;"
```

Manually mark the failed migration as complete if it was partially applied, or roll it back:
```bash
cd frontend/src-tauri
sqlx migrate revert
sqlx migrate run
```

---

## <a id="tauri--frontend-build-failures"></a>Tauri / Frontend Build Failures

### `webkit2gtk-4.1 not found`

```bash
sudo apt install libwebkit2gtk-4.1-dev
```

### `Cannot find module 'react-dom/client'`

```bash
cd frontend
npm install --save-dev @types/react-dom
```

### `failed to run custom build command for 'openssl-sys'`

```bash
# Ubuntu/Debian
sudo apt install libssl-dev pkg-config

# macOS
brew install openssl@3
export PKG_CONFIG_PATH="$(brew --prefix openssl@3)/lib/pkgconfig"
```

### TypeScript type errors from `@tauri-apps/api`

**Cause:** `@tauri-apps/api` version in `package.json` does not match the `tauri` crate version in `src-tauri/Cargo.toml`.

**Fix:** Upgrade both to the same version simultaneously:
```bash
cd frontend
npm install @tauri-apps/api@<version>
# Update src-tauri/Cargo.toml tauri = "<version>"
cargo update -p tauri
```

### Electron `app.asar` not found / blank window

```bash
cd frontend
npm run build          # Build React first
npm run start-electron # Then launch Electron
```

Do not run `npm run electron` without first building React — it points to `build/index.html` which does not exist until after `npm run build`.

---

## Mobile Build Failures

### Android: `SDK location not found`

**Fix:** Set `ANDROID_HOME` in `local.properties` (not committed to git):
```
# local.properties
sdk.dir=/home/<user>/Android/Sdk
```

### Android: `Execution failed for task ':app:compileDebugKotlin'`

Check the Kotlin / AGP compatibility matrix. The AGP (Android Gradle Plugin) version in `build.gradle.kts` must match the Gradle version in `gradle/wrapper/gradle-wrapper.properties`.

```bash
./gradlew --version  # shows Gradle version
# Check https://developer.android.com/studio/releases/gradle-plugin for AGP compatibility
```

### Android: Build succeeds but app crashes on launch

Enable verbose ADB logging:
```bash
adb logcat -s "ImageToolkit" "*:E"
```

Common cause: `ANDROID_SDK_ROOT` not available at runtime, causing `JNI_OnLoad` to fail for native libraries.

### iOS: `No signing certificate found`

**Fix:** Open Xcode → Preferences → Accounts → add your Apple ID → download certificates. Then re-run `xcodebuild`.

For CI builds (no interactive Xcode): use `xcodebuild CODE_SIGN_IDENTITY="" CODE_SIGNING_REQUIRED=NO` for simulator-only builds.

### iOS: `Module 'ImageToolkit' not found` in tests

```bash
xcodebuild clean -project app/ImageToolkit.xcodeproj -scheme ImageToolkit
xcodebuild test   -project app/ImageToolkit.xcodeproj -scheme ImageToolkit \
  -destination 'platform=iOS Simulator,name=iPhone 15'
```

---

## Test Suite Issues

### Tests hang / system becomes unresponsive

**Cause:** One of the §3.10 test-suite freeze root causes. All 5 are fixed; see `docs/moon/roadmaps/performance.md §3.10–§3.15` for the full analysis.

**Safe invocation:**
```bash
# Fast, no GPU — always safe
pytest backend/test/animation/ --skip-gpu

# Parallel workers — safe after §3.12 fix
pytest backend/test/animation/ -n auto --dist=worksteal --skip-gpu

# Full suite (all backend modules) — requires §3.15 non-animation audit
# Only run after auditing all non-animation module imports for ML singletons
pytest backend/test/ --skip-gpu -n auto
```

**Never run:**
```bash
pytest backend/test/          # without --skip-gpu on machines with GPU
pytest backend/test/gui/      # PySide6 tests require a display; drain RAM
```

### `ImportError` collecting tests

**Cause:** A module-level import failed (possibly a missing optional dependency).

**Fix:**
```bash
# Find the failing import
pytest backend/test/animation/ --collect-only 2>&1 | grep "ERROR\|ImportError"

# Check import times to identify which module is slow/failing
python backend/src/utils/check_import_times.py
```

### `pytest-forked` not found

```bash
pip install pytest-forked pytest-xdist
```

---

## Developer Best Practices

1. **Signal Safety** — Use `deleteLater()` on all `QObject` members of `QRunnable` when `setAutoDelete(True)` is set.
2. **Graceful Tab Exit** — Always override `closeEvent` and halt active `QThread` / `QProcess` workers before the widget is destroyed.
3. **Bridge Synchronisation** — Serialise all JPype (JVM) and pybind11 (C++) calls from worker threads using the appropriate lock.
4. **No Native Dialogs on Linux** — Pass `QFileDialog.Option.DontUseNativeDialog` to every `QFileDialog` call while JPype is active.
5. **No `QWebEngineView`** — Open URLs via `QDesktopServices.openUrl()`. The Chromium/Vulkan renderer conflicts with the JVM.
6. **Lazy ML imports** — Never import `diffusers`, `transformers`, `torch`, or large ML libraries at module level in `animation/` modules. Use lazy imports inside functions.
7. **Thread-local GPU state** — Do not share CUDA tensors across thread pool workers. Each QRunnable that uses a GPU model should have its own `torch.no_grad()` context.
8. **Widget reuse** — Call `setParent(None)` on a widget before deleting/replacing a container it's about to be reparented out of; deleting the container deletes its children first.
9. **Qt Multimedia hw-decode env vars** — Prefer no override, or an explicit device name (e.g. `"cuda"`), over `""`/`","` for `QT_FFMPEG_DECODING_HW_DEVICE_TYPES`. The "disable entirely" syntax is unreliable on some Qt/FFmpeg builds — see the Qt Multimedia section above.
