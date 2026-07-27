# Desktop App Crash — `QObjectPrivate::ConnectionData::deleteOrphaned` SIGSEGV (2026-07-27)

## Report

Crash when browsing/scanning a directory with videos after browsing/scanning
a directory with images (possibly also after navigating/changing pages
before switching). Observed in the Extractor and Wallpaper tabs; suspected
present in other thumbnail-gallery tabs too. Produced
`hs_err_pid79171.log` — a JVM ("hs_err") crash log, present because JPype's
embedded JVM (started at login for `VaultManager`) installs a process-wide
SIGSEGV handler that reports *any* thread's crash, not just Java ones. The
crashing thread itself is plain native/Qt code, not JVM/JPype code — this is
not the already-documented [[jvm_native_lib_conflicts]] pattern (native
dialog/GTK, QWebEngineView/Chromium, QMediaPlayer/FFmpeg-VA-API), it's a
separate, pure-Qt threading race that happens to be reported via the same
mechanism.

## Crash signature

```
SIGSEGV (0xb) at pc=..., si_code: 1 (SEGV_MAPERR), si_addr: 0x0000000000000001
Problematic frame:
C  [libQt6Core.so.6+0x1e73ae]  QObjectPrivate::ConnectionData::deleteOrphaned(...)
```

`deleteOrphaned` is Qt's internal cleanup of a signal/slot connection list.
A near-null faulting address plus this specific frame is the classic
signature of a cross-thread race on a `QObject`'s connection bookkeeping —
one thread emitting a signal (or a `QObject` destructing/being scheduled for
deletion) while another thread concurrently touches the same connection
list.

## Root cause

`gui/src/classes/base/gallery_base.py`'s `common_start_chunked_load()`
dispatches `ImageLoaderWorker`/`BatchImageLoaderWorker`/`VideoLoaderWorker`
instances (`QRunnable`, `setAutoDelete(True)`) onto the process-global
`QThreadPool.globalInstance()`, each with its own `QObject`-based `signals`
wrapper connected to gallery slots via the default (auto → queued,
cross-thread) connection type.

Both concrete gallery base classes' `cancel_loading()` — the method called
on every directory switch, tab switch, and page navigation, via
`clear_galleries()` (`AbstractClassTwoGalleries`, used by
Extractor/Convert/Delete/Merge tabs) and `clear_gallery_widgets()`
(`AbstractClassSingleGallery`, used by the Wallpaper tab) — only did
**best-effort** cancellation:

```python
for worker in list(self._active_workers):
    with contextlib.suppress(Exception):
        worker.stop()          # sets a Python _is_cancelled flag, checked
                                # only at a few checkpoints inside run()
self._active_workers.clear()
if hasattr(self, "thread_pool"):
    self.thread_pool.clear()   # only removes NOT-YET-STARTED queued tasks
```

Neither `.stop()` nor `.clear()` affects a worker **already executing** on a
pool thread — it keeps running, and keeps emitting its `result`/
`batch_result` signals, to whatever gallery slots it was connected to.
Immediately after calling `cancel_loading()`, both `clear_galleries()` and
`clear_gallery_widgets()` proceed straight to tearing down the gallery's
thumbnail widgets (`item.widget().deleteLater()` in a loop) with **no wait**
for those still-running workers to actually finish.

This is a genuine, unsynchronized race: a leftover worker from the previous
scan (e.g. the image directory) can still be mid-`run()` on a pool thread
delivering a queued cross-thread signal to a gallery slot at the exact
moment the main thread is tearing down/rebuilding the connections and
widgets that signal targets — corrupting Qt's `ConnectionData` and crashing
in `deleteOrphaned`.

**Why this needed both a base-class bug AND matches the user's report
exactly:**
- Same root cause lives in `gallery_base.py`/both concrete subclasses, so it
  affects every tab built on either (Extractor, Wallpaper, and per project
  architecture notes also Convert/Delete/Merge) — matching "I have reason to
  believe it may also be present in other tabs with thumbnail galleries."
- Video thumbnail extraction is heavier per-item than image decode, widening
  the window in which a previous batch's workers are still in flight when a
  new (video) scan's `clear_galleries()` call tears things down — consistent
  with the reported image → video trigger, though the underlying race isn't
  actually video-specific; it's a timing-window issue that any slower/larger
  batch widens.
- **A previous fix for the *exact same* race already exists**, just scoped
  too narrowly: `AbstractClassTwoGalleries.closeEvent()` already calls
  `self.thread_pool.waitForDone(500)` after `cancel_loading()`, with the
  comment *"Ensure signals don't fire to a destroyed object"* — but only for
  the tab-close path, not the much more frequently hit
  directory-switch/page-navigation path that actually triggered this crash.

## Fix

Move the wait into `cancel_loading()` itself, in both base classes, right
after `self.thread_pool.clear()` — this covers every caller (both
`clear_galleries()`/`clear_gallery_widgets()` and any tab-specific override
that calls `super().cancel_loading()`, e.g. `ExtractorTab.cancel_loading()`),
not just the two call sites found by direct inspection:

