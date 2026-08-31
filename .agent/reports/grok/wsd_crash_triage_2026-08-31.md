# WS-D — #461 stress / #373 close-out / crash-class sweep

**Date:** 2026-08-31
**Owner:** Grok

## #373 — KDE Smart Video Wallpaper black screen

Fix still present in `backend/src/core/wallpaper/_kde.py`: plugin switch and
video-config write are separate D-Bus `evaluateScript` calls with a 0.3s delay
so Reborn's 100ms `isLoading` guard can clear; `LastVideo` is the bare file URI.

Targeted tests on current tree:

```
pytest backend/test/image/test_wallpaper.py backend/test/core/test_qt_runtime_env.py
12 passed in 0.46s
```

(`test_wallpaper.py` is the original 9/9 set; the extra 3 pin `QT_MEDIA_BACKEND=ffmpeg`.)

**Disposition:** close. Symptom was a silent playback skip, not a process crash.
Live dbus/config verification was already recorded on the issue in 2026-08-15.
Reopen if a Plasma session shows a black screen after a plugin switch.

## #461 — gallery / PySide6 binding-corruption crash

Stress pass on current tree (real `WallpaperTab` dual linked panels, real
`ImageScannerWorker` QThreads, real 24×24 PNGs, `startup_settle_remaining_ms`
forced to 0):

| Case | File |
|---|---|
| Rapid dir-nav, both panels, 12 switches | `test_dual_linked_rapid_dir_nav` |
| Dual `set_config` restore burst then switch | `test_startup_restore_then_rapid_switch` |
| Close/cancel mid-scan, 6 tab lifetimes | `test_teardown_during_wallpaper_load` |
| Single-gallery load + cancel, 8 lifetimes | `test_teardown_during_single_gallery_load` |
| Wallpaper browse forces `DontUseNativeDialog` | `test_browse_scan_directory_forces_non_native_dialog` |

```
pytest --run-gui gui/test/core/test_gallery_crash_stress.py
  + linked-panel / scan-race / wallpaper-gallery / loading-pipeline /
    extractor-startup-deferral / event-filter / file-dialog-patch
60 passed, 12.94s, no SIGSEGV/SIGABRT

stress file alone, 5 extra repeats: 5×5 passed (7s each)
```

Related prior milestones still in tree: per-gallery `QThreadPool`,
`waitForDone(-1)`, JVM/#435 removal, `NATIVE_IMAGE_BATCH_LOCK`, OpenMP cap 8,
peer-reentrancy guard, queued `directory_scanned`, restartable restore timer.

**Disposition:** close as fixed in 1.0.0. Stochastic native faults can still be
reopened with a gdb backtrace; this pass did not reproduce one.

## Sweep — other crash-class / data-loss

Found and fixed (shipping desktop):

- Wallpaper scan browse omitted `DIALOG_OPTS` (`_scan_actions.py`). App-wide
  `file_dialog_patch` still OR'd it in; the explicit option is now on the
  #461 browse path.
- `QThread.terminate()` on two live QThreads: `ImageCrawlTab.cancel_crawl`
  (bounded wait then terminate) and `SeriesListingsSubTab._run_recommendation`
  (terminate previous worker). Both now cooperative-interrupt + unbounded
  `wait()`, matching the #461 scanner audit.

Checked, not 1.0.0 blockers:

- No `QWebEngineView` in `gui/`.
- Worker image loads emit `QImage`; `QPixmap.fromImage` is on the thumb hub
  (main thread).
- Production downloaders do not use `asyncio.run` on a `QThread`.
- Remaining `waitForDone(2000)` / `wait(1000)` in extractor storyboard/close
  are documented stuck-codec guards, not silent bounded drains.
- Other `.terminate()` sites are `QProcess`/subprocess, which is the correct
  API.
- Open GitHub crash/corruption search besides #461/#373: none in the shipping
  desktop app (`#470` is ASP yield, not a desktop crash).
- Data-loss: no new ticket. Directory-import already transactional
  (`test_directory_import_transaction.py`).

Residual: many `QFileDialog` call sites still omit an explicit
`DontUseNativeDialog`. `file_dialog_patch.py` covers the four static methods
at process start. Not worth a 50-file drive-by for 1.0.0.

## Tests run (targeted; no full suite)

- `backend/test/image/test_wallpaper.py` + `backend/test/core/test_qt_runtime_env.py`
- `gui/test/core/test_gallery_crash_stress.py` (×6 sessions)
- linked-panel / scan-race / wallpaper-gallery / loading-pipeline /
  extractor-startup / event-filter / file-dialog-patch
- `test_cancel_crawl_waits_unbounded_without_terminate`
- `test_rerun_recommendation_does_not_terminate_qthread`
