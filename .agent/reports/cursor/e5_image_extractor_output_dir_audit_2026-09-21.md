# E5 — Image extractor subtab output-dir audit

**Verdict: no issue.** The #687 stale-directory class does not exist on
the Image subtab. No code change.

Shared tree was on `fix/e3-dependabot-triage`; this is read-only against
`gui/src/tabs/core/image_extractor_subtab.py` on that checkout (file is
unmodified vs the #687-era Image subtab).

## What #687 actually was

Video queue items snapshot `output_dir` at enqueue. Changing Output
Directory afterwards left On Hold items pointed at the old folder. Re-
queueing a recent run preferred the history entry's recorded folder over
the current control. Fix: `retarget_pending_queue_items` on browse /
`set_config`, and `_recent_run_to_queue_config` always writes
`self.extraction_dir`. In-process items keep their snapshot on purpose.

Claude's #687 note: the Image subtab was not covered and keeps its own
`extraction_dir` (~245, ~436, ~650).

## Image subtab has no deferred write path

`ImageExtractorSubTab` is a one-shot cutter. There is no
`extraction_queue`, no On Hold / In Process lists, no recent-run history,
no re-queue helper.

| Path | What it does | Stale-dir risk |
|---|---|---|
| `browse_output_directory` (436) | Sets `extraction_dir` + read-only line edit immediately | None — next cut reads the new value |
| `extract_frames` (575) | Starts `ImageFrameCutWorker` with `str(self.extraction_dir)` at click | None — there is nothing waiting from an earlier enqueue |
| `ImageFrameCutWorker._output_dir` | Snapshot used only by that in-flight cut | Same as Video in-process: changing the control mid-cut must not retarget files already being written |
| `set_config` (648–651) | Restores session UI state if the path still exists | Restore, not a queued job; a later browse then cut uses the browsed dir |
| `collect` (619–622) | Persists the current control | No write |
| `ExtractorTab.__getattr__` / `__setattr__` | Forwards `extraction_dir` to the **Video** subtab | Image's field is separate; startup prefs / video browse never overwrite it |

`extract_frames` is only connected to the Cut button. Wrapper
`set_config` calls `image_subtab.set_config` then the video path; it
does not auto-cut. QML `ImageExtractorTab` / `extract_*_qml` are the
video extractor, not this subtab.

## Why a #687-style retarget would be wrong here

There is no pending-item list to rewrite. The only snapshot is the
running worker, which #687 deliberately left alone. Adding
`retarget_pending_queue_items` (or sharing Video's `extraction_dir`)
would either be a no-op or couple two independent destinations.

## Out of scope (not the bug class)

`_on_cut_finished` prints `self.extraction_dir`, not
`worker._output_dir`. If the user changes the control during a cut, the
status line can name the new folder while files landed in the snapshot.
Display-only; files still go where Cut was pressed. Image also does not
persist last-dir via `_save_last_extraction_dir` (Video does) — a
restart without session restore falls back to `LOCAL_SOURCE_PATH/Frames`.
Neither writes to a stale destination after the user changes Output
Directory.

-- Cursor, 2026-09-21
