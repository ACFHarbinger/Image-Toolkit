# Wallpaper gallery browse stability

The virtual gallery eagerly started thumbnail work for every path in both
linked wallpaper panels and left queued workers alive after a directory change.
That created blank placeholder rows and a native decoder burst during browse /
startup recovery.

The earlier bounded-pool mitigation did not close the native crash. Its settle
check observed only `QThreadPool.activeThreadCount()`: between a worker
returning and its queued completion callback submitting the next item, that
count briefly reached zero even though the model still held a fill queue and
loading paths. The linked panel could therefore start another scan/load cycle
inside that gap. Cancellation also cleared Python worker references without
waiting for already-running auto-deleting `QRunnable`s.

Wallpaper directory enumeration has now been rewritten without scanner
threads. A cancellable `os.scandir` state machine runs in bounded 4 ms / 256
entry GUI-event-loop slices, covers images and videos in one pass, and closes
its directory iterator immediately when a newer browse supersedes it. There
are no scanner worker `QObject`s, cross-thread result signals, native scan
calls, or scanner-thread teardown paths left in browsing.

The virtual gallery now exposes the complete queued/running/loading state and
drains an old generation before path replacement. Wallpaper is restricted to
one thumbnail worker, and the peer mirror starts only when the source has no
queued, active, or undelivered thumbnail work; it then reuses the shared
bounded cache. The affected GIF directory previously decoded cleanly in an
isolated model check (65 cached, 0 failed).

Native thumbnail drags mark the active DnD loop for Wallpaper's application
event filter, so wheel scrolling remains available over a monitor target.

Validation: `test_virtual_gallery.py`, `test_wallpaper_event_filter.py`,
`test_wallpaper_linked_panel_scan_race.py`, `test_gallery_crash_stress.py`,
and `test_wallpaper_gallery.py` — 49 passed.
