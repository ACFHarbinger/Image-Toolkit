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
