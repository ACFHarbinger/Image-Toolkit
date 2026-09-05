# New Features Roadmap — Capabilities and Integrations

---

## Table of Contents

- [How to Use This Document](#how-to-use-this-document)
- [4.1 Batch Stitching](#41-batch-stitching)
- [4.2 Export Stitched Panorama to Scrolling Video](#42-export-stitched-panorama-to-scrolling-video)
- [4.3 CLIP-Based Semantic Image Search](#43-clip-based-semantic-image-search)
- [4.4 Auto-Tagger Integration](#44-auto-tagger-integration)
- [4.5 Multi-Monitor Wallpaper Support](#45-multi-monitor-wallpaper-support)
- [4.6 Image Deduplication Across Directories](#46-image-deduplication-across-directories)
- [4.7 Slideshow Improvements](#47-slideshow-improvements)
- [4.8 ComfyUI Workflow Integration for Post-Processing](#48-comfyui-workflow-integration-for-post-processing)
- [4.9 Safetensors Metadata Viewer](#49-safetensors-metadata-viewer)
- [4.10 REST API Layer for Remote Control](#410-rest-api-layer-for-remote-control)
- [4.11 ASP Quality Feedback Interface (RLHF)](#411-asp-quality-feedback-interface-rlhf)
- [4.12 Appearance Profiles](#412-appearance-profiles)
- [4.13 Shortcut Macros and Custom Actions](#413-shortcut-macros-and-custom-actions)
- [4.14 Extractor Tab Storyboard Scrub Preview](#414-extractor-tab-storyboard-scrub-preview)
- [4.15 Extractor Tab Image Sub-Tab — Multi-Frame Image Splitter](#415-extractor-tab-image-sub-tab--multi-frame-image-splitter)
- [4.16 Additional Stitcher Options](#416-additional-stitcher-options)
- [4.17 Media Loader — Web Media Downloader](#417-media-loader--web-media-downloader)
- [Effort × Impact Matrix](#effort--impact-matrix)
- [Anchor Index](#anchor-index)

---

## Implementation Timeline

> **Legend** — *Node fill:* new feature (blue) · augmentation (violet) · integration (pink) — *Node border:* ⬜ planned (slate, thin) — *Edges:* `==>` critical blocking dependency · `-->` sequential dependency · `-.->` alternative approach · `---` complements

```mermaid
flowchart TD
    %% ── TYPE classes (node fill = element type) ─────────────────────────────
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef fix         fill:#dc2626,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef perf        fill:#ea580c,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef security    fill:#7f1d1d,color:#fff
    classDef refactor    fill:#0f766e,color:#fff
    classDef migration   fill:#4338ca,color:#fff
    classDef testing     fill:#a16207,color:#fff
    classDef docs        fill:#15803d,color:#fff
    classDef integration fill:#9d174d,color:#fff
    %% ── STATUS classes (node border = implementation status) ─────────────────
    classDef done        stroke:#16a34a,stroke-width:4px
    classDef active      stroke:#d97706,stroke-width:4px
    classDef planned     stroke:#64748b,stroke-width:2px
    classDef blocked     stroke:#dc2626,stroke-width:3px
    classDef hold        stroke:#9333ea,stroke-width:3px

    subgraph STITCH["🎞 Stitching & Export"]
        S1["§4.1 Batch Stitching\nAutomate ASP across directories"]:::feature:::planned
        S2["§4.2 Scrolling Video Export\nPanorama → scrolling MP4"]:::feature:::done
        S11["§4.11 RLHF Feedback Interface\nQuality rating loop for ASP"]:::feature:::planned
    end

    subgraph ML["🤖 ML & Search"]
        M3["§4.3 CLIP Semantic Search\nML-based image retrieval"]:::feature:::planned
        M4["§4.4 Auto-Tagger\nWD14 / Florence-2 tagging"]:::integration:::planned
        M9["§4.9 Safetensors Viewer\nModel metadata inspector"]:::feature:::planned
    end

    subgraph AUTOMATION["⚙ Automation & API"]
        A8["§4.8 ComfyUI Integration\nPost-processing workflow hooks"]:::integration:::planned
        A10["§4.10 REST API Layer\nRemote control & scripting"]:::integration:::planned
        A13["§4.13 Shortcut Macros ✅\nWorkflow templates"]:::augment:::done
    end

    subgraph MEDIA["🖼 Media & Presentation"]
        P5["§4.5 Multi-Monitor Wallpaper\nPer-display wallpaper support"]:::augment:::planned
        P6["§4.6 Image Deduplication\nCross-directory dedup"]:::feature:::planned
        P7["§4.7 Slideshow Improvements\nShuffle, fade, duration controls"]:::augment:::planned
    end

    subgraph UX["🎨 UI Customisation"]
        U12["§4.12 Appearance Profiles\nSave & switch theme presets"]:::augment:::planned
    end

    %% Stitching dependencies
    S1 --> S2
    S11 --- S1

    %% ML dependencies
    M4 --> M3
    M9 --- M4

    %% Automation dependencies
    A8 --> S1
    A10 --> S1
    A10 --- A13

    %% Cross-group edges
    M3 --> P6
    M3 --- M4
    P5 --- P7
    U12 --- A13
```

*Read the diagram: **fill colour** shows element type (blue = new feature, violet = augmentation, pink = integration); **border colour** shows status (slate thin = planned, green thick = complete, amber thick = in-progress); **edge style** shows relationship (`==>` blocking dependency, `-->` sequential order, `---` complements, `-.->` alternative).*

---

## How to Use This Document

Each section describes a proposed feature, all viable implementation options with trade-offs, and a recommendation. Items tagged **[Quick Win]** take under a day. Items tagged **[Research]** require prototyping.

---

## 4.1 Batch Stitching — ✅ Options A, C, E implemented (2026-07-27, issue #56)

**Pain point:** Users with large screenshot libraries (e.g., 50+ groups of frames from novel-reading sessions) currently process each group one at a time in the StitchTab.

**Status:** Options C (CLI batch mode) and E (resume support) were already fully implemented in `backend/src/utils/io/dispatcher.py::dispatch_stitch` before this item was picked up — `python main.py stitch --batch-dir /path --resume` scans immediate subdirectories, runs `AnimeStitchPipeline` on each via `_run_single_stitch()`, and persists `.stitch_progress.json` after every sequence. This wasn't reflected in the roadmap text (it read as an open TODO). Option A (the GUI counterpart the roadmap's own recommendation calls for "once C is validated") is now implemented too:

- **`gui/src/helpers/animation/batch_stitch_worker.py::BatchStitchWorker`** (`QThread`): runs the same batch loop as the CLI, reusing `dispatcher.py`'s `_collect_image_paths`/`_run_single_stitch` directly rather than re-implementing "run one sequence" a second time, so the two entry points can never silently diverge. Reads/writes the identical `.stitch_progress.json`, so a batch interrupted from one entry point resumes correctly from the other. Runs the plain (non-HITL) pipeline path — unattended batch runs don't pause for interactive review, unlike the single-sequence StitchTab/`StitchWorker` flow. `cancel()` is checked between items (a single `AnimeStitchPipeline.run()` call isn't interruptible mid-stage, matching this project's existing §2.7B cancellation granularity).
- **`gui/src/components/dialogs/batch_stitch_dialog.py::BatchStitchDialog`**: root-directory picker (`QFileDialog` with `DontUseNativeDialog`), renderer/output-suffix/resume options, and the progress list the roadmap asks for — one row per subdirectory with a status icon (queued/running/done/skipped/failed), backed by a progress bar. Its `closeEvent()` deliberately uses an *unbounded* `QThread.wait()` rather than a fixed timeout when cancelling mid-run — the gallery crash fixed earlier this same session (`.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`) is the exact same class of bug (a worker's signals connected to widgets that a bounded wait can let outlive), so this dialog was built to avoid it from the start rather than needing the same fix applied twice.
- New "⚏ Batch Stitch…" button in the StitchTab's action row, opening the dialog.
- **Not implemented**: ETA display (not asked for by Option A's exact text beyond "per-item status"), output preview thumbnails in the progress list, ATA ordering, and Options B (Postgres-backed queue) and D (filesystem watcher) — both explicitly deferred by the roadmap's own recommendation.
- **Tests**: 11 new cases in `gui/test/dialogs/test_batch_stitch_dialog.py` (worker: subdirectory iteration, resume-skip, progress-JSON format, cancellation, empty directory, too-few-images skip; dialog: construction defaults, missing-directory guard, progress-list/bar updates, batch-finished summary) — all passing, plus the existing `gui/test/animation/test_stitch_tab.py` (27) and `gui/test/core/test_stitch_tab.py` (2) re-verified unaffected (66 total across all stitch/dialog tests).

### Options

**A — Directory-level batch mode (GUI)**
Scan a root directory for subdirectories matching a naming pattern (e.g., `scene_*/`). Run the ASP pipeline on each, save outputs to a `stitched/` subfolder. Show a batch progress list in the StitchTab with per-item status, ETA, and output preview.
- Pros: No external tooling. Best experience for non-technical users.
- Cons: Long-running GUI operation. Requires cancellable QThread with item-level progress (§2.7).

**B — PostgreSQL-backed persistent queue**
A `stitch_jobs` table in the existing database where each row is a frame group. Workers process items in order. The queue survives app restarts. Expose via the database tab or a dedicated Job Queue tab.
- Pros: Queue survives crash/restart. Enables priority and retry.
- Cons: Significant schema + UI effort. Overkill for single-user desktop app.

**C — CLI batch mode [Quick Win]**
`python main.py stitch --batch-dir /path/to/groups/`. Iterates subdirectories, runs ASP on each, writes outputs. Suitable for scheduled/overnight runs via cron or systemd.
- Pros: Leverages existing `argparse` infrastructure. Fast to implement. Works headlessly.
- Cons: No GUI progress. No persistent state if interrupted.

**D — File system watcher**
Use `watchdog` (Python) or `notify` (Rust, via `inotify`) to watch a directory. When a new subdirectory appears (e.g., a screen recording session ends), automatically enqueue it for stitching.
- Pros: Fully automatic; zero user interaction for recurring workflows.
- Cons: Requires `watchdog` dependency. Auto-trigger may stitch incomplete captures if recording is still in progress.

**E — Batch mode with resume support**
Extend C with a `results.json` that records which groups have been processed. Re-running with `--resume` skips completed groups. Handles interrupted overnight runs.
- Pros: Resilient to crashes. Trivial to add on top of C.
- Cons: JSON state file must be kept consistent with filesystem.

**Recommendation:** C first (leverages existing infrastructure). E immediately after. A as a GUI counterpart once C is validated. D for power-user automation workflows.

---

## 4.2 Export Stitched Panorama to Scrolling Video — ✅ Option B implemented (2026-07-27, issue #57)

**Pain point:** Stitched manga/visual novel pages are long-form content users may want to share as videos (e.g., on platforms that don't support long images). A scrolling video export is a natural derived product.

**Status:** Option B (FFmpeg pipe, full-resolution/quality) is implemented. C (animated WebP) and E (easing/hold) are not — left as future follow-ons, not blocking.

- `ImageMerger.export_scrolling_video(image_path, output_path, scroll_speed_px_per_frame=10, fps=30, resolution=None, scroll_axis=None, codec="libx264")` in `backend/src/core/image_merger.py`. Auto-detects scroll axis from aspect ratio (tall -> vertical, wide -> horizontal) unless `scroll_axis` is given explicitly. Auto-derives a 16:9-ish viewport (clamped to the source, forced even for `yuv420p`) when `resolution` is `None`. Crops a sliding window across the panorama and pipes raw RGB24 frame bytes to `ffmpeg` via stdin (`-f rawvideo -pix_fmt rgb24 -s {W}x{H} -r {fps} -i pipe:0 -c:v {codec} -pix_fmt yuv420p out.mp4`), reusing the same bare-`ffmpeg`-on-PATH convention as `backend/src/core/video_converter.py`. If the panorama is smaller than one viewport's worth of scroll, it exports a short static clip (`fps` frames, ~1s) rather than raising — documented in the function's docstring.
- GUI entry point: a new "Export as Video…" action in the Merge tab's post-merge confirm dialog (`MergeTab.show_preview_and_confirm` in `gui/src/tabs/core/merge_tab.py`), alongside the existing Copy/Save/Save-and-Add-to-Canvas/Discard actions. Opens `ScrollVideoExportDialog` (`gui/src/components/dialogs/scroll_video_export_dialog.py`) to collect scroll speed, fps, codec (libx264/libx265/libvpx-vp9), and an optional custom resolution; output path uses `QFileDialog.getSaveFileName` with `DontUseNativeDialog` (project hard rule — native GTK dialog + live JVM SIGSEGV). Export runs off the GUI thread via `ScrollVideoExportWorker` (`gui/src/helpers/core/video_export_worker.py`), a `QThread` mirroring `MergeWorker`'s signal pattern. The action doesn't consume the in-progress merge result — the confirm dialog re-appears afterwards so Save/Copy/Discard still work normally.
- Verified directly (not via GUI) with real `ffmpeg`/`ffprobe`, no mocking of the encode path: `backend/test/core/test_export_scrolling_video.py` (5 tests — vertical auto-detect, horizontal auto-detect, nothing-to-scroll static clip, explicit resolution/axis override, missing-ffmpeg error path). All passing.

### Options

**A — OpenCV VideoWriter with pan-and-scan**
Crop a sliding window across the panorama and write each position as a video frame. Parameterise scroll speed (px/frame) and output resolution.
- Pros: Zero new binary dependencies. Quick to prototype.
- Cons: Limited codec support (MJPEG, XVID). No hardware encoding. Lower quality than ffmpeg.

**B — FFmpeg pipe from Python/Rust**
Pipe frame bytes to `ffmpeg` via subprocess stdout. Handles codec selection (H.264, H.265, AV1), hardware encoding (NVENC, VAAPI), and container formats (MP4, WebM).
- Example: `ffmpeg -f rawvideo -pix_fmt rgb24 -s {W}x{H} -r {fps} -i pipe: -c:v libx264 out.mp4`
- Pros: High quality. Hardware-accelerated encoding. No Python video library needed.
- Cons: Requires `ffmpeg` binary on PATH. Not bundled with PyInstaller by default (needs separate inclusion).

**C — Export as animated WebP (small panoramas)**
For panoramas < 1500px wide, `imageio` + `PIL` can produce a looping animated WebP. Zero new binary dependencies.
- Pros: Quick-share option. Self-contained.
- Cons: Animated WebP support limited in some browsers/viewers. Poor compression for large panoramas.

**D — GIF export (legacy compatibility)**
Use `PIL.Image.save(..., format='GIF', save_all=True, append_images=...)` for a looping GIF.
- Pros: Universal compatibility.
- Cons: 256-colour palette. Large file sizes. Poor quality for complex images.

**E — Configurable scroll parameters (easing, hold at ends)**
Extend A/B with configurable easing (linear, ease-in-out), pause at start/end, and audio track attachment.
- Pros: Polished output for sharing.
- Cons: Adds complexity. Best as a follow-on once basic export works.

**Recommendation:** B for full-resolution output (most portable quality path). C as a quick-share option. E as a polish layer on top of B.

---

## 4.3 CLIP-Based Semantic Image Search

**Pain point:** The database supports vector search via pgvector, but embeddings are ResNet-18 Siamese features tuned for duplicate detection, not semantic content. No natural-language query capability exists.

### Options

**A — OpenCLIP (open_clip_torch) text + image encoder**
Generate CLIP embeddings during database ingest. Store a second embedding column (e.g., `clip_embedding vector(512)`) in PostgreSQL. Support both text queries ("red sunset background") and image similarity queries.
- `open-clip-torch` is pip-installable, no API key required. Supports ViT-B/32, ViT-L/14, and larger.
- Processing speed: ~7 images/second on a GPU (cloud L4 benchmark).
- Pros: State-of-the-art semantic understanding. No external API dependency.
- Cons: Second embedding column doubles storage. Separate HNSW index needed.
- Reference: [open_clip GitHub](https://github.com/mlfoundations/open_clip)

**B — AnimeCLIP / WaifuDiffusion CLIP fine-tune**
Use a domain-specific CLIP variant fine-tuned on anime content (e.g., `ViT-B/16` fine-tuned on Danbooru) for better semantic accuracy on the primary use case.
- Pros: Higher accuracy for anime/manga content vs. general CLIP.
- Cons: Model requires separate download. Fine-tuned models may have less coverage for non-anime images.

**C — Dual-column search (Siamese + CLIP)**
Run both Siamese (duplicate detection) and CLIP (semantic similarity) embeddings in parallel. Show results from both in the search tab with a toggle.
- Pros: Preserves existing duplicate detection functionality alongside new semantic search.
- Cons: Two HNSW indexes to maintain. Higher storage cost.

**D — Multimodal re-ranking**
First retrieve top-50 candidates via CLIP, then re-rank using the Siamese embedding for visual similarity within the candidate set. Best of both.
- Pros: Better precision than either alone.
- Cons: Two-stage retrieval adds latency. Complex query pipeline.

**E — FAISS as a local in-memory index**
For collections that don't need persistent storage, use FAISS (`faiss-cpu` or `faiss-gpu`) as an in-memory vector index alongside pgvector.
- Pros: Faster query latency than pgvector for billion-scale collections.
- Cons: Index must be rebuilt on restart. Redundant if pgvector is already tuned (§3.4D).

**Recommendation:** A as the initial implementation. B as a model swap once A is validated. C for users who want both capabilities simultaneously.

---

## 4.4 Auto-Tagger Integration

**Pain point:** The database supports tags, but tagging is entirely manual. Crawlers fetch Danbooru/Gelbooru tags for downloaded images, but locally-sourced images have no tags.

**Status update (2026-07-27, issue #32):** Option A's backend (`backend/src/models/wrappers/wd_tagger_wrapper.py::WDTaggerWrapper`) was fully built previously but had zero callers anywhere in the codebase (confirmed via repo-wide grep). It now has its first real caller — `backend/src/pipeline/anime_training_pipeline.py`'s captioning stage, via `content_generation.md` §1.1 — as the fallback WD14 backend when no local ONNX path is configured. A category-mapping bug was fixed in the process (WD category `9` is the rating group, not "copyright"). The database-ingest tagging path (this section's actual pain point — tagging locally-sourced images on ingest) and background Celery ingest (§D) are still not built.

**Status update (2026-07-27, issue #58 — §C shipped):** Built the human-in-the-loop review queue for the LoRA training dataset-prep flow specifically (not the database-ingest path, which is a separate, still-open item). Verified before building: `WDTaggerWrapper.tag_with_review()` (§E's confidence-threshold split) already existed with a full implementation and test coverage, but — like `WDTaggerWrapper` itself before issue #32 — had zero callers anywhere in the codebase. This is now its first real caller.
- **`gui/src/helpers/models/tag_review_worker.py::TagReviewWorker`**: a `QThread` that runs `tag_with_review()` over a dataset folder's untagged images (skips any image whose `.txt` caption sidecar already exists, matching the training pipeline's own skip logic) and emits `(auto_tags, review_tags)` per image, tagged with which zone each came from.
- **`gui/src/components/dialogs/tag_review_dialog.py::TagReviewDialog`**: pages through each untagged image one at a time — thumbnail, a checkbox per predicted tag (auto-confidence tags pre-checked, borderline review-zone tags unchecked by default — the human's job is mainly to promote a few review-zone tags, not re-tag from scratch), a free-text "add a custom tag" field, and Prev/Next navigation that syncs in-progress edits so they aren't lost when paging. "Save All" writes each image's checked tags as a `.txt` caption sidecar — the exact same format `HybridCaptioner.write_caption_file` produces, so reviewed captions are indistinguishable from auto-generated ones to the training pipeline.
- **Not backed by PostgreSQL**, as this option's original text specified: the project has since moved away from Postgres entirely (`unified_database.md`), and the review happens synchronously within one GUI session against a dataset folder already on disk — a `.txt`-sidecar-per-image queue matches the existing training-pipeline convention with zero new schema, rather than introducing a retired dependency for a single-session workflow. A DB-backed, cross-session queue remains a valid future extension if the database-ingest tagging path (this section's still-open pain point) is ever built.
- **Wired into `gui/src/tabs/models/delta/lora_train_tab.py`**: a new "Review Tags..." button next to "Inspect .safetensors...", scoped to the tab's already-selected dataset folder.
- **Tests**: `gui/test/dialogs/test_tag_review_dialog.py` (6 cases — result bookkeeping, checkbox-toggle promotion of review-zone tags, custom-tag addition, caption-file writing with only checked tags, trigger-token prepending, navigation-preserves-edits) and `gui/test/helpers/test_tag_review_worker.py` (4 cases — skip-already-tagged, auto/review split with correct checked-by-default flags, unavailable-tagger error path, progress signal accuracy). All 10 passing.

### Options

**A — WD-1.4 (WaifuDiffusion Tagger) via ONNX**
Run the ONNX model locally on each image during database ingest. Generates booru-style tags at ~50–100ms/image on CPU, faster on GPU.
- 13 WD model variants available (v1, v2, v3; ViT, SwinV2, ConvNext).
- ONNX Runtime is already a likely dependency via BiRefNet.
- Reference: [WD Tagger HuggingFace Space](https://huggingface.co/spaces/SmilingWolf/wd-tagger); [wd14-tagger-server GitHub](https://github.com/LlmKira/wd14-tagger-server)
- Pros: Best accuracy for anime/manga content. Booru-compatible tags integrate naturally with existing tag schema. No internet required.
- Cons: Model download (~300 MB). ONNX Runtime dependency.

**B — MetaCLIP / CLIP-ViT zero-shot classification**
Use zero-shot classification against the full Danbooru tag vocabulary (50k+ tags) with CLIP. No separate tagger model needed if CLIP (§4.3A) is already present.
- Pros: No additional model if CLIP is installed.
- Cons: Much lower accuracy than WD-1.4 for domain-specific tags. Slow for large tag vocabularies.

**C — Human-in-the-loop tagging queue** `[shipped 2026-07-27, issue #58, LoRA-training-flow scope — see status update above]`
Show untagged images in a review queue. Present top-N auto-tag suggestions (from A or B) as checkboxes. User confirms or corrects. ~~Persistent queue backed by PostgreSQL~~ — shipped as `.txt`-sidecar-per-image instead, per the status update above (Postgres has been retired project-wide).
- Pros: Quality control — don't fully automate without review. Generates high-quality labelled data for future fine-tuning.
- Cons: Requires building a new UI component (tag review queue tab or panel).

**D — Batch background ingest tagger**
Run WD-1.4 as a background Celery task triggered on database ingest. Tags are stored as `pending_review` status until confirmed.
- Pros: Non-blocking ingest. Tags available quickly.
- Cons: Requires Celery worker to be running. `pending_review` status adds schema complexity.

**E — Tag confidence thresholds**
Allow configuring a minimum confidence threshold (e.g., 0.35). Only tags above the threshold are applied automatically; lower-confidence tags go to the human review queue (§C).
- Pros: Reduces false positives. Already a standard feature of WD tagger implementations.
- Cons: Threshold needs tuning per content type.

**Recommendation:** A for accuracy. C for quality control. E to tune the boundary between automatic and human review. D for large collections where blocking ingest is impractical.

---

## 4.5 Multi-Monitor Wallpaper Support

**Pain point:** Wallpaper tab sets wallpaper on the primary monitor via `qdbus-qt6`. Multi-monitor users want per-monitor control.

### Options

**A — KDE per-monitor wallpaper via D-Bus**
Enumerate monitors with `QScreen.availableScreens()`. For each screen, call the Plasma `org.kde.PlasmaShell` D-Bus method with the screen identifier.
- KDE 6 D-Bus API: `org.kde.PlasmaShell.setWallpaper(screen_id, plugin_id, config_object)`.
- Pros: Native KDE support. Already have `qdbus-qt6` integration.
- Cons: KDE-specific. GNOME requires a completely different approach.

**B — GNOME composited wallpaper**
GNOME doesn't natively support per-monitor wallpapers without extensions. Fall back to a composited image: stitch multiple source images side-by-side to match the total multi-monitor resolution and set as a single wallpaper.
- Tools: `xrandr` for screen geometry; PIL/Rust for image compositing.
- Pros: Works without GNOME extensions.
- Cons: Images must be manually aligned to screen boundaries. Composited image is static (no independent rotation per screen).

**C — Virtual desktop rotation (per-monitor scheduling)**
Rotate through different wallpaper categories per monitor on a configurable schedule. Each monitor gets a different image from its assigned queue.
- Pros: Diverse multi-monitor aesthetic without per-monitor wallpaper API.
- Cons: Requires per-monitor queue management in the UI.

**D — HydraPaper / Superpaper integration (GNOME)**
Call the HydraPaper or Superpaper CLI for GNOME multi-monitor support. These tools specifically solve the GNOME per-monitor wallpaper problem.
- Pros: Best GNOME experience. Well-maintained tools.
- Cons: External binary dependency. User must have HydraPaper/Superpaper installed.

**E — Wallpaper mirroring across all monitors**
Simplest mode: apply the same wallpaper to all monitors simultaneously. Already mostly implemented.
- Pros: No new complexity.
- Cons: Doesn't address the per-monitor request.

**Recommendation:** A for KDE (primary target given `qdbus-qt6`). B as GNOME fallback. D as the recommended path for GNOME power users who already have HydraPaper.

---

## 4.6 Native KDE video-wallpaper plugin (fallback if third-party plugins stay broken) — planned, not started

**Pain point:** [#373](https://github.com/ACFHarbinger/Image-Toolkit/issues/373) — KDE Smart Video Wallpaper (Reborn) shows a black screen instead of the configured video. Root-caused (2026-08-15/16) through several rounds:

1. An `isLoading` race on plugin switch (fixed, `a2312a23`).
2. A stale `LastVideo` vs. freshly-written `VideoUrls` mismatch that leaves `main.currentSource` resolving empty (fixed in `_kde.py`, keeps `LastVideo` in sync).
3. **Even with both of the above fixed, a fresh `plasmashell` restart, `QT_MEDIA_BACKEND=gstreamer` confirmed active, and a provably correct/consistent config, the video still never loads** (`mediaStatus` stuck at Qt Multimedia's `NoMedia`). Filed upstream as [luisbocanegra/plasma-smart-video-wallpaper-reborn#292](https://github.com/luisbocanegra/plasma-smart-video-wallpaper-reborn/issues/292).
4. **Installed and tested a second, independently-coded plugin** (`smartervideowallpaper`, from `PeterTucker/smartER-video-wallpaper`) as a fallback per this repo's existing `get_best_video_plugin()` search order. It fails identically — same file, same backend, same machine, config confirmed correctly written. Two unrelated codebases failing the same way points at something below plugin code: Qt Multimedia's gstreamer backend integration, GPU/driver video decode, or KWin compositor interaction on this specific Plasma 6.6.6 / Qt 6.10.2 / Ubuntu 26.04 combination — not yet isolated (a raw, non-wallpaper QtMultimedia+gstreamer smoke test was attempted but inconclusive: no system-matching Qt6 QML runtime or `gst-play-1.0` was available without installing new packages, which wasn't done without confirmation).

**Fallback option — build a small first-party video-wallpaper QML plugin**, scoped narrowly (loop a single `MediaPlayer`/`VideoOutput` bound to config Image-Toolkit already writes) rather than reimplementing Reborn's full feature set (crossfade, per-effect pause/blur, battery/lock-screen awareness, etc.). Only worth doing if:
- The upstream Reborn issue and/or further isolation of the Qt Multimedia/gstreamer layer don't produce a fix, **and**
- A minimal from-scratch `MediaPlayer`/`VideoOutput` QML scene is first confirmed to actually render video on this machine — if the underlying Qt Multimedia/gstreamer/compositor layer itself is broken, a custom plugin hits the identical wall two failed third-party plugins already hit, and building one would not fix anything.

**Gate condition answered, 2026-08-16 — do not start yet.** Ran the isolation test: a standalone Qt6 `MediaPlayer`/`VideoOutput` QML scene (`QT_MEDIA_BACKEND=ffmpeg`, no wallpaper plugin involved) decoded and produced real texture frames continuously (168 `createTexturesFromMemory` calls over 8s, real NAL-unit decode at framerate) — the Qt Multimedia/FFmpeg/codec stack works correctly on this machine standalone. The failure is specific to the Plasma wallpaper plugin → KWin Wayland compositor texture-import path (matches [luisbocanegra/plasma-smart-video-wallpaper-reborn#290](https://github.com/luisbocanegra/plasma-smart-video-wallpaper-reborn/issues/290)'s working theory: an NVIDIA+Wayland DMA-BUF/EGL compositor issue, not a plugin bug). A first-party plugin would hit the exact same KWin/Wayland/NVIDIA compositor question every existing plugin already hits — **not worth building until upstream (#290 / our own [#292](https://github.com/luisbocanegra/plasma-smart-video-wallpaper-reborn/issues/292)) narrows the compositor-side cause further**, since nothing plugin-side (ours or a replacement) can route around a compositor-level texture-import failure.

---

## 4.6 Image Deduplication Across Directories

**Pain point:** Duplicate detection operates within a single directory scan. Users with multiple collections (local, Dropbox, crawler downloads) accumulate cross-directory duplicates.

### Options

**A — Cross-directory phash index in PostgreSQL**
Store phash alongside the embedding on database ingest. Periodic deduplication job queries pairs with Hamming distance ≤ 4.
- SQL: `SELECT a.path, b.path FROM images a, images b WHERE a.id < b.id AND (a.phash <#> b.phash) <= 4`.
- Pros: Integrates cleanly with the existing database. No re-scanning.
- Cons: N² query complexity without an index. Requires a GiST index on the phash column or a batched comparison approach.

**B — Cross-directory duplicate scan GUI extension**
Extend the existing `DuplicateScanWorker` to accept multiple source directories as input. Results show which directory each duplicate is in, with options to keep-newer, keep-larger, or keep-all.
- Pros: Fastest UX path for users who don't use the database.
- Cons: In-memory comparison doesn't scale beyond ~50k images without the chunked approach already used.

**C — Locality-sensitive hashing (LSH) for near-duplicate detection**
Use LSH (e.g., `datasketch` MinHash LSH) to efficiently find near-duplicates across collections without N² comparisons.
- Pros: Sub-linear query complexity. Handles near-duplicates (resized, JPEG-recompressed versions).
- Cons: `datasketch` dependency. More complex than phash Hamming distance. LSH index must be rebuilt when collection grows.

**D — Differential sync deduplication**
When syncing from Dropbox/GDrive (§3.5-adjacent), compare incoming files against the local phash index before downloading. Prevents duplicates from entering the collection.
- Pros: Proactive deduplication at ingest.
- Cons: Requires the sync module to query the local database before committing downloads.

**Recommendation:** A integrates cleanly with the existing database. B is the fastest UX path if users don't use the database. C for near-duplicate detection at scale.

---

## 4.7 Slideshow Improvements — ✅ Option E implemented

**Pain point:** Slideshow daemon exists (`backend/src/utils/display/slideshow_daemon.py`) but has minimal configuration. Users want timing, ordering, and filtering control.

**Status:** Option E (Image health check before rotation) is implemented in `backend/src/utils/display/slideshow_daemon.py::_advance_all` with `_is_valid_image` verifying file existence, regular file status, and non-empty file size, gracefully skipping missing or corrupted images in rotation without crashing or infinite looping (verified by `backend/test/core/test_slideshow_daemon_health_check.py`).

### Options

**A — Configurable timing, order, and filter**
Expose interval (seconds), shuffle mode, and filter (by tag/group/source directory) as persistent settings in the wallpaper tab.
- Implementation: `slideshow_config.toml` loaded by the Rust daemon; UI sliders/dropdowns in the wallpaper tab persist to `QSettings`.
- Pros: Highest-value improvement. Direct user request.
- Cons: Requires Rust daemon + Python UI changes in sync.

**B — Tag-based playlist**
Define named playlists (e.g., "dark mode", "seasonal") as lists of tags. The slideshow plays images matching the active playlist.
- Pros: More granular control than directory-based filtering.
- Cons: Requires tag integration with the slideshow daemon.

**C — Time-of-day scheduling**
Different wallpaper categories at different times (bright mornings, dark evenings). Uses system time + sun position (optional, via `astral` for local sunrise/sunset).
- Pros: Ambient computing feature.
- Cons: `astral` dependency for sun-position mode. Edge cases around timezone/DST.

**D — Transition effects (fade, slide)**
Animate transitions between wallpapers by pre-rendering a short sequence and cycling the wallpaper in rapid succession via D-Bus.
- Pros: Polish.
- Cons: Requires D-Bus calls at ~30fps during transition (KDE may rate-limit). High effort for aesthetic-only improvement.

**E — Image health check before rotation [Shipped]**
Before advancing the slideshow, verify the next image is accessible and valid (exists, not corrupt). Skip to the next if not.
- Pros: Prevents blank/error wallpaper state. Defensive improvement.
- Cons: Adds a file check to the rotation loop.

**Recommendation:** A is the highest-value improvement. B as a follow-on for tag-aware playlists. C for ambient computing users. Skip D for now.

---

## 4.8 ComfyUI Workflow Integration for Post-Processing

**Pain point:** `comfy_generate_tab.py` and `comfy_manager.py` exist but are limited to generation. ComfyUI workflows could also be used for post-processing stitched outputs and gallery images.

### Options

**A — "Send to ComfyUI" button in StitchTab**
After stitching, allow loading the output into a pre-configured ComfyUI workflow (e.g., img2img cleanup, Real-ESRGAN upscale, inpainting).
- Implementation: POST to `http://localhost:8188/prompt` with the workflow JSON; poll `/history/{prompt_id}` for completion; load result via `/view?filename=...`.
- Reference: [ComfyUI Python API guide](https://apatero.com/blog/comfyui-workflow-to-production-api-deployment-guide-2025)
- Pros: High-quality post-processing using user's existing ComfyUI setup.
- Cons: Requires ComfyUI to be running. API calls are async — need status polling or WebSocket.

**B — ComfyUI as ASP post-processing backend**
Replace `animation/super_res.py` Real-ESRGAN path with a ComfyUI API call to a user-configured workflow. More flexible — any post-processing model the user has installed.
- Pros: Decouples ASP from specific model implementations. Users can swap models without code changes.
- Cons: ComfyUI must be running during ASP execution. Adds latency for the API round-trip.

**C — Drag-and-drop image to ComfyUI queue**
Any gallery image can be dragged to a "ComfyUI" drop target that sends it to the running ComfyUI instance's queue via the API.
- Pros: Most generally useful (not tied to stitching). Natural extension of drag-and-drop patterns.
- Cons: Drop target UX requires detecting a running ComfyUI instance.

**D — ComfyUI workflow editor integration**
Embed a workflow node graph editor (using the ComfyUI frontend's JSON format) within the app. Allow users to build post-processing workflows without opening a browser.
- Pros: Seamless integration.
- Cons: Massive scope. The ComfyUI frontend is a complex React app — embedding it is impractical without `QWebEngineView` (which is banned due to JVM conflicts). Skip.

**E — Workflow template library**
Ship a set of pre-built workflow templates (upscale, denoise, colorise, inpaint borders) that users can select from a dropdown. Auto-configure the template with the correct input image.
- Pros: Low barrier to entry for non-ComfyUI-expert users.
- Cons: Templates must be kept up to date with ComfyUI node changes.

**Recommendation:** C is the most generally useful (not tied to stitching). A as a stitching-specific QoL improvement. E to lower the barrier for first-time users. Skip D.

---

## 4.9 Safetensors Metadata Viewer — ✅ Options A, D implemented

**Pain point:** `safetensors_metadata.py` exists but is not exposed in the GUI. Users managing LoRA and checkpoint files want to inspect metadata without external tools.

**Status:** Options A (read-only metadata & tensor summary modal dialog) and D (SHA256 model hash verification) are implemented:
- **`SafetensorsInspectorDialog`** (`gui/src/components/dialogs/safetensors_inspector_dialog.py`): Non-blocking metadata and tensor inspect dialog displaying file size, parameter counts, dtype breakdown, parsed model spec (LoRA rank, alpha, base model, trigger words), user metadata tree, sortable tensor slice tree, copy to clipboard, and asynchronous SHA256 integrity verification with `✓ MATCHED` / `✗ MISMATCH` indicators.
- **`backend/src/utils/data/safetensors_metadata.py`**: `read_metadata()`, `parse_model_spec()`, and `calculate_file_hash()`.
- **GUI Integration**: "Inspect .safetensors..." buttons wired in `lora_train_tab.py` and `lora_generate_tab.py`.
- **Tests**: `gui/test/dialogs/test_safetensors_inspector_dialog.py` and `backend/test/test_safetensors_metadata.py`.

### Options

**A — "Inspect Model" button in LoRA/generate tabs [Quick Win] [Shipped]**
Load any `.safetensors` file and display its metadata in a read-only `QDialog` with a `QTreeWidget` (key-value tree for nested metadata).
- Metadata fields: training parameters, trigger words, base model, hash, file size, architecture.
- Pros: Quick-win improvement to existing tabs. Minimal new code.
- Cons: Narrow scope (only accessible from specific tabs).

**B — Drag-and-drop model inspector panel**
A dedicated side panel where users drag `.safetensors`, `.ckpt`, and `.pt` files to see their metadata, architecture summary, and estimated VRAM usage.
- VRAM estimation: based on parameter count × dtype size (e.g., float16 = 2 bytes/param).
- Pros: Discoverable from anywhere in the app. Useful for model management.
- Cons: Larger investment. Needs VRAM estimation logic.

**C — Model comparison view**
Select two model files and display their metadata side-by-side for comparison (e.g., two LoRA checkpoints from different training runs).
- Pros: Useful for evaluating training progress.
- Cons: Niche use case. Better as a follow-on to A or B.

**D — Model hash verification [Shipped]**
Display the sha256/blake3 hash of the model file alongside the embedded metadata hash (if present). Show a green/red indicator for integrity verification.
- Pros: Security and provenance benefit.
- Cons: Hashing large files takes a few seconds (3–5s for a 6 GB model). Should run asynchronously.

**Recommendation:** A is a Quick Win improvement to existing tabs. B is better UX but a larger investment. D adds security value with minimal extra effort on top of A.

---

## 4.10 REST API Layer for Remote Control

**Pain point:** The Django/Celery `api/` layer exists but its relationship to the desktop app's features is undocumented. Mobile clients (§5.6) and automation scripts need a well-defined API.

### Options

**A — OpenAPI 3.0 schema for existing endpoints**
Document all existing `api/urls.py` endpoints with `drf-spectacular` or `drf-yasg`. Generate a Swagger UI available at `/api/docs/`.
- Pros: Immediate discoverability for all consumers. Zero new endpoints.
- Cons: Requires annotating existing views.

**B — Trigger desktop operations via REST**
Expose long-running operations (stitch, scan, convert) as REST endpoints that enqueue Celery tasks. Return a job ID for status polling.
- Pros: Enables CLI automation and mobile remote control.
- Cons: Desktop app must be running with the Django server active.

**C — WebSocket real-time status**
Add a WebSocket endpoint (`/ws/jobs/{job_id}/`) that streams stage-level progress events as JSON. Pairs with §2.7 (progress and cancellation).
- Pros: Real-time progress in any WebSocket-capable client (browser, mobile, CLI).
- Cons: Django Channels dependency. Adds server infrastructure complexity.

**Recommendation:** A first (document what already exists). B as the automation-enabling extension. C for real-time mobile/web clients.

---

## 4.11 ASP Quality Feedback Interface (RLHF)

**Status (2026-07-27):** The entire foundation this item was written against — the `StitchRewardModel` /
`_compute_rlhf_score()` / `_get_reward_model()` reward-model loop in `bench_anime_stitch.py` (formerly §1.10A,
S29) — was deleted in the 2026-07-09 "S200 great trim" (`refactor(asp): trim benchmark to core metrics; prune
dead-feature tests` / `refactor(asp): trim Python pipeline to its benchmarked core path`). The HITL
checkpoints/session-review UI in `stitch_tab.py`/`stitch_worker.py` still exist and still collect a per-run
"final output quality rating" at checkpoint 5, but nothing currently consumes that rating to train a reward
model — there is no reward model left to train. This item is **not done**; it would need the RLHF
foundation rescoped and rebuilt from scratch (a reward model, a training loop, and a reason to have one)
before any of the UI options below are worth building. The current `the ASP submodule's moon/ROADMAP.md` roadmap has no equivalent item.

**Pain point (original framing, now describing removed infrastructure):** The `StitchRewardModel` in `bench_anime_stitch.py` (§1.10A, S29) uses random weights until feedback is collected. There is no UI for users to rate stitching outputs so the reward model can learn meaningful preferences. Without rated outputs, the RLHF loop cannot close and the reward model never improves.

### Options

**A — Inline rating panel in StitchTab [Quick Win]**
After each stitch completes, show a 5-point rating widget (thumbs up / thumbs down / star rating) below the output preview. Ratings are written to a `~/.image-toolkit/stitch_feedback.jsonl` file as `{test_id, asp_score, simple_score, user_rating, timestamp}`. The reward model loads this file at startup to fine-tune weights.
- Implementation: ~80 LOC — `QToolBar` with `QSlider` (1–5 stars) + "Submit" button. Writes to JSONL via `json.dumps` + `f.write`.
- Pros: Minimal UI work. JSONL is portable and auditable.
- Cons: No per-seam granularity — only a global output rating.

**B — Side-by-side comparison mode with preference labelling**
Show ASP output and simple-stitch output side by side. User clicks "this one is better" (or "equal"). Preference pairs `(asp_result, simple_result, preferred)` are written to the feedback file.
- Pros: Generates richer comparative data (Bradley-Terry model compatible). Directly maps to RLHF preference learning.
- Cons: Requires the simple-stitch output to be retained alongside the ASP output. 2× disk usage per test.

**C — Batch rating mode for existing outputs [Quick Win]**
A separate "Rate Previous Outputs" dialog that loads already-saved PNG outputs from `~/.image-toolkit/stitched/` and presents them one-by-one for rating. Useful for rating the 96-test corpus in bulk.
- Pros: No blocking of the main stitch workflow. Can be done asynchronously.
- Cons: Must reconstruct metadata (which test, what parameters) from the output filename.

**D — Per-seam quality annotation**
After stitching, show each boundary seam zone as a thumbnail strip. User rates each seam 1–5. The reward model receives per-seam signals rather than a global output score — finer-grained training.
- Pros: More useful for targeted seam parameter tuning (feather width, gain, DP seam routing).
- Cons: 13 seams per output × ~30s per seam = ~7 minutes of annotation per dataset. Fatigue risk.

**Recommendation:** A immediately (simplest path to start collecting feedback). B for users who want to generate comparative DPO-style preference data. C as a bulk-annotation tool for the existing 96-test corpus. D as an advanced mode once A is validated.

---

## 4.12 Appearance Profiles

**Pain point:** Theme (dark/light), accent colour (§2.30), font scale (§2.30B), density (§2.30C), and keyboard shortcuts (§2.29) are stored separately — theme in the vault, shortcuts in `keybindings.json`, font scale in vault preferences. Users who switch between contexts (e.g., laptop with small screen vs external monitor, or different lighting environments) must manually change each setting individually. A single "profile switch" that atomically applies all appearance settings would eliminate this friction.

### Options

**A — Appearance profile in existing "System Preference Profiles"**
Extend the vault's `system_preference_profiles` entries (already used for theme + tab configs) to include: `accent_color_dark`, `accent_color_light`, `font_scale`, `density`, and optionally a reference to a shortcut profile name. Applying a profile calls `set_application_theme()`, `QApplication.setFont()`, and (if shortcuts changed) rebuilds `QShortcut` objects.
- Pros: Reuses existing profile infrastructure. No new UI sections needed.
- Cons: Vault profiles already hold theme + tab configs; adding appearance fields makes them broader. Users may want to apply an appearance profile without changing tab configs.

**B — Separate "Appearance Profiles" concept**
A dedicated `appearance_profiles` key in the vault (or a plain `~/.image-toolkit/appearance_profiles.json`), decoupled from system preference profiles. Each profile: `{name, theme, accent_dark, accent_light, font_scale, density}`. Exposed in a dedicated "Appearance Profiles" dropdown in the Appearance settings tab.
- Pros: Clear separation of concerns. Appearance profiles can be swapped without touching tab default configs.
- Cons: Yet another profile concept alongside "System Preference Profiles" and "Tab Default Configurations". Three profile systems may confuse users.

**C — Named workspaces (superset of profiles)**
A full workspace concept capturing: appearance profile + layout profile (§2.32B) + session state (§2.5B). `File → Workspaces → Switch`. One click restores the entire working environment.
- Pros: Maximum ergonomic gain for context-switching users.
- Cons: Depends on §2.29, §2.30, §2.32B all being implemented. Long-term item.

**Recommendation:** A first (minimal code, reuses the existing profile dialog). B if users find appearance and tab-config profiles becoming unwieldy to manage together. C as the long-term unified workspace concept.

---

## 4.13 Shortcut Macros and Custom Actions ✅ Option C (2026-08-01, issue #61) {: #413-shortcut-macros-and-custom-actions }

**Shipped: workflow templates**, per this section's own recommendation ("essentially the existing Tab Default Configuration system extended to cross-tab context"). `Ctrl+Shift+M` opens a picker (`gui/src/windows/main/_workflow_templates.py`, new `_WorkflowTemplatesMixin`) listing saved named templates with Run/New/Delete. A template is an ordered list of `{category, tab_name, config_name}` steps — building one reuses the *existing* `tab_configurations` vault store (the same one the Settings window's "Tab Default Configuration Management" section and Ctrl+S already read/write, no new config format). Running a template applies each step's saved config to its tab via the already-universal `set_config()` contract every tab implements, then switches to the **last** step's tab via the same `command_combo` + `_select_tab_by_name` cross-tab-activation pattern used by Ctrl+T and §2.28's global search — directly matching the pain point's own example ("browse to directory X, scan, then switch to delete tab": set up N tabs' state, then land on the one you actually work in next). New `general.workflow_templates` shortcut-registry entry (`Ctrl+Shift+M`, remappable). Stored in the vault under a new `workflow_templates` key, parallel to `tab_configurations`.

Options A (registered-command-ID macro playback) and B (eval'd Python expressions) not pursued: A's "sequence of commands" framing turned out to reduce to "sequence of tab-config-applications + one final tab switch" once actually designed, which is exactly what shipped without needing a separate command-ID registry; B was explicitly flagged skip-unless-requested for its security profile.

Tests: `gui/test/core/test_workflow_templates.py` (4, new — key dispatch, save/load round-trip, run applying a config + activating the last tab, and the missing-template warning path).

**Pain point:** Some workflows require a fixed sequence of tab switches + operations (e.g., "browse to directory X, scan, then switch to delete tab"). These multi-step sequences have no automation path — users repeat them manually every session. A lightweight macro system bound to user-defined hotkeys would eliminate repetitive navigation.

### Options

**A — Recorded macro playback via QEventLoop replay**
Record a sequence of `QAction` / callable references as a named macro. Play back via the registered shortcut. Macros are stored as ordered lists of registered command IDs (from `SHORTCUT_REGISTRY` / command registry in §2.16A).
- Example macro: `["tab:convert", "action:scan_start", "wait:5000", "action:select_all"]`.
- Pros: No scripting language. Uses the command registry as the primitive set. Playback is just iterating callables.
- Cons: Only covers operations that are registered commands. Cannot express conditional logic.

**B — Python expression macros (power users)**
A text field in settings where users type a Python expression (a lambda or short function body) that is `eval`-ed and bound to a shortcut. The expression receives a `ctx` object with references to all tab instances.
- Pros: Unlimited expressiveness.
- Cons: Security risk if shared. Must sandbox or document clearly as a developer feature.

**C — Workflow templates (non-macro)**
Instead of executable macros, provide named "workflow templates" that pre-fill all relevant tab settings (scan directory, output format, filter) with one click. Not a hotkey macro — a preset loader.
- Pros: Safer than macro playback. Covers 80% of the use case (state setup, not operation sequencing).
- Cons: Does not automate multi-step operation sequences.

**Recommendation:** C first (workflow templates are essentially the existing Tab Default Configuration system extended to cross-tab context). A as the scripted macro layer once §2.16 (command palette + registry) is established. Skip B unless explicitly requested.

---

## 4.14 Extractor Tab Storyboard Scrub Preview

**Pain point:** Dragging the playhead across the Extractor tab's progress bar needs to show frames updating live, matching Haruna/YouTube-style scrubbing. Several attempts (2026-07) to make this fast by decoding real frames on demand — a per-frame `ffmpeg` subprocess, a background dense-keyframe proxy, and finally a persistent in-process PyAV decoder — kept hitting a mix of latency and `QMediaPlayer` surface-swap bugs (see `gui_ux.md` §2.33 for the follow-up libmpv item tracking a proper fix for the *main player's* seek speed). The realization: none of that is actually how large-scale video platforms solve this. YouTube's scrub preview isn't a live decode at all — it's a pre-generated storyboard (a sprite sheet of small thumbnails at fixed intervals, built once when the video is processed), so dragging the scrubber is just cropping an already-in-memory image, with zero per-tick decode cost.

### Options

**A — Pre-generated sprite-sheet storyboard + floating preview widget [Chosen]**
On video load, build a storyboard image in the background (one `ffmpeg` call: `fps=1/N,scale=W:-1,tile=RxC`), cached alongside the existing scrub proxy. A small floating widget positioned above the slider at the cursor's x-position looks up `position_ms → tile index` and crops the pixmap — no decode, no subprocess, no thread involved in the interactive path. The main player's video surface is left completely alone during the drag; it commits to the real frame only when dragging pauses (not just on release), reusing the existing `videoSink().videoFrameChanged`-gated safe-reveal logic so it fires rarely instead of on every tick.
- Pros: Interactive-path cost is array-slicing, not decoding — smoothness stops being a function of decode speed at all. Structurally cannot reproduce the `QMediaPlayer` surface-swap bugs hit in every prior attempt, since it never touches that code path during the drag. Matches the proven, battle-tested approach every major video platform actually uses.
- Cons: Preview granularity is fixed at generation time (e.g. one tile per 2s) — not frame-accurate, same trade-off YouTube itself makes. One more background-cached asset per video (same pattern as the scrub proxy, same cache directory conventions).

**B — Live-decoded low-res preview (superseded)**
The prior approach: decode an actual frame near the cursor position on every drag tick, at low resolution to keep it cheap. Covered at length by the three implementation attempts referenced above.
- Cons: Every variant tried (subprocess-per-frame, proxy-backed subprocess, persistent PyAV decoder) either couldn't sustain real-time cadence under real interactive dragging or reintroduced `QMediaPlayer` surface coupling bugs. Not pursued further.

**Recommendation:** A. Implemented 2026-07.

---

## 4.15 Extractor Tab Image Sub-Tab — Multi-Frame Image Splitter

**Pain point:** The Extractor tab only handled videos/GIFs, but multi-frame *images* are common in the corpus — sprite sheets, webtoon strips, and contact-sheet style grids where one file contains many frames stacked vertically, horizontally, or in a grid. Splitting those meant leaving the app for an external slicer, and external tools give no fast way to verify that the assumed frame size actually lands on the real frame boundaries (an off-by-a-few-pixels frame height accumulates across a long strip).

**Implemented 2026-07-17:** The Extractor tab was restructured into **Video / Image subtabs** (same `QTabWidget` pattern as the Convert and Wallpaper tabs). The Video subtab is the pre-existing extractor unchanged (`VideoExtractorSubTab`, still in `extractor_tab.py` so test patch targets survive); the outer `ExtractorTab` wrapper transparently delegates attribute access to it so the main window's duck-typed settings hooks and class-name-keyed session recovery are untouched.

The new Image subtab (`gui/src/tabs/core/elements/image_extractor_subtab.py`):

- **Parameters** — arrangement (Vertical / Horizontal / Grid), per-frame size (one dimension for strips — the other spans the image; both for grids), X/Y offset, inter-frame spacing, and an "include partial last frame" toggle.
- **Boundary preview** — every cut rectangle is drawn over the image with cosmetic (zoom-invariant 1-px) alternating cyan/magenta outlines; regions the current parameters leave uncovered render as dashed amber, so a wrong frame size is visible at overview zoom before zooming in.
- **Deep-zoom canvas** (`FrameSliceCanvas`) — 0.01×–80× range, cursor-anchored wheel zoom (aggressive 1.3×/notch to cross the range quickly), drag panning, Fit/1:1/±buttons, and double-click toggling between fit-to-view and 1:1 at the clicked point — the intended loop is: overview → double-click a boundary → verify at pixel scale (nearest-neighbor rendering ≥1:1) → double-click back out → next boundary.
- **Extraction** — frame rects are cut via `QImage.copy` in a `QRunnable` worker (progress-reported, cancellable via `cancel_loading()`) and saved as `{stem}_fNNN.png` into a configurable output directory (default `Frames/`). File dialogs pass `DontUseNativeDialog` per the JVM/GTK SIGSEGV rule.
- **Session recovery** — the Image subtab's parameters ride inside the ExtractorTab config under the `image_extractor` key.

**Possible follow-ups:** per-boundary draggable adjustment handles on the canvas; auto-detection of frame pitch via edge/periodicity analysis; feeding cut frames straight into the GIF-assembly path the Video subtab already has.

---

## 4.16 Additional Stitcher Options

**Pain point:** The Merge tab's "panorama" mode only ever drove OpenCV's
`Stitcher`, and a separate "stitch" mode existed solely to run the same
`Stitcher` in SCANS mode (mode 1) instead of PANORAMA mode (mode 0) — two
top-level Modes for what is really one engine with one parameter. Getting a
genuinely different stitching *algorithm* (not just a different `Stitcher`
mode) meant checking "Perfect Stitch Mode", a single boolean that routed to
the Anime Stitch Pipeline (ASP) with no way to reach Overmix or Hugin — both
already built and benchmarked as reference comparators in `https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md`
§0.3/§0.5 — from the GUI at all. A boolean checkbox also doesn't scale: adding
a third or fourth engine would mean more checkboxes fighting for the same
mutually-exclusive slot.

**Implemented 2026-07-27:** replaced the checkbox with an **Engine** dropdown, shown
only when Mode is "panorama", with four options — each revealing only its
own relevant settings:

- **OpenCV** (the previous panorama/stitch split, now one engine):
  - *Stitcher mode*: `0 — Panorama` or `1 — SCANS` (this *is* the old "stitch"
    Mode — folded in here since it was never a different algorithm, just a
    different `cv2.Stitcher` mode + registration resolution).
  - *Registration resolution*: the same `setRegistrationResol()` knob SCANS
    mode already used internally, now user-facing for both modes.
- **Hugin Toolchain** (external tool, `pto_gen`→`cpfind`→`autooptimiser`→
  `pano_modify`→`nona`→`enblend`, via system `hugin-tools`/`enblend` packages —
  see §0.5's field notes for why system packages rather than the vendored
  fork):
  - *Projection*: Rectilinear / Cylindrical / Equirectangular.
  - *Linear sequence matching*: on by default — uses `cpfind --linearmatch`
    (frames are a scrolling pan, not a rotating-camera panorama) instead of
    the multi-row heuristic.
- **Overmix** (external tool, GPL-3.0, `vendor/Overmix/build/OvermixCli` — see
  §0.3's field notes):
  - *Aligner*: Recursive / Average / Linear.
  - *Render statistic*: average / median / min / max / difference. Comparator
    is fixed to `Gradient` internally — the field notes found `BruteForce`
    too slow to expose as a real option (didn't finish a 6-frame test in
    90s at full frame resolution).
- **Anime Stitch Pipeline**: the pre-existing AI options panel, reused as-is
  except for two cleanups found while auditing it for this change — neither
  is wired to anything in `AnimeStitchPipeline.__init__` (verified by grep):
  the "Order-Agnostic Matching / Parallax Absorption / Structure Preservation /
  Neural Synthesis Refinement" checkboxes (`use_siamese`/`use_apap`/`use_lsd`/
  `use_gan` — dead parameters `perfect_stitch()`'s own docstring already
  flagged as ignored) and the entire "MFSR Super-Resolution" group (no `mfsr_*`
  reference exists anywhere in `backend/src/animation/`). Both removed rather
  than left as non-functional UI. Kept: renderer, motion model, BiRefNet/BaSiC/
  LoFTR/ECC toggles, composite-foreground toggle, edge crop, and pyramid
  (Laplacian band) levels — all genuinely consumed by the pipeline.

Backend: `backend/src/core/image_merger.py` gained `_merge_images_hugin` and
`_merge_images_overmix` (subprocess wrappers, matching the benchmark scripts'
settings) alongside the existing `_merge_images_opencv` (now parameterized by
stitcher mode + registration resolution instead of two near-duplicate
functions). `merge_images()`'s `direction="panorama"` branch takes an
`engine` kwarg; `direction="stitch"` no longer exists.

**Possible follow-ups:** exposing Hugin's `cpclean` outlier-removal pass and
Overmix's `AnimationSeparator` phase-aware alignment as opt-in toggles once
either proves worth the extra control; a "compare all four engines" batch
button that runs every engine on the current canvas selection side by side.

## 4.17 Media Loader — Web Media Downloader ✅ Reddit + nhentai shipped (2026-08-03, issue #182) {: #417-media-loader--web-media-downloader }

**Shipped: a new "Media Loader" tab under Web Integration** for downloading media (images/videos) from the web, with two initial source integrations. `backend/src/web/downloaders/reddit_downloader.py` (`RedditDownloader`) supports subreddit/user/single-post modes and downloads direct images, gallery posts, and `v.redd.it` video (video-only stream, no audio remux — modeled on, and sharing this exact trade-off with, the [RedDownloader](https://pypi.org/project/RedDownloader/) PyPI package). `backend/src/web/downloaders/nhentai_downloader.py` (`NhentaiDownloader`) scrapes a gallery page's embedded JSON metadata and downloads each page from nhentai's image CDN — modeled on the [nhentai-downloader](https://pypi.org/project/nhentai-downloader/) PyPI package. Both use the synchronous `requests` library (a plain `QObject`, no C++ `base` module dependency). **Not** `asyncio`/`aiohttp`/`asyncpraw`: an initial version of both downloaders used that combination and crashed the app on its first real download (`QSocketNotifier`/SIGSEGV/heap corruption — the extensively-documented off-main-thread-native-lib-with-JVM-loaded crash class, see `architecture.md` and `.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`); fixed same-day by switching to `requests` — the same pattern already proven safe in this exact QThread+JVM environment by `ImageCrawler`/`WebRequestsLogic`/the MAL sync workers. `RedditDownloader` hits Reddit's public `.json` listing endpoints (no OAuth app registration needed). `NhentaiDownloader` parses nhentai's current SvelteKit-embedded gallery JSON, with a fallback parser for the older markup.

GUI: `gui/src/elements/web/media_loader_tab/` (manager.py + mixins, same composition pattern as `image_crawler_tab`/`drive_sync_tab`) with a source picker, per-source settings pages, and shared download-dir/run/cancel/progress controls; `gui/src/helpers/web/media_loader_worker.py` (`MediaLoaderWorker`, a `QThread` mirroring `image_crawl_worker.py`) dispatches to the selected downloader. Registered as `"Media Loader"` in `_tab_registry.py`'s Web Integration category. Both downloaders emit `backend/src/core/telemetry.py` events (`media-loader` category) around every HTTP call and the overall run.

**Possible follow-ups** (tracked in issue #182): ffmpeg audio remux for Reddit video; Cloudflare-challenge handling for nhentai; wiring Reddit credentials into the Vault/credentials system instead of env-vars only; automated tests for the two downloader classes; additional source integrations (Twitter/X, Pixiv, generic gallery-dl-style sites).

---

## 4.18 Image Board Crawler — Rating Filter & SFW Board Support {: #418-image-board-crawler--rating-filter--sfw-board-support }

**Status:** ✅ Implemented (2026-08-15, Issue #370 / S379).

**Motivation:** ASP's benchmark corpus is currently built entirely from
sexually explicit source content, sourced by hand (manual booru-tag browsing).
This is not a website/marketing concern — `docs/website` and `docs/tutorials`
were checked (2026-08-15) and contain no NSFW text or imagery — but it is a
real gap in ASP's promotion ladder: every quality gate in
`asp_change_roadmap_2026q3.md`'s M0–M6 is tuned and validated against one
content distribution, with no second distribution to catch overfitting to
that domain's visual characteristics. Building a SFW benchmark corpus is
tracked separately (ASP's `asp_sfw_corpus_roadmap_2026q3.md`); this section
is the crawler-engine work that unblocks it.

**Implementation (2026-08-15):**
- `backend/src/web/crawlers/image_board_crawler.py`: Added automatic rating normalization (`config["rating"]` appends `rating:<val>` to tags if not already present) and added `get_crawler_backend_name()` for polymorphic C++ backend dispatch.
- `backend/src/web/crawlers/safebooru_crawler.py`: Added `SafebooruCrawler` preset backed by the Gelbooru DAPI engine (`https://safebooru.org`).
- `backend/src/web/crawlers/__init__.py`: Re-exported all active crawler classes.
- `backend/test/web/test_image_board_crawler.py`: Added unit tests covering Safebooru preset and rating normalization.


---

## 4.19 Account-Linked Settings Sync (Google Drive) {: #419-account-linked-settings-sync-google-drive }

**Status:** Draft only — quick scope note for future work, not a fully
specced feature. Deliberately kept light per Harbinger's explicit request
(2026-08-15).

**Goal:** link an Image-Toolkit install to a Google account and sync app
settings across a user's own multiple devices via a Google Drive folder.

**Narrowed scope (Harbinger, 2026-08-15):** despite `~/.image-toolkit/`
containing a lot of state (databases, caches, logs, telemetry — several GB
total), only **two files matter for this entry**, both already encrypted:
`secrets/my_keystore-a.p12` and `secrets/my_secure_data-a.vault`. Together
they hold the app's settings — the highest-impact thing to sync, and the
only target in scope right now. Everything else in `~/.image-toolkit/`
(caches, logs, telemetry, the actual content databases) is explicitly out of
scope for this entry — regenerable/large data has different sync
requirements and isn't part of this draft.

**Existing foundation, not starting from zero:** `backend/src/web/cloud/`
already has a working `GoogleDriveSync` (+ Dropbox/OneDrive siblings) with
both Service Account and personal OAuth flows, a native C++ implementation,
and a GUI worker (`gui/src/helpers/web/cloud/google_drive_sync_worker.py`).
That infrastructure syncs arbitrary local folders to a named Drive folder
today — this feature is about **pointing it at (or extending it for) the
two encrypted settings files specifically**, with account-linking as the
entry point, not building Drive sync from scratch.

**Genuinely open, left for whoever picks this up:**

- **Conflict resolution** when the same settings file changes on two
  devices before a sync — simple last-write-wins (matches the existing
  sync worker's likely current behavior, unverified), or version-keep-both
  with a user prompt? Different files, different answer is plausible (the
  keystore rarely changes; the vault might change more often).
- Whether "git-like tracking" (versioned snapshots, useful since these are
  small encrypted blobs, not large databases — diffing doesn't help but
  keeping N prior versions does) or something simpler (just overwrite,
  rely on Drive's own version history) is worth building vs. relying on
  Google Drive's native file-revision history, which may already cover
  this need for free.
- Whether "database replication" (mentioned in the original ask) is even
  relevant to this narrowed two-file scope — it matters much more for
  large multi-writer SQLite databases (`library.db` etc.) than for two
  small encrypted settings blobs, and that broader database-sync problem is
  explicitly not what this entry covers. If cross-device DB sync is wanted
  later, it deserves its own, separately-scoped roadmap entry — don't
  assume this one expands to cover it.

**ASP note:** Harbinger asked for a pointer entry in ASP too, not current
priority there — see `asp_change_roadmap_2026q3.md` §7 (future work,
non-priority) for the cross-link.

---

## 4.20 Cloud Sync tab restructure + Local Directory Sync {: #420-cloud-sync-local-directory-sync }

**Status:** Completed (issue #479, 2026-08-31).

**Goal:** synchronize the whole local `~/.image-toolkit/` directory with a
remote `.image-toolkit/` folder on the user's cloud provider. All three ship
per-file clients now — Google Drive (`gdrive_file_client.py`), Dropbox
(`dropbox_file_client.py`) and OneDrive (`onedrive_file_client.py`) — driving
each provider's per-file REST API instead of the whole-folder-only C++ sync.
Broader than §4.19 (which is scoped to just the two encrypted settings
files) — this covers configs, keybindings, user QSS, and opt-in data —
while deliberately **not** attempting multi-writer database replication
(that stays its own separately-scoped problem).

**Part A — tab restructure.** The top-level **Cloud Synchronization** tab
(`gui/src/tabs/web/drive_sync_tab/`, registered `_tab_registry.py:113`)
becomes a container with a `QTabWidget`:

- **"Sync Data" subtab** — today's entire behavior (provider switch, remote
  map, folder browse/share, the DB-backed `_sync_worker`), moved into a new
  `sync_data_subtab/` package.
- The parent `DriveSyncTab` retains only shared logic: provider
  selection / auth (`_auth_config`, `_provider_switch`, `gdrive_auth_helper`),
  the UI lock (`_ui_lock`), `_defaults`, cross-subtab signal plumbing.
- Every new/changed file **< 500 LoC**.

**Part B — "Local Directory Sync" subtab.**

- Bidirectional diff of `~/.image-toolkit/` ↔ remote `.image-toolkit/` by
  relative path + mtime + size (content hash on tie).
- Conflict policy: newer-wins default, with *prefer local / prefer remote /
  ask* setting; remote dir auto-created; dry-run preview before first sync.
- Dedicated GC-disabled QThread worker (mirrors
  `google_drive_sync_worker.py`), progress + cancel.
- **Security:** default exclude list keeps the vault keystore / key material
  and anything carrying absolute host paths (logs, traces) out of the cloud;
  editable include/exclude UI; one-time warning that contents of
  `~/.image-toolkit/` will leave the machine. The `.vault` / `.p12` files are
  AES-256-GCM but path leakage from logs is not.

**Effort:** Medium–High. **Impact:** High (cross-device state, and the
container refactor unblocks further cloud subtabs).

**Tests:** subtab construction; the diff / conflict resolver as pure logic
(no network); exclude-list enforcement; worker dry-run/live e2e against a
fake Drive client (`gui/test/web/test_local_dir_sync_e2e.py`). Live Google
Drive arm is opt-in via `IT_GDRIVE_ACCESS_TOKEN`.

---

## 4.21 Cloud Compute Offload {: #421-cloud-compute-offload }

**Status:** In progress (issue #486). PoC first: Extractor-tab extractions via
Google Cloud (`gcd`). Dashboards aggregation + charts: issue #490.

**Goal:** run the app's heavy requests — video-frame / GIF / clip extraction,
deep-learning image generation — on a chosen managed cloud provider instead of
the local machine, from a dedicated **Cloud Compute** window (Settings-window
shape: left nav + stacked panes).

**Window layout**

- **Providers pane** — a card per platform (Google Cloud / Cloudflare / Oracle
  Cloud; AWS/Azure later) with a detailed description, the hardware/shape
  options it exposes (CPU-flex, L4/A10/A100 GPU, memory tiers), rough
  cost-per-hour, region list, and cold-start behaviour. Selecting one sets the
  active target.
- **Request Builder pane** — define a heavy request the same way its local tab
  does (source, range/params for extraction; prompt/model/steps/resolution for
  generation), pick the shape, then **Run in Cloud** → the request is packaged
  and dispatched to the provider's worker (`infra/cloud/<provider>/`), inputs
  uploaded, outputs pulled back into the normal gallery / output dir on
  completion. A queue view shows pending / running / done with cancel.
- **Dashboards tab** — plots/charts of cloud-request resource usage over time:
  per-job wall time, peak vCPU / GPU / memory, egress bytes, cost estimate,
  success/failure rate, provider comparison. Data comes from the worker's
  status/usage rows (Cloudflare D1 / Cloud Run logs+metrics / OCI monitoring).
  Follow the `dataviz` skill for the charts.

**Infra** (present): `infra/cloud/gcd/cloud-run-service.yaml` (Knative,
CPU-flex now, GPU pool for generation), `infra/cloud/cloudflare/wrangler.toml`
(Workers + Queues + R2 + D1), `infra/cloud/oracle/oci-container-instance.tf`
(Container Instance, GPU shapes). Common contract: enqueue job JSON → worker
runs a container image of the extraction / generation code → writes
outputs + a usage row → app polls / webhooks for completion.

**PoC scope (issue #487):** Extractor tab gains a "Run in Cloud (GCD)" path
that dispatches one extraction config to the Cloud Run worker, uploads the
source video (or a signed URL), downloads the produced frames, and records one
usage row the Dashboards tab reads. No GPU, one provider, one request type.

**Worker foundation (issue #491, implemented):** `infra/cloud/gcd/worker/`
provides the slim FFmpeg-only Cloud Run image and `POST /jobs` endpoint. It
accepts a `gs://` range/GIF/video job, uploads outputs plus `usage.json` to
`RESULTS_BUCKET`, and keeps each FFmpeg phase within the service request
budget. Desktop dispatch and result download remain part of the PoC scope.

**Security:** provider credentials via `VaultManager` (never in configs — the
`infra/` files use env/secret placeholders); the source-video upload path
warns before anything leaves the machine (same rule as §4.20).

**Effort:** Very High (external dependency, new window, per-provider adapters).
**Impact:** Very High (differentiating — offloads the exact features that OOM
the local box, see #483/#485).

**Tests:** provider-descriptor rendering; request→job-JSON serialization
(pure logic); dashboard aggregation from mock usage rows; the GCD adapter
against a mocked Cloud Run endpoint.

---

## Effort × Impact Matrix {: #effort--impact-matrix }

*Effort* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks or external dependency
*Impact* — **Low**: niche · **Medium**: measurable user QoL · **High**: major capability unlock · **Very High**: differentiating feature

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | §4.2C WebP quick-share export · §4.7E image health check · §4.9A safetensors viewer [Quick Win] · §4.10A OpenAPI schema · §4.13C workflow templates · §4.18 crawler rating filter + Safebooru preset | §4.2B ffmpeg scrolling video · §4.5E wallpaper mirror all monitors · §4.9D model hash verify · §4.11A inline rating panel [Quick Win] · §4.11C batch rating mode · §4.14A storyboard scrub preview [Quick Win] | §4.1C CLI batch stitch · §4.7A slideshow config | — |
| **Medium (1d–1w)** | — | §4.5A KDE per-monitor wallpaper · §4.5D HydraPaper GNOME · §4.6A cross-dir phash dedup · §4.8A stitch→ComfyUI button · §4.10B trigger operations via REST · §4.12A appearance profiles | §4.4A WD14 auto-tagger · §4.6C LSH near-dedup · §4.8C drag-drop to ComfyUI · §4.8E workflow template library · §4.13A macro playback | §4.3A CLIP semantic search |
| **High (1–2w)** | — | §4.1A GUI batch mode | §4.10C WebSocket job status · §4.11B side-by-side preference labelling · §4.11D per-seam annotation | §4.3C dual-column CLIP + Siamese search |
| **Very High (2w+)** | — | — | §4.1B PostgreSQL job queue | §4.3B AnimeCLIP fine-tune |

---

## Anchor Index

| Section | Anchor |
|---------|--------|
| 4.1 Batch Stitching | [#41-batch-stitching](#41-batch-stitching) |
| 4.2 Scrolling Video Export | [#42-export-stitched-panorama-to-scrolling-video](#42-export-stitched-panorama-to-scrolling-video) |
| 4.3 CLIP Semantic Search | [#43-clip-based-semantic-image-search](#43-clip-based-semantic-image-search) |
| 4.4 Auto-Tagger | [#44-auto-tagger-integration](#44-auto-tagger-integration) |
| 4.5 Multi-Monitor Wallpaper | [#45-multi-monitor-wallpaper-support](#45-multi-monitor-wallpaper-support) |
| 4.6 Cross-Directory Dedup | [#46-image-deduplication-across-directories](#46-image-deduplication-across-directories) |
| 4.7 Slideshow Improvements | [#47-slideshow-improvements](#47-slideshow-improvements) |
| 4.8 ComfyUI Integration | [#48-comfyui-workflow-integration-for-post-processing](#48-comfyui-workflow-integration-for-post-processing) |
| 4.9 Safetensors Metadata Viewer | [#49-safetensors-metadata-viewer](#49-safetensors-metadata-viewer) |
| 4.10 REST API Layer | [#410-rest-api-layer-for-remote-control](#410-rest-api-layer-for-remote-control) |
| 4.11 RLHF Quality Feedback | [#411-asp-quality-feedback-interface-rlhf](#411-asp-quality-feedback-interface-rlhf) |
| 4.12 Appearance Profiles | [#412-appearance-profiles](#412-appearance-profiles) |
| 4.13 Shortcut Macros and Custom Actions | [#413-shortcut-macros-and-custom-actions](#413-shortcut-macros-and-custom-actions) |
| 4.14 Extractor Tab Storyboard Scrub Preview | [#414-extractor-tab-storyboard-scrub-preview](#414-extractor-tab-storyboard-scrub-preview) |
| 4.15 Extractor Tab Image Sub-Tab — Multi-Frame Image Splitter | [#415-extractor-tab-image-sub-tab--multi-frame-image-splitter](#415-extractor-tab-image-sub-tab--multi-frame-image-splitter) |
| 4.16 Additional Stitcher Options | [#416-additional-stitcher-options](#416-additional-stitcher-options) |
| 4.17 Media Loader — Web Media Downloader | [#417-media-loader--web-media-downloader](#417-media-loader--web-media-downloader) |
| 4.18 Image Board Crawler — Rating Filter & SFW Board Support | [#418-image-board-crawler--rating-filter--sfw-board-support](#418-image-board-crawler--rating-filter--sfw-board-support) |
| 4.19 Account-Linked Settings Sync (Google Drive) | [#419-account-linked-settings-sync-google-drive](#419-account-linked-settings-sync-google-drive) |
| 4.20 Cloud Sync tab restructure + Local Directory Sync | [#420-cloud-sync-local-directory-sync](#420-cloud-sync-local-directory-sync) |
| 4.21 Cloud Compute Offload | [#421-cloud-compute-offload](#421-cloud-compute-offload) |

---

## Document History

*Last updated: 2026-08-31 — §4.21 Cloud Compute Offload added (run heavy requests — extraction, DL generation — on a chosen cloud provider from a Settings-shaped window with per-platform hardware descriptions + a resource-usage dashboards tab; PoC = Extractor extractions via Google Cloud Run; infra/cloud/{gcd,cloudflare,oracle}/ configs added; issues #486/#487). Previous update same day — §4.20 Cloud Sync tab restructure into subtabs + Local Directory Sync (~/.image-toolkit ↔ remote .image-toolkit) added, Priority 1 in progress (issue #479). Previous update 2026-08-15 — §4.19 Account-Linked Settings Sync (Google Drive) added as a quick draft, deliberately not fully specced. Previous update same day: §4.18 Image Board Crawler rating filter and Safebooru board support added (planned, not yet implemented), motivated by the ASP SFW benchmark corpus roadmap. Previous update 2026-08-03: §4.17 Media Loader (Reddit + nhentai web media downloader tab) added and shipped same day, issue #182. Previous update 2026-07-17: §4.15 Extractor Tab Image Sub-Tab (multi-frame image splitter) added, implemented same day: Extractor tab split into Video/Image subtabs. Previous update 2026-07-11 (§4.14 storyboard scrub preview).*
