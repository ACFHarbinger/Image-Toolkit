# Issue #480 — reusable GC-guard for JSON/listing worker threads (audit + fix)

Date: 2026-08-31 · Owner: OpenCode (GLM 5.3) · Status: done, uncommitted→committed with this report

## Mechanism (the #478 crash class, generalized)

CPython's cyclic collector is process-global with no thread affinity. Any
worker thread whose allocations trip the collection threshold can run a
collection, and a collectable `QWidget` left in the GUI's cyclic garbage is
then finalized *on that thread* — `QWidget::~QWidget` off the GUI thread
segfaults (#461 class). Workers that parse large JSON or walk big listings
allocate enough to trip the threshold regularly, so they must run with the
cyclic GC disabled for the whole `run()`. Refcounted frees are unaffected;
the next allocation after the guard restores the GC re-collects.

## Deliverable

`gui/src/helpers/gc_safe.py` (new):

- `gc_disabled()` — context manager; restores prior state, leaves it off
  if it was already off.
- `@gc_disabled_run` — decorator for `run()` methods; works identically for
  `QThread.run()`, `QRunnable.run()` (QThreadPool), and plain
  `threading.Thread` targets. On `@Slot()`-tagged `run()`s it sits
  *outermost* so Slot sees the original function.
- `GcSafeThread(QThread)` — template-method base (`_execute()` guarded).

`BaseQThreadWorker.run()` and `BaseQRunnableWorker.run()`
(`gui/src/helpers/base.py`) now carry the guard, so every `_execute()`
implementor is covered — immediately `SearchWorker`,
`SemanticSearchWorker`, `ListingsSemanticSearchWorker`, and all future
base-class workers. `_SyncBackupWorker` was refactored off its inline #478
code onto the same decorator (behavior identical, incl. the params-drop so
DB/vault QObject teardown stays on the GUI thread; its regression test is
unchanged and green).

## Audit — applied set (JSON/listing/DB exposure, direct `run()` overrides)

| Worker | Thread | Exposure |
|---|---|---|
| `_SyncBackupWorker` (web) | QThread | #478 original; now on the shared guard |
| `GoogleDriveSyncWorker` (web/cloud) | QRunnable | whole-tree listing diff, drive-SDK JSON pagination, long run |
| `DropboxDriveSyncWorker` (web/cloud) | QRunnable | same |
| `OneDriveSyncWorker` (web/cloud) | QRunnable | same |
| `ImageCrawlWorker` (web) | QThread | `json.loads` per saved image + long Selenium crawl |
| `MediaLoaderWorker` (web) | plain `threading.Thread` | downloader JSON + bulk image writes |
| `MalSyncWorker` (web) | QThread | network JSON parse per fetch |
| `WebRequestsWorker` (web) | QThread | generic request/JSON logic (backend) on this thread |
| `RecommendationWorker` (database) | QThread | embedder/retriever/scorer over the listing DB (named in #480) |
| `UpsertWorker` (database) | QThread | per-entry `QImage` decode over listing-scale batches (DB-worker scope of #480) |
| `BatchImageLoaderWorker` (image) | QRunnable | native batch decode → large arrays + `QImage` copies (named in #480) |

The cloud-sync trio is also the pattern #479's new Local Directory Sync
workers must mirror (per the delegation note) — they now inherit it by
convention from these files.

## Audit — Tier 2 (same mechanism applies; heavy CV/torch/ffmpeg allocation)

Left un-decorated in this pass — not JSON/listing scope, and each deserves
its own call + regression test rather than a mechanical sweep (long torch
jobs holding the GC off accumulate cyclic garbage for their whole run;
that tradeoff was accepted for the bursty JSON/listing workers in #478 but
should be decided per worker here):

- core: `ConversionWorker`, `DeletionWorker`, `MergeWorker`,
  `SamplerWorker`, `SimilarityScanWorker`, `DuplicateScanWorker`,
  `CodecConversionWorker`, `ScrollVideoExportWorker`,
  `QueueExecutionWorker`, `WallpaperWorker`
- video: `VideoScannerWorker`, `CodecScanWorker`,
  `FrameExtractionWorker`, `GifCreationWorker`, `VideoExtractionWorker`,
  `VideoLoaderWorker`, `BatchVideoLoaderWorker`, `StoryboardBuilder`
  (its `json.loads` at storyboard.py:124/160 run on the calling/GUI
  thread — not worker exposure; `StoryboardBuilder.run` is),
  `clip_splicer._probe_streams` (called from these workers)
- image: `ImageScannerWorker`, `ImageLoaderWorker`, card thumb worker
- database: `ImageEmbeddingWorker`, `ListingsEmbeddingWorker` (torch)
- web: `IndexBuildWorker` / `ResolveWorker` / `BatchSuggestWorker` (recon —
  torch/HNSW), `ReverseSearchWorker` (Selenium)
- models: `TrainingWorker`, `LoRATrainingWorker`, `TagReviewWorker`
- components: `_FrameWorker` (frame_selection_dialog.py)
- core/tasks: orb / sift / ssim / phask / sn tasks (QRunnable)

Recommendation: fold Tier-2 workers onto `@gc_disabled_run` opportunistically
as they are next touched, or as one reviewed follow-up issue.

## Verification

- `gui/test/helpers/test_gc_safe.py` (new, 11 tests): guard semantics
  (disable/restore/exception/already-off), decorator on plain methods,
  `GcSafeThread`, both base classes incl. exception paths.
- `gui/test/helpers/` targeted run: **14 passed, 7 skipped** (skips are the
  pre-existing `--run-gui` gates). The #478 regression file is included and
  unchanged.
- `ruff` clean and `py_compile` OK on every touched file; all modified
  worker modules import cleanly through the standard submodule bootstrap
  (`register_submodule_packages`). Bare `import gui.src.helpers` without
  the bootstrap fails identically on `main` — pre-existing, unrelated.
- No full suite / benchmark runs (RESOURCE RULE).
