# Image Toolkit — Master Roadmap

*Last updated: 2026-06-18. Architecture roadmap updated: §5.5 (Gradual Static Type Safety), §5.8–§5.13 (model wrapper ABC, worker base class, gallery consolidation, circular imports, docs/diagrams, decorators), §5.14–§5.16 (settings facade, fault isolation, ML wrapper contract tests) added. Phase 4 updated to remove stale §4.1 Vault Manager link. New Phase Arch added for code-quality items. Session 131: §1.66 NCC structural coherence gate (Stage 11.4), §1.67 pre-BA frame canvas spread validation, §1.8C/D dump_asp_config with typed TOML schema comments (827 tests). Session 130: §1.60 fg pose-gap pre-escalation, §1.62 canvas aspect-ratio gate, §1.63 sort-frames-by-index, §1.64 exact-duplicate dHash guard, §1.65 fg seam erosion buffer, §1.10D MC-dropout uncertainty, §3.17 seam NCC coherence + §3.5A composite quality score in bench (822 tests). Session 78: §2.3 Canvas Layout Inspector read-only viewer (422 tests passing). Session 77: §2.2 Edge Graph Inspector read-only viewer (413 tests passing). Session 76: GNC-TLS BA (§1.32, 412 tests passing). GUI: §2.23A accessibility, §2.4B+C range-select + context menu, §2.25A shortcut overlay, §2.20A splitter persistence, §2.17D log window, §2.16C Ctrl+T tab search, §2.12A+B+C system tray, §2.11A+B+D preview enhancements, §2.21A+D dir history + MRU, §2.26B inline rename, §2.10C QStatusBar, §2.14A filename labels, §2.18 sort + search ops, §2.19 trash, §3.9 item range, §4.11 thumbnail slider, §3.15–3.17 shortcuts/QSS/geometry all shipped. §2.30 accent colour picker + font scale + UI density shipped. New roadmap sections added: §2.29 (configurable keyboard shortcuts), §2.30–2.32 (appearance customisation), §4.12–4.13 (appearance profiles + macros). Session 9: ToonCrafter seam synthesis wired (§3.6/ML.4, `ASP_TOONCRAFTER_SEAM=1`). Session 8: DINOv2 submodular frame selection (§3.3/ML.2), LSD collinearity in ARAP (§0.1/A3), Aligned-SSIM metric. Session 7: Stage 12.5 scroll-axis content trim (§2.6). Session 6: hold detection (§1.11/ML.1), GNC BA, SLIC SGM proxy (§3.1/ML.5). 107 tests passing. Session 5: alignment stability gate (+0.074 test08, +0.049 test25), fg pixel L1 pose metric (+0.010 test27 with pose-on), 90 unit tests. Session 4: ARAP Push (Sýkora 2009), 96-test run. Research: `reports/Image_Stitching_Research.md`, `reports/Anime Stitch Pipeline ML Research.md`.*

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
- [Anime Stitch Pipeline ML Research](../reports/Anime%20Stitch%20Pipeline%20ML%20Research.md) — ML-driven solutions for aperture problem (AnimeInterp SGM), frame selection (DINOv2 submodular), camera estimation (CamFlow), generative composition (ToonCrafter, RDIStitcher), and reference-free metrics (SIQE, SI-FID, MLLM SIQS). Full roadmap entries in [asp.md §3.0](roadmaps/asp.md#30-ml-driven-pipeline-modernisation-research-phase--from-ml-research-report).

Phases are ordered by impact-to-effort ratio and dependency order. Items within a phase are independent and can be parallelised.

---

## Phase 0 — ASP Foreground Assembly (Priority 0, The Core Quality Fix)

The single highest-impact track: the pipeline cannot register the deforming foreground, so characters tear at every strip seam (ASP loses to simple-stitch on GT-SSIM). Implements the foreground-assembly architecture from the consolidated stitching research.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 0.1 | **[ASP] ✅ Foreground pose registration (A2/A4 prototype)** — `fg_register.py`: DIS dense flow → residual extraction → symmetric midpoint warp; integrated into Stage 11. Validated on test09. | Done | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.2 | **[ASP] A1 — SEA-RAFT flow engine** (anime-tuned via LinkTo-Anime) replacing DIS for flat-region robustness | ~3d | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.3 | **[ASP] ✅ A3 — full Sýkora ARAP + LSD** — ARAP Push→Regularise shipped (S4); LSD collinearity term shipped (S8): boundary-cell projection onto detected line directions, magnitude guard ≥50% | Done | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.4 | **[ASP] A5 — foreground-excluded temporal median** (background plate only; near-free correctness) | ~0.5d | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.5 | **[ASP] A6 — confidence-gated single-pose graph-cut fallback** (Eden 2006) | ~3d | [asp.md §0.1](roadmaps/asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.6 | **[ASP] 🔄 Pose-consistency frame selector** — two-pass architecture built; fg pixel L1 + DINOv2 cosine distance (S8) as pose metrics; activated via `ASP_POSE_WINDOW_PX=80`; GT-coupling still limits default-on use | ~2d | [asp.md §0.2](roadmaps/asp.md#02-pose-consistency-aware-frame-selection-priority-1) |
| 0.7 | **[ASP] min_gap vector-magnitude + 25px threshold** (multi-axis scroll fix) | ~0.5d | [asp.md §0.5](roadmaps/asp.md) |
| 0.8 | **[ASP] Segment-guided flow (AnimeInterp SGM)** flat-region fallback — see ML.5/ML.8 for full roadmap | [Research] | [asp.md §3.1](roadmaps/asp.md#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact) |

---

## Phase ML — ASP ML-Driven Modernisation (Research Phase)

*Source: `reports/Anime Stitch Pipeline ML Research.md` (2026-06-04). Full detail and implementation options in [asp.md §3.0](roadmaps/asp.md#30-ml-driven-pipeline-modernisation-research-phase--from-ml-research-report).*

These items address the three quantified ceilings that classical CV methods have exhausted: (1) aperture problem on flat cel regions, (2) background-entangled frame selection, (3) reference-free quality assessment. Each maps to a specific pipeline stage and existing file. All are tagged [Research] — none require new training from scratch; all use pretrained weights or classical algorithms with offline fitting.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| ML.1 | **[ASP] ✅ FD-Means animation hold detection** — `_detect_hold_blocks()` shipped (S6); `ASP_HOLD_THRESHOLD=0.025`; perceptual MAD hold clustering; hold IDs used in Pass 2 penalty | Done | [asp.md §3.4](roadmaps/asp.md#34-fd-means-animation-hold-detection-quick-win--preprocessing) |
| ML.2 | **[ASP] ✅ DINOv2 submodular frame selection** — `_compute_dinov2_features()` shipped (S8); `dinov2_vits14` via `torch.hub`; cosine distance replaces fg pixel L1 in Pass 2; activated via `ASP_POSE_WINDOW_PX=80` | Done | [asp.md §3.3](roadmaps/asp.md#33-dinov2--siglip-submodular-frame-selection-priority-high--directly-addresses-gt-coupling) |
| ML.3 | **[ASP] SIQE ghosting metric** — steerable pyramid + GMM ghosting detector (94.36% human-opinion precision); replaces `_ghosting_score()`; adds spatial ghost localisation per seam | ~3d | [asp.md §3.8](roadmaps/asp.md#38-siqe-no-reference-ghosting-detection-quick-win--metric-upgrade) |
| ML.4 | **[ASP] ✅ ToonCrafter seam synthesis wiring** — shipped (S9); worst single-pose seam triggers `_generate_canonical_cel()` from `anim_fill.py`; canonical cel replaces hard partition for fg pixels; `ASP_TOONCRAFTER_SEAM=1` | Done | [asp.md §3.6](roadmaps/asp.md#36-tooncrafter-seam-synthesis--wiring-the-generative-fallback-priority-medium) |
| ML.5 | **[ASP] ✅ SLIC segment-level centroid tracking** — `_slic_sgm_proxy()` shipped (S6); ARAP Push fallback for flat regions; `ASP_SGM_PROXY=1` | Done | [asp.md §3.1](roadmaps/asp.md#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact) |
| ML.6 | **[ASP] Deep homography with foreground masking** — CVPR 2020 joint dynamics-mask + homography network; replaces phase correlation for camera displacement in `frame_selection.py`; pretrained weights available | ~3d | [asp.md §3.5](roadmaps/asp.md#35-camflow-hybrid-motion-basis-for-camera-displacement-research) |
| ML.7 | **[ASP] SI-FID as benchmark metric** — reference-free stitching quality (Fréchet distance in artifact-trained latent space); supplements GT-SSIM for the 41 GT-less tests; enables GT-coupling-free RLHF optimization | ~3d | [asp.md §3.9](roadmaps/asp.md#39-si-fid-stitched-image-fréchet-distance-for-reference-free-evaluation-research) |
| ML.8 | **[ASP] AnimeInterp SGM as ARAP Push replacement** — segment-guided matching via VGG-19 pooled per-segment features; completely bypasses aperture problem; ~40ms/seam GPU; `ASP_FLOW_ENGINE=animeinterp` flag | ~1w | [asp.md §3.1](roadmaps/asp.md#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact) |
| ML.9 | **[ASP] CamFlow Hybrid Motion Basis** — ICCV 2025 model for sub-pixel-accurate 2D camera estimation even with full-frame foreground; replaces phase correlation; physical+stochastic motion bases | ~1w | [asp.md §3.5](roadmaps/asp.md#35-camflow-hybrid-motion-basis-for-camera-displacement-research) |
| ML.10 | **[ASP] MLLM semantic quality gate** — Qwen2-VL-7B via ollama; detects severed torsos, duplicated limbs, mismatched body orientation; `ASP_MLLM_QA=1`; benchmark-only initially | ~2d | [asp.md §3.10](roadmaps/asp.md#310-mllm-semantic-quality-scoring-research--autonomous-quality-assurance) |
| ML.11 | **[ASP] UDIS++ diffusion-based seam composition** — replaces Laplacian blend in Stage 11 with unsupervised spatial warp + diffusion hallucination of seam zone; open-source weights; needs anime fine-tune | ~2w | [asp.md §3.7](roadmaps/asp.md#37-udis--udtatis-diffusion-based-seam-composition-long-term--end-to-end-replacement) |
| ML.12 | **[ASP] ConvGRU recurrent flow refinement** — AnimeInterp's confidence-guided iterative residual flow; fills null regions after SGM; trained on ATD-12K with animation-specific exaggeration | ~1w | [asp.md §3.2](roadmaps/asp.md#32-convgru-recurrent-flow-refinement-for-kinematic-accuracy-research) |

**Dependency order:** ML.1 → ML.2 (holds detected first, then selection uses DINOv2). ML.3 + ML.7 are independent evaluation upgrades. ML.4 depends on existing `anim_fill.py` (already present). ML.5 → ML.8 (SLIC is the cheap approximation; AnimeInterp is the full solution). ML.6 → ML.9 (deep homography first, CamFlow second as quality upgrade). ML.10 independent. ML.11 + ML.12 depend on ML.8 being validated.

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
| 2.18 | **[GUI] ✅ Gallery sort toolbar + search operators** — Sort QComboBox (Name/Date/Size/Ext) + ↑↓ button in pagination bar; `_apply_sort()` / `_sort_key_fn()` in both gallery base classes; `_common_filter_string_list` upgraded to support `-exclude`, `"phrase"`, `a\|b` OR; placeholder text updated to hint syntax; sort applied on directory load too | Done | [gui_ux.md §2.13](roadmaps/gui_ux.md#213-gallery-filtering-and-sort-controls) |
| 2.19 | **[GUI] ✅ Move to Trash instead of permanent delete** — `send2trash` replaces `os.remove` in DeleteTab, WallpaperTab, SearchTab; confirmation dialogs updated; `send2trash>=1.8.3` added to `pyproject.toml` | Done | [gui_ux.md §2.15](roadmaps/gui_ux.md#215-undoredo-for-destructive-operations) |
| 2.17 | **[GUI] ✅ Accent colour picker + UI density + font scale** — `QColorDialog` swatches in settings "Display and Media" tab; `compute_accent_vars()` derives hover/pressed from base; `load_qss_with_overrides()` substitutes at runtime; density appends Compact/Spacious QSS; font scale via `QApplication.setFont`; all persisted in vault `preferences` | Done | [gui_ux.md §2.30](roadmaps/gui_ux.md#230-accent-color-and-ui-density-customization) |
| 2.12 | **[Perf] Rust two-pass streaming image merger** (Option A) | ~2d | [performance.md §3.1](roadmaps/performance.md#31-rust-streaming-image-merger) |
| 2.13 | **[Arch] ✅ Pipeline execution trace JSON** — `_ProgressPipeline.run()` writes a per-run JSON to `~/.image-toolkit/traces/stitch_YYYYMMDD_HHMMSS.json` containing `started_at`, `finished_at`, `elapsed_seconds`, `frames_input`, `edges_found`, `canvas_size`, `fallback_used`, `success`, `error`, `stage_timings` | Done | [architecture.md §5.4](roadmaps/architecture.md#54-logging-and-diagnostics) |
| 2.14 | **[Arch] ✅ pgvector HNSW index tuning** — `schema.sql` index updated to `m=32, ef_construction=128`; `search_images()` sets `hnsw.ef_search = 80` via `SET LOCAL` before each vector query | Done | [performance.md §3.4](roadmaps/performance.md#34-database-query-optimisation) |
| 2.15 | **[Arch] `pip-audit` + `cargo audit` in CI** (Options C + D) | ~0.5d | [architecture.md §5.7](roadmaps/architecture.md#57-dependency-audit-and-pinning) |

---

## Phase 3 — Feature Enrichment (1–2 Weeks per Item)

New capabilities that expand the app's core value proposition.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 3.1 | **[ASP] ✅ GNC robust loss in bundle adjustment** — GNC-TLS outer continuation loop shipped S76 (§1.32); Cauchy one-shot (§1.1C) available via `ASP_GNC_OUTER=0` | Done | [asp.md §1.32](roadmaps/asp.md#132-gnc-tls-bundle-adjustment-quick-win--shipped-s76) |
| 3.2 | **[ASP] OpenCV PANORAMA fallback for scale/rotation sequences** (Option B) | ~1d | [asp.md §1.3](roadmaps/asp.md#13-scale-and-rotation-handling) |
| 3.3 | **[ASP] Poisson blending at seam zone** — `cv2.seamlessClone` in final-output mode (Option C) | ~1d | [asp.md §1.6](roadmaps/asp.md#16-ghosting-reduction-in-composite-zone) |
| 3.4 | **[ASP] SRStitcher inpainting for border rectangling** — when `sr_mode=True` (Option A) | ~0.5d | [asp.md §1.7](roadmaps/asp.md#17-recdiffusion-border-rectangling) |
| 3.5 | **[Feat] CLI batch stitching** — `python main.py stitch --batch-dir` with `--resume` (Options C + E) | ~2d | [new_features.md §4.1](roadmaps/new_features.md#41-batch-stitching) |
| 3.6 | **[Feat] WD-1.4 auto-tagger via ONNX** with confidence thresholds (Options A + E) | ~3d | [new_features.md §4.4](roadmaps/new_features.md#44-auto-tagger-integration) |
| 3.7 | **[Feat] Safetensors metadata viewer** — "Inspect Model" button in LoRA/generate tabs (Option A) | ~0.5d | [new_features.md §4.9](roadmaps/new_features.md#49-safetensors-metadata-viewer) |
| 3.8 | **[Feat] Slideshow configuration** — timing, order, tag-based filter (Option A) | ~2d | [new_features.md §4.7](roadmaps/new_features.md#47-slideshow-improvements) |
| 3.9 | **[GUI] ✅ Increase page size + item range indicator** — default page size 100→150; "150" added to page-size combo; item range label "Items A–B of C" in every pagination bar (§3.9); updated in `_update_pagination_ui` for both gallery base classes | Done | [gui_ux.md §2.1](roadmaps/gui_ux.md#21-virtual-scroll-gallery) |
| 3.10 | **[GUI] QSS dark/light mode toggle** with override option (Option A) | ~2d | [gui_ux.md §2.8](roadmaps/gui_ux.md#28-theme-support) |
| 3.15 | **[GUI] ✅ Configurable keyboard shortcuts** — `ShortcutRegistry` (21 actions) + `QKeySequenceEdit` table in Settings "⌨️ Shortcuts" tab; JSON persistence to `~/.image-toolkit/keybindings.json`; conflict detection; `keyPressEvent` in both gallery base classes and `ImagePreviewWindow` uses `reg.matches()`; PySide6 6.10 flag-type fix in `matches()` | Done | [gui_ux.md §2.29](roadmaps/gui_ux.md#229-configurable-keyboard-shortcuts) |
| 3.16 | **[GUI] ✅ QSS user override file** — `load_user_qss_override()` appends `~/.image-toolkit/user_theme.qss` as the final step in `set_application_theme()`; returns `""` silently if the file is absent | Done | [gui_ux.md §2.31](roadmaps/gui_ux.md#231-custom-qss-user-theme-override) |
| 3.17 | **[GUI] ✅ Auto-save/restore window geometry** — `QSettings("ImageToolkit","ImageToolkit")` saves `mainwindow/geometry` in `closeEvent()`, restored in `__init__` before `showMaximized()` | Done | [gui_ux.md §2.32](roadmaps/gui_ux.md#232-window-layout-and-state-profiles) |
| 3.11 | **[Perf] PyTorch GPU temporal median** — `torch.median` on CUDA with NumPy fallback (Option A + B) | ~1d | [performance.md §3.2](roadmaps/performance.md#32-asp-render-stage-gpu-acceleration) |
| 3.12 | **[Perf] Dynamic BiRefNet batching** — `torch.cuda.mem_get_info()` based batch size (Option C) | ~1d | [performance.md §3.3](roadmaps/performance.md#33-birefnet-inference-batching) |
| 3.13 | **[Arch] ASP unit tests for bundle_adjust, compositing, matching stages** (Option A) | ~3d | [architecture.md §5.1](roadmaps/architecture.md#51-asp-pipeline-unit-test-coverage) |
| 3.14 | **[Arch] GitHub Actions benchmark regression CI** — fast Python benchmarks on push to main (Option A) | ~1d | [architecture.md §5.2](roadmaps/architecture.md#52-benchmark-regression-ci) |

---

## Phase 4 — Platform Hardening (2–4 Weeks, Some Architecture Change)

Items that improve reliability, architecture cleanliness, and long-term maintainability.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 4.1 | **[Arch] Abstract Matcher base class** — formal interface for all matcher tiers (Option B) | ~1w | [architecture.md §5.3](roadmaps/architecture.md#53-plugin-system-for-matchers-and-compositors) |
| 4.2 | **[Arch] ✅ `ModelWrapper` ABC + `@lazy_load` decorator + `ModelRegistry`** — `backend/src/models/base.py`; all 7 wrappers migrated; `loaded` property + `is_available()` classmethod; `@lazy_load` on public entry-points; `ModelRegistry.unload_all()` | Done | [architecture.md §5.8](roadmaps/architecture.md#58-model-wrapper-abstraction-layer-backendsrcmodels) |
| 4.3 | **[Arch] Weekly scheduled ASP + Rust benchmark CI** (Option B) | ~1d | [architecture.md §5.2](roadmaps/architecture.md#52-benchmark-regression-ci) |
| 4.4 | **[Arch] ✅ LogWindow upgraded (§2.17D)** — `QPlainTextEdit`, colour-coded levels, timestamps, Copy All / Save / Clear / Follow. Full collapsible global panel (Option C) remains. | Partial | [architecture.md §5.4](roadmaps/architecture.md#54-logging-and-diagnostics) |
| 4.5 | **[Feat] OpenAPI schema for existing REST endpoints** (Option A) | ~1d | [new_features.md §4.10](roadmaps/new_features.md#410-rest-api-layer-for-remote-control) |
| 4.6 | **[Feat] Cross-directory phash deduplication index** in PostgreSQL (Option A) | ~2d | [new_features.md §4.6](roadmaps/new_features.md#46-image-deduplication-across-directories) |
| 4.7 | **[Feat] KDE per-monitor wallpaper via D-Bus** (Option A) | ~2d | [new_features.md §4.5](roadmaps/new_features.md#45-multi-monitor-wallpaper-support) |
| 4.8 | **[Perf] psycopg3 async connection pool** for database tab (Option A) | ~2d | [performance.md §3.4](roadmaps/performance.md#34-database-query-optimisation) |
| 4.9 | **[GUI] QListView + QAbstractItemModel virtual scrolling** — prototype against `AbstractClassTwoGalleries` (Option A) | ~1w | [gui_ux.md §2.1](roadmaps/gui_ux.md#21-virtual-scroll-gallery) |
| 4.10 | **[GUI] Global hotkey table in settings** — JSON-backed `QShortcut` (Option B) | ~1w | [gui_ux.md §2.3](roadmaps/gui_ux.md#23-keyboard-navigation) |
| 4.12 | **[GUI] Named layout profiles** — extend "System Preference Profiles" to bundle geometry + splitter state + appearance settings (§2.32B) | ~2d | [gui_ux.md §2.32](roadmaps/gui_ux.md#232-window-layout-and-state-profiles) |
| 4.13 | **[Feat] Appearance profiles** — extend vault profiles to include accent colour, font scale, density (Option A) | ~1d | [new_features.md §4.12](roadmaps/new_features.md#412-appearance-profiles) |
| 4.11 | **[GUI] ✅ Thumbnail slider + per-tab persistent size** — `QSlider` (64–512 px, step 16) in every pagination bar; `_save_thumbnail_size()` on slider release and after Ctrl+scroll; `_load_thumbnail_size()` at `__init__` time keyed by `{ClassName}/thumbnail_size`; `_sync_thumb_slider()` keeps all sliders in sync; both gallery base classes updated | Done | [gui_ux.md §2.2](roadmaps/gui_ux.md#22-gallery-thumbnail-size-control) |

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

## Phase Arch — Code Quality & Developer Experience (Days to 2 Weeks, No New Features)

Targeted refactors that reduce maintenance burden, improve onboarding, and prevent regressions. Items are ordered by ascending effort; all are independent and can be parallelised. Full detail in [architecture.md](roadmaps/architecture.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| A.1 | **[Arch] ✅ Pyright `basic` mode** — `typeCheckingMode = "basic"` in `pyproject.toml` | Done | [architecture.md §5.5B](roadmaps/architecture.md#55-gradual-static-type-safety-migration) |
| A.2 | **[Arch] ✅ Eliminate silent `print()` errors** — `conversion_worker.py` (3×), `duplicate_scan_worker.py` (2×), `gan_wrapper.py` (1×), `lo_ra_tuner.py` (1×); all replaced with `logger.warning/error` | Done | [architecture.md §5.15C](roadmaps/architecture.md#515-fault-isolation--error-boundary-protocol) |
| A.3 | **[Arch] ✅ Remove `# --- Relocated Nested Imports ---` comment blocks** — single grep-and-edit pass across all model wrappers; consolidate into standard PEP 8 import order | Done | [architecture.md §5.8D](roadmaps/architecture.md#58-model-wrapper-abstraction-layer-backendsrcmodels) |
| A.4 | **[Arch] ✅ `__all__` hygiene pass** — 15 `__init__.py` files updated: `backend/src/{models,web,core,pipeline,utils,controller,__init__}` and `gui/src/{utils,styles,helpers/{image,video,web,core},tabs,tabs/core/common}`; empty files get `[]`; populated files get explicit `__all__` lists | Done | [architecture.md §5.11D](roadmaps/architecture.md#511-circular-import-prevention--module-boundary-documentation) |
| A.5 | **[Arch] ✅ QSettings key validation at startup** — `SETTINGS_SCHEMA` dict + `SETTINGS_PREFIX_TYPES` + `_validate_settings()` in `app.py`; called after `QApplication()` creation; logs warnings for type-mismatched keys and clears them; unknown keys logged at DEBUG | Done | [architecture.md §5.14D](roadmaps/architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.6 | **[Arch] ✅ `@log_call` timing decorator** — `backend/src/utils/decorators.py`; logs entry/exit + elapsed ms at DEBUG; compatible with §5.4B trace JSON; exported via `backend/src/utils/__init__.py` | Done | [architecture.md §5.13C](roadmaps/architecture.md#513-decorator-library-for-cross-cutting-concerns-backendsrcutilsdecoratorspy) |
| A.7 | **[Arch] ✅ Metaclass docstring + `_load_thumbnail_size` extraction** — extended docstring in `meta_abstract_class_gallery.py` explaining Qt metaclass fusion + injection rationale; `save_thumbnail_size`/`load_thumbnail_size` extracted to `gui/src/utils/thumbnail_size.py`; both gallery base classes delegate to shared functions | Done | [architecture.md §5.10C](roadmaps/architecture.md#510-gallery-base-class-consolidation-guisrcclasses) |
| A.8 | **[Arch] ✅ TYPE_CHECKING guards for heavy GUI→backend imports** — `from __future__ import annotations` + `if TYPE_CHECKING:` for `AnimeStitchPipeline` and other PyTorch imports in GUI workers; reduces cold-start by ~2–4s | Done | [architecture.md §5.11B](roadmaps/architecture.md#511-circular-import-prevention--module-boundary-documentation) |
| A.9 | **[Arch] ✅ ML wrapper contract tests (mock-based)** — one `TestXxxWrapperContract` class per wrapper in `backend/test/models/`; verifies output shape/dtype, `unload()` idempotency, `loaded` property; no GPU required; <1s per test | Done | [architecture.md §5.16A](roadmaps/architecture.md#516-contract-testing-for-ml-model-wrappers-backendsrcmodels) |
| A.10 | **[Arch] ✅ mypy baseline config + TypedDict worker configs** — `[tool.mypy]` section in `pyproject.toml` (permissive baseline); `ConversionConfig`, `DeletionConfig`, `MergeConfig`, `StitchConfig` TypedDicts in `gui/src/helpers/core/config_types.py`; wired into `ConversionWorker`, `DeletionWorker`, `MergeWorker` | Done | [architecture.md §5.5A](roadmaps/architecture.md#55-gradual-static-type-safety-migration) |
| A.11 | **[Arch] ✅ `AppSettings` GUI facade** — `gui/src/utils/settings.py` singleton; replaces 20+ inline `QSettings("ImageToolkit","ImageToolkit")` constructor calls; typed properties per key; wired into both gallery base classes, `main_window.py`, `splitter_persistence.py`, `listings_common.py`, `thumbnail_size.py` | Done | [architecture.md §5.14A](roadmaps/architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.12 | **[Arch] ✅ `get_asp()` helper in `config.py`** — `get_asp(key, default="")` reads `os.environ[key]` with fallback; `ConfigError` raised in `validate_asp_config` strict mode; exported from `backend/src/anim/config.py` | Done | [architecture.md §5.14B](roadmaps/architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.13 | **[Arch] ✅ Custom exception hierarchy** — `backend/src/exceptions.py` with `ImageToolkitError` → `PipelineError`/`AlignmentFailedError`/`CanvasError`/`FallbackExhaustedError`/`ModelLoadError`/`ConfigError`; bare `RuntimeError`/`ValueError` replaced in `anim/pipeline.py`, `anim/canvas.py`, `anim/config.py`, `models/birefnet_wrapper.py`; `BaseQThreadWorker` three-tier handler routes `AlignmentFailed`/`Canvas` as WARNING, `Pipeline`/`Model`/`Config` as ERROR | Done | [architecture.md §5.15A](roadmaps/architecture.md#515-fault-isolation--error-boundary-protocol) |
| A.14 | **[Arch] ✅ `BaseQThreadWorker` + `BaseQRunnableWorker` + `_WorkerSignals`** — `gui/src/helpers/base.py`; uniform `cancel()`/`stop()`, exception routing; `SearchWorker` migrated to `BaseQRunnableWorker` | Done | [architecture.md §5.9](roadmaps/architecture.md#59-worker-thread-base-class--lifecycle-standardisation-guisrchelpers) |
| A.15 | **[Arch] NumPy-style docstrings + Mermaid class diagrams** — all public methods in `backend/src/models/` and `backend/src/anim/`; hierarchy diagrams in `backend/src/models/__init__.py` and `gui/src/classes/__init__.py` | ~3d | [architecture.md §5.12](roadmaps/architecture.md#512-codebase-documentation--diagrams) |
| A.16 | **[Arch] `AbstractGalleryBase` + replace metaclass injection** — new `gui/src/classes/gallery_base.py`; shared `__init__` state extracted; injected functions become real methods; both gallery classes migrate | ~1w | [architecture.md §5.10A](roadmaps/architecture.md#510-gallery-base-class-consolidation-guisrcclasses) |
| A.17 | **[Arch] Module dependency graph + `import-linter` contracts** — `pydeps` SVG committed to `docs/`; `import-linter` contracts in `pyproject.toml` enforcing layer ordering; CI-gated | ~1w | [architecture.md §5.11A](roadmaps/architecture.md#511-circular-import-prevention--module-boundary-documentation) |

**Dependency order:** A.1–A.7 are independent Quick Wins (batch in one PR each). A.8 depends on A.4 (`__all__` first). A.9 is independent. A.13 → A.14 (exception hierarchy makes error boundary meaningful). A.11 + A.12 can be done together (settings facade sprint). A.16 depends on A.7.

---

## Phase 6 — Long-term Research (Months, Exploratory)

Aspirational improvements requiring significant experimentation, external data, or architectural investment. No fixed timeline.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 6.1 | **[ASP] Online DRL agent for ECC/registration** — wire `rlhf_trainer.py` into Stage 8 | [Long-term] | [asp.md §1.10](roadmaps/asp.md#110-rlhf-loop-integration) |
| 6.2 | **[ASP] RANSAC/MAGSAC++ pre-filter for >40% outlier datasets** | [Research] | [asp.md §1.1](roadmaps/asp.md#11-bundle-adjustment-hardening) |
| 6.3 | **[ASP] ToonCrafter fill for overlap ghost reduction** — final-quality mode; see ML.4 for wiring plan | [Research] | [asp.md §3.6](roadmaps/asp.md#36-tooncrafter-seam-synthesis--wiring-the-generative-fallback-priority-medium) |
| 6.4 | **[ASP] Background histogram matching via CLAHE** for complex dark scenes | [Research] | [asp.md §1.4](roadmaps/asp.md#14-gain-clamp-widening-for-dark-scenes) |
| 6.5 | **[Feat] AnimeCLIP domain-specific CLIP fine-tune** — swap into §5.1 once validated | [Research] | [new_features.md §4.3](roadmaps/new_features.md#43-clip-based-semantic-image-search) |
| 6.6 | **[Feat] File system watcher auto-stitch** — `watchdog`/`inotify` triggered batch | [Research] | [new_features.md §4.1](roadmaps/new_features.md#41-batch-stitching) |
| 6.7 | **[Feat] Mobile remote wallpaper + push notifications** — depends on §5.6 REST API | [Exploratory] | [new_features.md §4.5](roadmaps/new_features.md#45-multi-monitor-wallpaper-support) |
| 6.8 | **[Arch] Hypothesis property-based tests for bundle_adjust and compositing** | [Research] | [architecture.md §5.1](roadmaps/architecture.md#51-asp-pipeline-unit-test-coverage) |
| 6.9 | **[Perf] CUDA seam DP via PyTorch scatter/gather** — GPU seam computation | [Research] | [asp.md §1.5](roadmaps/asp.md#15-stage-11-composite-performance) |
| 6.10 | **[Arch] Full mypy strict coverage** — all modules under `disallow_untyped_defs = true`; end state of §5.5 gradual migration | [Long-term] | [architecture.md §5.5](roadmaps/architecture.md#55-gradual-static-type-safety-migration) |

---

## Master Effort × Impact Matrix

Cross-roadmap overview. Items are the top-priority pending work from each sub-roadmap, classified by effort and expected impact.

*Effort* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks, research, or data-gated
*Impact* — **Low**: marginal · **Medium**: noticeable targeted improvement · **High**: major capability or quality gain across multiple users/tests · **Very High**: architectural unlock or differentiating feature

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | [GUI] §2.10 toast · §2.14 overlay · [Arch] §5.7A uv lock · [Perf] §3.6A move semantics · [Arch] A.1 Pyright basic · A.2 bare-except fix · A.3 relocated-import cleanup · A.4 `__all__` hygiene · A.5 QSettings key validation · A.6 `@log_call` decorator · A.7 metaclass docstring | [GUI] §2.2B ctrl+scroll · §2.7A progress bar · §2.32A geometry save · [Perf] §3.4D HNSW tune · §3.5A crawler context mgr · [Feat] §4.11A inline RLHF rating · [Arch] A.8 TYPE_CHECKING guards · A.9 wrapper contract tests | [GUI] §2.3A+C keyboard nav · [ASP] §2.5 coverage map · §2.6 crop assistant · §3.15A SemanticStitch column filter · [CG] §1.1 WD14 captioning | [ASP] §10A2 click-based SAM-2 refinement |
| **Medium (1d–1w)** | [Arch] §5.4B pipeline trace JSON | [Perf] §3.3C dynamic BiRefNet batch · §3.4A psycopg3 · [GUI] §2.13 gallery filter+sort · §2.8A dark/light theme · [Feat] §4.5A KDE per-monitor wallpaper · [Arch] A.10 mypy baseline + TypedDicts · A.11 AppSettings facade · A.12 ASP env-var consolidation | [ASP] §1.10B Bayesian param search · §2.9 BigWarp fallback · §3.3 DINOv2 submodular · §3.13 ProPainter · §3.15B OBJ-GSP mesh · §10A3 NL seam routing · §10B1 COCO serializer · [Arch] A.13 exception hierarchy · A.14 BaseQThreadWorker · §5.8A ModelWrapper ABC · [Feat] §4.3A CLIP semantic search · §4.4A WD14 tagger · [CG] §1.3 LyCORIS · §2.1A AnimateDiff | [ASP] §9A PyAV video ingestion · §10A1 Grounded SAM-2 |
| **High (1–2w)** | — | [ASP] §3.12 Overmix sub-pixel · §3.16A StabStitch++ | [ASP] §2.10 SAM2Flow · §3.2 ConvGRU flow · §3.6 ToonCrafter seam · §3.14B horizontal-strip composite · [Arch] §5.3B abstract Matcher interface · [Perf] §3.2A GPU CUDA median render · [CG] §1.4B native ControlNet/IP-Adapter | [ASP] §9C Hybrid 4K/1080p composite |
| **Very High (2w+ / data-gated)** | — | — | [ASP] §3.7 UDIS++ diffusion seam · [CG] §3.x video→LoRA full pipeline · [Arch] §5.5C Rust AES-256-GCM vault | [ASP] §10C1 SAM-2 anime fine-tune · §10C2 Pose contrastive · §10C3 PPO optimization · [CG] §2.3 Wan2.1/SVD foundation video |

---

## Dependency Graph Summary

```
Phase 1 (Quick Wins)
  └─► Phase 2 (Core QoS)
        ├─► Phase 3 (Feature Enrichment)
        │     ├─ 3.13 Unit tests unblocks 3.14 CI gate
        │     └─ 3.6 Auto-tagger unblocks 5.5 Review queue
        ├─► Phase 4 (Platform Hardening)
        │     ├─ 4.1 Matcher interface unblocks 5.10 Compositor registry
        │     ├─ 4.2 ModelWrapper ABC unblocks A.9 contract tests + A.16 mixin
        │     └─ 4.9 QListView unblocks full bulk-select UX
        ├─► Phase Arch (Code Quality — parallelisable with Phase 3/4)
        │     ├─ A.1–A.7 Quick Wins (independent, batch as single PR each)
        │     ├─ A.13 Exception hierarchy → A.14 BaseQThreadWorker (sequential)
        │     ├─ A.11+A.12 Settings facade sprint (independent)
        │     └─ A.16 AbstractGalleryBase depends on A.7 (metaclass docstring first)
        └─► Phase 5 (Advanced Features)
              ├─ 5.1 CLIP search requires §4.8 psycopg3 pool + §2.14 HNSW tuning
              ├─ 5.6 REST API enables §6.7 mobile features
              └─ 5.7 RLHF param search requires §2.5 quality gate (Phase 2)
```