```python
if hasattr(self, "thread_pool"):
    self.thread_pool.clear()
    self.thread_pool.waitForDone(500)
```

Same 500ms value as the existing `closeEvent()` precedent, for consistency.
`self.thread_pool` is the process-global `QThreadPool.globalInstance()`, so
this wait can briefly block on unrelated in-flight tasks elsewhere in the
app — an accepted tradeoff already present in the `closeEvent()` case;
applying the same already-vetted pattern to the same classes' more common
path is a direct, low-risk extension, not a new risk category. Thumbnail
loads are typically sub-second per chunk, so the practical UI impact is a
brief, bounded pause, not a hang.

Files changed:
- `gui/src/classes/abstract_class_two_galleries.py::cancel_loading()`
- `gui/src/classes/abstract_class_single_gallery.py::cancel_loading()`

## Verification

- Syntax-checked both files.
- `gui/test/image/test_gallery_classes.py --run-gui`: 17/17 passing
  (unchanged from before the fix).
- `gui/test/core/test_extractor_drag_preview.py --run-gui`: 4/6 passing —
  the 2 failures are pre-existing and unrelated (a stale mock-patch
  `AttributeError` on `_hide_scrub_popup`), confirmed identical with the fix
  stashed out.
- `gui/test/core/test_core_tab.py --run-gui`: times out both with and
  without the fix — pre-existing, unrelated to this change, not
  investigated further here (out of scope for this crash fix).
