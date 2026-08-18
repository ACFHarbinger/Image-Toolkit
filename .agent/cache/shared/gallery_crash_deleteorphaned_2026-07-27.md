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

**Fix**: `gui/src/utils/guard/startup_probe_guard.py` (new) tracks the probe's
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

## Addendum 17 (2026-08-01) -- recurred again (glibc heap corruption); built permanent instrumentation + gdb tooling instead of another guess

Recurred with the same repro shape (auto-restored directory on startup,
then browsing a video directory -- specifically observed going
Hentai (images) -> Cinematography (videos) this time) and the same
`QSocketNotifier: ... another thread` warning, this time followed by
`corrupted size vs. prev_size` (glibc `malloc_consolidate()` heap
corruption) and SIGABRT -- the same failure mode already seen once in
Addendum 13. Every round 6-16 fix is still in place and none of them
closed this.

Rather than another single-shot Python-level guess (the pattern that
produced sixteen rounds without a confirmed fix), this round built
permanent, reusable tooling instead, per the standing recommendation right
above this addendum ("external process tracing... GDB attached ahead of
time"):

1. **`backend/src/core/telemetry.py`** -- a toggleable (`IMAGE_TOOLKIT_TELEMETRY=1`
   env var, near-zero cost when off), dependency-light structured JSONL
   event logger, with an `emit()` one-shot call and a `span()` context
   manager for start/end/error timing. Flushes every line immediately, same
   "survive a SIGABRT moments later" reasoning as the existing
   `flush=True` print idiom this sits alongside (not replaces -- every
   existing `[thread-lifecycle]`/`[startup-probe-guard]` print in this
   file's fix history is untouched).
2. **Wired additively into every existing instrumented call site**:
   `app.py` (JVM start, JPEG-plugin priming, login, `MainWindow`
   construction/show), `vault_manager.py` (`jpype.startJVM()` span),
   `lifecycle_memory.py` (RSS snapshots), `startup_probe_guard.py`, the
   full Wallpaper scan pipeline (`_scan_pipeline.py`,
   `_scanner_lifecycle.py`, `system_display_subtab/_config.py`), and
   `ExtractorTab`'s equivalent scan path.
3. **New instrumentation at the actual suspected native-crash boundary**
   (Addendum 11's finding, never directly instrumented before this round):
   `video_thumbnailer.py`'s three `QImage().loadFromData(...)` calls --
   the first video-thumbnail JPEG decode in the process, off a
   `ThreadPoolExecutor` worker thread, with the JVM already loaded --
   wrapped in `telemetry.span()`, plus every `base.scan_files_multi()`
   native call boundary in both `image_scan_worker.py` and
   `video_scan_worker.py`, and the `ThreadPoolExecutor` creation/dispatch
   itself in `video_scan_worker.py`. A crash mid-decode now leaves an
   unambiguous *orphaned span* (a `.start` event with no matching `.end`)
   in the telemetry file, instead of requiring inference from which
   `print()` line happened to be last in a terminal scrollback.
4. **`debug/telemetry_analyzer.py`** -- parses the JSONL file into one
   merged, time-ordered timeline across every thread, and automatically
   flags orphaned spans and overlapping scanner-thread windows (the
   overlap shape every root-cause theory in this document has pointed at).
5. **`debug/run_with_gdb.sh`** -- runs `main.py` under `gdb -batch`,
   stopping on SIGSEGV/SIGABRT (glibc's heap-corruption abort included) and
   dumping `thread apply all bt full` to a timestamped file before the
   JVM's own `hs_err` handler or process exit gets a chance to run. This is
   the actual external-process-tracing escalation this document has called
   for since round 15/16, just never had a ready-made tool for.

**Not a fix.** This round deliberately did not attempt another
speculative code change -- eleven-plus code-level mitigations across
rounds 2-16 without a confirmed close is itself evidence a twelfth guess
isn't the efficient next move. The tooling above is meant to make the
*next* live reproduction diagnostic instead of another round of
inference: reproduce with `IMAGE_TOOLKIT_TELEMETRY=1 debug/run_with_gdb.sh`,
then run `python debug/telemetry_analyzer.py` and correlate its
orphaned-span/overlap findings against the gdb backtrace's timestamp
before proposing a fix.

See `debug/README.md` for full usage.

## Addendum 18 (2026-08-01) -- first-ever real backtrace + telemetry capture; the trigger has inverted, and the crash may not be about scanner-thread races at all

First live use of the round-17 tooling produced the first-ever gdb
backtrace and correlated telemetry for this crash class. Two findings,
both significant:

**1. The telemetry file's last event was `startup/jvm.start.start`, with
no matching `.end`.** The crash was detected while inside/immediately
after `jpype.startJVM()` -- before `MainWindow` was ever constructed,
before any scanner thread, directory scan, or `QImage` decode ran at all.
Every one of rounds 1-17 assumed the crash required a directory switch (or
at minimum `MainWindow` to exist); this capture didn't need either.

**2. The gdb backtrace itself is unusually informative for this crash
class.** Threads 2-17 are all `blas_thread_server` -- NumPy/SciPy's
OpenBLAS worker pool, idle in `pthread_cond_wait`, spawned whenever
`numpy`/`base` is imported, well before login. Their presence confirms
**16 background pthreads already exist in-process by the time
`jpype.startJVM()` runs.** Thread 1 (main) is where it matters: its
unwind terminates after 2 frames at non-code addresses (`0x...692`, then
literally `0x202`, then `0x0`), `No symbol table info available` -- not
"missing debug symbols for a real function" but the stack itself
containing garbage return addresses. This is the first *physical*
confirmation (not inference from a warning string) that this is real
heap/stack corruption, consistent with "corrupted size vs. prev_size."

**The user also reported the reproduction trigger has inverted.**
Previously (rounds 1-16) the crash required acting *fast* -- switching
directories quickly after startup, within a race window. Now: the crash
happens if the user is *slow* -- waits an interval after opening the app
before browsing -- and only requires browsing/scanning **one** video
directory, with no image-directory prerequisite and no rapid switching.

**Working hypothesis (not yet confirmed): this may never have been a Qt
scanner-thread race at all.** A corruption event that happens once,
sometime after `jpype.startJVM()` returns -- plausibly from JVM-internal
background-thread activity (HotSpot JIT compilation or a first GC cycle,
which need some idle wall-clock time to kick in) interacting badly with
the 16 pre-existing OpenBLAS pthreads -- would explain both new
observations at once: (a) glibc's heap-consistency check is lazy, only
firing on a later `malloc`/`free`, so the *detection* point (a video scan's
`QImage` decode, which allocates heavily) is downstream of the actual
corrupting write, not causally connected to it the way every previous
round assumed; (b) waiting longer gives the JVM's background threads more
time to do whatever the damage is before the next heavy allocation touches
the corrupted chunk, naturally flipping "fast" (protective) to "slow"
(triggering).

**Status**: not confirmed. Debug symbols (`libc6-dbg`, `python3-dbg`)
requested for the next capture, so thread 1's actual crashing frame
resolves instead of showing `?? ()`. The next cheap experiment once that's
in place: set `OPENBLAS_NUM_THREADS=1`/`OMP_NUM_THREADS=1` before
launching (eliminates the 16-thread OpenBLAS pool) and reproduce again
under `debug/run_with_gdb.sh` with telemetry on -- if the crash stops or
moves to a different telemetry-adjacent point, that's strong evidence for
the OpenBLAS/JVM-threading hypothesis above; if it reproduces identically,
this hypothesis is falsified and the search should move to what else JPype/
JVM startup touches in this process (BouncyCastle provider, the JNI
classpath JARs, or JPype's own C extension).

**Correction, same session -- the debug-symbols request was based on an
incomplete read of the gdb output.** Reading the full saved
`gdb-backtrace-20260801-110805.txt` (not just what was pasted into chat,
which started mid-thread-list) instead of the partial paste changed the
diagnosis again:

```
Starting JVM with classpath: [...]
Installing openjdk unwinder
Python Exception <class 'gdb.error'>: No type named CodeBlob.

Thread 1 "python" received signal SIGSEGV, Segmentation fault.
0x00007ffddfa5f692 in ?? ()
```

`libc6-dbg` turned out to already be installed, and `python3-dbg` was
never going to help -- `just python` runs a uv-managed, already-unstripped
standalone CPython 3.11.14 build (`~/.local/share/uv/python/...`), not the
system Python the `python3-dbg` package targets. Neither was the actual
gap. **"Installing openjdk unwinder"** is gdb auto-detecting the embedded
JVM and loading HotSpot's own gdb integration script to resolve JIT-compiled
("CodeBlob") frames -- and that script errored out on this JDK/gdb
combination. That is almost certainly *why* thread 1's frame shows `?? ()`:
not corrupted-stack garbage as first read, but a real code address inside
HotSpot's JIT code cache (an anonymous executable mapping with no ELF
symbol table) that only a working JVM-aware unwinder could resolve.

This also means no `hs_err_pid*.log` was produced for this capture --
`run_with_gdb.sh` originally stopped the process at the fault and never
let the signal reach the JVM's own installed handler, so its normal
diagnostic output never got a chance to run. **Fixed**: the script now adds
a final `-ex "continue"` after dumping its own backtrace, re-delivering the
same signal (gdb's default "pass" behavior for a handled-but-not-`nopass`
signal) to the inferior so `hs_err_pid*.log` still gets written for the
same crash. The JVM's own frame dump is very likely a better diagnostic
here than gdb's own broken CodeBlob unwinder -- next capture should have
both.

## Addendum 20 (2026-08-01) — first-ever symbol-resolved crashes, via the fixed gdb script's hs_err pass-through: this really is the deleteOrphaned family, plus a new second crash site inside QObjectPrivate::connect()

With the Addendum 19 fix in place (`run_with_gdb.sh` no longer stops on
SIGSEGV, only SIGABRT, then `continue`s to let the JVM's own signal
handler run), two live crashes finally produced real `hs_err_pid*.log`
files with the JVM's own fatal-error diagnosis — something no round of
this investigation has had before (every previous `hs_err` was either
absent, or, per Addendum 18/19, intercepted by an incorrectly-configured
gdb before the JVM's handler could run).

**Crash 1** (`hs_err_pid2887978.log`, 25.7s after JVM start — the "fast"
repro): `SIGSEGV`, `si_code: 2 (SEGV_ACCERR)`, `si_addr: 0x67187028`,
`Problematic frame: C [libQt6Core.so.6+0x1e74d5]`.

**Crash 2** (`hs_err_pid2888898.log`, 52 minutes after JVM start — the
"slow" repro the user has been reporting recently): `SIGSEGV`,
`si_code: 1 (SEGV_MAPERR)`, `si_addr: 0x100000005`,
`Problematic frame: C [libQt6Core.so.6+0x1df7c9]`.

Both `Problematic frame` lines only show a raw offset because the
PySide6-bundled `libQt6Core.so.6` is fully stripped (`file` confirms
`stripped`, only a `.note.gnu.build-id` remains — no matching debug
package exists for it since it's PySide6's own private Qt build, not the
system Qt). But the **dynamic symbol table** (`.dynsym`, exported C++
mangled names) survives stripping, and computing which exported symbol's
address is the nearest one *below* each crash offset resolves both:

```
0x1e74d5 -> QObjectPrivate::ConnectionData::deleteOrphaned(QObjectPrivate::TaggedSignalVector) + 0x165
0x1df7c9 -> QObjectPrivate::connect(const QObject*, int, QtPrivate::QSlotObjectBase*, Qt::ConnectionType) + 0x109
```

(`nm -D --defined-only libQt6Core.so.6`, sorted, nearest-preceding-address
lookup against each crash `pc`.)

**This confirms, for the first time with hard evidence rather than
inference, that the crash class documented throughout this entire file
(rounds 1-16) is real and still open.** `+0x1e74d5` is *exactly* the
`deleteOrphaned` family from the very first crash log at the top of this
document (`+0x1e73ae` originally, `+0x1e74d5` recurring identically in
Addenda 9 and 14) — the connection-list cleanup race this file's Fix
section (rounds 2-10) targeted with unbounded waits, `DeferredDelete`
flushing, stale-sender guards, and linked-panel synchronization. None of
that closed it; it's still crashing inside the same function, at the same
offset, in a live capture today.

**`+0x1df7c9` resolving to `QObjectPrivate::connect()` is new, useful
information no previous round had** — this exact offset is the *original*
"root cause #8" address from Addendum 10, which Addendum 11 attributed to
the JPEG image-format plugin lazily loading off a worker thread, "fixed"
by priming it on the main thread, then subsequently disproven as the real
cause in Addendum 15 (the crash recurred with no Qt Multimedia/JPEG-plugin
banner in stdout at all). It was never actually understood. Now it is:
this is a `QObject::connect()` call — i.e., the exact
`self.img_scanner_worker.scan_finished.connect(...)`-style code in
`_scan_pipeline.py`/`_directory_scanning.py` that wires up every new
scanner/loader worker's signals immediately after construction — crashing
~0x109 bytes into `QObjectPrivate::connect()`'s own logic, dereferencing a
value (`si_addr: 0x100000005`, register `R15: 0x100000001` in the same
crash — both improbable-looking 33-ish-bit "pointers" with an identical
`0x00000001` upper half) that looks far more like a small tagged/packed
integer than a real heap pointer.

**Working unified theory**: there is one underlying corruption — a
cross-thread race that damages a `QObject`'s `ConnectionData` structure
(the same structure `deleteOrphaned` cleans up) — and every crash frame
seen across 20 rounds of this investigation (`deleteOrphaned` at three
close offsets, `QSocketNotifier::setEnabled`/`::type()`, unresolved raw
addresses, and now `connect()`) is a different place that *same* corrupted
structure happens to get touched next, not 20 independent bugs each
needing its own fix. This would explain why fixing any one observed
call-site/ordering issue (rounds 2-10's stop/wait/flush fixes) reduced
frequency without closing the class: the actual corrupting write is
upstream of all of them, and any one of `deleteOrphaned`,
`connect()`, or Qt's own socket-notifier bookkeeping can be the next
thing to dereference the damaged memory, depending on timing — matching
both the "sometimes fast, sometimes needs 52 minutes of idle time"
variability and the wide scatter of previously-reported offsets.

**Not yet actionable as a code fix.** Neither of these two captures had
`IMAGE_TOOLKIT_TELEMETRY=1` set, so there is no Python-level event log to
correlate against either crash's timestamp — meaning there is currently no
way to identify *which* worker's `.connect()` call, or which prior
`deleteOrphaned` invocation, actually touched the damaged object. Writing
a speculative fix now would repeat the exact mistake this document has
already made many times. `ulimit -c` is `0` on this machine, so neither
crash produced a core dump either, despite `hs_err`'s own message saying
one would be written — closer inspection (walking the actual corrupted
`QObjectPrivate`/`ConnectionData` in a debugger) isn't possible without
one.

**Next steps, in priority order:**
1. Reproduce again with **both** `IMAGE_TOOLKIT_TELEMETRY=1` set **and**
   `ulimit -c unlimited` exported first, ideally via `debug/run_with_gdb.sh`
   (now fixed to only stop on SIGABRT and pass SIGSEGV through) so a
   crash produces telemetry + hs_err + (this time) a core file together.
2. Correlate the crash's `hs_err` timestamp against the telemetry file's
   last few events (`python debug/telemetry_analyzer.py`) to identify
   which specific worker construction/`.connect()` or teardown/
   `deleteLater()` call was in flight.
3. If a core file is produced, load it in gdb (`gdb python core.<pid>`)
   and inspect the `QObjectPrivate`/`ConnectionData` at the faulting
   pointer's neighborhood — with the exported symbols now known, gdb can
   at least identify frame boundaries even without full debug info.

## Addendum 21 (2026-08-01) — first full telemetry+hs_err correlated capture: crash localized to primary panel's own populate_scan_image_gallery(), 0-22ms after a reentrant peer-triggered DeferredDelete flush

A `IMAGE_TOOLKIT_TELEMETRY=1 debug/run_with_gdb.sh` run produced, for the
first time, telemetry + gdb backtrace + `hs_err_pid*.log` all for the same
crash (`telemetry-2940282.jsonl`, `hs_err_pid2940282.log`,
`gdb-backtrace-20260801-124858.txt`). Same offset as before —
`libQt6Core.so.6+0x1e74d5` → `QObjectPrivate::ConnectionData::deleteOrphaned(...)`
(confirmed via `debug/resolve_qt_offset.py`) — but this time with a full
Python-level event trail leading up to it.

**Timeline reconstruction** (anchoring hs_err's JVM-relative "elapsed time:
16.4s" against telemetry's `jvm.start.start` at `t=5.709`, giving an
estimated crash window of `t≈22.1-22.5`, which lines up exactly with the
telemetry file's own last recorded event at `t=22.233`):

1. `t=15.866` — Wallpaper tab's `system_display` panel (`panel=...9680`,
   called "primary" below) auto-restores `Wallpapers/Cinematography`.
   `populate_scan_image_gallery()` stops both itself and its linked peer
   (`monitor_display`, `panel=...8608`) via `_stop_scanner_threads()`,
   emits `directory_scanned` (queued connection), then continues
   synchronously to build its own new scan. The peer's mirrored call
   (triggered by the queued signal, delivered once primary's own call
   returns) reaches the event loop at `t=15.868` and — racing ahead of
   primary's own sequence — starts its own `ImageScannerWorker` at
   `t=15.880` and its own `VideoScannerWorker` at `t=15.891`. Primary's
   *own* `ImageScannerWorker` doesn't start until `t=15.997` (131ms after
   its own `_stop_scanner_threads()` flush) and its own
   `VideoScannerWorker` at `t=16.056`. **Both panels end up running their
   own independent `VideoScannerWorker` (8-thread `ThreadPoolExecutor`
   each) over the identical 451-file directory, ~165ms apart, concurrently.**
   This survived — both scans completed cleanly (dozens of matched
   `process_video_task`/`qimage_from_cache` begin/end pairs through
   `t≈16.3`).

2. `t=22.121` — the **same primary panel**, still on the same session, is
   switched again (this time to `Cinematography`, no `Wallpapers/` prefix
   — the same directory pair from the very first crash report at the top
   of this document). Its `_scan_pipeline_busy` guard was already clear
   (switch 1's scan had long finished), so this proceeds immediately:
   `populate_scan_image_gallery.enter` → `_stop_scanner_threads()` flushes
   both itself and the peer (`sendPostedEvents(None, QEvent.Type.DeferredDelete)`
   — note `receiver=None`: this flushes **every** pending deferred deletion
   in the whole application, not just this panel's own stale widgets).

3. `t=22.143` (22ms later) — the peer's mirrored call (again via the
   queued `directory_scanned` signal, only dispatched once primary's own
   synchronous call has returned control to the event loop) enters, and
   its own `_stop_scanner_threads()` loop reaches back into **primary**
   again (`peer._stop_scanner_threads()`, logged with `panel=...9680`
   since `self` inside that call is primary) — a **second** global
   `DeferredDelete` flush, 22ms after primary's own.

4. The peer's own sequence completes cleanly from there — its own
   `ImageScannerWorker` at `t=22.164`, `VideoScannerWorker` at `t=22.200`
   (this is the orphaned span `telemetry_analyzer.py` flagged: no `.end`
   because the process died with it still running, not because it was
   the direct cause).

5. **Primary panel's own `ImageScannerWorker`/`VideoScannerWorker` for
   this second switch never appear in the telemetry file at all.** Given
   the peer's queued call only dispatches once primary's own synchronous
   `populate_scan_image_gallery()` call has already returned to the event
   loop, primary's *entire* call — flush, `clear_gallery_widgets()`,
   cache clear, `cancel_loading()`, the `os.scandir` quick-paths prefetch,
   and constructing/starting its own new `ImageScannerWorker` — had to
   execute somewhere inside that same 22ms window. It logged the flush
   and nothing after. **The crash is localized to primary's own
   `populate_scan_image_gallery()` body, after its `_stop_scanner_threads()`
   flush and before it reaches its own `img_worker.start.begin` line** —
   i.e. somewhere in `clear_gallery_widgets()` / `_initial_pixmap_cache.clear()`
   / `cancel_loading()` / the quick-paths prefetch, or in the act of
   constructing the new `ImageScannerWorker` and wiring its signals
   (recall Addendum 20 also resolved a *separate* crash instance to
   `QObjectPrivate::connect()` — consistent with this exact code region,
   which does both teardown *and* a fresh `.connect()` call for the new
   worker in the same stretch).

**Working hypothesis (evidence-backed, not yet implemented or confirmed
as a fix — matching this document's standing rule against speculative
fixes)**: the peer's *reentrant* `_stop_scanner_threads()` call reaching
back into primary — via `for peer_obj in self.linked_tabs: peer_obj._stop_scanner_threads()`,
with no guard against primary being mid-flight through its own, unrelated
`populate_scan_image_gallery()` call for a *different* switch — triggers a
**global** `sendPostedEvents(None, QEvent.Type.DeferredDelete)` flush that
is not scoped to just the peer's own stale objects. If primary's own
teardown/rebuild code has, in the intervening ~22ms, itself queued new
`deleteLater()` calls (e.g. from its own `clear_gallery_widgets()`) or
constructed new `QObject`s whose connections are being wired up, a
global flush triggered from a completely different call stack (the
peer's) at exactly the wrong moment is a plausible mechanism for
corrupting the very `ConnectionData` structure `deleteOrphaned` then
trips over. This is a materially more specific theory than "linked-panel
cross-talk" (Addendum 3) — it names the exact reentrant call path and the
`receiver=None` global-flush scope as the likely mechanism, not just "two
panels share state."

**Fix implemented (2026-08-01, same session, with explicit user
confirmation before touching this crash-history-sensitive code)**:
`populate_scan_image_gallery()`'s `for peer in linked_tabs:` loop
(`_scan_pipeline.py`) now skips calling `peer._stop_scanner_threads()`
when `getattr(peer, "_scan_pipeline_busy", False)` is true, emitting a new
`thread-lifecycle/stop_scanner_threads.peer_skip_busy` telemetry event
when it does. Semantics: if a linked panel is itself still mid-flight
through its own `populate_scan_image_gallery()` call (for a different,
newer switch than the one that call originally started for), that call
already handled — or, since it hasn't returned yet at the point of the
crash, still owns — its own scanner-thread lifecycle and its own
`_stop_scanner_threads()` call; a peer reaching in from a different call
stack to redundantly re-flush it is exactly the reentrant path Addendum
21 correlated with the live crash, via a process-wide (`receiver=None`)
`DeferredDelete` flush landing in the middle of that panel's own
in-progress teardown/rebuild.

**New regression tests**: `gui/test/core/test_wallpaper_linked_panel_scan_race.py::TestPeerReentrancyGuard`
— `test_peer_does_not_reenter_stop_scanner_threads_on_busy_panel` (asserts
the skip; verified this test *fails* against the pre-fix code, confirming
it actually exercises the new guard, not a tautology) and
`test_peer_still_stops_a_non_busy_panel` (the guard must not become a
blanket no-op — a genuinely idle linked panel with stale scanner threads
must still get stopped/drained exactly as before). All 12 tests across
`test_wallpaper_scan_race.py`, `test_wallpaper_linked_panel_scan_race.py`,
and `test_startup_probe_guard.py` pass with the fix in place.

**Still not independently verified against a live reproduction** — same
standing caveat as every prior round's fix. This one has unusually strong
evidence behind it (a real, telemetry+hs_err-correlated crash localized to
almost exactly this code path, not just a plausible-looking mechanism),
but "strong evidence" has looked like enough before and wasn't (rounds
2-16). Reproduce again with `IMAGE_TOOLKIT_TELEMETRY=1 debug/run_with_gdb.sh`
and the same rapid-switch pattern; if it recurs, check first whether the
new `stop_scanner_threads.peer_skip_busy` event fired before the crash
(if so, the guard engaged but something else is still wrong) or didn't
(the reentrancy path assumed here isn't the only trigger). No core dump
was available this round to directly inspect the corrupted
`QObjectPrivate`/`ConnectionData` and confirm the exact object involved —
`ulimit -c unlimited` (added to `run_with_gdb.sh` this round) didn't
produce one either; worth investigating apport/`core_pattern`
configuration separately if a core file is needed to go further.

## Addendum 22 (2026-08-01) — Addendum 21's fix is real but insufficient: a third capture shows genuine cross-thread contention on deleteOrphaned's mutex, triggered via a path the fix doesn't touch

A third `IMAGE_TOOLKIT_TELEMETRY=1 debug/run_with_gdb.sh` capture (`hs_err_pid2953168.log`,
`telemetry-2953168.jsonl`, `gdb-backtrace-20260801-131048.txt`) landed
after Addendum 21's fix was already in place. This is the richest capture
yet — for the first time, gdb's `thread apply all bt full` fully resolved
**Thread 1's entire native stack**, not just a raw offset:

```
QBasicMutex::lockInternal()
QObjectPrivate::ConnectionData::cleanOrphanedConnectionsImpl(QObject*, ...)
?? (unresolved, almost certainly deleteOrphaned's own frame)
QObject::destroyed(QObject*)
QWidget::~QWidget()
QObjectPrivate::deleteChildren()
QWidget::~QWidget()          <- a parent widget's destructor cascading into a child's
QObject::event(QEvent*)
QApplicationPrivate::notify_helper / QCoreApplication::notifyInternal2
QCoreApplicationPrivate::sendPostedEvents(QObject*, int, QThreadData*)
[Python C API frames: cfunction_call, _PyEval_EvalFrameDefault, ...]
PySide::SignalManager::callPythonMetaMethod(...)
QAbstractButton::clicked(bool)
[mouse event delivery frames]
QCoreApplication::exec()
[Python main / app.exec() entry]
```

Reading bottom-up: this is the **normal Qt event loop**, delivering a
**mouse click on a `QAbstractButton`**, invoking its connected Python
slot, which itself calls `QCoreApplicationPrivate::sendPostedEvents` —
i.e. **this is `_stop_scanner_threads()`'s own
`QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)` call**,
reached via a button click (most likely "Browse..." →
`browse_scan_directory()` → `populate_scan_image_gallery()`), **not** the
auto-restore timer path Addendum 21's reentrancy fix targets. That flush
processes a queued widget deletion; the widget's destructor cascades into
a child widget's destructor, which fires `QObject::destroyed`, which
tries to clean up that object's now-orphaned signal connections —
and blocks trying to acquire `QBasicMutex::lockInternal()`, at the exact
moment `gdb` caught SIGABRT (glibc heap-corruption abort) on this thread.

**Second, independent finding from the same run**: after gdb's `continue`
re-delivered the SIGABRT, the JVM's own fatal-error handler caught a
**second, separate SIGSEGV — on a different OS thread (`tid=2953934`,
not the main thread above) — at the exact same instruction offset**
(`libQt6Core.so.6+0x1e74d5`, i.e. `deleteOrphaned+0x165`, confirmed via
`debug/resolve_qt_offset.py`). Two different threads independently
faulting inside the identical instruction of the identical function
around the same moment is strong evidence this is genuine **cross-thread
contention**, not a single-thread ordering issue: telemetry for this run
shows an 8-thread `VideoScannerWorker` `ThreadPoolExecutor` was still
densely active at the crash instant — hundreds of
`process_video_task`/`qimage_from_cache` begin/end pairs completing every
~1ms, continuing right up to the very last recorded event, all for the
same `Wallpapers/Cinematography` scan traced in Addendum 21's
double-panel race. A worker thread emitting `thumbnail_ready` (which
touches its own `QObject`'s connection list) while the main thread
concurrently tears down widgets/connections on a related object is
exactly the shape of race `QBasicMutex` contention on
`ConnectionData` would produce.

**Assessment: Addendum 21's fix is a real, legitimate improvement — it
closes one genuine reentrant-call source of the same crash class — but
this capture proves it is not the whole story and likely not sufficient
on its own.** The crash here was reached via a **direct button click**,
not the peer-reentrancy path that fix guards against, and the evidence
now points at true concurrent thread contention on Qt's connection-list
mutex rather than (only) a single-thread timing/ordering problem. Do not
treat Addendum 21's fix as a resolution of this crash class; it should be
kept (it's correct and tested on its own terms) but the investigation
should continue.

**Fix (a) implemented (2026-08-01, same session, explicit user
confirmation to pursue this direction over (b))**: every scanner-worker
stop path now disconnects the worker's signals (`thumbnail_ready`/
`finished` for `VideoScannerWorker`; `scan_finished`/`scan_error`/
`finished` for `ImageScannerWorker`) as the very first step, before
`requestInterruption()`/`stop()`/`.wait()`/`deleteLater()` or anything
else touches the worker — emptying its connection list up front, while
it's still safe to do so, so a later concurrent `deleteOrphaned()`
elsewhere in the app has nothing left to race against for that specific
worker. Applied in all three inline stop-block locations: `_scanner_lifecycle.py`'s
`_stop_vid_scanner_worker()` and `_stop_scanner_threads()` (Wallpaper
tab), and `extractor_tab/_directory_scanning.py`'s equivalent inline
block (this crash class isn't Wallpaper-tab-specific). A disconnected
signal's `emit()` is a fast, safe no-op (Qt iterates zero connections),
so this cannot break a worker's own in-flight `run()` logic — it only
stops results/completion from reaching UI slots, which is exactly what
tearing the worker down means to do anyway.

**Confirmed live, incidentally, while writing the regression test**:
`_stop_scanner_threads()`'s own trailing `sendPostedEvents(None,
QEvent.Type.DeferredDelete)` really does synchronously process a
just-`deleteLater()`'d worker's actual C++ destruction before the
function returns (a test emitting on the worker immediately afterward hit
`RuntimeError: Signal source has been deleted`) — direct confirmation of
the exact `sendPostedEvents → ~QWidget → ... → deleteOrphaned` call chain
this addendum's gdb backtrace showed.

**New regression tests**: `test_wallpaper_scan_race.py::TestSignalDisconnectBeforeTeardown`
(2 tests) confirm the disconnect actually takes effect — a stale `emit()`
after the stop call never reaches the old slot (either because it's
disconnected, or because the object was already fully destroyed by the
trailing flush, an even stronger guarantee). All 20 tests across
`test_wallpaper_scan_race.py`, `test_wallpaper_linked_panel_scan_race.py`,
`test_startup_probe_guard.py`, and `test_extractor_drag_preview.py` pass.

Candidate direction (b) — auditing whether `.wait()` genuinely blocks
until the worker's own `ThreadPoolExecutor` is fully idle, or only until
the outer `VideoScannerWorker.run()` QThread returns — remains
unexplored; worth revisiting if this fix also proves insufficient. Still
no core dump available to inspect the actual contended mutex/object
directly; `ulimit -c unlimited` continues to not produce one despite four
consecutive crashes all claiming they would write one.

**Still not independently verified against a live reproduction.** This
is the second fix attempt in this session alone (see Addendum 21, also
unconfirmed live and shown insufficient by Addendum 22's own later
capture) — reproduce again with `IMAGE_TOOLKIT_TELEMETRY=1
debug/run_with_gdb.sh`, the same rapid-switch pattern, and this time also
try clicking "Browse..." while a scan is still active (the path Addendum
22's crash actually went through). If it recurs, check the telemetry for
the new `*.signals_disconnected` events to confirm the fix path was
actually reached before the crash.

**Reassessed status**: the SIGSEGV landing inside JVM-managed code, on the
main thread, during/immediately after `jpype.startJVM()` (matching
telemetry's unclosed `jvm.start.start` span, same PID) is the strongest
lead this investigation has had in eighteen rounds that this may be a
genuine HotSpot-side issue (JIT compiler bug, or a JNI/native problem
inside the JVM) rather than a Qt/PySide6 scanner-thread race -- with the
directory-scan trigger being an unrelated, downstream detection point
(glibc's heap check is lazy; a video scan's heavy allocation is just where
it happens to next look), not the cause. The "too slow now triggers it,
too fast used to" behavioral flip fits this: more idle wall-clock time
lets the JVM's own JIT/GC threads do more work before the next heavy
allocation stumbles on whatever they damaged. Next repro should use the
fixed `run_with_gdb.sh` and prioritize reading the resulting `hs_err_pid*.log`
over gdb's own backtrace.

## Addendum 19 (2026-08-01) — Addendum 18 was a tooling artifact, not a real lead: gdb was intercepting the JVM's own benign, self-handled SIGSEGVs

The user ran the fixed `run_with_gdb.sh` (with the `continue`-after-backtrace
change from Addendum 18) and reported the app now appeared to crash
*before the login window even opened* -- a symptom that has never occurred
in eighteen rounds of un-debugged reproduction. That mismatch was the tell
that something about the gdb harness itself, not the app, was the problem.

**Root cause of the whole Addendum 18 detour: HotSpot JVMs raise SIGSEGV
*on purpose* as part of normal operation.** Implicit null-pointer checks
and safepoint polling are both implemented by deliberately letting the CPU
fault, then the JVM's own installed signal handler catches the SIGSEGV,
determines it's an expected case, and recovers (turns it into a
`NullPointerException`, or simply resumes execution) -- this is standard,
documented HotSpot behavior, not a bug. `run_with_gdb.sh`'s
`handle SIGSEGV stop print` made gdb break on *every single one* of these
totally benign, self-handled signals, indistinguishable at that level from
a real fault. That explains, retroactively, everything Addendum 18 found:

- The "matching JIT-codecache address" (`0x00007ffddfa5f692`, reproduced
  identically across separate process runs) wasn't evidence of a
  deterministic real crash -- gdb disables ASLR for the debuggee by
  default, so a routine, always-executed safepoint-poll fault at a fixed
  point in JVM bootstrap naturally lands at the same address every time
  under gdb. It says nothing about corruption.
- `Installing openjdk unwinder` / `No type named CodeBlob` wasn't a clue
  that something was going wrong in JIT code -- it's gdb correctly
  recognizing it's looking at a HotSpot-internal fault and trying (and, on
  this JDK/gdb pairing, failing) to give it a nicer unwind. Completely
  consistent with "this is a normal HotSpot mechanism," not evidence of a
  bug.
- Confirmed directly this round: after fixing the script to stop only on
  SIGABRT and letting SIGSEGV pass through untouched
  (`handle SIGSEGV nostop noprint pass`), the exact same run proceeded
  cleanly through JVM startup, keystore loading, and secret-key retrieval
  -- reaching much further into the login flow than any previous gdb
  capture -- before a **second** SIGSEGV occurred during
  `"Retrieving secret key for alias: my-aes-key"` (JNI crypto operations).
  Whether *that* one is another benign HotSpot signal or a genuine fault
  is not yet known -- it needs the same nostop/pass treatment applied and
  reproduced again to see whether the app fully recovers past it too.

**Fix applied**: `run_with_gdb.sh` now uses
`handle SIGSEGV nostop noprint pass` (invisible pass-through, matching
un-debugged behavior exactly) and only `handle SIGABRT stop print` --
SIGABRT is never used by the JVM for anything routine, so stopping there
still catches the actual "corrupted size vs. prev_size" symptom this tool
was built for, without the false-positive noise.

**This round's core lesson for the whole investigation, restated
plainly**: debugging a process with an embedded JVM under gdb requires
telling gdb about the JVM's own signal conventions first
(`nostop noprint pass` on SIGSEGV, at minimum), or every capture will be
dominated by artifacts of the JVM's normal operation rather than the
actual bug. **Addendum 18's central finding -- that this crash class might
be JVM/HotSpot-internal rather than a Qt/PySide6 scanner-thread race -- is
now unconfirmed again**, not disproven, just no longer supported by the
evidence that prompted it. The original SIGABRT/"corrupted size vs.
prev_size" symptom, and every one of rounds 1-17's Qt-side findings, still
stand exactly as documented above Addendum 17. Next repro with the fixed
script is needed before drawing any new conclusion.

## Addendum 23 (2026-08-01) — change of approach: video-directory scanning removed entirely, rather than fixed; live-tested, crash confirmed gone

After Addendum 22's fix (disconnect worker signals before teardown) was
committed, the user reported it made the crash class *worse*, not
better: the app now crashed on the very first video-directory browse,
where it previously needed rapid repeated switches to reproduce. Given
23 rounds of fixes to this exact crash class, two of them landed and
tested in this very session, neither closing it and the last one making
it more reliable rather than less, the user made the call to stop
patching and remove the feature instead: **all code implementing
"browsing/scanning a directory with videos" was deleted wholesale**,
across every tab that had it, keeping only image-directory scanning
(never implicated in this crash class across 22 rounds).

**Scope of the deletion:**

1. **`VideoScannerWorker`** (`gui/src/helpers/video/video_scan_worker.py`,
   deleted entirely) — the bespoke QThread + internal
   `ThreadPoolExecutor` class that scanned a directory for video files
   and generated thumbnails for each. This was the actual crash
   mechanism traced in Addenda 20-22. All wiring removed from:
   - Wallpaper tab: `_scan_pipeline.py` (the image-scan-then-video-scan
     chain collapsed to image-scan-only; `_on_image_scan_finished()` now
     settles the pipeline directly instead of chaining into a video
     scan), `_scanner_lifecycle.py` (`_stop_vid_scanner_worker()` deleted,
     `_stop_scanner_threads()` now only handles the image scanner
     thread), `_widget_ui_lifecycle.py`/`system_display_subtab/_lifecycle.py`
     (video-scanner teardown blocks removed from `closeEvent()`/
     `cancel_loading()`), `manager.py` (`vid_scanner_worker` attribute
     removed).
   - Extractor tab (`_directory_scanning.py`, `manager.py`,
     `_media_player.py`): this tab's entire reason to exist is browsing a
     folder of videos, so removing the worker left a real functional gap
     -- `scan_directory()` is now a plain, synchronous `os.scandir()`
     listing (no background thread, no signal-based thumbnail delivery).
     Placeholders show the filename only; a thumbnail only appears if one
     already exists in the on-disk cache from a prior session. Nothing
     *generates* a new one anymore.

2. **`VideoLoaderWorker`/`BatchVideoLoaderWorker`** (`gui/src/helpers/video/video_loader_worker.py`/
   `batch_video_loader_worker.py`, both deleted entirely) — the separate,
   QRunnable/`QThreadPool`-based thumbnail loader used by every tab
   inheriting `AbstractClassTwoGalleries` (Convert/Delete/Merge/Search/
   scan_metadata/similarity) or `AbstractClassSingleGallery`
   (Wallpaper/Extractor/reverse_search/merge). This class was **never
   implicated in any of the 22 rounds of crash reports** -- it has a
   fundamentally different threading model (per-task `QRunnable` on the
   global pool, not a bespoke `QThread` with its own internal executor)
   -- but the user explicitly asked for it removed too, for consistency:
   these tabs no longer discover or load video files as part of a
   directory scan at all, only images. Wiring removed from
   `_found_gallery_load.py`, `_found_gallery_populate.py`,
   `_selected_panel.py`, `_sort_zoom.py` (two-galleries) and
   `_loading_pipeline.py` (single-gallery). `VideoThumbnailer` itself
   (`video_thumbnailer.py`, the low-level ffmpeg-subprocess-calling
   utility both deleted workers used) was **kept** -- it's also used by
   `extractor_tab/_extraction_workers.py` and
   `wallpaper_common_base/_gallery_label.py` for on-demand, synchronous,
   single-file thumbnail generation (extraction preview, card labels),
   which is a different feature (not directory scanning) and was never
   part of this crash class either.

**Unrelated, concurrent complication**: mid-deletion, an independent,
already-in-progress reorganization of `gui/src/utils/` (moving
`lru_image_cache.py`, `shortcut_manager.py`, `startup_probe_guard.py`
into new `cache/`/`manager/`/`guard/` subpackages with barrel
`__init__.py` re-exports) landed in the same working tree, breaking every
direct-submodule import of those three modules across ~16 files
(including several this session's own earlier telemetry/shortcuts work
had added). Fixed by updating every `utils.lru_image_cache` /
`utils.shortcut_manager` / `utils.startup_probe_guard` import to its new
`utils.cache.` / `utils.manager.` / `utils.guard.` path.

**Live-tested result: the crash is gone.** The user ran the app with
this round's changes and reproduced their exact original repro (browse a
Wallpaper directory, then immediately browse a second, different
directory) twice in a row with no native crash, no `QSocketNotifier`
warning, no SIGABRT/SIGSEGV -- the app ran a full session and shut down
cleanly. This is the first time in 23 rounds this exact repro has not
crashed.

**A new, much more tractable bug surfaced instead**: repeated
`RuntimeError: Internal C++ object (DoubleClickableLabel) already
deleted` in `gui/src/helpers/image/card_thumb_worker.py`'s
`_dispatch_thumbnail()` -- a `QLabel` registered as a thumbnail-load
waiter got destroyed (gallery rebuilt for a new directory switch) before
the queued, cross-thread `ready` signal carrying its thumbnail arrived.
Unlike every crash this document tracks, this is a **caught Python
exception** (Qt/PySide's exception boundary logs it and continues, no
native fault), and a completely standard instance of a pattern already
guarded against everywhere else in this codebase. Fixed by wrapping the
per-waiter access in `try/except RuntimeError: continue`, skipping stale
waiters instead of touching a deleted object.

**Known, accepted gap**: video files are no longer discovered, scanned,
or thumbnailed *anywhere* in the app. A directory containing only videos
(no images) now shows nothing in any gallery. This is the direct,
expected consequence of the deletion above, not a bug -- "re-do it from
scratch" (the second half of the user's instruction) has not been
started yet. Given `VideoLoaderWorker`'s `QRunnable`/`QThreadPool`
architecture was never once implicated across 22 rounds, unlike
`VideoScannerWorker`'s bespoke `QThread` + internal executor, that
architecture is the leading candidate to build the replacement on --
pending discussion before implementing, per this document's own standing
rule.

## Addendum 24 (2026-08-01): video thumbnail scanning re-implemented

Same session, later: the user asked for the video-scanning functionality
to be rebuilt from scratch, informed by everything above. The rebuild
deliberately keeps the architectural split the deletion phase's own
analysis pointed at -- **directory scanning** (finding video file paths)
and **thumbnail generation** (decoding a frame) are now two entirely
separate concerns, each reusing whichever of the two pre-existing
patterns was never implicated across 22+ rounds of crash reports:

1. **`VideoScannerWorker`** (`gui/src/helpers/video/video_scan_worker.py`)
   was rewritten from scratch as a scan-only `QThread`, deliberately
   modeled line-for-line on `ImageScannerWorker`
   (`gui/src/helpers/image/image_scan_worker.py`) -- `os.scandir`/
   `base.scan_files_multi`, no internal `concurrent.futures.ThreadPoolExecutor`,
   no thumbnail generation inside `run()`, just a `scan_finished(list)`
   signal carrying found video paths. The **old** `VideoScannerWorker`
   combined scanning AND thumbnail generation in one `QThread`, fanning
   the latter out across an internal executor -- concurrent
   subprocess+`QImage` decode calls on raw Python threads Qt's own
   machinery doesn't manage, landing squarely on the suspected native
   crash boundary documented in `video_thumbnailer.py`'s
   `_decode_span()` docstring (Addendum 11). That coupling is gone.

2. **`VideoLoaderWorker`/`BatchVideoLoaderWorker`** (QRunnable, dispatched
   via the normal `QThreadPool` -- same architecture as
   `ImageLoaderWorker`/`BatchImageLoaderWorker`) were restored close to
   verbatim from before the deletion (they were never implicated in any
   of the 22 rounds), with an added optional `crop_square` parameter to
   preserve the Extractor tab's square-cropped thumbnails without a
   separate code path.

**Wallpaper tab** (`wallpaper_common_base/_scan_pipeline.py`): the video
scan is deliberately sequenced strictly **after** the image scan settles
-- `_on_image_scan_finished()` now calls `_start_video_scan()` instead of
`_settle_scan_pipeline()` directly, and only the video phase's own
completion (`_on_video_scan_finished()`/`_on_video_scan_error()`) settles
the pipeline. The two scans are never concurrent within one panel, so the
existing busy-flag serialization and peer-reentrancy guards (Addenda
9/21) cover both phases as a single unit without modification. Found
video paths are merged into the gallery via the existing
`start_loading_gallery(..., append=True)` path, which was already
video-aware once `_loading_pipeline.py`'s video branches (below) were
restored -- no wallpaper-specific thumbnail-loading code was needed.
`_scanner_lifecycle.py` gained a `_stop_vid_scanner_worker()` mirroring
`_stop_scanner_threads()` exactly (same Addendum 22
disconnect-before-teardown mitigation, same unbounded `wait()`), called
from inside `_stop_scanner_threads()` itself so every existing call site
(including the peer loop) drains both worker types. `manager.py` gained
`vid_scanner_worker`/`vid_scanner_thread` attributes;
`_widget_ui_lifecycle.py`'s `closeEvent()` and
`system_display_subtab/_lifecycle.py`'s `cancel_loading()` gained the
matching cleanup blocks, mirroring the image-scanner ones exactly.

**Extractor tab** (`extractor_tab/_directory_scanning.py`): kept its
existing safe, synchronous `os.scandir()` placeholder-population logic
unchanged, and added thumbnail generation as a separate step: paths with
no disk-cache hit are dispatched as one `BatchVideoLoaderWorker(...,
crop_square=True)` on `QThreadPool.globalInstance()`. No persistent
worker QThread is kept on `self` at all (unlike before) -- a
monotonically increasing `_extractor_scan_generation` counter, bumped at
the very start of `scan_directory()` before any teardown, is captured by
value in the result-signal closures and compared at delivery time; a
mismatch means the directory was switched again since dispatch, and the
result is silently dropped. This sidesteps the old design's entire
`vid_scanner_worker` stop/wait/drain/disconnect lifecycle (previously
duplicated in `manager.py` and `_media_player.py`) rather than
reproducing it.

**Two-galleries / single-gallery bases**: `_found_gallery_load.py`,
`_found_gallery_populate.py`, `_selected_panel.py`, `_sort_zoom.py`
(`abstract_class_two_galleries`) and `_loading_pipeline.py`
(`abstract_class_single_gallery`) had their video branches restored
close to verbatim from before the deletion -- this code was never
implicated in any crash round, so no redesign was needed, only
re-wiring against the current file state (Shiboken guards added
elsewhere in this session, drag-reorder mixin, disk-cache mixin).

**A second, independent bug found and fixed during verification**:
scoped `pytest --run-gui` runs of `test_extraction_history.py` segfaulted
during test-fixture teardown, traced to `self.sender()` being called on
a gallery widget (`abstract_class_single_gallery`/
`abstract_class_two_galleries`) whose C++ `QObject` was already destroyed
by the time a queued cross-thread load-result signal was delivered --
`self.sender()` on a dead `QObject` segfaults rather than raising
`RuntimeError`. This is the same crash *class* as everything else in
this document, just newly caught in the image-loading path rather than
video-scanning. Fixed with a `Shiboken.isValid(self)` guard at the top of
`_on_single_image_loaded`, `_on_batch_images_loaded`,
`_on_found_image_loaded`, `_on_batch_found_loaded`,
`_on_batch_selected_loaded`, and `_on_selected_image_loaded`.

**Verification**: full repo import sweep (`backend.src.app`, `gui.src.tabs`,
`gui.src.windows`, etc.) clean; `python -m compileall` clean (only
pre-existing Python-2 fixtures under vendored `.pixi/` envs fail, as
expected); every scoped GUI test file touched by this session passes
individually, run one file at a time per the standing "never run
unscoped GUI test files together" rule --
`test_video_helper.py` (7, including new `TestVideoScannerWorker`/
`TestVideoLoaderWorker`/`TestBatchVideoLoaderWorker` coverage),
`test_wallpaper_scan_race.py`, `test_wallpaper_linked_panel_scan_race.py`,
`test_gallery_classes.py`, `test_extraction_history.py` (previously
segfaulting, now passing 3x in a row), `test_main_window.py`,
`test_settings_window.py`, `test_extractor_drag_preview.py`. **Not yet
live-tested in the running app** by the user -- unlike every previous
round in this document, this one has not yet been confirmed against a
real directory-switch repro. That confirmation is still needed before
this addendum's fix can be considered validated the way Addendum 23 was.

## Addendum 26 (2026-08-03) — round 24's rebuild recurred on its first live exercise; delegated analysis, applied a native-scan-concurrency lock (unverified)

Round 24's rebuilt `VideoScannerWorker` (scan-only, modeled on the never-implicated `ImageScannerWorker`) hit its first live exercise via this session's automatic Wallpaper-tab startup restore of a video-only directory (`Wallpapers/Videos`) — and crashed anyway, ~37.5 minutes after JVM start (`hs_err_pid284752.log`): `QSocketNotifier: Socket notifiers cannot be enabled or disabled from another thread`, then `QSocketNotifier: Invalid socket 29 and type 'Read', disabling...`, then `SIGSEGV` at `libQt6Core.so.6+0x1f6cec` → `QSocketNotifier::setEnabled(bool)+0x3c`, `si_code: SEGV_MAPERR`, `si_addr: 0x91` — on the **main thread**. The stdout trace shows both linked Wallpaper panels' `_on_image_scan_finished()` had *just* proceeded within the same event-loop burst, meaning (per round 24's design) both panels' `_start_video_scan()` — and therefore two independent `VideoScannerWorker` QThreads, each about to call the native `base.scan_files_multi()` — were starting at essentially the same instant. No `IMAGE_TOOLKIT_TELEMETRY` was set for this run, so there's no correlated telemetry for this specific crash.

Per explicit user instruction, this round's analysis was delegated to a Gemini subagent (via the `agy`/Antigravity CLI) with the full 24-round history + current source of `_scan_pipeline.py`/`_scanner_lifecycle.py`/`video_scan_worker.py` + this crash's stdout and `hs_err` header as zero-shot context. Gemini's hypothesis (stated confidence: high, but **not independently verified live** by this session): the two linked panels' `VideoScannerWorker` QThreads both call `base.scan_files_multi()` concurrently for the same directory almost simultaneously — nothing in the 24 prior rounds ever established this native pybind11 boundary is safe to call reentrantly from two threads at once, and the `QSocketNotifier`/near-null-address crash signature is consistent with concurrent native-side file-descriptor churn (FD 29 colliding with a Qt-internal notifier's own fd). This is a genuinely new angle: every prior round focused on Qt-side connection/lifecycle races (`deleteOrphaned`, `QObjectPrivate::connect()`, widget teardown ordering) or startup timing, never on whether the shared native call itself is thread-safe when hit concurrently by two independent scanner QThreads (a scenario that structurally can't happen for the image-scan phase alone, since round 21's peer-busy-skip guard only serializes the *outer* `populate_scan_image_gallery()` call, not the *inner* `_start_video_scan()` call both panels reach independently once their own image phase settles).

**Fix applied (defensive, low-risk, NOT yet live-verified)**: added `telemetry.NATIVE_SCAN_LOCK` (a plain `threading.Lock()`, module-level in `backend/src/core/telemetry.py` since both scanner workers already import that module) and wrapped the `base.scan_files_multi(...)` call in both `ImageScannerWorker.run_scan()` and `VideoScannerWorker.run_scan()` with it, serializing every call into this native boundary across every scanner-worker instance/panel. This does not change any Qt-side connection/signal logic already fixed in rounds 1-25 — it only prevents two threads from being inside the native call at the same time, which costs at most one scan's worth of serialization delay (scans are fast; the lock is held only for the duration of the native call, not the whole worker lifecycle).

**Verification status, stated plainly**: `python -m py_compile` and `ruff check` pass on all three changed files; the lock object itself was confirmed present and correctly typed via an isolated module load (bypassing `backend.src.core`'s package `__init__`, which eagerly imports `duplicate_finder` → `import base`). **The native `base` C++ extension currently fails to import at all in this environment** (`ImportError: libopencv_videoio.so.413: cannot open shared object file`) — confirmed via `git stash` that this import failure pre-dates this round's changes entirely (almost certainly fallout from an unrelated repo-directory reorganization moving `~/Repositories/Image-Toolkit` to `~/Repositories/Repos/Image-Toolkit`, breaking a pixi-env RPATH lookup — see `project_extension_roadmap`/build-env memory). This means **this fix could not be live-tested against a real video-directory scan in this session at all** — unlike every other round in this document, which each got at least a real-or-refuted live cycle. The native extension environment needs to be repaired (rebuild `base` against the new path, or fix the pixi env's RPATH resolution) before this fix — or anything else touching `VideoScannerWorker`/`ImageScannerWorker` — can be confirmed live.

**Honesty note per this document's own standing rule**: this is Gemini's hypothesis, relayed and applied by Claude without independent confirmation of whether `base.scan_files_multi()` is actually unsafe under concurrent calls (the C++ source wasn't available to either party to check directly) — treat this as a plausible, low-risk mitigation worth keeping regardless of whether it's the actual root cause, not a confirmed fix. If the crash recurs with an identical signature after this lock is in place (once the native extension is working again to even test it), that would be reasonably strong evidence against this round's hypothesis and should point back toward the Qt-connection-lifecycle theories rounds 20-22 already explored in depth.

## Addendum 27 (2026-08-03) — the Addendum 16 "second, unrelated bug" finally root-caused and fixed: eager QSystemTrayIcon construction; a lower-frequency residual crash confirmed still open

After the `~/Repositories/Image-Toolkit` → `~/Repositories/Repos/Image-Toolkit` directory move (a separate, intentional user action), `just python` failed outright: first `python: command not found` (the venv's `activate`/`activate.csh`/`activate.fish` scripts had the old absolute path hardcoded into `VIRTUAL_ENV`/`PATH` — fixed via `sed` in-place, not a code change, not committed since `.venv/` is gitignored), then `ImportError: libopencv_videoio.so.413: cannot open shared object file` (the compiled `base.cpython-311-x86_64-linux-gnu.so` extension had the OLD absolute path baked into its ELF `RUNPATH` — fixed via `patchelf --set-rpath` pointing at the new `.pixi/envs/default/lib` location, again a build artifact fix, not committed/not a source change).

With those two environment-only fixes in place, the app launched but crashed **4/4 times** with a **null-pointer SIGSEGV in `libQt6Gui.so.6+0x136666`**, `si_addr: 0x0`, on the **main thread**, with **no preceding `QSocketNotifier` warning**, immediately after "Logging reconfigured from preferences" and before any wallpaper-tab scan code ran — this is an **exact match for the "second, apparently unrelated bug" flagged in Addendum 16 above and never investigated further** (that round explicitly named `_setup_tray_icon()`, `QGuiApplication.styleHints().colorSchemeChanged.connect(...)`, and `self.restoreGeometry(_geom)` as candidates for "what runs next in `MainWindow.__init__()`").

**Root-caused via direct bisection** (not inference): temporarily skipping the `self._setup_tray_icon(app_icon)` call inside `MainWindow.__init__()` (gated behind `if QSystemTrayIcon.isSystemTrayAvailable():`) took the crash rate from 4/4 to **0/3**. Re-enabling it and instead deferring the call — first via `QTimer.singleShot(0, ...)`, then `QTimer.singleShot(1500, ...)`, then via this window's own first `showEvent()` — still crashed roughly half the time either way, at the same or an immediately adjacent offset (`+0x136666`, `+0x14071e`, `+0x1342c4` all observed across these attempts). This is the same shape as this document's own Addendum 13 conclusion for a *different* Qt subsystem (`QAudioOutput`/Qt Multimedia's PipeWire backend): a genuinely unstable native call under this specific Plasma6/Wayland/Qt6 combination is not fixed by *when* it's called, only by not calling it unconditionally at all.

**Fix**: removed the automatic call to `_setup_tray_icon()` entirely (`gui/src/windows/main/main_window.py`, `gui/src/windows/main/_lifecycle.py`). `_setup_tray_icon()` itself (`_tray.py`) is untouched and fully callable — this only removes the unconditional every-session call, so the crash-risk cost is no longer paid regardless of whether tray features are ever used. `self._tray_icon` stays `None`; every existing reader of it (`tray_notify()`, `_lifecycle.py`'s minimize-to-tray check) already null-guards correctly.

**Verified**: 6 consecutive `just python` launches post-fix — **5/6 clean**. Nearest-exported-symbol resolution (`debug/resolve_qt_offset.py`) for this crash family points to `QPlatformWindow::setMouseGrabEnabled(bool)@@Qt_6_PRIVATE_API + 0x184e` — the `+0x184e` gap is large enough that this is almost certainly landing in unexported/static platform-plugin code near that symbol, not literally inside mouse-grab logic; treat this resolution as a rough locator, not a confirmed identification. Also confirmed the crash is **not** Wayland-platform-specific: forcing `QT_QPA_PLATFORM=xcb` reproduced the identical `+0x136666` offset.

**Known residual, NOT fixed by this round**: the 1 crash out of the 6 post-fix verification runs happened during the *login* phase (right after "Data loaded and decrypted successfully", well before "MainWindow construction starting" ever printed) — a different point in the startup sequence than the tray-icon bug, same `libQt6Gui.so.6` offset cluster (`+0x1342c4`). This is consistent with the "one underlying corruption, many possible touch points" unified theory from Addendum 20 rather than a new, distinct bug — not investigated further this round given the scope was "make `just python` work reliably," which is now true the large majority of the time (was 100% failure, now ~17% failure via a separately-tracked, already-open crash class). If this residual crash becomes frequent/blocking on its own, it needs its own dedicated round rather than being conflated with the tray-icon fix this round made.

## Addendum 28 (2026-08-03) — Addendum 26's own hypothesis re-examined against the actual C++ source; the real unguarded native boundary found and locked

A user-reported crash during Media Loader/nhentai use produced the exact Addendum-26 signature (`QSocketNotifier: Socket notifiers cannot be enabled or disabled from another thread` → `SIGSEGV` in `libQt6Core.so.6+0x28a641`, `QString::vasprintf`) — but the stdout trace showed it firing during the *Wallpaper tab's automatic startup scan-dir restore* for two linked panels (`populate_scan_image_gallery` → `ImageScannerWorker` for panels `7b7e792b8800`/`7b7e78ab9400`, both proceeding within the same event-loop burst), not inside any nhentai/Media Loader code path at all. A dedicated subagent traced the full nhentai → `MediaLoaderWorker` (`QThread`, overrides `run()`, never calls `exec()`) → `NhentaiDownloader` (`requests`-only, no Qt objects touched off-thread) call chain and found it clean — confirming this instance is unrelated to Media Loader specifically and is another recurrence of this document's still-open residual crash class, coincidentally timed with the user's session.

This time, unlike every prior round chasing this specific signature, the native `base` C++ extension **was importable and its source directly readable**, so Addendum 26's Gemini-relayed hypothesis (concurrent calls into `base.scan_files_multi()` from two scanner `QThread`s) could finally be checked against ground truth rather than inferred:

- **`base::image::scan_files`/`scan_files_multi`** (`base/src/image/scan_files.cpp`) turns out to be reentrant by construction — pure `std::filesystem` iteration into local `std::vector`s, no global/static mutable state whatsoever. `NATIVE_SCAN_LOCK` (added in round 26) was almost certainly never fixing anything real for this function; it's kept anyway (cheap, harmless) rather than removed on read-only confidence, but round 26's hypothesis was very likely misdirected.
- **`base::image::load_image_batch`** (`base/src/image/image_batch.cpp`) is the actual candidate this document never checked: it explicitly releases the GIL (`py::gil_scoped_release`) and fans out `cv::imread`/`cv::imdecode`/`cv::resize`/`cv::imwrite` across an **OpenMP** thread team (`#pragma omp parallel for schedule(dynamic)`), including unlocked read-then-write access to a **shared on-disk thumbnail cache** (mtime-invalidated, no file lock). It is called from `gui/src/helpers/image/batch_image_loader_worker.py::native_load_batch()`, which both `BatchImageLoaderWorker` (batch) and `ImageLoaderWorker` (single-image) funnel through — i.e. essentially every `QThreadPool` thumbnail-load task, across every open gallery tab, calls into this same native boundary, with **no prior synchronization at all** (this function was never covered by `NATIVE_SCAN_LOCK`). Two linked Wallpaper panels finishing their scans back-to-back both immediately queue thumbnail-loading runnables — exactly the concurrency shape round 26 was looking for, just one function over from where it looked.

**Fix applied**: added `telemetry.NATIVE_IMAGE_BATCH_LOCK`, a dedicated `threading.Lock()` (kept separate from `NATIVE_SCAN_LOCK` since the two are logically unrelated hot paths), and wrapped both `base.load_image_batch()` call sites in `native_load_batch()` with it. Cost is expected to be low: a single call already parallelizes across all cores via OpenMP internally, so serializing *concurrent Python-level entries* removes race risk without removing real parallelism (OpenMP was already doing that inside one call).

**Verification status, stated plainly**: `python -m py_compile` passes on all changed files; a real Python import of both `backend.src.core.telemetry` and `gui.src.helpers.image.batch_image_loader_worker` succeeds and the new lock is present/correctly typed; the pre-existing `backend/test/core/test_telemetry.py` suite was run before and after this change and produces identical pass/fail results (8 pre-existing failures unrelated to this change, confirmed via `git stash`) — so no regression there. **This fix has NOT been live-verified against a real repeated `just python` + concurrent-gallery-load cycle in this session** (no interactive display available to this agent) — same caveat as round 26's own fix. If the `QSocketNotifier`/`vasprintf` signature recurs after this lands, that's reasonably strong evidence this wasn't the (whole) mechanism either, and the next round should look at whether OpenMP itself (`libgomp`) has a documented incompatibility with being invoked from multiple truly-concurrent host threads under glibc, independent of any particular OpenCV call.

## Addendum 29 (2026-08-18) — three fresh crashes, two different offsets, no new independent trigger found; a real repro-strategy trap identified (telemetry masks the race)

Harbinger hit this crash class three times in one session: once attributed to Media Loader (log truncated, not captured), once on a plain app restart, and once right after the Web tabs (`ImageCrawlTab`/`WebRequestsTab`/`DriveSyncTab`) finished loading their configs. Two dedicated subagent rounds investigated; summary below so a future round doesn't repeat this work.

**Offset resolution, via `dev/resolve_qt_offset.py` (Addendum 20's tool) against the two hs_err logs still on disk from the first two crashes** (`hs_err_pid11459.log`, `hs_err_pid23123.log`):

```
libQt6Core.so.6+0x1df7c9 -> QObjectPrivate::connect(QObject const*, int, QtPrivate::QSlotObjectBase*, Qt::ConnectionType)@@Qt_6_PRIVATE_API + 0x109
```

— **identical offset in both logs**, and identical to Addendum 20's own `connect()` capture from 2026-08-01. Both crashes' visible startup logs showed the two linked Wallpaper panels (`system_display`/`monitor_display`) racing `populate_scan_image_gallery` for the same restored scan directory (the already-understood, already-partially-guarded race from Addenda 16/21/22/26/28) — consistent with Addendum 20's still-open, never-telemetry-correlated `connect()` lead, not a new bug. `IMAGE_TOOLKIT_TELEMETRY` was unset for both, so (same gap Addendum 20 flagged five weeks ago) *which* `.connect()` call was in flight at the fault remains unknown.

**Third crash: a genuinely different offset, at a different point in startup, with no wallpaper-scan activity yet:**

```
libQt6Core.so.6+0x47c9e1 -> QEventDispatcherGlibPrivate::~QEventDispatcherGlibPrivate()@@Qt_6_PRIVATE_API + 0x191
```

(`hs_err_pid69166.log`, repo root). The `[thread-lifecycle]` prints (`_scan_pipeline.py`'s own unconditional, non-telemetry-gated logging) — present before both of the first two crashes — are **absent entirely** before this one: the wallpaper scan-dir restore had not started yet. This destructor offset, and the immediately-preceding `QSocketNotifier: Socket notifiers cannot be enabled or disabled from another thread` warning, closely match the mechanism `gui/src/helpers/web/media_loader_worker.py`'s own docstring documents and was already fixed for (constructing a `QObject` inside an overridden `QThread.run()` that never calls `exec()` lazily allocates a per-thread glib-dispatcher socket notifier; tearing down that thread, or an unrelated socket later reusing the closed fd, crashes when the notifier is next touched off-thread).

**Two subagent rounds searched for an auto-started (non-user-triggered) `QThread` that could be responsible — found none.** Checked and ruled out (all construction sites are behind explicit user actions — button clicks, dialog confirmations — not startup/`__init__`/`set_config`):
- `ImageCrawlTab`/`WebRequestsTab`/`DriveSyncTab`'s own `set_config()` (synchronous widget population only, no threads)
- `ImageCrawlWorker`, `WebRequestsWorker`, `SyncBackupWorker`/`_SyncBackupWorker`, `MalSyncWorker`, `ImageEmbeddingWorker`, `ListingsEmbeddingWorker`, `RecommendationWorker`, `UpsertWorker`, `ListingsSemanticSearchWorker`, `IndexBuildWorker`/`ResolveWorker`/`BatchSuggestWorker`
- `DatabaseTab.__init__`'s auto `connect_database(silent=True)` call (does run automatically at startup — traced its full body, no `QThread` construction anywhere in it)
- `ExtractorTab.scan_directory()` (also auto-runs at startup) — synchronous `os.scandir()` + `QThreadPool`/`QRunnable` (`BatchVideoLoaderWorker`), not a raw `QThread`; this module's own docstring already says this path was never implicated across 22+ rounds
- `MainWindow.__init__`/`_tab_registry.py` directly — no thread starts of their own
- `WebRequestsWorker.run()` spot-checked as a representative on-demand worker: only uses its own QThread signal (`self.status.emit`), no `QObject` constructed inside `run()` — doesn't match the vulnerable shape even when it does run

**Working theory (unconfirmed, same as Addendum 20's own conclusion): this is one underlying `QObject`/event-dispatcher corruption surfacing at whichever call site happens to touch it next, not a second independent bug.** A thread that ran *earlier* in startup (JVM/JPype init being the prime remaining un-investigated candidate, or a wallpaper-panel scan that crashed before its own `[thread-lifecycle]` print line — the print happens partway through `populate_scan_image_gallery`, not at the very start of whatever thread eventually touches the corrupted object) tearing down around this moment is at least as plausible as an undiscovered new trigger, and is consistent with three different offsets (`deleteOrphaned`, `connect()`, now this destructor) all being observed for what looks like the same class of bug across this document's history.

**Repro-strategy trap identified — important for future rounds:** the one `IMAGE_TOOLKIT_TELEMETRY=1 just python` run attempted this session did **not** crash; a same-session plain `just python` (no telemetry) crashed on its very next launch. `telemetry.emit()`'s synchronous, `flush=True` file writes on every call plausibly perturb thread-interleaving timing enough to dodge the race window — a classic Heisenbug interaction. This is a single data point, not proof, but it means **future repro attempts should not assume a telemetry-instrumented run will actually reproduce this** — the fresh-JSONL-correlation approach every prior successful round (18, 21) relied on may simply not be available for this residual crash, and gdb/core-dump capture (per Addendum 20's own suggestion — core dumps have never actually materialized despite hs_err claiming they would, across every round including this one) remains the most promising untried avenue for a *ground-truth* look at the corrupted object, rather than continued offset-guessing.

**Not touched this round**: no code changes. This was diagnosis only, at Harbinger's explicit request to delegate investigation rather than attempt a blind fix.
