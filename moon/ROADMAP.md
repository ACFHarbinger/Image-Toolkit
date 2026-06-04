# Image Toolkit — Master Roadmap

*Last updated: 2026-06-04 (session 5). Session 5: alignment stability gate (+0.074 test08, +0.049 test25), fg pixel L1 pose metric (+0.010 test27 with pose-on), 90 unit tests. Session 4: ARAP Push phase (full Sýkora 2009), 96-test run: 52/96 true ASP composites (was 44/96), avg ASP SSIM 0.667 vs simple 0.694. Session 3: pose-consistent frame selection infrastructure. Session 2: RAFT/ARAP/post_warp_diff. Session 1: foreground-assembly pipeline (A1–A6). Research consolidated: `reports/Image_Stitching_Research.md`.*

Completed items have been moved to [CHANGELOG.md](CHANGELOG.md).

---

## How to Use This Document

This document defines the **phased execution sequence** for all upcoming improvements. Each item links to the corresponding brainstorming section in the appropriate section-specific roadmap for full context, options, and trade-offs.

Section-specific roadmaps:
- [ASP — Anime Stitch Pipeline](roadmaps/asp.md)
- [Content Generation — Anime Image & Video](roadmaps/content_generation.md)
- [GUI/UX — Desktop Interface](roadmaps/gui_ux.md)
- [Performance — Compute, Memory, I/O](roadmaps/performance.md)
- [New Features — Capabilities & Integrations](roadmaps/new_features.md)
- [Architecture & Infrastructure](roadmaps/architecture.md)

Consolidated research reports (read before working on the respective pipeline):
- [Anime Stitching — Consolidated Research](../reports/Image_Stitching_Research.md) — foreground-assembly paradigm, per-stage toolbox, 13-stage spec.
- [Anime Generation — Consolidated Research](../reports/Image_Generation_Research.md) — image + video models, fine-tuning, video→LoRA pipeline.

Phases are ordered by impact-to-effort ratio and dependency order. Items within a phase are independent and can be parallelised.

---

## Phase 0 — ASP Foreground Assembly (Priority 0, The Core Quality Fix)

