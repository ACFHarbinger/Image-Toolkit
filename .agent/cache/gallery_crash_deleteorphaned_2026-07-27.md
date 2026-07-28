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

## Addendum 3 (2026-07-28) — cross-panel race, same repro, after round 3's fix already landed

A fifth crash report (`hs_err_pid155258.log`) with the **exact same repro**
as Addendum 2's Wallpaper case (app restarted with a directory restored
from the previous session, then immediately browsed a new video directory)
— but this time it happened *after* round 3's fix to
`populate_scan_image_gallery()`'s ordering was already committed. Crash
frame: `libQt6Core.so.6+0x1e74d5`, only ~0x127 bytes past the *original*
crash's `deleteOrphaned` offset (`+0x1e73ae`) — almost certainly the same
function, confirming the underlying race was still reachable through a
different path than the one already fixed.

**Root cause: the Wallpaper tab has two linked gallery instances
(`system_display`/`monitor_display`, `wallpaper_tab.py`) that share mutable
state and can be mid-teardown simultaneously.** `wallpaper_tab.py`
explicitly aliases `monitor_display._initial_pixmap_cache =
system_display._initial_pixmap_cache` (the same dict object, not a copy),
and wires each panel's `directory_scanned` signal to call the *other*
panel's `populate_scan_image_gallery(directory, emit_signal=False)`. Tracing
the actual startup sequence: `SystemDisplaySubTab.set_config()` (called
while restoring the previous session's saved directory) calls
`populate_scan_image_gallery(old_dir)`, which — via `directory_scanned` —
synchronously, recursively calls `monitor_display.populate_scan_image_gallery(old_dir, ...)`
too. Both panels end up with their own actively-running
`img_scanner_thread`/`vid_scanner_worker` for the old directory.

Round 3's fix made `populate_scan_image_gallery()` correctly stop-and-wait
for **its own** previous scanner threads before touching **its own**
widgets — sufficient for a single instance, but each panel only guarded its
own state. When the user then browses a *new* directory (13 seconds later,
per the crash log), whichever panel receives the click calls
`populate_scan_image_gallery(new_dir)`, which emits `directory_scanned`
*before* fully settling — and while that fix does stop this panel's own
threads first, the **peer** panel's own still-running threads (from the
startup restore, on the other side of the shared cache/signal link) were
never accounted for by this instance's guard at all. The peer's old
scanner thread remained free to write into the shared
`_initial_pixmap_cache` (or emit to widgets) while this instance concurrently
cleared/rebuilt that same shared dict and its own widget tree.

