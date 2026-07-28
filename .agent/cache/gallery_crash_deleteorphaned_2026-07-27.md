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
