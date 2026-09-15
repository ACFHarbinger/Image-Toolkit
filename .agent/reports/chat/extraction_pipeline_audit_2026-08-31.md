# Extraction pipeline resource audit (#485)

Requested by Harbinger, executed by Claude, 2026-09-15 (against `main` @ `6355fb1f`, after the #633/#634 merge round).

## Context

`#483`'s described fix (realistic per-worker RAM estimate, OS/desktop reserve, low-swap freeze-risk escalation, memory-capped worker spinbox) is **already fully implemented** in current code — verified directly, not inferred from the issue text:

- `gui/src/components/widgets/resource_simulator_dashboard.py`: `PER_WORKER_RAM_MIB = 4096`, `OS_RESERVE_MIN_GIB`/`OS_RESERVE_FRACTION`, `LOW_SWAP_GIB` → `freeze_risk` escalation to the red state, all present and matching the issue's "Fix (first pass)" list line for line.
- `gui/src/windows/settings/_misc_sections.py:110`: `self.parallel_extraction_processors_spinbox.setRange(1, max(1, min(cpu_cap, mem_cap)))` — the worker spinbox is already memory-capped, not just CPU-capped.
- `gui/src/helpers/core/_queue_extraction_process.py::_extraction_pool_worker_init`: `os.nice(10)` + `oom_score_adj=700` already set on every pool child.
- `gui/src/helpers/core/queue_execution_worker.py`: `maxtasksperchild=1` already set on the Pool.

**#483 should be closed as already-fixed** — filing this here since the issue itself has no comment confirming that.

## Audit findings (this session)

### 1. `cv2.VideoCapture` release paths

- `_queue_extraction_process.py::run_extraction_in_process`'s two internal `VideoCapture` uses:
  - Line ~242 (gif open-ended duration probe): already wrapped in `try/finally` with `cap.release()` — correct on all paths.
  - Line ~84 (`get_video_fps`, called once per range/single extraction): **real leak, now fixed this session** — `if not cap.isOpened(): return 23.976` skipped `cap.release()` entirely on that path. Wrapped in `try/finally` (commit on `main`, this round).
- No retained `np` frame arrays or frame-list accumulation found in the range/single non-smart path — it operates via ffmpeg subprocess + file rename, not in-process frame buffers.

### 2. MoviePy clip closing

- `gif_extractor_worker.py` (`base_clip`, `clip`): closed in a `finally` covering both, `contextlib.suppress(Exception)` guards a double-close when `clip is base_clip`. Correct.
- `video_extractor_worker.py` (`base_clip`, `clip`, `original_audio_clip`): closed in a `finally` covering all three in the right order. Correct.
- ffmpeg subprocess reaping: both workers call moviepy's own `write_gif`/`write_videofile`, which manage their own ffmpeg subprocess lifetime; no evidence of an orphaned subprocess on cancel (moviepy raises into the same `except`/`finally` chain either way).

**Conclusion: no remaining leak in the clip-closing paths.** The one real gap was the `VideoCapture` early-return above.

### 3. Per-worker peak RSS — real number vs. #483's assumed 4 GiB

Not independently re-measured this round (no representative test clip staged in this environment) — #483's `PER_WORKER_RAM_MIB = 4096` already reflects the user's own measured ≈4 GB/worker from the original report, so it isn't a fabricated constant anymore. Whoever next touches this: the self-calibration follow-up from #483 (record peak RSS of the actual pool children via `psutil` per-PID and feed the rolling max back) is still open and would replace this static constant with a measured one — worth its own follow-up issue if wanted, not done here.

### 4. `snap.just` cgroup `MemoryMax`

Checked in this dev environment: `cat /proc/self/cgroup` shows a plain user-session/KDE scope, not a `snap.just`-launched one, and no per-app `app-*.scope` for Image-Toolkit exists right now (the app isn't running under a packaged launch in this checkout). **Inconclusive here** — this check only means something when run from an actual installed/packaged (snap) launch of the app. Flagging for whoever next reproduces the SIGTERM on a packaged build: run `systemctl --user show <the app's scope> -p MemoryMax` (or read `/sys/fs/cgroup/.../memory.max` for that scope) while it's running, and compare against `workers × PER_WORKER_RAM_MIB + GUI RSS`.

### 5. `fork` vs `spawn` Pool start method — the real fix, this session

**Confirmed and fixed.** `queue_execution_worker.py`'s `Pool(...)` used the platform default start method with no explicit `context=` — on Linux that's `fork`. A forked worker is a copy-on-write image of the **entire** parent (GUI) process's resident memory at fork time: any already-loaded Qt buffers, decoded-thumbnail caches, or ML model weights the main app was holding get inherited into every single pool child, and COW pages that any worker touches (even read-mostly ones touched by cv2/ffmpeg/moviepy's own internals) turn fully resident fast. With `workers=2` and "supposed headroom," this is a completely different (and much larger) memory bill than `2 × PER_WORKER_RAM_MIB` accounts for — matching the SIGTERM report exactly (2 workers, headroom on paper, SIGTERM anyway).

**Fix applied**: `multiprocessing.get_context("spawn").Pool(...)` instead of the bare `Pool(...)`. A spawned worker starts as a fresh interpreter that only imports what `run_extraction_in_process` actually needs (cv2 lazily inside the function, moviepy at module import in the two extractor-worker files it doesn't even use directly) — it does not inherit the GUI process's heap at all.

Checked for spawn-compatibility before applying:
- `ExtractionConfig` (the task argument) is a plain `TypedDict` → a plain `dict` at runtime — fully picklable, no QObjects/closures/file handles inside it.
- Both `_extraction_pool_worker_init` and `run_extraction_in_process` are module-level functions in an importable module (`gui.src.helpers.core._queue_extraction_process`) — spawn requires the target to be re-importable by the fresh child interpreter, which this already satisfies (it was already required for pickling the `Pool.apply_async` call under fork too — fork does not exempt Python from pickling the callable/args across the process boundary, it only skips re-running module-level import code).
- Windows and macOS already default to `spawn`/have no `fork` at all — this change only alters (and only improves) behavior on Linux, where fork was silently the worse choice for a GUI app with a large resident heap.

Trade-off: `spawn` workers take longer to start (fresh interpreter + imports) than `fork` workers. Given `maxtasksperchild=1` already recycles a worker per task, this was already re-paying some interpreter-startup-adjacent cost per item; the added latency is a small, one-time-per-worker cost against a real, large memory-safety win for exactly the failure mode in this issue.

## Summary / prioritized list

| # | Item | Status |
|---|------|--------|
| 1 | `cv2.VideoCapture` leak in `get_video_fps()` | **Fixed this session** |
| 2 | MoviePy clip closing | Already correct, no fix needed |
| 3 | Real per-worker peak RSS measurement | Not done — needs a staged test clip; #483's constant is already a real measured value, not fabricated |
| 4 | `snap.just` cgroup `MemoryMax` | Inconclusive in this dev environment — needs checking on an actual packaged/snap launch |
| 5 | `fork` → `spawn` Pool start method | **Fixed this session — the most likely actual root cause of the SIGTERM reports** |

Also confirmed and flagged: **#483 is stale** — its described fix already shipped; recommend closing it with a pointer to this audit as evidence.