- **Not verified**: no way to reproduce the exact race deterministically in
  this environment (it's a genuine timing-dependent concurrency bug); the
  fix directly closes the identified missing-synchronization window using
  the same pattern this project already shipped and trusted for the
  tab-close case. A live reproduction attempt (browse a large image
  directory, immediately switch to a video directory before thumbnails
  finish loading, repeat) would be the natural human-side confirmation step.

## Addendum (same day) — crash recurred, the 500ms bound was the bug

The user confirmed the crash still happened after the fix above shipped —
no longer on the *first* image↔video switch, but after several repeated
back-and-forth switches. New crash log: `hs_err_pid116664.log`, a different
signature:

```
SIGSEGV (0xb) ..., si_code: 2 (SEGV_ACCERR), si_addr matches RIP
Current thread (...): JavaThread "main"   [_thread_in_native, ...]
C  0x00005a94b51c0f70          <- no resolved symbol
```

Unlike the first crash (a clean, symbol-resolved frame inside
`libQt6Core.so.6`'s `deleteOrphaned`), this one has **no resolved symbol**
and the instruction bytes at the fault address decode as floating-point-like
data, not code — the CPU jumped into non-code memory (`SEGV_ACCERR`, not
`SEGV_MAPERR`: the page is mapped, just not executable at that offset — e.g.
heap memory reused for something else). Crucially, **the crashing thread is
the main thread** — JPype attaches the thread that calls `startJVM()` as the
JVM's own "main" JavaThread, and that's the same OS thread running the Qt
event loop.

This is still the same underlying bug, not a new one: a worker's
`.emit()` on a pool thread only *posts* a queued-connection event; the
actual slot delivery happens later, when the *main* thread's event loop
processes that event. If the connection's target has already been
corrupted/freed by delivery time, the crash naturally happens on the main
thread, at delivery time — consistent with everything observed here,
just a different snapshot of the same missing-synchronization race
depending on exactly what memory got reused in between.

**The actual bug in the first fix**: `self.thread_pool.waitForDone(500)` is
a *bounded* wait — `QThreadPool::waitForDone(msecs)` returns after either
all tasks finish OR `msecs` elapses, whichever comes first. `VideoLoaderWorker`
(`gui/src/helpers/video/video_loader_worker.py`) shells out to
`ffmpegthumbnailer`/`ffmpeg` subprocesses
(`gui/src/helpers/video/video_thumbnailer.py`), each with its own **15-second**
subprocess timeout, and the worker tries up to three of these in sequence on
failure (ffmpegthumbnailer → ffmpeg@5s → ffmpeg@0s) — up to ~45s worst case
on a single slow/corrupt video file. A 500ms bound times out long before any
of that finishes, so the wait returns while the video worker is *still
running*, and the caller proceeds to tear down gallery widgets anyway —
reintroducing the *exact* race the wait was meant to close, just requiring a
slower worker (video, not image) and enough repeated attempts to hit the
timing window. This matches the user's report precisely: harder to hit, not
impossible.

**Corrected fix**: changed the bound from `500` to `-1` (Qt's own sentinel
for "wait until the pool is actually idle, no timeout") in both base
classes, replacing the previous fixed-timeout constant. Picking a *longer*
fixed number (e.g. 20s) would only have repeated the same mistake with lower
odds — the real worst case (~45s, or worse on a truly hanging subprocess)
can't be bounded reliably in advance. Workers are still asked to
cooperatively cancel first (`.stop()`), so in practice this returns quickly;
the accepted tradeoff is a rare, subprocess-timeout-bounded UI pause instead
of a crash, which is the correct trade for a crash-prevention fix.

Files re-changed: same two base classes, `_WORKER_DRAIN_TIMEOUT_MS` constant
added (`= -1`) and used at all three call sites (both `cancel_loading()`s
plus `AbstractClassTwoGalleries.closeEvent()`, which had the same 500ms bug
independently).

**Still not independently verified against a live reproduction** — same
caveat as before, now with a stronger, less guessable fix.

## Addendum 2 (2026-07-27→28) — two more, structurally separate instances of the identical pattern

The user reported the crash a third and fourth time even after the
unbounded-wait fix above (`hs_err_pid131317.log`, then
`hs_err_pid138049.log` — the latter specifically reported as happening in
the **Wallpaper tab**, on the very first directory switch right after app
launch, not requiring repeated back-and-forth). This meant the fix above,
while correct for what it covered, did not cover the actual code paths these
crashes came from.

**Root cause: this codebase has (at least) three independent,
hand-rolled "stop the previous scan" implementations, and the base-class
fix only touched one of them.** `cancel_loading()` in the two gallery base
classes only knows about `QRunnable` tasks tracked in `_active_workers`/
`thread_pool` (`ImageLoaderWorker`, `BatchImageLoaderWorker`,
`VideoLoaderWorker`). Two other, completely separate code paths use bespoke
`QThread` subclasses (`ImageScannerWorker`, `VideoScannerWorker`) for
directory-level scanning, each with its own inline stop/wait logic that
`cancel_loading()` has no knowledge of and does not wait for:

1. **`ExtractorTab.scan_directory()`** (`gui/src/tabs/core/extractor_tab.py`,
   the video-scan path) — stopped/waited for the previous `vid_scanner_worker`
   *after* clearing `source_path_to_widget`/`source_grid` via `deleteLater()`,
   using a bounded `wait(1000)`. Both the ordering (wait after teardown, not
   before) and the bound were wrong, independently of the base-class fix.
2. **`WallpaperCommonBase.populate_scan_image_gallery()`**
   (`gui/src/tabs/core/elements/common/wallpaper_common_base.py`) — same
   shape, for *both* `img_scanner_thread` (`ImageScannerWorker`, wait already
   unbounded but wrongly ordered) and `vid_scanner_worker`
   (`VideoScannerWorker`, bounded `wait(1000)`, wrongly ordered) — the
   stop/wait block ran *after* `clear_gallery_widgets()` and after
   `start_loading_gallery()` had already begun the new directory's load.
   This is the confirmed source of the Wallpaper-tab crash, including the
   "first switch after launch" case: the previous session's auto-restored
   directory's scanner thread was still running when the user immediately
   browsed a new one.
3. `WallpaperCommonBase.closeEvent()` didn't stop `vid_scanner_worker` at
   all (only `img_scanner_thread`) — a related, narrower gap for the
   tab-close path, fixed alongside the others even though not directly
   implicated in the reported crashes.

**Fix**: in both `scan_directory()` and `populate_scan_image_gallery()`,
moved the previous scanner thread's stop-and-wait block to the *start* of
the method, before any widget teardown or new-load dispatch, and changed
every bounded `wait(1000)` to an unbounded `wait()` — same reasoning as
Addendum 1: `VideoScannerWorker`'s internal `ThreadPoolExecutor` can't be
force-killed mid-subprocess, and `concurrent.futures.ThreadPoolExecutor`'s
context-manager `__exit__` (which `run()` always passes through before
`finished` fires) already blocks until truly idle regardless of any earlier
non-blocking `shutdown()` call — so `.wait()` accurately reflects genuine
completion, it just needs to not be given a timeout short enough to give up
before that. `ImageScannerWorker` checks its cancellation flag on every
scanned filesystem entry (or delegates to a single fast C++ call with no
subprocess involved), so its already-unbounded wait was never the risky one
— only its *ordering* needed fixing.

**This may not be exhaustive.** The pattern (bespoke per-tab scanner thread,
inline stop/wait logic, no shared mechanism) suggests other tabs could have
the same shape; this pass fixed the three confirmed by an actual crash
report plus the one directly-adjacent gap in `closeEvent()`, not a
codebase-wide audit. If another gallery/tab is found to have its own
scanner-thread stop/wait logic outside `cancel_loading()`, apply the same
two checks: (a) does the stop/wait happen *before* any widget teardown or
new load, and (b) is the wait unbounded.

Files changed this round: `gui/src/tabs/core/extractor_tab.py`
(`scan_directory()`, `cancel_loading()`),
`gui/src/tabs/core/elements/common/wallpaper_common_base.py`
(`populate_scan_image_gallery()`, `closeEvent()`).

**Still not independently verified against a live reproduction.**