**Fix**: extracted the stop-and-drain logic into `_stop_scanner_threads()`,
and call it — at the very start of `populate_scan_image_gallery()`, before
even the `directory_scanned.emit()` that triggers the peer's own nested
call — on **both `self` and every entry in `self.linked_tabs`**. This
guarantees neither panel has a live scanner thread before either panel
touches the shared cache or either panel's widgets, regardless of which
panel's browse action started the chain, and regardless of the recursive
call ordering through the `directory_scanned` signal. Redundant calls (the
peer's own nested `populate_scan_image_gallery` re-invoking the now-already-
stopped threads' guard) are cheap no-ops.

File changed: `gui/src/tabs/core/elements/common/wallpaper_common_base.py`
only, this round — `ExtractorTab` has no equivalent linked-instance/shared-
cache structure, so its round-3 fix should not have the same gap, but
hasn't been independently re-audited for other forms of this same
cross-instance pattern.

**Still not independently verified against a live reproduction** — this is
now the fourth iteration of this fix; if it recurs again, the shared-cache/
linked-panel architecture itself (not just the stop/wait ordering) may need
reconsidering rather than another instance-level patch.

## Addendum 4 (2026-07-28) — the actual root cause: a known, already-documented startup race, not the scanner-thread ordering at all

The user provided the full stdout leading up to `hs_err_pid155258.log` for
the first time, and it changes the diagnosis substantially. Immediately
before the crash:

```
qt.multimedia.ffmpeg: Using Qt multimedia with FFmpeg version 7.1.1 ...
INFO     root: Logging reconfigured from preferences: ...
QSocketNotifier: Socket notifiers cannot be enabled or disabled from another thread
free(): invalid pointer
error: Recipe `python` was terminated on line 30 by signal 6
```

`free(): invalid pointer` is glibc's malloc corruption detector catching a
bad `free()` call and calling `abort()` (SIGABRT, signal 6) — this is
**heap corruption**, a stronger and more specific signal than any of the
SIGSEGV frames alone gave. And critically, **the exact `QSocketNotifier`
message is already a known, documented issue in this codebase** — found by
grepping for it directly:

- `gui/src/helpers/core/similarity_scan_worker.py` (module docstring):
  *"a plain `QThread` + `moveToThread` would start the default per-thread
  event loop (`exec()`), which on Linux/glib creates an event dispatcher
  with socket notifiers in a secondary thread. With the JPype JVM loaded
  in-process that collides fatally ('QSocketNotifier: ... from another
  thread' → SIGSEGV in libQt6Core)."*
- `gui/src/tabs/core/extractor_tab.py:311-320` (already fixed): *"Constructing
  QAudioOutput eagerly for every tab at app startup ... triggers the
  platform audio backend (PipeWire) to probe devices on its own thread;
  that probe can race Qt's event loop startup and raise 'QSocketNotifier:
  ...', cascading into heap corruption and a SIGABRT. Deferring
  construction until a video is actually opened avoids doing this during
  the fragile startup window."*

**This is the same underlying Qt/PipeWire/JPype startup race documented and
already fixed once (for `ExtractorTab`'s `QAudioOutput`), triggered here
through a different path: starting new `QThread`s
(`img_scanner_thread`/`vid_scanner_worker`, via `SystemDisplaySubTab.set_config()`
auto-restoring the previous session's directory) *synchronously during
`MainWindow`/tab construction*, before the Qt event loop has started
processing events at all.** `ExtractorTab`'s module-level `QtMultimedia`
import (needed for its own `QMediaPlayer`) triggers Qt's FFmpeg/PipeWire
backend registration around the same startup moment (`ExtractorTab` and
`WallpaperTab` are both constructed in `MainWindow.__init__`, close
together) — if the Wallpaper tab's auto-restore *also* starts new QThreads
during this exact window, the two race, corrupting the heap. This
retroactively re-frames rounds 2-4's fixes (the scanner-thread stop/wait
ordering, and the linked-panel synchronization) as real, worthwhile
correctness fixes for a genuine race in their own right — but not the
actual trigger of *this specific* crash log. They likely reduced how often
this crash class surfaces (fewer overlapping thread-lifecycle events) without
addressing its root cause.

**Fix**: deferred `SystemDisplaySubTab.set_config()`'s directory-restore
call — `self.populate_scan_image_gallery(config["scan_directory"])` — with
`QTimer.singleShot(250, ...)`, so the actual scan (and the `QThread` starts
it triggers) happens after the event loop is running, not synchronously
during tab construction. `MonitorDisplaySubTab` needed no separate fix: it
doesn't restore a directory itself, only receiving it via
`system_display`'s `directory_scanned` signal, which now only fires once
the deferred call executes.

**Caveat, stated plainly**: 250ms is a reasonable, precedented deferral
(matching the common `QTimer.singleShot(0, ...)` Qt idiom for "wait for the
event loop"), not a guaranteed fix — if PipeWire's own probe genuinely takes
longer than that in a worse environment, the race window could still be hit,
just narrower. If this recurs with the same `QSocketNotifier` signature
after this fix, the next step would be instrumenting exactly which QThread
start is racing which Qt Multimedia probe (e.g., temporarily logging
timestamps around both), rather than guessing at another deferral value.

## Addendum 5 (2026-07-28) — round 5's per-call defer was too narrow; gate the source, not one caller

Round 5's fix recurred a *sixth* time (`hs_err_pid257455.log`), same repro,
same crash offset (`libQt6Core.so.6+0x1e74d5` — identical to round 4's log).
Two things narrowed this down:

1. **The user's repro is "browse the new directory *immediately* after
   startup."** Round 5 only deferred `SystemDisplaySubTab.set_config()`'s
   *auto-restore* call by 250ms. If the user's own manual browse action
   fires within that window — plausible, since it doesn't require waiting
   for anything — it starts the exact same `QThread`s through a completely
   different call path (`browse_scan_directory()`), entirely unprotected by
   that defer. A per-call-site defer can never fully close this: it only
   protects the one caller it wraps, not whatever the user does with their
   own hands in the meantime.
2. **`main.py` already has an extensive, pre-existing comment describing
   this exact failure mode and error string** (lines 24-34): a version/build
   mismatch between the system `libpulse.so.0` and a pixi-built copy
   transitively pulled in by `import base`'s OpenCV/FFmpeg dependency,
   resolved by SONAME-based dynamic-linker deduplication onto whichever
   copy loads *first* — if the wrong one wins, Qt Multimedia's own later
   `dlopen("libpulse.so.0")` binds to a build it wasn't tested against.
   `main.py` already preloads the system copy first as a fix. Verified this
   preload actually succeeds in isolation (`ctypes.CDLL(...)` returns
   cleanly, no silently-swallowed `OSError`) — so this specific,
   already-documented cause is not what's still happening; `QSocketNotifier`
   is a generic Qt warning with more than one possible trigger, and the
   *timing* race (round 5's hypothesis: a new `QThread` starting while Qt
   Multimedia's async device-probe thread is still running) remains the
   live, unaddressed one.

**Fix: stop trying to defer individual call sites and gate the source
instead.** `backend/src/app.py::launch_app()` now:
1. Explicitly primes Qt Multimedia's backend — `QAudioOutput()` — as early
   as possible, immediately after `QApplication` is constructed and *before*
   the login window is even shown. This starts the PipeWire probe with the
   maximum possible head start: the user still has to authenticate (vault
   unlock, keystore load, credential decryption — several real,
   sequential, non-trivial operations) before `launch_main_gui()` even
   fires.
2. `launch_main_gui()` (the callback that builds and shows `MainWindow`,
   previously synchronous) now defers the actual `MainWindow(...)`
   construction with `QTimer.singleShot(400, ...)`.

Since **no tab, and therefore no scanner `QThread`, can exist before
`MainWindow` is constructed**, this closes the race for every call path at
once — the auto-restore, the user's own manual browse, and any future
gallery/tab that starts a `QThread` during its own construction — rather
than requiring every individual call site to separately remember to defer
itself. Round 5's narrower defer (`SystemDisplaySubTab.set_config()`,
250ms) is left in place as harmless defense-in-depth, not removed.

**Not verified against a live reproduction** — same standing caveat, now
six iterations in. If this exact `QSocketNotifier`/`libQt6Core+0x1e74d5`
signature recurs *after* this fix, the working theory (an async PipeWire
probe racing new-thread creation) should be considered falsified, and the
next step is direct instrumentation (temporarily logging wall-clock
timestamps around the `QAudioOutput()` prime call, the PipeWire probe's
own completion if observable, and every scanner-thread `.start()` call) to
find the real ordering — not another blind deferral-value guess.

## Addendum 6 (2026-07-28) — round 6's own fix had a self-inflicted regression

The user reported the app now "crashes immediately after login" — no crash
log this time (`hs_err_*.log` never generated), stdout cut off mid-way
through credential decryption, well before the `qt.multimedia.ffmpeg`/
`QSocketNotifier` lines that every prior round's log showed. This pointed
away from a native crash and toward round 6's own new code.

**Found it on re-reading the round-6 diff**: `launch_main_gui()` closed the
`LoginWindow` *immediately*, synchronously, while the new
`MainWindow(...)` construction was deferred 400ms via
`QTimer.singleShot`. For that entire 400ms window, **zero top-level
windows were open**. `QApplication`'s default `quitOnLastWindowClosed`
(never explicitly set anywhere in this codebase — confirmed by grep, so
Qt's default `True` applies) means closing the last remaining window
immediately quits the application — silently, no signal, no crash log,
exactly matching "crashes immediately after login." The 400ms defer this
round added to fix the *original* race directly created this *new*,
different bug.

**Fix**: reordered so `MainWindow` is constructed and shown *first*, inside
the deferred callback, and `LoginWindow` is only closed *after* that
succeeds — so at least one top-level window is open at every point in the
transition, never zero. This is a strictly safer ordering regardless of
`quitOnLastWindowClosed`'s value, not just a workaround for this specific
default.

This was caught and fixed in the same turn as the report, entirely from
re-reading the diff rather than needing another crash log — a reminder to
re-review any startup-sequencing change for this exact "is a window ever
briefly absent" hazard before shipping it, given `quitOnLastWindowClosed`'s
default is easy to forget about.

## Addendum 7 (2026-07-28) — a second, independent instance of round 7's bug, in a file round 7 never touched

The user reported the exact same symptom persisting after round 7 —
identical stdout, cutting off right after credential decryption, no crash
log. Since round 7's fix was a deterministic (non-race) bug fix, an
identical *recurrence* after it landed meant either the fix wasn't the
whole story, or there was a second source of the same underlying problem.

**Found it**: `gui/src/windows/main/login_window.py` has its own,
independent `self.close()` call immediately after each of its three
`login_successful.emit(...)` call sites (guest login, existing-account
unlock, new-account creation) — code round 7 (which only touched
`backend/src/app.py`) never touched. `login_successful` is a direct
(same-thread) signal connection, so `app.py`'s connected
`launch_main_gui()` slot runs *synchronously*, inside the `emit()` call
itself. Since round 6, that slot doesn't build `MainWindow` immediately —
it only *schedules* construction 400ms later via `QTimer.singleShot`. Once
`emit()` returns, control falls straight through to
`login_window.py`'s own `self.close()`, which runs essentially instantly —
long before the 400ms deferred `MainWindow` construction — recreating the
exact same zero-top-level-windows-open state round 7 already fixed once,
through a second, entirely separate code path.

**Fix**: removed all three `self.close()` calls from `login_window.py`.
`app.py`'s `_build_and_show_main_window()` already closes the previous
window itself, correctly, only once `MainWindow` is actually constructed
and shown — that was always the intended single source of truth for this
transition; `login_window.py`'s own close calls were redundant even before
they became actively harmful.

**Lesson for future rounds of this bug class**: when a startup-sequencing
fix changes a slot connected to a signal via a *direct* connection, audit
every place that *emits* that signal too, not just the slot itself — a
direct connection means the emitting code's own subsequent statements run
before the now-deferred work the slot scheduled, and any of those
statements that assumed the old (synchronous) slot behavior can silently
reintroduce the exact bug the slot-side fix just closed.

## Addendum 8 (2026-07-28) — the login bug is confirmed fixed; a queue-backlog gap remained for rapid repeated switches

The user's login-transition repro is now confirmed fixed by round 8: the
stdout of the next crash report progressed well past login (through
"Logging reconfigured from preferences" and into `MainWindow` construction)
before failing — genuinely further than any previous report reached. The
new crash came from a **more aggressive repro**: restore the previous
session's directory, browse a new (video) directory immediately, switch
back to the original (image) directory, then immediately browse the video
directory again — four rapid, back-to-back scans. Crash frame:
`libQt6Core.so.6+0x1df7c9`, yet another nearby-but-distinct offset from
every previous report, on the same `QSocketNotifier` warning immediately
before it.

**Identified gap**: every fix through round 4 correctly uses `QThread.wait()`
(unbounded) or `QThreadPool.waitForDone(-1)` to block the calling (main)
thread until a previous scan's worker(s) actually finish, before letting
the caller proceed to tear down/rebuild gallery widgets. What none of those
fixes accounted for: **`.wait()`/`waitForDone()` block the calling thread
without pumping that thread's own event loop.** Any `deleteLater()` calls
already queued from an *earlier* switch (this same code's own widget-
teardown loops, on a previous invocation) are still sitting unprocessed in
the event queue when the wait returns — no matter how long the wait itself
took, it does nothing to drain what's already queued. With four rapid
switches in a row, each one's teardown queues more `deleteLater()` events
before the previous batch has ever actually been processed, since nothing
in the chain ever yields back to the event loop. This is a plausible
mechanism for a use-after-free distinct from (but the same broad family
as) every previous instance: not a still-running thread racing new
teardown, but a *backlog* of not-yet-executed deferred deletions
potentially referencing objects that later teardown steps also touch.

**Fix**: added an explicit `QApplication.processEvents()` call immediately
after every unbounded `.wait()`/`waitForDone()` in this file,
`abstract_class_two_galleries.py`, `abstract_class_single_gallery.py`, and
`extractor_tab.py` (all four call sites fixed across rounds 3-4, plus the
two `closeEvent()`s) — explicitly flushing the event queue (processing any
pending `deleteLater()`s and queued signal deliveries) before the caller
is allowed to proceed to its own teardown/rebuild. `QApplication.processEvents()`
was already an established idiom elsewhere in `wallpaper_common_base.py`
before this fix, not a new pattern introduced here.

**Still not independently verified against a live reproduction.** This is
now the fifth distinct mechanism found in this crash-class investigation
(deleteOrphaned race → bounded-timeout insufficiency → linked-panel
state → login zero-window bug → this queue-backlog gap). If the *exact*
rapid-repeated-switch repro recurs after this fix, the next step is
direct instrumentation (log queue depth / pending event count immediately
before each teardown) rather than another mechanism guess.

## Addendum 9 (2026-07-28) — round 9's own fix was the trigger; a regression test now guards this

The user reported `hs_err_pid291347.log`, and this time the repro was
*simpler* than round 8's: just the automatic session-restore of a
Wallpaper directory on startup, followed by *one* immediate manual browse
to a different (video) directory. Same `QSocketNotifier` warning, same
`SIGSEGV` in `libQt6Core.so.6`, at yet another nearby offset
(`+0x1e74d5`, close to the very first `deleteOrphaned` signature's
`+0x1e73ae` from the top of this document) — a strong hint this was the
*original* `deleteOrphaned` class again, not a new one.

The user also asked, reasonably, why this is being diagnosed by reading
crash logs alone: *"can't you simply create a test that simulates fast
browsing... and update the codebase until the test passes?"* That's
exactly what this round did, and it's how the actual bug got found.

**Root cause: round 9's own `QApplication.processEvents()` fix was the
trigger.** `ImageScannerWorker`/`VideoScannerWorker` are bespoke
`QThread`s (see the "third and fourth recurrence" section above);
`_on_image_scan_finished()` (connected to `ImageScannerWorker.scan_finished`,
a queued cross-thread signal) unconditionally does:
```python
if self.scanned_dir:
    self.vid_scanner_worker = VideoScannerWorker(self.scanned_dir)
    ...
    self.vid_scanner_worker.start()
```
with **no check that this call is still current**, and **no stop of
any existing `self.vid_scanner_worker` first**. Round 9's `processEvents()`
(added at the end of `_stop_scanner_threads()`, right after waiting for
the *previous* directory's `ImageScannerWorker` to drain) doesn't just
flush `deleteLater()`s as intended — it also delivers *any other* queued
event, including that previous worker's own `scan_finished` signal, which
was posted the instant its `run()` returned (during the `.wait()` just
above). That delivery happens **reentrantly, mid-`_stop_scanner_threads()`,
before `populate_scan_image_gallery()` has even updated `self.scanned_dir`
to the new directory** — so `_on_image_scan_finished()` fires for the
*old* directory and starts a brand-new `VideoScannerWorker` for it, right
in the middle of switching away from it. That worker is never stopped by
the switch in progress (its own stop-before-touch logic already ran
earlier in this same call), only by whichever *later* switch's
`_stop_scanner_threads()` happens to notice `self.vid_scanner_worker` is
non-`None` — one full switch late, or never, if the next
`_on_image_scan_finished()` (also unguarded) overwrites the reference
first. Confirmed empirically with a 4-instance reproduction (below):
exactly one rapid switch already showed the pattern; four made it worse.

**Fix, two parts:**
1. **Narrow the round-9 flush.** `QApplication.processEvents()` →
   `QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` at
   all six round-9 call sites (`wallpaper_common_base.py`,
   `abstract_class_two_galleries.py` ×2, `abstract_class_single_gallery.py`,
   `extractor_tab.py` ×2). This still flushes the `deleteLater()` backlog
   round 9 was written for, but no longer reentrantly delivers ordinary
   queued signals (like a stale `scan_finished`) mid-teardown. The two
   *pre-existing* `processEvents()` calls in `_select_monitor()`/
   `_select_monitor_peer()` were left alone -- unrelated, established
   idiom, not part of this crash's call chain.
2. **Make `_on_image_scan_finished()` reject stale deliveries and never
   orphan a video worker**, regardless of how the stale signal eventually
   gets delivered (round 9's reentrancy was only the *most reliable*
   trigger, not the only one -- the ordinary event loop can deliver a
   stale `scan_finished` on its own, just less predictably). Two changes
   in `wallpaper_common_base.py`:
   - The `ImageScannerWorker.scan_finished` connection now binds the
     worker instance into the connection itself (a lambda default-arg
     captured at connect time), and `_on_image_scan_finished()` compares
     it against `self.img_scanner_worker`/`self.img_scanner_thread` by
     Python object identity, returning early if they don't match.
     **This deliberately does not use `QObject.sender()`** -- that was
     the first fix attempted, and it failed silently: by the time a
     stale `scan_finished` is actually processed, the sender's C++
     object has frequently already been destroyed (an earlier
     `_stop_scanner_threads()` call already `deleteLater()`'d and
     flushed it), and Qt's `sender()` returns `None` for a destroyed
     sender -- exactly backwards from what a staleness check needs.
     Comparing captured Python references by identity needs no access
     to the (possibly-destroyed) C++ side at all.
   - `_on_image_scan_finished()` now calls a new `_stop_vid_scanner_worker()`
     helper (the `vid_scanner_worker` stop/drain block extracted out of
     `_stop_scanner_threads()`) before constructing a new
     `VideoScannerWorker`, so even a *legitimate* (non-stale) second scan
     completion can never leave an earlier video scan running unstopped.

**Regression test**: `gui/test/core/test_wallpaper_scan_race.py`
reproduces the user's exact four-switch sequence (restore dir A, browse
dir B immediately, switch back to A, browse B again) against the real
`WallpaperCommonBase.populate_scan_image_gallery()`/`_on_image_scan_finished()`
code path, using a real `ImageScannerWorker` subclass with an artificial
delay (so overlap between successive scans is deterministic, not
dependent on real filesystem/thread scheduling timing) and a spying
`VideoScannerWorker` subclass that records every instance ever created.
It asserts exactly one `VideoScannerWorker` is created across the whole
sequence (the one legitimate completion), and that any instance not
belonging to the final directory was actually stopped. **Verified this
test fails against the pre-fix code** (4 spurious workers created, one
per switch) **and passes against the fix.** This is the first round of
this crash class with an automated regression test instead of relying
solely on the user reproducing a live crash.

**Still true**: the live SIGSEGV itself has not been re-reproduced by the
user against this fix (SIGSEGV can't be caught in-process, so the test
above verifies the *logic* race, not the native crash directly) --
please retry the exact repro when convenient. But this round is on
firmer ground than any previous one: the mechanism was reproduced,
fixed, and is now guarded by a test that fails without the fix.

## Addendum 10 (2026-07-28) — round 10's fix was correct but for a different bug; this crash was always root cause #8

The user reran the *exact same simplest repro* as round 10
(`hs_err_pid306373.log`): restore a directory on startup, browse a
different one immediately. Same `QSocketNotifier` warning, `SIGSEGV`
inside `libQt6Core.so.6` -- but this time at `+0x1df7c9`, **not** the
`+0x1e74d5`/`+0x1e73ae` family round 10 fixed. `+0x1df7c9` is the *exact*
offset from the very first crash log at the start of this whole
investigative arc (`hs_err_pid282122.log`), which was already reported
*after* round 8's login fix was in place. In hindsight this should have
been the first thing checked: round 9 and round 10 both assumed every
report in this family was the `deleteOrphaned`/gallery-scanner-ordering
class documented above, because the `QSocketNotifier` warning text is
identical for both. It isn't. `+0x1df7c9` matches **root cause #8**
(Qt Multimedia's async PipeWire device probe racing a new `QThread`
during the fragile startup window) from the top of this document —
a bug rounds 9 and 10 never touched at all, because their fixes were
entirely inside `wallpaper_common_base.py`'s scan-completion handling,
nowhere near `app.py`'s startup sequencing.

**Why root cause #8's existing mitigation wasn't enough.** `app.py::launch_app()`
primes `QAudioOutput()` immediately after `QApplication` is constructed
(before the login window even shows) and defers `MainWindow` construction
by a fixed `QTimer.singleShot(400, ...)`. The implicit assumption was that
login/vault-unlock (JVM start, keystore load, vault decrypt -- all real,
sequential work visible in every stdout dump) would reliably eat far more
than 400ms on its own, making the total margin from "probe started" to
"first scanner QThread can start" comfortably larger than however long
the PipeWire probe takes. That assumption doesn't hold for every
environment/run: if login is fast (a remembered/short auth flow) and the
user acts immediately once `MainWindow` appears, the *actual* elapsed
time since the probe started can still be short -- and every one of
these reports also shows a `parseSampleFormat` parse-error warning from
PipeWire right at the very top of stdout, before anything else, which is
at least consistent with the probe having some kind of trouble/retry
happening that could extend its real duration unpredictably.

**Fix**: `gui/src/utils/startup_probe_guard.py` (new) tracks the probe's
real start time (`mark_startup_probe_started()`, called from `app.py`
right where `_startup_audio_prime` is constructed) and exposes
`startup_settle_remaining_ms()` -- milliseconds still needed, measured
from that real timestamp, with a `1.5s` settle window (up from the
effective ~400ms-plus-login-time margin). Every scanner-QThread call site
now checks this **at the point where it's actually about to start a
thread**, not by proxy through window-construction timing:
`WallpaperCommonBase.populate_scan_image_gallery()` and
`VideoExtractorSubTab.scan_directory()` each check
`startup_settle_remaining_ms()` first and, if still within the window,
reschedule their *entire own call* via `QTimer.singleShot()` and return —
whichever code path reaches the dangerous point first (auto-restore, or
the user's own manual click) gets the same guaranteed floor, regardless
of how quickly login happened. This directly addresses the "why a
per-call-site defer isn't enough on its own" lesson already documented
for this root cause: the earlier per-call-site attempt deferred the
*trigger* (a specific call), this one gates the *destination* (every
place a scanner thread can actually start), the same "gate the source"
principle `app.py`'s `MainWindow` defer already used, just applied one
layer closer to the actual danger.

**Test coverage**: `gui/test/core/test_startup_probe_guard.py` covers the
guard module itself (zero before marking, positive immediately after,
decays to zero, never negative) and — more importantly — confirms
`populate_scan_image_gallery()` actually defers a scanner-worker
construction while the guard reports time remaining, and that the
deferred retry goes on to construct it once the window passes. This does
not (and can't) prove the real PipeWire race is closed — the 1.5s figure
is a judgment call, not a measured value, since this session has no way
to run against real PipeWire hardware/timing. If this exact repro
recurs a third time with the *same* `+0x1df7c9` offset, the fixed
1.5-second margin is insufficient and the next step should be an actual
completion signal (e.g. `QMediaDevices.audioOutputsChanged`) instead of
a bigger guess, or increasing the margin further while investigating why
`parseSampleFormat` is erroring in the first place.

## Addendum 11 (2026-07-28) — root cause #8 (timing) directly disproven by instrumentation; the real mechanism found

Round 11's instrumentation (`[startup-probe-guard]` print lines) was run
against the exact same repro and gave direct, unambiguous evidence:
`remaining_ms=0` at *every single* checkpoint, starting from the very
first `populate_scan_image_gallery()` call. Login + vault-unlock alone
already exceeded the 5s ceiling before any scan could start, and the
`QMediaDevices.audioOutputsChanged`/`audioInputsChanged` confirmation
signal **never fired once in the entire session**. The crash still
happened anyway, immediately after the log line for starting the
second directory's `VideoScannerWorker`. This rules out root cause #8
(the Qt Multimedia startup-probe timing race) as the mechanism for this
specific, highly reproducible crash — not by inference this time, but by
direct measurement. (Root cause #8 may still be real for *other*
`QSocketNotifier` reports; the guard from rounds 11-12 is left in place
as a harmless, tested safety net, but it is not what round 12's crash
needed.)

**The actual mechanism**: comparing the instrumented log's thread-start
sequence, the Hentai directory's four scanner-thread starts (two panels
× image+video) all succeeded, but the Videos directory's crashed right
after its `VideoScannerWorker` started. The directories differ in one
obvious way: Hentai contains few/no video files, Videos is entirely
video files. `VideoScannerWorker.run()` (`gui/src/helpers/video/video_scan_worker.py`)
only spins up a `concurrent.futures.ThreadPoolExecutor` (plain Python
threads, not `QThread`s) if `video_paths` is non-empty — so Hentai's
scan effectively did nothing thread-wise, while Videos' scan actually
dispatched worker tasks. Each task
(`process_video_task` → `VideoThumbnailer.generate()`, in
`gui/src/helpers/video/video_thumbnailer.py`) calls
`QImage().loadFromData(result.stdout)` to decode the JPEG bytes
`ffmpeg`/`ffmpegthumbnailer` wrote to stdout — **from one of those
background threads, not the main/GUI thread**. This is the first time
in the process's lifetime any video thumbnail gets decoded, so Qt's JPEG
image-format plugin lazily loads right there — off the main thread, with
the JPype JVM already loaded in-process. This is the exact same crash
class already fixed three times before for other Qt subsystems (native
file dialog/GTK, `QWebEngineView`/Chromium, `QMediaPlayer` FFmpeg
VA-API — see `jvm_native_lib_conflicts` in project memory): *any* Qt
subsystem lazily `dlopen()`-ing a native lib off the main thread while
the JVM is loaded risks this. It also explains the crash's **perfect
determinism** far better than a timing race would: a directory with
video files always hits this path, a directory without them never does
— nothing to do with luck or scheduling.

**Fix**: `backend/src/app.py::launch_app()` now also primes the JPEG
image-format plugin synchronously on the main thread, in the same spot
and for the same reason as the existing `QAudioOutput()` priming —
before the JVM has loaded. It encodes a tiny 2×2 `QImage` to JPEG via a
`QBuffer` and decodes it straight back, forcing both the encode and
decode plugin paths to load on the main thread. A print line confirms
both succeeded.

**Not yet independently verified** — this fix has not been committed or
tested live yet per explicit user instruction (test locally first, no
more commit-then-hope-they-test cycles). If this closes the crash, the
`startup_probe_guard` machinery from rounds 11-12 should be considered
for removal/simplification in a follow-up, since its own instrumentation
is what disproved its premise for this crash class.

## Addendum 12 (2026-07-28) — JPEG-plugin fix changed the failure mode; the round-12 QMediaDevices listener is the new suspect

The user tested Addendum 11's JPEG-plugin-priming fix against the exact
same repro. Result: **no more SIGSEGV, no more crash log at all** — the
`+0x1df7c9` offset that recurred identically four times running is gone.
Progress. But the process didn't exit cleanly either: instead it produced
an unbounded, repeating `QSocketNotifier: Invalid socket 58 and type
'Read', disabling...` spam (hundreds of repetitions, effectively a hang/
spin rather than a crash) right at the same point in the sequence
(immediately after the second directory's `VideoScannerWorker` started).

This is the *other* symptom `main.py`'s own preexisting comment already
attributes to this general `QSocketNotifier` problem class: "...or a
frozen event loop spamming 'QSocketNotifier: Invalid socket'" — the same
underlying issue, a different observable failure mode depending on
exactly what state gets hit.

**Prime suspect: round 12's own `QMediaDevices()` addition.** Round 12
added a long-lived `QMediaDevices()` instance in `app.py`, connected to
`audioOutputsChanged`/`audioInputsChanged`, specifically to get positive
confirmation of the startup probe settling. Round 12's own instrumentation
(Addendum 11) already showed those signals **never fired once** in a full
session — meaning this listener contributed nothing useful, but did keep
a persistent Qt Multimedia device-watch object alive for the entire app
lifetime, itself a plausible new source of the exact kind of long-lived,
possibly cross-thread socket-notifier churn ("socket 58" going invalid
repeateds) now being observed. It's also the single biggest change
between the round-12 run (clean SIGSEGV) and this round-13 run (hang) —
the JPEG-plugin fix was the other change, and it's already shown to have
removed the SIGSEGV specifically, not introduced a hang.

**Action taken**: removed the `QMediaDevices()` listener and its signal
connections from `app.py` entirely, reverting `startup_probe_guard` to
elapsed-time-only (the round-11 ceiling), which is simpler and was never
shown to cause any problem on its own. Kept the JPEG-plugin priming from
Addendum 11 (the fix that actually removed the SIGSEGV). `mark_startup_probe_settled()`
remains in `startup_probe_guard.py` (and its tests) for potential future
use, just no longer wired to anything in `app.py`.

**Not yet independently verified.** This is a hypothesis about *which*
round-12 change caused the hang, not a confirmed diagnosis — the
`QMediaDevices()` object was removed because it's the most plausible
suspect and contributed no measured benefit, not because the hang was
traced to it directly. If the hang recurs even after removing it, the
JPEG-plugin fix itself (or something else entirely) needs to be
re-examined instead.

## Addendum 13 (2026-07-28) — removed QAudioOutput() priming entirely; every failure mode traced back to it

Addendum 12's fix (removing the `QMediaDevices()` listener) was tested
against the same repro. Result: no more infinite spam this time, but a
*third* distinct failure mode instead: a single `QSocketNotifier: Invalid
socket 58` line, then `corrupted size vs. prev_size while consolidating`
(glibc's `malloc_consolidate()` catching heap corruption) and a SIGABRT.

Stepping back across all seven rounds of this specific sub-investigation
(rounds 6-13): every single failure mode -- the original SIGSEGV at
`+0x1df7c9`, the `+0x1e74d5` variant, the infinite invalid-socket spam,
and now the glibc heap-corruption abort -- starts with the identical
`QSocketNotifier: Socket notifiers cannot be enabled or disabled from
another thread` warning. The only thing in this app that ever triggers
Qt Multimedia's PipeWire backend during a pure Wallpaper-tab-browsing
session is `_startup_audio_prime = QAudioOutput()` in `app.py`
(`ExtractorTab`'s own `QAudioOutput`/`QMediaPlayer` are already
constructed lazily -- confirmed by reading `extractor_tab.py`'s
`audio_output`/`media_player` properties -- so nothing else touches Qt
Multimedia at all in this repro). No timing adjustment (400ms → 1.5s →
5s ceiling), no completion-signal wiring, and no lazy-plugin fix for a
*different* subsystem (the JPEG plugin, which did close its own specific
SIGSEGV) has stopped this. The pattern across seven attempts stopped
looking like "a race that needs more time to settle" and started looking
like "Qt Multimedia's PipeWire integration is fundamentally unstable
alongside the JPype JVM on this machine, independent of timing" -- in
which case no amount of waiting was ever going to fix it, only avoiding
the trigger entirely (for sessions that don't need it).

**Action taken**: removed `_startup_audio_prime = QAudioOutput()` (and
the now-pointless `mark_startup_probe_started()` call) from `app.py`
entirely. This is the single biggest lever left untried: previously
every round *kept* this object (the whole point of rounds 6-7 was to
construct it *earlier*), on the theory that priming early was strictly
better than not priming at all. That theory is what's now in question.
`startup_probe_guard.py`'s elapsed-time/`remaining_ms` machinery is left
in place at the scan call sites (harmless, always reports 0 now that
nothing ever marks the probe started -- effectively inert) rather than
ripped out under time pressure; worth a cleanup pass once this is
confirmed fixed.

**This intentionally narrows protection**: if a user opens `ExtractorTab`
and previews a video with audio within seconds of app startup, the
*original* crash this priming was meant to prevent (from rounds 6-7)
could in principle recur, now unprotected. That's a real, accepted
trade-off, not an oversight -- the user's actual repeated repro never
involves `ExtractorTab`/audio playback at all, and an unconditional
startup cost that has not measurably helped across seven rounds isn't
worth keeping "just in case" for a scenario nobody has actually hit yet.
If that specific scenario does recur, it needs its own, narrower fix
(e.g. priming only when `ExtractorTab`'s video-preview path is actually
about to be used, not unconditionally at app startup).

## Addendum 14 (2026-07-28) — removing QAudioOutput priming helped a lot but didn't close it; the actual remaining trigger is QGraphicsVideoItem in ExtractorTab

Addendum 13's fix (removing `_startup_audio_prime`) was tested. Real,
measurable progress: the app survived the *entire* previous repro
(Hentai → Frames/Videos) and went on to survive several more directory
switches (→ Wallpapers/Anime → Frames/Videos again) before finally
crashing -- the first time in this whole investigation the app got past
the very first switch. The crash frame is now also named, not just an
offset: `QSocketNotifier::type() const+0x8` inside `libQt6Core.so.6` --
a crash dereferencing a `QSocketNotifier` object that's null or already
destroyed.

Traced the remaining trigger with an isolated, reproducible test:
constructing `QAudioOutput()` alone does *not* print Qt's
`"Using Qt multimedia with FFmpeg version..."` backend-load banner, but
constructing `QGraphicsVideoItem()` (from `PySide6.QtMultimediaWidgets`)
does, immediately, on construction -- confirmed with a standalone
`QApplication` + single `QGraphicsVideoItem()` call. `ExtractorTab.__init__`
(`extractor_tab.py:288`, before this fix) constructed one unconditionally,
every session, as part of `MainWindow.__init__` (`main_window.py:220`,
`self.extractor_tab = ExtractorTab()`) -- meaning Qt Multimedia's backend
was *still* getting triggered on every session, just later (during
MainWindow construction, milliseconds before the user can act) and via a
different object than the one rounds 6-13 had been focused on removing.

**Fix**: made `video_item` lazy in `extractor_tab.py`, mirroring the
*already-existing* lazy pattern for `audio_output`/`media_player` in the
same file (which round-6-era work had already made lazy, for the same
reason, just never noticed this specific object was still eager). Added
a `video_item` property that constructs `QGraphicsVideoItem()` and adds
it to the graphics scene only on first access; `media_player`'s own lazy
construction (which already referenced `self.video_item`) now correctly
chains into it. Guarded `fit_video_in_view()` (called from resize event
handling, which fires long before any video is loaded) to no-op if
`_video_item` hasn't been constructed yet, so a resize event can't itself
force the construction this fix exists to defer.

**Verified in isolation**: constructing `ExtractorTab()` standalone no
longer prints the FFmpeg backend banner at all (confirmed via a scripted
check). This is scoped entirely inside `extractor_tab.py` -- deliberately
did *not* pursue deferring `ExtractorTab`'s own construction in
`main_window.py` (a much larger change touching tab-dict structure and
extensive per-tab config-restoration logic with real regression risk to
users' saved Extractor preferences) after evaluating that path and
finding it materially riskier for uncertain additional benefit, given
`QGraphicsVideoItem` was the actual remaining trigger either way.

Existing test suite (28 gallery/wallpaper/probe-guard tests, 6 app-logging
tests, 4 non-preexisting-failure extractor-drag-preview tests) all still
pass.

**Not yet independently verified against a live reproduction** — awaiting
the user's test, per explicit instruction not to commit until confirmed
working.

## Addendum 15 (2026-07-28) — Qt Multimedia is definitively ruled out; the real cause is still unknown

The user tested Addendum 14's fix (lazy `video_item`). Result: the crash
recurred on the very first directory switch (Hentai → Frames/Videos,
no further switches attempted) — faster/more reliably than the previous
round, which had survived several switches. Crash frame this time:
`QSocketNotifier::setEnabled(bool)+0x3c`, another *named* function (not
just an offset), on the identical warning text.

**Critical new evidence: no `"qt.multimedia.ffmpeg: Using Qt multimedia
with FFmpeg version..."` banner appears anywhere in this run's stdout.**
That banner is Qt's own one-time announcement that its FFmpeg/PipeWire
multimedia backend has loaded — confirmed printed the instant `QAudioOutput()`
or `QGraphicsVideoItem()` is constructed (see Addendum 11/14's isolated
tests). Its total absence here proves Qt Multimedia's backend was **never
triggered at all** in this session: neither `_startup_audio_prime` (removed,
Addendum 13) nor `QGraphicsVideoItem` (made lazy, Addendum 14) fired. The
crash happened anyway, with the same warning text, on the same class of
`QSocketNotifier` internal function. **Root cause #8 (the Qt Multimedia
startup-probe timing race) is not just insufficiently mitigated — it was
never the cause of this specific, highly-reproducible crash at all.**
Every round from 6 through 14 chased a plausible-looking but ultimately
coincidental correlation: the warning text is generic enough that a
completely different mechanism produces the identical string.

**Reassessment**: this crash's actual signature — happening deterministically
on the *first* rapid directory switch, involving `QSocketNotifier`, and
tied to QThread activity — points back to the `deleteOrphaned`/scanner-QThread-lifecycle
class documented at the top of this file (rounds 2-10), not to any startup
timing issue. One real, previously-untested gap: every fix and regression
test through round 10 (`test_wallpaper_scan_race.py`) exercises a single
`WallpaperCommonBase` instance. The real Wallpaper tab always has **two
linked instances** (`system_display`/`monitor_display`, wired in
`wallpaper_tab.py`: mutual `linked_tabs`, a shared/aliased
`_initial_pixmap_cache` dict, and `directory_scanned` cross-connected with
`emit_signal=False`) — a topology no existing test covered.

**Built `gui/test/core/test_wallpaper_linked_panel_scan_race.py`** to close
that gap: constructs two linked instances exactly matching
`wallpaper_tab.py`'s wiring, drives rapid switching through one panel
(mirroring how a real user only interacts with System Display while
Monitor Display mirrors silently), and asserts neither panel orphans a
`VideoScannerWorker`. **Result: passes cleanly against the current code**
— this specific two-panel interaction, simulated at the Python/Qt-signal
level with an artificial scan delay, does not reproduce an orphaned
worker or any other detectable bad state. This is a meaningful negative
result: it suggests the actual crash mechanism operates at a level this
kind of test can't reach (genuine native thread-scheduling timing, real
`ffmpeg`/`ffmpegthumbnailer` subprocess spawning, or a Qt-internal
event-dispatcher/socket-notifier interaction that only manifests under
real OS thread creation) — not a logic bug reachable by simulating the
Python-level call sequence with mocked timing.

**Fix this round: fine-grained thread-lifecycle instrumentation**, not a
new behavioral fix (none is confidently indicated by the evidence so
far). Added `print(..., flush=True)` at every `QThread` lifecycle
transition in `wallpaper_common_base.py` — `requestInterruption`/`stop`/
`quit`, before and after every `wait()`, `deleteLater()`, before and
after every `start()`, and `_on_image_scan_finished()`'s stale-vs-proceed
decision — every line tagged with `panel={id(self):x}` (distinguishes
system_display from monitor_display) and `tid={threading.get_ident()}`
(distinguishes which OS thread is executing). The goal: the *next* crash
report's last few lines before the SIGSEGV should show exactly which
specific lifecycle operation (a `wait()` that never printed "returned", a
`start()` that never printed "returned", a stale delivery right before
the crash, etc.) was in flight, which none of rounds 9-14's diagnosis
could determine from the existing coarser prints.

**Not yet independently verified against a live reproduction** — awaiting
the user's test with this new instrumentation, per explicit instruction
not to commit until confirmed working. If the new prints don't land
*any* new information (e.g. because the crash happens between two prints
that both show "returned" cleanly), the next step is external process
tracing (`strace -f`, or GDB attached ahead of time) rather than more
Python-level print instrumentation, since that would indicate the issue
is below what Python-level tracing can observe at all.

## Addendum 16 (2026-07-28) — 100% reproducible via `just python` alone; root of the double-switch found; still not fully fixed

**Major methodology breakthrough**: `timeout 30 just python`, run completely
unattended with zero manual interaction, reproduces this crash reliably
(hit it in 5 of 9 consecutive runs; the other 4 hit either a clean pass or
a second, unrelated bug -- see below). This turned a slow, user-in-the-loop
debugging cycle into a fast, self-service one for this session.

**Traced the exact "second directory" mechanism with a stack-trace dump**
added to `populate_scan_image_gallery()` (prints `traceback.format_stack()`
whenever `emit_signal=True`). Two real findings:
1. `set_config()` is called **only once** per run (confirmed with
   timestamped instrumentation in `system_display_subtab.py`) -- the
   "two different saved directories" theory (each panel independently
   restoring a different config) was wrong. There is only one auto-restore.
2. The second directory switch traces back to `WallpaperCommonBase.browse_scan_directory()`
   -- the *manual* browse-button handler -- being reached during these
   unattended runs. Since this method's `QFileDialog` (patched via
   `file_dialog_patch.py`, always `DontUseNativeDialog`) returned a valid
   directory and the call proceeded, *something* triggered/accepted it
   despite no deliberate input from this session's automation. This is
   run on the user's real, active KDE Wayland desktop session (confirmed:
   `plasmashell`/`kwin_wayland` running, not headless) -- most likely a
   stray focus/input event specific to running many rapid launches in a
   live desktop, not a bug in `browse_scan_directory()` itself. Whatever
   the exact cause, the *effect* -- auto-restore one directory, then a
   rapid switch to a second one -- is exactly the user's own consistently
   reported manual repro, so this remains a faithful, useful reproduction
   even without pinning down why the dialog is being accepted automatically
   in this environment specifically.

**Fixes made this round** (both real hardening, neither confirmed
sufficient alone):
1. `system_display_subtab.py`: `set_config()`'s `scan_directory` restore
   used a fire-and-forget `QTimer.singleShot(250, ...)` with no
   cancellation of any previously-scheduled one. Replaced with a single,
   restartable `QTimer` (`self._scan_dir_restore_timer`) plus
   `self._pending_restore_dir` read at fire-time -- if `set_config()`
   were ever called twice in quick succession (not confirmed to happen in
   practice this round, but was the original hypothesis and remains a
   real latent risk with the old code), only the latest directory would
   now actually restore, once. Kept as a legitimate correctness fix
   independent of whether it was *this* run's actual trigger.
2. `wallpaper_tab.py`: the `directory_scanned` cross-panel connections
   (`system_display` ↔ `monitor_display`) used the implicit direct/
   same-thread connection, meaning the peer's `populate_scan_image_gallery()`
   -- and thus its own 2 new `QThread` starts -- ran synchronously nested
   inside the emitting panel's own call, before that panel's own worker-
   starting code even executes. Changed to explicit
   `Qt.ConnectionType.QueuedConnection` so the peer's scan is deferred to
   the next event-loop tick instead of packed into the same call stack.
   **Tested and did not eliminate the crash** (run 6 with this fix in
   place still crashed, same signature) -- kept anyway since it's a
   correct, principled change (spacing out 4 QThread starts across 2
   panels instead of bursting them), but it is not, on its own, the fix
   this crash needed.

**A second, apparently unrelated bug was also found**: `libQt6Gui.so.6+0x136666`,
a **null-pointer** SIGSEGV (`si_addr: 0x0000000000000000`) on the **main
thread** (`tid` == `pid`), reproduced twice with the identical offset,
happening immediately after `"Logging reconfigured from preferences"` --
i.e. inside or immediately after `MainWindow._apply_startup_preferences()`
returns, **before any wallpaper-tab scan code runs at all**. No
`QSocketNotifier` warning precedes it. Candidates for what runs next in
`MainWindow.__init__()`: `_setup_tray_icon()` (`QSystemTrayIcon`/`QIcon`
construction), `QGuiApplication.styleHints().colorSchemeChanged.connect(...)`,
or `self.restoreGeometry(_geom)`. Not investigated further this round --
flagging it clearly as a **separate, second crash class** so a future
round doesn't conflate its evidence with the QSocketNotifier/scan-thread
class this file otherwise tracks. Two of nine `just python` runs hit this
instead of the scan-thread crash; one run hung indefinitely at "Logging
initialised" before any JVM output (killed by timeout, no crash) --
possibly an unrelated environment hiccup from rapid repeated launches,
not reproduced again.

**Diagnostic instrumentation added this round, left in place** (verbose,
should be removed once this crash class is confirmed fixed, not before):
timestamped `set_config()`/timer prints in `system_display_subtab.py`,
and a `traceback.format_stack()` dump in `populate_scan_image_gallery()`
whenever `emit_signal=True`. These were essential to finding the actual
call sequence above and should stay until a live fix is confirmed.

**Status: still not fixed.** Between rounds 9-16, the crash has been
reproduced with the *exact* two-linked-panel, rapid-consecutive-directory-switch
pattern using real (non-mocked) `ImageScannerWorker`/`VideoScannerWorker`
and a real JVM, and every code-level mitigation tried so far (stale-sender
guards, DeferredDelete-only flushes, stop-before-create ordering, debounced
restore timers, queued cross-panel connections) has either not applied to
the actual trigger or not been sufficient alone. The next step, if
picked up again, should be external process tracing (`strace -f` or a
GDB session attached before the crash) rather than another Python-level
code change guess -- eight-plus rounds of plausible, principled Python-side
fixes have not closed this, which is itself evidence the remaining
mechanism is likely below what Python-level reasoning can reach.