The single highest-impact track: the pipeline cannot register the deforming foreground, so characters tear at every strip seam (ASP loses to simple-stitch on GT-SSIM). Implements the foreground-assembly architecture from the consolidated stitching research.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 0.1 | **[ASP] ✅ Foreground pose registration (A2/A4 prototype)** — `fg_register.py`: DIS dense flow → residual extraction → symmetric midpoint warp; integrated into Stage 11. Validated on test09. | Done | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.2 | **[ASP] A1 — SEA-RAFT flow engine** (anime-tuned via LinkTo-Anime) replacing DIS for flat-region robustness | ~3d | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.3 | **[ASP] A3 — full Sýkora ARAP + LSD** warp (line-art-preserving upgrade over similarity warp) | ~1w | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.4 | **[ASP] A5 — foreground-excluded temporal median** (background plate only; near-free correctness) | ~0.5d | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.5 | **[ASP] A6 — confidence-gated single-pose graph-cut fallback** (Eden 2006) | ~3d | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.6 | **[ASP] 🔄 Pose-consistency frame selector** — `frame_selection.py` two-pass architecture built; gradient proxy disabled (background confound). Needs foreground-only flow or pose model. | ~2d | [asp.md §0.2](roadmaps/asp.md#02-pose-consistency-aware-frame-selection-priority-1) |
| 0.7 | **[ASP] min_gap vector-magnitude + 25px threshold** (multi-axis scroll fix) | ~0.5d | [asp.md §0.5](roadmaps/asp.md) |
| 0.8 | **[ASP] Segment-guided flow (AnimeInterp SGM)** flat-region fallback | [Research] | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |

---

## Phase CG — Content Generation (Anime Image & Video)

Builds on the existing generation stack (`LoRATuner` on Illustrious-XL, `SD3Wrapper`, ComfyUI integration, data pipeline). Full detail in [content_generation.md](roadmaps/content_generation.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| CG.1 | **[Gen] WD14 + Florence-2 anime captioning** (booru tags + trigger token; shared with auto-tagger) | ~2d | [content_generation.md §1.1](roadmaps/content_generation.md) |
| CG.2 | **[Gen] Shared anime upscaler** — Real-ESRGAN anime_6B module reused by gen tabs + ASP | ~1d | [content_generation.md §1.6](roadmaps/content_generation.md) |
| CG.3 | **[Gen] ComfyUI control workflows** — curated txt2img / pose / reference / upscale JSONs | ~2d | [content_generation.md §1.4](roadmaps/content_generation.md) |
| CG.4 | **[Gen] Video→Character-LoRA guided flow** — PySceneDetect + dedup + caption + per-GPU TOML | ~1–2w | [content_generation.md §3](roadmaps/content_generation.md) |
| CG.5 | **[Gen] LyCORIS variants** (LoCon/LoHa/LoKr) in `LoRATuner` | ~3d | [content_generation.md §1.3](roadmaps/content_generation.md) |
| CG.6 | **[Gen] AnimateDiff via ComfyUI** — short anime clips/GIFs with character LoRA | ~1w | [content_generation.md §2.1](roadmaps/content_generation.md) |
| CG.7 | **[Gen] v-prediction / zero-terminal-SNR** support in `LoRATuner` + samplers | [Research] | [content_generation.md §1.2](roadmaps/content_generation.md) |
| CG.8 | **[Gen] ToonCrafter inbetweening** (shared with ASP `anim/anim_fill.py` ghost-fill) | [Research] | [content_generation.md §2.2](roadmaps/content_generation.md) |
| CG.9 | **[Gen] FLUX.1 [dev] secondary support** (FP8/GGUF for 16 GB) | [Research] | [content_generation.md §1.5](roadmaps/content_generation.md) |
| CG.10 | **[Gen] Wan2.1 / SVD foundation video** (3090 Ti, VRAM-gated) | [Long-term] | [content_generation.md §2.3](roadmaps/content_generation.md) |

---

## Phase 1 — Immediate Wins (Days, No New Dependencies)

These are one-line or near-trivial changes with immediate measurable benefit. Ship as a single batch.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 1.1 | **[ASP] ✅ Fallback path purity** — `scans_frames` snapshot taken before ML corrections at Stage 2; all fallback call-sites pass `scans_frames` | Done | [asp.md §1.9](roadmaps/asp.md#19-fallback-path-purity) |
| 1.2 | **[ASP] ✅ Dark scene gain clamp widening** — conditional `[0.80, 1.25]` when `ref_lum_scalar < 80`, `[0.88, 1.14]` otherwise | Done | [asp.md §1.4](roadmaps/asp.md#14-gain-clamp-widening-for-dark-scenes) |
| 1.3 | **[ASP] ✅ Static edge pre-bundle rejection** — `MIN_EXPECTED_STEP = 50` (defined in constants/anim.py) now correctly imported into pipeline.py; min-step guard at lines 278–298 is active | Done | [asp.md §1.2](roadmaps/asp.md#12-near-zero--zero-translation-edge-filter) |
| 1.4 | **[ASP] ✅ Content-aware minimal bounding crop** — `_crop_to_valid` uses `_largest_valid_rect` when valid_ratio < 0.80; SCANS fallback also uses `_largest_valid_rect` for diagonal panoramas | Done | [asp.md §1.7](roadmaps/asp.md#17-recdiffusion-border-rectangling) |
| 1.5 | **[ASP] ✅ Restrict seam search window** — `_seam_dp` gains `search_half` parameter; `de_seam` propagates it; callers pass `search_half=100` for small cross-axis displacement | Done | [asp.md §1.5](roadmaps/asp.md#15-stage-11-composite-performance) |
| 1.6 | **[Perf] WebDriver context manager** — `with webdriver.Chrome() as driver` on all crawlers (Option A) | ~2h | [performance.md §3.5](roadmaps/performance.md#35-webdriver-lifecycle-management) |
| 1.7 | **[Perf] Rust DynamicImage move semantics** — take ownership in `apply_ar_transform`, `fast_resize` (Option A) | ~2h | [performance.md §3.6](roadmaps/performance.md#36-dynamicimage-move-semantics-in-rust) |
| 1.8 | **[Perf] ✅ ML model unload after BiRefNet + LoFTR stages** — `unload()` added to all 7 model wrappers (BiRefNet, LoFTR, EfficientLoFTR, RoMa, ALIKED+LG, JamMa, BaSiC); pipeline calls `unload()` instead of `offload()` | Done | [performance.md §3.7](roadmaps/performance.md#37-python-ml-model-memory-lifecycle) |
| 1.9 | **[GUI] ✅ Session persistence** — `_save_last_dir` / `_load_last_dir` via `QSettings` in both gallery base classes | Done | [gui_ux.md §2.5](roadmaps/gui_ux.md#25-session-persistence) |
| 1.10 | **[GUI] ✅ OS dark mode follow** — `QGuiApplication.styleHints().colorScheme()` + `colorSchemeChanged` live signal in `MainWindow` | Done | [gui_ux.md §2.8](roadmaps/gui_ux.md#28-theme-support) |
| 1.11 | **[GUI] ✅ Ctrl+scroll thumbnail zoom** — `ctrl_wheel` signal on `MarqueeScrollArea`; auto-connected in `_on_layout_change`; reloads current page at new size | Done | [gui_ux.md §2.2](roadmaps/gui_ux.md#22-gallery-thumbnail-size-control) |
| 1.14 | **[GUI] ✅ Settings window — Gallery/Startup/Performance/Slideshow/Logging/Reset State sections** — implemented | Done | [gui_ux.md §2.9](roadmaps/gui_ux.md#29-settings-window-extensions) |
| 1.12 | **[Arch] `uv lock` + CI frozen install** (Option A) | ~1h | [architecture.md §5.7](roadmaps/architecture.md#57-dependency-audit-and-pinning) |
| 1.13 | **[Arch] ✅ Python `logging` module + rotating file handler** — `_setup_logging()` in `app.py` creates a 5 MB rotating file handler + console handler; `logger = logging.getLogger(__name__)` added to `pipeline.py`, `canvas.py`, `matching.py`, and all model wrappers; `print()` migrated to `logger.info/debug/warning/error` | Done | [architecture.md §5.4](roadmaps/architecture.md#54-logging-and-diagnostics) |

---

## Phase 2 — Core Quality-of-Service (Days to 1 Week, Minimal Dependencies)

Reliable improvements with a clear implementation path and direct impact on daily use.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 2.1 | **[ASP] TOML config file for pipeline constants** — `asp_config.toml` via `tomllib` (Option A) | ~1d | [asp.md §1.8](roadmaps/asp.md#18-asp-pipeline-configuration-file) |
| 2.2 | **[ASP] NumPy vectorised seam DP** — cumulative minimum over 2D cost array (Option A) | ~1d | [asp.md §1.5](roadmaps/asp.md#15-stage-11-composite-performance) |
| 2.3 | **[ASP] Near-duplicate frame deduplication** — SSIM threshold ~0.97 (Option B) | ~1d | [asp.md §1.2](roadmaps/asp.md#12-near-zero--zero-translation-edge-filter) |
| 2.4 | **[ASP] Increase foreground penalty in seam DP** — raise `sem_cost` multiplier (Option A) | ~0.5d | [asp.md §1.6](roadmaps/asp.md#16-ghosting-reduction-in-composite-zone) |
| 2.5 | **[ASP] Post-run RLHF quality gate** — `reward_model.predict(output)`, flag < 0.6 (Option A) | ~1d | [asp.md §1.10](roadmaps/asp.md#110-rlhf-loop-integration) |
| 2.6 | **[ASP] ✅ Stage-level progress signals** — `_ProgressPipeline` in `stitch_worker.py` emits `sig_stage(idx, total, label)` at the start of all 13 stages via `_emit()`; `StitchWorker.sig_stage = Signal(int, int, str)` | Done | [gui_ux.md §2.7](roadmaps/gui_ux.md#27-progress-and-cancellation) |
| 2.7 | **[GUI] ✅ Cancellable QThread `_should_stop` flag** — `WallpaperWorker` and `TrainingWorker` now set `self._should_stop = True` in `stop()` (previously only `is_running` was set); both initialise `_should_stop = False` for uniform tooling | Done | [gui_ux.md §2.7](roadmaps/gui_ux.md#27-progress-and-cancellation) |
| 2.8 | **[GUI] ✅ Arrow key gallery navigation** — `keyPressEvent` in `AbstractClassTwoGalleries`: Left/Right/Up/Down move `_focused_found_idx`, Enter emits `path_double_clicked` on focused widget | Done | [gui_ux.md §2.3](roadmaps/gui_ux.md#23-keyboard-navigation) |
| 2.9 | **[GUI] ✅ Shift+click / Ctrl+click multi-select** — `handle_marquee_selection()` in `AbstractClassTwoGalleries` checks `Qt.ShiftModifier` (additive) and `Qt.ControlModifier` (subtractive); fully wired | Done | [gui_ux.md §2.4](roadmaps/gui_ux.md#24-bulk-selection-and-operations) |
| 2.26 | **[GUI] ✅ F2 Rename (§2.26B)** — `_rename_focused_file()` in `AbstractClassTwoGalleries` (triggered by F2, renames the file focused via arrow-key navigation) and `_rename_selected_file()` in `AbstractClassSingleGallery` (renames last selected item). Both sanitise the new name, guard against conflicts, and update `found_files`, `master_found_files`, `selected_files`, and `path_to_label_map` / `path_to_card_widget`. | Done | [gui_ux.md §2.26](roadmaps/gui_ux.md#226-inline-rename) |
| 2.19 | **[GUI] ✅ Export selection as paths list (§2.19A)** — `_export_selection_as_paths()` on both gallery base classes; Ctrl+E saves `selected_files` (or all found files if none selected) to a user-chosen `.txt`/`.csv`. Uses `DontUseNativeDialog` to avoid JVM RTTI conflict. | Done | [gui_ux.md §2.19](roadmaps/gui_ux.md#219-gallery-export-and-contact-sheet) |
| 2.10 | **[GUI] ✅ Recent directories MRU helpers** — `_add_recent_dir` / `_get_recent_dirs` on both gallery base classes; backed by `QSettings`; ready for concrete tabs to wire up a dropdown | Done | [gui_ux.md §2.5](roadmaps/gui_ux.md#25-session-persistence) |
| 2.16 | **[GUI] ✅ Wire settings A/B/C/D/E/F/G** — All seven sub-items now wired: §A+C (thumbnail/page size, startup category), §B (LRU cache resize), §D (confirm_deletions checkbox load/save/reset), §E (WallpaperTab slideshow spinboxes/combo), §F (file_logging_enabled + log level), §G (restore_last_dir). | Done | [gui_ux.md §2.9](roadmaps/gui_ux.md#29-settings-window-extensions) |
| 2.11 | **[GUI] Toggle button + quality metrics overlay** in StitchTab (Options B + C) | ~1d | [gui_ux.md §2.6](roadmaps/gui_ux.md#26-stitch-tab-ux--beforeafter-comparison) |
| 2.12 | **[Perf] Rust two-pass streaming image merger** (Option A) | ~2d | [performance.md §3.1](roadmaps/performance.md#31-rust-streaming-image-merger) |
| 2.13 | **[Arch] ✅ Pipeline execution trace JSON** — `_ProgressPipeline.run()` writes a per-run JSON to `~/.image-toolkit/traces/stitch_YYYYMMDD_HHMMSS.json` containing `started_at`, `finished_at`, `elapsed_seconds`, `frames_input`, `edges_found`, `canvas_size`, `fallback_used`, `success`, `error`, `stage_timings` | Done | [architecture.md §5.4](roadmaps/architecture.md#54-logging-and-diagnostics) |
| 2.14 | **[Arch] ✅ pgvector HNSW index tuning** — `schema.sql` index updated to `m=32, ef_construction=128`; `search_images()` sets `hnsw.ef_search = 80` via `SET LOCAL` before each vector query | Done | [performance.md §3.4](roadmaps/performance.md#34-database-query-optimisation) |
| 2.15 | **[Arch] `pip-audit` + `cargo audit` in CI** (Options C + D) | ~0.5d | [architecture.md §5.7](roadmaps/architecture.md#57-dependency-audit-and-pinning) |

---

## Phase 3 — Feature Enrichment (1–2 Weeks per Item)

New capabilities that expand the app's core value proposition.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 3.1 | **[ASP] GNC robust loss in bundle adjustment** — scipy `loss='cauchy'` swap (Option C) | ~2d | [asp.md §1.1](roadmaps/asp.md#11-bundle-adjustment-hardening) |
| 3.2 | **[ASP] OpenCV PANORAMA fallback for scale/rotation sequences** (Option B) | ~1d | [asp.md §1.3](roadmaps/asp.md#13-scale-and-rotation-handling) |
| 3.3 | **[ASP] Poisson blending at seam zone** — `cv2.seamlessClone` in final-output mode (Option C) | ~1d | [asp.md §1.6](roadmaps/asp.md#16-ghosting-reduction-in-composite-zone) |
| 3.4 | **[ASP] SRStitcher inpainting for border rectangling** — when `sr_mode=True` (Option A) | ~0.5d | [asp.md §1.7](roadmaps/asp.md#17-recdiffusion-border-rectangling) |
| 3.5 | **[Feat] CLI batch stitching** — `python main.py stitch --batch-dir` with `--resume` (Options C + E) | ~2d | [new_features.md §4.1](roadmaps/new_features.md#41-batch-stitching) |
| 3.6 | **[Feat] WD-1.4 auto-tagger via ONNX** with confidence thresholds (Options A + E) | ~3d | [new_features.md §4.4](roadmaps/new_features.md#44-auto-tagger-integration) |
| 3.7 | **[Feat] Safetensors metadata viewer** — "Inspect Model" button in LoRA/generate tabs (Option A) | ~0.5d | [new_features.md §4.9](roadmaps/new_features.md#49-safetensors-metadata-viewer) |
| 3.8 | **[Feat] Slideshow configuration** — timing, order, tag-based filter (Option A) | ~2d | [new_features.md §4.7](roadmaps/new_features.md#47-slideshow-improvements) |
| 3.9 | **[GUI] Increase page size to 150–200 + scroll position indicator** (Option C) | ~0.5d | [gui_ux.md §2.1](roadmaps/gui_ux.md#21-virtual-scroll-gallery) |
| 3.10 | **[GUI] QSS dark/light mode toggle** with override option (Option A) | ~2d | [gui_ux.md §2.8](roadmaps/gui_ux.md#28-theme-support) |
| 3.11 | **[Perf] PyTorch GPU temporal median** — `torch.median` on CUDA with NumPy fallback (Option A + B) | ~1d | [performance.md §3.2](roadmaps/performance.md#32-asp-render-stage-gpu-acceleration) |
| 3.12 | **[Perf] Dynamic BiRefNet batching** — `torch.cuda.mem_get_info()` based batch size (Option C) | ~1d | [performance.md §3.3](roadmaps/performance.md#33-birefnet-inference-batching) |
| 3.13 | **[Arch] ASP unit tests for bundle_adjust, compositing, matching stages** (Option A) | ~3d | [architecture.md §5.1](roadmaps/architecture.md#51-asp-pipeline-unit-test-coverage) |
| 3.14 | **[Arch] GitHub Actions benchmark regression CI** — fast Python benchmarks on push to main (Option A) | ~1d | [architecture.md §5.2](roadmaps/architecture.md#52-benchmark-regression-ci) |

---

## Phase 4 — Platform Hardening (2–4 Weeks, Some Architecture Change)

Items that improve reliability, architecture cleanliness, and long-term maintainability.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 4.1 | **[Arch] Vault Manager → Rust AES-256-GCM via PyO3** — eliminate JVM dependency (Option C) | ~1w | [architecture.md §5.5](roadmaps/architecture.md#55-vault-manager-modernisation) |
| 4.2 | **[Arch] Abstract Matcher base class** — formal interface for all matcher tiers (Option B) | ~1w | [architecture.md §5.3](roadmaps/architecture.md#53-plugin-system-for-matchers-and-compositors) |
| 4.3 | **[Arch] Weekly scheduled ASP + Rust benchmark CI** (Option B) | ~1d | [architecture.md §5.2](roadmaps/architecture.md#52-benchmark-regression-ci) |
| 4.4 | **[Arch] ✅ LogWindow upgraded (§2.17D)** — `QPlainTextEdit`, colour-coded levels, timestamps, Copy All / Save / Clear / Follow. Full collapsible global panel (Option C) remains. | Partial | [architecture.md §5.4](roadmaps/architecture.md#54-logging-and-diagnostics) |
| 4.5 | **[Feat] OpenAPI schema for existing REST endpoints** (Option A) | ~1d | [new_features.md §4.10](roadmaps/new_features.md#410-rest-api-layer-for-remote-control) |
| 4.6 | **[Feat] Cross-directory phash deduplication index** in PostgreSQL (Option A) | ~2d | [new_features.md §4.6](roadmaps/new_features.md#46-image-deduplication-across-directories) |
| 4.7 | **[Feat] KDE per-monitor wallpaper via D-Bus** (Option A) | ~2d | [new_features.md §4.5](roadmaps/new_features.md#45-multi-monitor-wallpaper-support) |
| 4.8 | **[Perf] psycopg3 async connection pool** for database tab (Option A) | ~2d | [performance.md §3.4](roadmaps/performance.md#34-database-query-optimisation) |
| 4.9 | **[GUI] QListView + QAbstractItemModel virtual scrolling** — prototype against `AbstractClassTwoGalleries` (Option A) | ~1w | [gui_ux.md §2.1](roadmaps/gui_ux.md#21-virtual-scroll-gallery) |
| 4.10 | **[GUI] Global hotkey table in settings** — JSON-backed `QShortcut` (Option B) | ~1w | [gui_ux.md §2.3](roadmaps/gui_ux.md#23-keyboard-navigation) |
| 4.11 | **[GUI] Thumbnail slider + per-tab persistent size** (Options A + D) | ~1d | [gui_ux.md §2.2](roadmaps/gui_ux.md#22-gallery-thumbnail-size-control) |

---

## Phase 5 — Advanced Features (1–3 Weeks per Item, Research Required)

Higher-complexity features that depend on Phase 3–4 infrastructure or require experimentation.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 5.1 | **[Feat] OpenCLIP semantic search** — dual embedding column in PostgreSQL (Options A + C) | ~2w | [new_features.md §4.3](roadmaps/new_features.md#43-clip-based-semantic-image-search) |
| 5.2 | **[Feat] GUI batch stitching** — directory-level batch mode with progress list (Option A) | ~1w | [new_features.md §4.1](roadmaps/new_features.md#41-batch-stitching) |
| 5.3 | **[Feat] FFmpeg scrolling video export** (Option B) | ~1w | [new_features.md §4.2](roadmaps/new_features.md#42-export-stitched-panorama-to-scrolling-video) |
| 5.4 | **[Feat] ComfyUI drag-and-drop gallery integration** (Option C) | ~1w | [new_features.md §4.8](roadmaps/new_features.md#48-comfyui-workflow-integration-for-post-processing) |
| 5.5 | **[Feat] WD tagging review queue** — PostgreSQL-backed human-in-the-loop (Option C) | ~1w | [new_features.md §4.4](roadmaps/new_features.md#44-auto-tagger-integration) |
| 5.6 | **[Feat] REST API trigger for desktop operations + WebSocket status** (Options B + C) | ~2w | [new_features.md §4.10](roadmaps/new_features.md#410-rest-api-layer-for-remote-control) |
| 5.7 | **[ASP] RLHF Bayesian parameter search** — optuna over gain, feather, seam cost (Option B) | ~1w | [asp.md §1.10](roadmaps/asp.md#110-rlhf-loop-integration) |
| 5.8 | **[ASP] Similarity transform (scale+rotation+translation) matcher** — `estimateAffinePartial2D` (Option E) | ~1w | [asp.md §1.3](roadmaps/asp.md#13-scale-and-rotation-handling) |
| 5.9 | **[ASP] Seam DP cache for RLHF iteration** — keyed by `(frame_ids, seam_cost_config)` (Option D) | ~1d | [asp.md §1.5](roadmaps/asp.md#15-stage-11-composite-performance) |
| 5.10 | **[Arch] Compositor registry** — same pattern as Matcher (Option E) | ~1w | [architecture.md §5.3](roadmaps/architecture.md#53-plugin-system-for-matchers-and-compositors) |
| 5.11 | **[Perf] Rust memory-mapped output buffer** — `memmap2` for >10K px panoramas (Option C) | ~2d | [performance.md §3.1](roadmaps/performance.md#31-rust-streaming-image-merger) |

---

## Phase 6 — Long-term Research (Months, Exploratory)

Aspirational improvements requiring significant experimentation, external data, or architectural investment. No fixed timeline.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 6.1 | **[ASP] Online DRL agent for ECC/registration** — wire `rlhf_trainer.py` into Stage 8 | [Long-term] | [asp.md §1.10](roadmaps/asp.md#110-rlhf-loop-integration) |
| 6.2 | **[ASP] RANSAC/MAGSAC++ pre-filter for >40% outlier datasets** | [Research] | [asp.md §1.1](roadmaps/asp.md#11-bundle-adjustment-hardening) |
| 6.3 | **[ASP] ToonCrafter fill for overlap ghost reduction** — final-quality mode | [Research] | [asp.md §1.6](roadmaps/asp.md#16-ghosting-reduction-in-composite-zone) |
| 6.4 | **[ASP] Background histogram matching via CLAHE** for complex dark scenes | [Research] | [asp.md §1.4](roadmaps/asp.md#14-gain-clamp-widening-for-dark-scenes) |
| 6.5 | **[Feat] AnimeCLIP domain-specific CLIP fine-tune** — swap into §5.1 once validated | [Research] | [new_features.md §4.3](roadmaps/new_features.md#43-clip-based-semantic-image-search) |
| 6.6 | **[Feat] File system watcher auto-stitch** — `watchdog`/`inotify` triggered batch | [Research] | [new_features.md §4.1](roadmaps/new_features.md#41-batch-stitching) |
| 6.7 | **[Feat] Mobile remote wallpaper + push notifications** — depends on §5.6 REST API | [Exploratory] | [new_features.md §4.5](roadmaps/new_features.md#45-multi-monitor-wallpaper-support) |
| 6.8 | **[Arch] Hypothesis property-based tests for bundle_adjust and compositing** | [Research] | [architecture.md §5.1](roadmaps/architecture.md#51-asp-pipeline-unit-test-coverage) |
| 6.9 | **[Perf] CUDA seam DP via PyTorch scatter/gather** — GPU seam computation | [Research] | [asp.md §1.5](roadmaps/asp.md#15-stage-11-composite-performance) |
| 6.10 | **[Arch] OS keyring integration** — replace vault files with Freedesktop Secret Service | [Long-term] | [architecture.md §5.5](roadmaps/architecture.md#55-vault-manager-modernisation) |

---

## Dependency Graph Summary

```
Phase 1 (Quick Wins)
  └─► Phase 2 (Core QoS)
        ├─► Phase 3 (Feature Enrichment)
        │     ├─ 3.13 Unit tests unblocks 3.14 CI gate
        │     └─ 3.6 Auto-tagger unblocks 5.5 Review queue
        ├─► Phase 4 (Platform Hardening)
        │     ├─ 4.1 Vault → Rust eliminates JVM (removes libstdc++ conflict risk)
        │     ├─ 4.2 Matcher interface unblocks 5.10 Compositor registry
        │     └─ 4.9 QListView unblocks full bulk-select UX
        └─► Phase 5 (Advanced Features)
              ├─ 5.1 CLIP search requires §4.8 psycopg3 pool + §2.14 HNSW tuning
              ├─ 5.6 REST API enables §6.7 mobile features
              └─ 5.7 RLHF param search requires §2.5 quality gate (Phase 2)
```
