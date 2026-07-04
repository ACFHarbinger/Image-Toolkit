# Image Toolkit — Master Roadmap

*Last updated: 2026-07-04. New Phase EXT (Browser Extension) added — webpack multi-browser manifest builds (chrome/firefox/edge/brave) in `extension/webpack/`, TypeScript migration, unified MV3, local app bridge (HTTP → native messaging), in-browser duplicate search against a configured directory tree (reuses `PhashDeduplicator` §4.6), send-to-app ingestion with provenance, visual similarity search, bulk page grabber, per-site folder rules + filename templating + metadata sidecar, full-resolution extraction, and turbo mode polish; full detail in [extension.md](extension.md). S206: thumbnail loading optimized (C++ reduced decode + disk cache + progressive gallery fill). Previous update 2026-06-18: Architecture roadmap updated: §5.5 (Gradual Static Type Safety), §5.8–§5.13 (model wrapper ABC, worker base class, gallery consolidation, circular imports, docs/diagrams, decorators), §5.14–§5.16 (settings facade, fault isolation, ML wrapper contract tests) added. Phase 4 updated to remove stale §4.1 Vault Manager link. New Phase Arch added for code-quality items. Session 131: §1.66 NCC structural coherence gate (Stage 11.4), §1.67 pre-BA frame canvas spread validation, §1.8C/D dump_asp_config with typed TOML schema comments (827 tests). Session 130: §1.60 fg pose-gap pre-escalation, §1.62 canvas aspect-ratio gate, §1.63 sort-frames-by-index, §1.64 exact-duplicate dHash guard, §1.65 fg seam erosion buffer, §1.10D MC-dropout uncertainty, §3.17 seam NCC coherence + §3.5A composite quality score in bench (822 tests). Session 78: §2.3 Canvas Layout Inspector read-only viewer (422 tests passing). Session 77: §2.2 Edge Graph Inspector read-only viewer (413 tests passing). Session 76: GNC-TLS BA (§1.32, 412 tests passing). GUI: §2.23A accessibility, §2.4B+C range-select + context menu, §2.25A shortcut overlay, §2.20A splitter persistence, §2.17D log window, §2.16C Ctrl+T tab search, §2.12A+B+C system tray, §2.11A+B+D preview enhancements, §2.21A+D dir history + MRU, §2.26B inline rename, §2.10C QStatusBar, §2.14A filename labels, §2.18 sort + search ops, §2.19 trash, §3.9 item range, §4.11 thumbnail slider, §3.15–3.17 shortcuts/QSS/geometry all shipped. §2.30 accent colour picker + font scale + UI density shipped. New roadmap sections added: §2.29 (configurable keyboard shortcuts), §2.30–2.32 (appearance customisation), §4.12–4.13 (appearance profiles + macros). Session 9: ToonCrafter seam synthesis wired (§3.6/ML.4, `ASP_TOONCRAFTER_SEAM=1`). Session 8: DINOv2 submodular frame selection (§3.3/ML.2), LSD collinearity in ARAP (§0.1/A3), Aligned-SSIM metric. Session 7: Stage 12.5 scroll-axis content trim (§2.6). Session 6: hold detection (§1.11/ML.1), GNC BA, SLIC SGM proxy (§3.1/ML.5). 107 tests passing. Session 5: alignment stability gate (+0.074 test08, +0.049 test25), fg pixel L1 pose metric (+0.010 test27 with pose-on), 90 unit tests. Session 4: ARAP Push (Sýkora 2009), 96-test run. Research: `reports/Image_Stitching_Research.md`, `reports/ASP_Comprehensive_Research_Report.md`.*

Completed items have been moved to [CHANGELOG.md](../../moon/CHANGELOG.md).

---

## How to Use This Document

This document defines the **phased execution sequence** for all upcoming improvements. Each item links to the corresponding brainstorming section in the appropriate section-specific roadmap for full context, options, and trade-offs.

Section-specific roadmaps:
- [ASP — Anime Stitch Pipeline](asp.md)
- [Content Generation — Anime Image & Video](content_generation.md)
- [GUI/UX — Desktop Interface](gui_ux.md)
- [Performance — Compute, Memory, I/O](performance.md)
- [New Features — Capabilities & Integrations](new_features.md)
- [Architecture & Infrastructure](architecture.md)
- [Browser Extension — Capture, Build System & App Integration](extension.md)

Consolidated research reports (read before working on the respective pipeline):
- [Anime Stitching — Consolidated Research](../../reports/Image_Stitching_Research.md) — foreground-assembly paradigm, per-stage toolbox, 13-stage spec.
- [Anime Generation — Consolidated Research](../../reports/Image_Generation_Research.md) — image + video models, fine-tuning, video→LoRA pipeline.
- [Anime Stitch Pipeline ML Research](../../reports/ASP_Comprehensive_Research_Report.md) — ML-driven solutions for aperture problem (AnimeInterp SGM), frame selection (DINOv2 submodular), camera estimation (CamFlow), generative composition (ToonCrafter, RDIStitcher), and reference-free metrics (SIQE, SI-FID, MLLM SIQS). Full roadmap entries in [asp.md §3.0](asp.md#30-ml-driven-pipeline-modernisation-research-phase--from-ml-research-report).

Phases are ordered by impact-to-effort ratio and dependency order. Items within a phase are independent and can be parallelised.

---

## Phase 0 — ASP Foreground Assembly (Priority 0, The Core Quality Fix)

The single highest-impact track: the pipeline cannot register the deforming foreground, so characters tear at every strip seam (ASP loses to simple-stitch on GT-SSIM). Implements the foreground-assembly architecture from the consolidated stitching research.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 0.1 | **[ASP] ✅ Foreground pose registration (A2/A4 prototype)** — `fg_register.py`: DIS dense flow → residual extraction → symmetric midpoint warp; integrated into Stage 11. Validated on test09. | Done | [asp.md §0.1](asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.2 | **[ASP] A1 — SEA-RAFT flow engine** (anime-tuned via LinkTo-Anime) replacing DIS for flat-region robustness | ~3d | [asp.md §0.1](asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.3 | **[ASP] ✅ A3 — full Sýkora ARAP + LSD** — ARAP Push→Regularise shipped (S4); LSD collinearity term shipped (S8): boundary-cell projection onto detected line directions, magnitude guard ≥50% | Done | [asp.md §0.1](asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.4 | **[ASP] ✅ A5 — foreground-excluded temporal median** — `_render_median` builds `bg_canvas[i]` per-frame background pixel mask from BiRefNet `bg_masks`; `eff_masks` prefers background samples, falls back to all valid pixels for character-covered positions; `ASP_FG_EXCLUDE_MEDIAN=1` (default ON) | Done | [asp.md §0.1](asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.5 | **[ASP] A6 — confidence-gated single-pose graph-cut fallback** (Eden 2006) | ~3d | [asp.md §0.1](asp.md#01-foreground-pose-registration--the-core-fix-priority-0) |
| 0.6 | **[ASP] 🔄 Pose-consistency frame selector** — two-pass architecture built; fg pixel L1 + DINOv2 cosine distance (S8) as pose metrics; activated via `ASP_POSE_WINDOW_PX=80`; GT-coupling still limits default-on use | ~2d | [asp.md §0.2](asp.md#02-pose-consistency-aware-frame-selection-priority-1) |
| 0.7 | **[ASP] ✅ min_gap vector-magnitude for diagonal sequences** — `_compute_adaptive_min_gap` now selects `dx_span` for horizontal, `dy_span` for vertical, and `sqrt(dy_span² + dx_span²)` for diagonal (§0.7); corrects underestimate by up to 1.41× at 45° giving proportionally higher adaptive threshold; `min_step=25px` already set in `_validate_affines` | Done | [asp.md §0.5](asp.md) |
| 0.8 | **[ASP] Segment-guided flow (AnimeInterp SGM)** flat-region fallback — see ML.5/ML.8 for full roadmap | [Research] | [asp.md §3.1](asp.md#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact) |

---

## Phase ML — ASP ML-Driven Modernisation (Research Phase)

*Source: `reports/ASP_Comprehensive_Research_Report.md` (2026-06-04). Full detail and implementation options in [asp.md §3.0](asp.md#30-ml-driven-pipeline-modernisation-research-phase--from-ml-research-report).*

These items address the three quantified ceilings that classical CV methods have exhausted: (1) aperture problem on flat cel regions, (2) background-entangled frame selection, (3) reference-free quality assessment. Each maps to a specific pipeline stage and existing file. All are tagged [Research] — none require new training from scratch; all use pretrained weights or classical algorithms with offline fitting.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| ML.1 | **[ASP] ✅ FD-Means animation hold detection** — `_detect_hold_blocks()` shipped (S6); `ASP_HOLD_THRESHOLD=0.025`; perceptual MAD hold clustering; hold IDs used in Pass 2 penalty | Done | [asp.md §3.4](asp.md#34-fd-means-animation-hold-detection-quick-win--preprocessing) |
| ML.2 | **[ASP] ✅ DINOv2 submodular frame selection** — `_compute_dinov2_features()` shipped (S8); `dinov2_vits14` via `torch.hub`; cosine distance replaces fg pixel L1 in Pass 2; activated via `ASP_POSE_WINDOW_PX=80` | Done | [asp.md §3.3](asp.md#33-dinov2--siglip-submodular-frame-selection-priority-high--directly-addresses-gt-coupling) |
| ML.3 | **[ASP] SIQE ghosting metric** — steerable pyramid + GMM ghosting detector (94.36% human-opinion precision); replaces `_ghosting_score()`; adds spatial ghost localisation per seam | ~3d | [asp.md §3.8](asp.md#38-siqe-no-reference-ghosting-detection-quick-win--metric-upgrade) |
| ML.4 | **[ASP] ✅ ToonCrafter seam synthesis wiring** — shipped (S9); worst single-pose seam triggers `_generate_canonical_cel()` from `anim_fill.py`; canonical cel replaces hard partition for fg pixels; `ASP_TOONCRAFTER_SEAM=1` | Done | [asp.md §3.6](asp.md#36-tooncrafter-seam-synthesis--wiring-the-generative-fallback-priority-medium) |
| ML.5 | **[ASP] ✅ SLIC segment-level centroid tracking** — `_slic_sgm_proxy()` shipped (S6); ARAP Push fallback for flat regions; `ASP_SGM_PROXY=1` | Done | [asp.md §3.1](asp.md#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact) |
| ML.6 | **[ASP] Deep homography with foreground masking** — CVPR 2020 joint dynamics-mask + homography network; replaces phase correlation for camera displacement in `frame_selection.py`; pretrained weights available | ~3d | [asp.md §3.5](asp.md#35-camflow-hybrid-motion-basis-for-camera-displacement-research) |
| ML.7 | **[ASP] SI-FID as benchmark metric** — reference-free stitching quality (Fréchet distance in artifact-trained latent space); supplements GT-SSIM for the 41 GT-less tests; enables GT-coupling-free RLHF optimization | ~3d | [asp.md §3.9](asp.md#39-si-fid-stitched-image-fréchet-distance-for-reference-free-evaluation-research) |
| ML.8 | **[ASP] AnimeInterp SGM as ARAP Push replacement** — segment-guided matching via VGG-19 pooled per-segment features; completely bypasses aperture problem; ~40ms/seam GPU; `ASP_FLOW_ENGINE=animeinterp` flag | ~1w | [asp.md §3.1](asp.md#31-animeinterp-sgm-segment-guided-matching-for-flat-region-correspondence-research--highest-aperture-problem-impact) |
| ML.9 | **[ASP] CamFlow Hybrid Motion Basis** — ICCV 2025 model for sub-pixel-accurate 2D camera estimation even with full-frame foreground; replaces phase correlation; physical+stochastic motion bases | ~1w | [asp.md §3.5](asp.md#35-camflow-hybrid-motion-basis-for-camera-displacement-research) |
| ML.10 | **[ASP] MLLM semantic quality gate** — Qwen2-VL-7B via ollama; detects severed torsos, duplicated limbs, mismatched body orientation; `ASP_MLLM_QA=1`; benchmark-only initially | ~2d | [asp.md §3.10](asp.md#310-mllm-semantic-quality-scoring-research--autonomous-quality-assurance) |
| ML.11 | **[ASP] UDIS++ diffusion-based seam composition** — replaces Laplacian blend in Stage 11 with unsupervised spatial warp + diffusion hallucination of seam zone; open-source weights; needs anime fine-tune | ~2w | [asp.md §3.7](asp.md#37-udis--udtatis-diffusion-based-seam-composition-long-term--end-to-end-replacement) |
| ML.12 | **[ASP] ConvGRU recurrent flow refinement** — AnimeInterp's confidence-guided iterative residual flow; fills null regions after SGM; trained on ATD-12K with animation-specific exaggeration | ~1w | [asp.md §3.2](asp.md#32-convgru-recurrent-flow-refinement-for-kinematic-accuracy-research) |

**Dependency order:** ML.1 → ML.2 (holds detected first, then selection uses DINOv2). ML.3 + ML.7 are independent evaluation upgrades. ML.4 depends on existing `anim_fill.py` (already present). ML.5 → ML.8 (SLIC is the cheap approximation; AnimeInterp is the full solution). ML.6 → ML.9 (deep homography first, CamFlow second as quality upgrade). ML.10 independent. ML.11 + ML.12 depend on ML.8 being validated.

---

## Phase CG — Content Generation (Anime Image & Video)

Builds on the existing generation stack (`LoRATuner` on Illustrious-XL, `SD3Wrapper`, ComfyUI integration, data pipeline). Full detail in [content_generation.md](content_generation.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| CG.1 | **[Gen] WD14 + Florence-2 anime captioning** (booru tags + trigger token; shared with auto-tagger) | ~2d | [content_generation.md §1.1](content_generation.md) |
| CG.2 | **[Gen] Shared anime upscaler** — Real-ESRGAN anime_6B module reused by gen tabs + ASP | ~1d | [content_generation.md §1.6](content_generation.md) |
| CG.3 | **[Gen] ComfyUI control workflows** — curated txt2img / pose / reference / upscale JSONs | ~2d | [content_generation.md §1.4](content_generation.md) |
| CG.4 | **[Gen] Video→Character-LoRA guided flow** — PySceneDetect + dedup + caption + per-GPU TOML | ~1–2w | [content_generation.md §3](content_generation.md) |
| CG.5 | **[Gen] LyCORIS variants** (LoCon/LoHa/LoKr) in `LoRATuner` | ~3d | [content_generation.md §1.3](content_generation.md) |
| CG.6 | **[Gen] AnimateDiff via ComfyUI** — short anime clips/GIFs with character LoRA | ~1w | [content_generation.md §2.1](content_generation.md) |
| CG.7 | **[Gen] v-prediction / zero-terminal-SNR** support in `LoRATuner` + samplers | [Research] | [content_generation.md §1.2](content_generation.md) |
| CG.8 | **[Gen] ToonCrafter inbetweening** (shared with ASP `animation/anim_fill.py` ghost-fill) | [Research] | [content_generation.md §2.2](content_generation.md) |
| CG.9 | **[Gen] FLUX.1 [dev] secondary support** (FP8/GGUF for 16 GB) | [Research] | [content_generation.md §1.5](content_generation.md) |
| CG.10 | **[Gen] Wan2.1 / SVD foundation video** (3090 Ti, VRAM-gated) | [Long-term] | [content_generation.md §2.3](content_generation.md) |

---

## Phase 1 — Immediate Wins (Days, No New Dependencies)

These are one-line or near-trivial changes with immediate measurable benefit. Ship as a single batch.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 1.1 | **[ASP] ✅ Fallback path purity** — `scans_frames` snapshot taken before ML corrections at Stage 2; all fallback call-sites pass `scans_frames` | Done | [asp.md §1.9](asp.md#19-fallback-path-purity) |
| 1.2 | **[ASP] ✅ Dark scene gain clamp widening** — conditional `[0.80, 1.25]` when `ref_lum_scalar < 80`, `[0.88, 1.14]` otherwise | Done | [asp.md §1.4](asp.md#14-gain-clamp-widening-for-dark-scenes) |
| 1.3 | **[ASP] ✅ Static edge pre-bundle rejection** — `MIN_EXPECTED_STEP = 50` (defined in constants/animation.py) now correctly imported into pipeline.py; min-step guard at lines 278–298 is active | Done | [asp.md §1.2](asp.md#12-near-zero--zero-translation-edge-filter) |
| 1.4 | **[ASP] ✅ Content-aware minimal bounding crop** — `_crop_to_valid` uses `_largest_valid_rect` when valid_ratio < 0.80; SCANS fallback also uses `_largest_valid_rect` for diagonal panoramas | Done | [asp.md §1.7](asp.md#17-recdiffusion-border-rectangling) |
| 1.5 | **[ASP] ✅ Restrict seam search window** — `_seam_dp` gains `search_half` parameter; `de_seam` propagates it; callers pass `search_half=100` for small cross-axis displacement | Done | [asp.md §1.5](asp.md#15-stage-11-composite-performance) |
| 1.6 | **[Perf] ✅ WebDriver context manager** — all crawlers migrated to Rust (`base/src/web/`); Python wrappers call `base.run_*` and never hold a driver reference; Rust code calls `driver.quit().await` on all exit paths; Python-level orphaned-driver risk eliminated by architecture | Done | [performance.md §3.5](performance.md#35-webdriver-lifecycle-management) |
| 1.7 | **[Perf] ✅ Rust DynamicImage move semantics** — take ownership in `apply_ar_transform` (`image_converter.rs`) and `fast_resize` (`image_merger.rs`); no-op path returns owned image, eliminating ~30 MB clone for 4K RGBA on convert+merge | Done | [performance.md §3.6](performance.md#36-dynamicimage-move-semantics-in-rust) |
| 1.8 | **[Perf] ✅ ML model unload after BiRefNet + LoFTR stages** — `unload()` added to all 7 model wrappers (BiRefNet, LoFTR, EfficientLoFTR, RoMa, ALIKED+LG, JamMa, BaSiC); pipeline calls `unload()` instead of `offload()` | Done | [performance.md §3.7](performance.md#37-python-ml-model-memory-lifecycle) |
| 1.9 | **[GUI] ✅ Session persistence** — `_save_last_dir` / `_load_last_dir` via `QSettings` in both gallery base classes | Done | [gui_ux.md §2.5](gui_ux.md#25-session-persistence) |
| 1.10 | **[GUI] ✅ OS dark mode follow** — `QGuiApplication.styleHints().colorScheme()` + `colorSchemeChanged` live signal in `MainWindow` | Done | [gui_ux.md §2.8](gui_ux.md#28-theme-support) |
| 1.11 | **[GUI] ✅ Ctrl+scroll thumbnail zoom** — `ctrl_wheel` signal on `MarqueeScrollArea`; auto-connected in `_on_layout_change`; reloads current page at new size | Done | [gui_ux.md §2.2](gui_ux.md#22-gallery-thumbnail-size-control) |
| 1.14 | **[GUI] ✅ Settings window — Gallery/Startup/Performance/Slideshow/Logging/Reset State sections** — implemented | Done | [gui_ux.md §2.9](gui_ux.md#29-settings-window-extensions) |
| 1.12 | **[Arch] ✅ `uv lock` + CI frozen install** — `uv.lock` committed; `.github/workflows/ci.yml` uses `uv sync --frozen --no-install-project`; `pip-audit` + `numpy` added to dev deps | Done | [architecture.md §5.7](architecture.md#57-dependency-audit-and-pinning) |
| 1.13 | **[Arch] ✅ Python `logging` module + rotating file handler** — `_setup_logging()` in `app.py` creates a 5 MB rotating file handler + console handler; `logger = logging.getLogger(__name__)` added to `pipeline.py`, `canvas.py`, `matching.py`, and all model wrappers; `print()` migrated to `logger.info/debug/warning/error` | Done | [architecture.md §5.4](architecture.md#54-logging-and-diagnostics) |

---

## Phase 2 — Core Quality-of-Service (Days to 1 Week, Minimal Dependencies)

Reliable improvements with a clear implementation path and direct impact on daily use.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 2.1 | **[ASP] ✅ TOML config file for pipeline constants** — `load_asp_config()` + `get_asp()` in `backend/src/animation/config.py`; `_CONFIG_SCHEMA` (14 keys); `validate_asp_config()` strict/warning modes; `asp_config.toml` loaded on startup (§1.8A/B, S27/S42) | Done | [asp.md §1.8](asp.md#18-asp-pipeline-configuration-file) |
| 2.2 | **[ASP] ✅ NumPy vectorised seam DP** — `_seam_cut()` forward pass uses `scipy.ndimage.minimum_filter1d(size=3, cval=np.inf)`; traceback uses slice-argmin; 5–10× speedup vs explicit loop (§1.5A, S10) | Done | [asp.md §1.5](asp.md#15-stage-11-composite-performance) |
| 2.3 | **[ASP] ✅ Near-duplicate frame deduplication** — `_near_dup_luma_filter()` + `_detect_hold_blocks_dhash()` (INTER_AREA + horizontal gradient hash, distance ≤ 4); wired in `smart_select_frames` step 1b; `ASP_HOLD_DHASH_THRESH=4` (§1.2B/§3.4A, S26/S43) | Done | [asp.md §1.2](asp.md#12-near-zero--zero-translation-edge-filter) |
| 2.4 | **[ASP] ✅ Increase foreground penalty in seam DP** — tiered cost map: fg-interior=1.0, fg-edge-buffer=0.5, bg=0.0; `sem_weight=200.0` in `_seam_cut()`; fg-dominated-column barrier cost=2.0 (§1.6A S19, §3.15A S33) | Done | [asp.md §1.6](asp.md#16-ghosting-reduction-in-composite-zone) |
| 2.5 | **[ASP] ✅ Post-run RLHF quality gate** — `_compute_rlhf_score()` + `_get_reward_model()` lazy singleton in `bench_anime_stitch.py`; `_RLHF_FLAG_THRESHOLD=0.6`; emits `rlhf_score` + `rlhf_flagged` per test (§1.10A, S29) | Done | [asp.md §1.10](asp.md#110-rlhf-loop-integration) |
| 2.6 | **[ASP] ✅ Stage-level progress signals** — `_ProgressPipeline` in `stitch_worker.py` emits `sig_stage(idx, total, label)` at the start of all 13 stages via `_emit()`; `StitchWorker.sig_stage = Signal(int, int, str)` | Done | [gui_ux.md §2.7](gui_ux.md#27-progress-and-cancellation) |
| 2.7 | **[GUI] ✅ Cancellable QThread `_should_stop` flag** — `WallpaperWorker` and `TrainingWorker` now set `self._should_stop = True` in `stop()` (previously only `is_running` was set); both initialise `_should_stop = False` for uniform tooling | Done | [gui_ux.md §2.7](gui_ux.md#27-progress-and-cancellation) |
| 2.8 | **[GUI] ✅ Arrow key gallery navigation** — `keyPressEvent` in `AbstractClassTwoGalleries`: Left/Right/Up/Down move `_focused_found_idx`, Enter emits `path_double_clicked` on focused widget | Done | [gui_ux.md §2.3](gui_ux.md#23-keyboard-navigation) |
| 2.9 | **[GUI] ✅ Shift+click / Ctrl+click multi-select** — `handle_marquee_selection()` in `AbstractClassTwoGalleries` checks `Qt.ShiftModifier` (additive) and `Qt.ControlModifier` (subtractive); fully wired | Done | [gui_ux.md §2.4](gui_ux.md#24-bulk-selection-and-operations) |
| 2.26 | **[GUI] ✅ F2 Rename (§2.26B)** — `_rename_focused_file()` in `AbstractClassTwoGalleries` (triggered by F2, renames the file focused via arrow-key navigation) and `_rename_selected_file()` in `AbstractClassSingleGallery` (renames last selected item). Both sanitise the new name, guard against conflicts, and update `found_files`, `master_found_files`, `selected_files`, and `path_to_label_map` / `path_to_card_widget`. | Done | [gui_ux.md §2.26](gui_ux.md#226-inline-rename) |
| 2.19 | **[GUI] ✅ Export selection as paths list (§2.19A)** — `_export_selection_as_paths()` on both gallery base classes; Ctrl+E saves `selected_files` (or all found files if none selected) to a user-chosen `.txt`/`.csv`. Uses `DontUseNativeDialog` to avoid JVM RTTI conflict. | Done | [gui_ux.md §2.19](gui_ux.md#219-gallery-export-and-contact-sheet) |
| 2.10 | **[GUI] ✅ Recent directories MRU helpers** — `_add_recent_dir` / `_get_recent_dirs` on both gallery base classes; backed by `QSettings`; ready for concrete tabs to wire up a dropdown | Done | [gui_ux.md §2.5](gui_ux.md#25-session-persistence) |
| 2.16 | **[GUI] ✅ Wire settings A/B/C/D/E/F/G** — All seven sub-items now wired: §A+C (thumbnail/page size, startup category), §B (LRU cache resize), §D (confirm_deletions checkbox load/save/reset), §E (WallpaperTab slideshow spinboxes/combo), §F (file_logging_enabled + log level), §G (restore_last_dir). | Done | [gui_ux.md §2.9](gui_ux.md#29-settings-window-extensions) |
| 2.11 | **[GUI] ✅ Toggle button + quality metrics overlay in StitchTab** — `_show_stitch_result()` loads result + first-frame pixmaps after stitch; "◀ Before / After ▶" toggle button switches between them; `_MetricsTask` (QRunnable) computes Laplacian sharpness + file size + dimensions off-thread; metrics label updates via `_MetricsSignals.ready`; result group hidden until first stitch | Done | [gui_ux.md §2.6](gui_ux.md#26-stitch-tab-ux--beforeafter-comparison) |
| 2.18 | **[GUI] ✅ Gallery sort toolbar + search operators** — Sort QComboBox (Name/Date/Size/Ext) + ↑↓ button in pagination bar; `_apply_sort()` / `_sort_key_fn()` in both gallery base classes; `_common_filter_string_list` upgraded to support `-exclude`, `"phrase"`, `a\|b` OR; placeholder text updated to hint syntax; sort applied on directory load too | Done | [gui_ux.md §2.13](gui_ux.md#213-gallery-filtering-and-sort-controls) |
| 2.19 | **[GUI] ✅ Move to Trash instead of permanent delete** — `send2trash` replaces `os.remove` in DeleteTab, WallpaperTab, SearchTab; confirmation dialogs updated; `send2trash>=1.8.3` added to `pyproject.toml` | Done | [gui_ux.md §2.15](gui_ux.md#215-undoredo-for-destructive-operations) |
| 2.17 | **[GUI] ✅ Accent colour picker + UI density + font scale** — `QColorDialog` swatches in settings "Display and Media" tab; `compute_accent_vars()` derives hover/pressed from base; `load_qss_with_overrides()` substitutes at runtime; density appends Compact/Spacious QSS; font scale via `QApplication.setFont`; all persisted in vault `preferences` | Done | [gui_ux.md §2.30](gui_ux.md#230-accent-color-and-ui-density-customization) |
| 2.12 | **[Perf] ✅ Rust two-pass streaming image merger** (Option A). All three `merge_images_{horizontal,vertical,grid}_core` functions refactored: Pass 1 reads image headers via `image::image_dimensions()` (no pixel decode) to compute canvas size; canvas allocated once; Pass 2 loads one image at a time, blits, drops immediately. Peak RAM = 1 image + output canvas instead of all-images-at-once. 6 Rust tests (2 original preserved, 4 new streaming-correctness tests). | Done | [performance.md §3.1](performance.md#31-rust-streaming-image-merger) |
| 2.13 | **[Arch] ✅ Pipeline execution trace JSON** — `_ProgressPipeline.run()` writes a per-run JSON to `~/.image-toolkit/traces/stitch_YYYYMMDD_HHMMSS.json` containing `started_at`, `finished_at`, `elapsed_seconds`, `frames_input`, `edges_found`, `canvas_size`, `fallback_used`, `success`, `error`, `stage_timings` | Done | [architecture.md §5.4](architecture.md#54-logging-and-diagnostics) |
| 2.14 | **[Arch] ✅ pgvector HNSW index tuning** — `schema.sql` index updated to `m=32, ef_construction=128`; `search_images()` sets `hnsw.ef_search = 80` via `SET LOCAL` before each vector query | Done | [performance.md §3.4](performance.md#34-database-query-optimisation) |
| 2.15 | **[Arch] ✅ `pip-audit` + `cargo audit` in CI** — `.github/workflows/security.yml`: weekly `pip-audit --requirement` scan of locked deps; `cargo audit` on `base/` crate; both upload JSON reports as CI artifacts; fails on any CVE (§5.7C/D) | Done | [architecture.md §5.7](architecture.md#57-dependency-audit-and-pinning) |

---

## Phase 3 — Feature Enrichment (1–2 Weeks per Item)

New capabilities that expand the app's core value proposition.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 3.1 | **[ASP] ✅ GNC robust loss in bundle adjustment** — GNC-TLS outer continuation loop shipped S76 (§1.32); Cauchy one-shot (§1.1C) available via `ASP_GNC_OUTER=0` | Done | [asp.md §1.32](asp.md#132-gnc-tls-bundle-adjustment-quick-win--shipped-s76) |
| 3.2 | **[ASP] ✅ OpenCV PANORAMA fallback** — `_panorama_stitch_fallback()` in `canvas.py`; uses `cv2.Stitcher_create(mode=0)` (PANORAMA); wired between Retry 3 and SCANS as last classical attempt (§1.3B, S31) | Done | [asp.md §1.3](asp.md#13-scale-and-rotation-handling) |
| 3.3 | **[ASP] ✅ Poisson blending at seam zone** — `_poisson_seam_blend()` in `compositing.py`; `cv2.seamlessClone(NORMAL_CLONE)` in ±20px seam band; hard-partition boundary + gradient minimisation; `ASP_POISSON_SEAM=1`; falls back to hard partition on cv2.error (§1.6C, S21) | Done | [asp.md §1.6](asp.md#16-ghosting-reduction-in-composite-zone) |
| 3.4 | **[ASP] ✅ SRStitcher diffusion border fill** — P1.8 in `pipeline.py` now checks `self.sr_mode and _SRSTITCHER_OK`; when both true uses `border_diffusion_fill(device=…)` from `sr_stitcher.py` (style-consistent diffusion inpainting) with TELEA fallback; when false keeps existing MFSR `inpaint_gaps` → TELEA path | Done | [asp.md §1.7](asp.md#17-recdiffusion-border-rectangling) |
| 3.5 | **[Feat] ✅ CLI batch stitching** — top-level `stitch` command: single-sequence (`-i frames/ -o out.png`) and `--batch-dir` mode (stitch each sub-dir); `--resume` skips sequences where output exists (Option C); `.stitch_progress.json` progress file tracks done/failed/skipped per sequence (Option E); `--renderer` passes `median`/`first`/`blend` to pipeline; `--output-suffix` for output naming | Done | [new_features.md §4.1](new_features.md#41-batch-stitching) |
| 3.6 | **[Feat] ✅ WD-1.4 auto-tagger via ONNX** with confidence thresholds (Options A + E). `WDTaggerWrapper(ModelWrapper)` in `backend/src/models/wd_tagger_wrapper.py`; HuggingFace download + ONNX session on first `load()`; NHWC BGR float32 preprocessing with white-bg RGBA composite + square-pad; `tag()` / `tag_batch()` / `tag_with_review()` public API; `tag_with_review()` splits auto-accepted vs review-queue tags (Option E); default threshold 0.35; `WD_TAGGER_MODEL_REPO` + `WD_TAGGER_CACHE_DIR` env overrides; 26 tests passing. | Done | [new_features.md §4.4](new_features.md#44-auto-tagger-integration) |
| 3.7 | **[Feat] ✅ Safetensors metadata viewer** — `read_metadata()` in `safetensors_metadata.py` (shape/dtype via `get_slice()` without loading tensors); `SafetensorsInspectorDialog` (`gui/src/components/`): file info, user metadata, tensor tree (sortable, 197+ rows fast); "Inspect" button in LoRA generate tab; "Inspect .safetensors..." in LoRA train tab (§4.9A) | Done | [new_features.md §4.9](new_features.md#49-safetensors-metadata-viewer) |
| 3.8 | **[Feat] ✅ Slideshow configuration** — timing, order, source-directory filter (Option A). Wallpaper tab gains `slideshow_filter_group` row (QLineEdit + Browse) below interval/order controls; stored as `filter_dir` in tab config. `_apply_vault_slideshow_defaults()` deferred-loads interval/order from vault preferences at init. `collect()`/`set_config()`/`get_default_config()` wired. Both `_sync_daemon_config()` and `toggle_daemon()` emit `filter_directories: [filter_dir]` in `.slideshow_config.json`. Rust daemon: `filter_directories: Vec<String>` field + `matches_filter()` helper; filtered queue falls back to full queue when no match (slideshow never stalls). 4 new Rust tests (6 total). | Done | [new_features.md §4.7](new_features.md#47-slideshow-improvements) |
| 3.9 | **[GUI] ✅ Increase page size + item range indicator** — default page size 100→150; "150" added to page-size combo; item range label "Items A–B of C" in every pagination bar (§3.9); updated in `_update_pagination_ui` for both gallery base classes | Done | [gui_ux.md §2.1](gui_ux.md#21-virtual-scroll-gallery) |
| 3.10 | **[GUI] ✅ QSS dark/light mode toggle** — ☀/🌙 toggle button in header; `_toggle_theme()` switches `current_theme` + calls `set_application_theme()` + saves `creds["theme"]` to vault; `set_application_theme` syncs button icon on every call; OS auto-follow (§1.10) backs off once vault preference is set | Done | [gui_ux.md §2.8](gui_ux.md#28-theme-support) |
| 3.15 | **[GUI] ✅ Configurable keyboard shortcuts** — `ShortcutRegistry` (21 actions) + `QKeySequenceEdit` table in Settings "⌨️ Shortcuts" tab; JSON persistence to `~/.image-toolkit/keybindings.json`; conflict detection; `keyPressEvent` in both gallery base classes and `ImagePreviewWindow` uses `reg.matches()`; PySide6 6.10 flag-type fix in `matches()` | Done | [gui_ux.md §2.29](gui_ux.md#229-configurable-keyboard-shortcuts) |
| 3.16 | **[GUI] ✅ QSS user override file** — `load_user_qss_override()` appends `~/.image-toolkit/user_theme.qss` as the final step in `set_application_theme()`; returns `""` silently if the file is absent | Done | [gui_ux.md §2.31](gui_ux.md#231-custom-qss-user-theme-override) |
| 3.17 | **[GUI] ✅ Auto-save/restore window geometry** — `QSettings("ImageToolkit","ImageToolkit")` saves `mainwindow/geometry` in `closeEvent()`, restored in `__init__` before `showMaximized()` | Done | [gui_ux.md §2.32](gui_ux.md#232-window-layout-and-state-profiles) |
| 3.11 | **[Perf] ✅ PyTorch GPU temporal median** — `_gpu_nanmedian()` in `rendering.py`; all 5 `np.nanmedian` calls (1 main + 2 vertical fade + 2 horizontal fade) replaced; `ASP_GPU_MEDIAN=1` env flag; lazy CUDA detection via `_cuda_available`; falls back to numpy on no-CUDA or any failure | Done | [performance.md §3.2](performance.md#32-asp-render-stage-gpu-acceleration) |
| 3.12 | **[Perf] ✅ Dynamic BiRefNet batching** — `get_mask_batch` now pre-transforms all frames, groups into VRAM-sized chunks via `_compute_batch_size()` (`torch.cuda.mem_get_info()` − 1 GB reserve, 32× raw-tensor estimate, cap=4); batched forward pass via `torch.stack`; falls back to batch=1 on CPU/failure | Done | [performance.md §3.3](performance.md#33-birefnet-inference-batching) |
| 3.13 | **[Arch] ✅ ASP unit tests for bundle_adjust, compositing, matching** — 827 unit tests in `backend/test/animation/`; covers `bundle_adjust.py`, `compositing.py`, `frame_selection.py`, `canvas.py`, `pipeline.py`, `matching.py`, `validation.py`, `config.py`, `fg_register.py` and more; each test <1 s, no GPU required | Done | [architecture.md §5.1](architecture.md#51-asp-pipeline-unit-test-coverage) |
| 3.14 | **[Arch] ✅ GitHub Actions benchmark regression CI** — `.github/workflows/benchmark.yml`: runs all 827 ASP unit tests on push to main; `uv sync --frozen --no-install-project`; artifacts retained 14 days; fails PR if any test regresses (§5.2A) | Done | [architecture.md §5.2](architecture.md#52-benchmark-regression-ci) |

---

## Phase 4 — Platform Hardening (2–4 Weeks, Some Architecture Change)

Items that improve reliability, architecture cleanliness, and long-term maintainability.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 4.1 | **[Arch] Abstract Matcher base class** — formal interface for all matcher tiers (Option B) | ~1w | [architecture.md §5.3](architecture.md#53-plugin-system-for-matchers-and-compositors) |
| 4.2 | **[Arch] ✅ `ModelWrapper` ABC + `@lazy_load` decorator + `ModelRegistry`** — `backend/src/models/base.py`; all 7 wrappers migrated; `loaded` property + `is_available()` classmethod; `@lazy_load` on public entry-points; `ModelRegistry.unload_all()` | Done | [architecture.md §5.8](architecture.md#58-model-wrapper-abstraction-layer-backendsrcmodels) |
| 4.3 | **[Arch] ✅ Weekly scheduled ASP benchmark CI** — `benchmark.yml` gains `schedule: cron: "0 6 * * 1"` (every Monday 06:00 UTC); catches dep-induced regressions that don't touch the codebase (e.g. scipy minor bump) | Done | [architecture.md §5.2](architecture.md#52-benchmark-regression-ci) |
| 4.4 | **[Arch] ✅ LogWindow upgraded (§2.17D)** — `QPlainTextEdit`, colour-coded levels, timestamps, Copy All / Save / Clear / Follow. Full collapsible global panel (Option C) remains. | Partial | [architecture.md §5.4](architecture.md#54-logging-and-diagnostics) |
| 4.5 | **[Feat] ✅ OpenAPI schema for existing REST endpoints** — `drf-spectacular>=0.27.2` added; `drf_spectacular` in `INSTALLED_APPS`; `SPECTACULAR_SETTINGS` (title/desc/version); `/api/schema/` (YAML), `/api/docs/` (Swagger UI), `/api/redoc/` (ReDoc) in `api/urls.py`; all 19 task views annotated with `@extend_schema` (tags, summary, request, 202/400 responses) | Done | [new_features.md §4.10](new_features.md#410-rest-api-layer-for-remote-control) |
| 4.6 | **[Feat] ✅ Cross-directory phash deduplication index** — `phash BIGINT` column + `idx_images_phash` index added to PostgreSQL `images` table via idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` in `schema.sql`; `update_phash(image_id, phash_int)` + `find_near_duplicates_by_phash(phash_int, threshold, limit)` on `PgvectorImageDatabase` (Hamming distance via `bit_count(phash::bit(64) # query::bit(64))`); `compute_phash(path)` + `PhashDeduplicator` (index_image/index_directory/find_duplicates_for/find_all_duplicate_groups) in `backend/src/core/phash_deduplicator.py`; 10 unit tests | Done | [new_features.md §4.6](new_features.md#46-image-deduplication-across-directories) |
| 4.7 | **[Feat] ✅ KDE per-monitor wallpaper via D-Bus** — `find_qdbus_binary()` auto-detects `qdbus6`/`qdbus-qt6`/`qdbus`/`qdbus-qt5`; `evaluate_kde_script_dbus_python()` pure-Python D-Bus fallback (bypasses CLI); `evaluate_kde_script_with_fallback(qdbus, script)` chain (CLI → dbus-python → clear error); all three KDE script call-sites in `WallpaperManager` migrated; `wallpaper_tab.py` uses `find_qdbus_binary()` instead of inline 2-name check; works on Wayland+KDE where `DESKTOP_SESSION` ≠ `plasma` | Done | [new_features.md §4.5](new_features.md#45-multi-monitor-wallpaper-support) |
| 4.8 | **[Perf] ✅ psycopg3 connection pool** — `PooledPgvectorDatabase` in `backend/src/database/pooled_image_database.py` uses `psycopg_pool.ConnectionPool` (psycopg3 sync pool, min=2, max=10). Drop-in replacement for `PgvectorImageDatabase`: identical public API, each method borrows a thread-safe connection from the pool, returns it automatically. Eliminates single-connection bottleneck where multiple QThread workers raced on `self.conn`. `psycopg[pool]>=3.2` added to `pyproject.toml`. Row access via `psycopg.rows.dict_row` row_factory; duplicate-column queries (`get_all_subgroups_detailed`, `get_statistics`) use per-cursor `tuple_row` override. `VACUUM`/`REINDEX` use a direct `autocommit=True` connection outside the pool. 22 unit tests using mocked pool/connection, no live DB required. | Done | [performance.md §3.4](performance.md#34-database-query-optimisation) |
| 4.9 | **[GUI] QListView + QAbstractItemModel virtual scrolling** — prototype against `AbstractClassTwoGalleries` (Option A) | ~1w | [gui_ux.md §2.1](gui_ux.md#21-virtual-scroll-gallery) |
| 4.10 | **[GUI] Global hotkey table in settings** — JSON-backed `QShortcut` (Option B) | ~1w | [gui_ux.md §2.3](gui_ux.md#23-keyboard-navigation) |
| 4.12 | **[GUI] ✅ Named layout profiles** — extend "System Preference Profiles" to bundle geometry + splitter state + appearance settings (§2.32B). `_get_current_ui_preferences()` now snapshots `saveGeometry()` as base64 + all `splitters/*` QSettings keys as a `layout_splitters` dict. New `_apply_layout_from_profile()` restores geometry to the main window immediately and writes splitter states to QSettings (active on next tab init). Both Load Profile and Use Profile call the helper. | Done | [gui_ux.md §2.32](gui_ux.md#232-window-layout-and-state-profiles) |
| 4.13 | **[Feat] ✅ Appearance profiles** — extend vault profiles to include accent colour, font scale, density (Option A). `_get_current_ui_preferences()` now bundles `accent_color_dark/light`, `font_scale`, `ui_density` alongside `theme`/`active_tab_configs`. New `_apply_appearance_from_profile()` helper updates swatches + spinbox + combo. Load/Use profile both call helper. Login profile selection merges appearance keys into `preferences`. | Done | [new_features.md §4.12](new_features.md#412-appearance-profiles) |
| 4.11 | **[GUI] ✅ Thumbnail slider + per-tab persistent size** — `QSlider` (64–512 px, step 16) in every pagination bar; `_save_thumbnail_size()` on slider release and after Ctrl+scroll; `_load_thumbnail_size()` at `__init__` time keyed by `{ClassName}/thumbnail_size`; `_sync_thumb_slider()` keeps all sliders in sync; both gallery base classes updated | Done | [gui_ux.md §2.2](gui_ux.md#22-gallery-thumbnail-size-control) |

---

## Phase 5 — Advanced Features (1–3 Weeks per Item, Research Required)

Higher-complexity features that depend on Phase 3–4 infrastructure or require experimentation.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 5.1 | **[Feat] OpenCLIP semantic search** — dual embedding column in PostgreSQL (Options A + C) | ~2w | [new_features.md §4.3](new_features.md#43-clip-based-semantic-image-search) |
| 5.2 | **[Feat] GUI batch stitching** — directory-level batch mode with progress list (Option A) | ~1w | [new_features.md §4.1](new_features.md#41-batch-stitching) |
| 5.3 | **[Feat] FFmpeg scrolling video export** (Option B) | ~1w | [new_features.md §4.2](new_features.md#42-export-stitched-panorama-to-scrolling-video) |
| 5.4 | **[Feat] ComfyUI drag-and-drop gallery integration** (Option C) | ~1w | [new_features.md §4.8](new_features.md#48-comfyui-workflow-integration-for-post-processing) |
| 5.5 | **[Feat] WD tagging review queue** — PostgreSQL-backed human-in-the-loop (Option C) | ~1w | [new_features.md §4.4](new_features.md#44-auto-tagger-integration) |
| 5.6 | **[Feat] REST API trigger for desktop operations + WebSocket status** (Options B + C) | ~2w | [new_features.md §4.10](new_features.md#410-rest-api-layer-for-remote-control) |
| 5.7 | **[ASP] RLHF Bayesian parameter search** — optuna over gain, feather, seam cost (Option B) | ~1w | [asp.md §1.10](asp.md#110-rlhf-loop-integration) |
| 5.8 | **[ASP] Similarity transform (scale+rotation+translation) matcher** — `estimateAffinePartial2D` (Option E) | ~1w | [asp.md §1.3](asp.md#13-scale-and-rotation-handling) |
| 5.9 | **[ASP] Seam DP cache for RLHF iteration** — keyed by `(frame_ids, seam_cost_config)` (Option D) | ~1d | [asp.md §1.5](asp.md#15-stage-11-composite-performance) |
| 5.10 | **[Arch] Compositor registry** — same pattern as Matcher (Option E) | ~1w | [architecture.md §5.3](architecture.md#53-plugin-system-for-matchers-and-compositors) |
| 5.11 | **[Perf] Rust memory-mapped output buffer** — `memmap2` for >10K px panoramas (Option C) | ~2d | [performance.md §3.1](performance.md#31-rust-streaming-image-merger) |

---

## Phase EXT — Browser Extension (Capture, Build System & App Integration)

Upgrades the `extension/` WebExtension from a minimal image saver into a first-class companion to the desktop app. Full detail, options, and dependency graph in [extension.md](extension.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| EXT.1 | **[Ext] ✅ Webpack multi-browser build system** — `extension/webpack/` generates per-browser `manifest.json` (chrome, firefox, edge, brave) from `manifest.base.json` + overlays; replaces the three hand-maintained manifests; per-browser dist zips | ~2d | [extension.md §7.1](extension.md#71-webpack-multi-browser-build-system) |
| EXT.2 | **[Ext] ✅ TypeScript migration + shared core** — typed message contract, single browser-API adapter, typed `storage.local` schema | ~2d | [extension.md §7.2](extension.md#72-typescript-migration--shared-core) |
| EXT.3 | **[Ext] ✅ Unified Manifest V3** — drop MV2 Firefox manifest; MV3 everywhere with per-browser overlays (Firefox 109+) | ~1d | [extension.md §7.3](extension.md#73-unified-manifest-v3) |
| EXT.4 | **[Ext] 🔄 Options page redesign** — popup (profile switcher, turbo, bridge status) + full options tab (profiles, site rules, app connection) | ~2–3d | [extension.md §7.4](extension.md#74-options-page-redesign) |
| EXT.5 | **[Ext] 🔄 Local app bridge** — Phase A: token-authenticated localhost Django endpoints (`/api/extension/…`); Phase B: native messaging host per browser | ~3d + ~1w | [extension.md §7.5](extension.md#75-local-app-bridge-http--native-messaging) |
| EXT.6 | **[Ext] ✅ In-browser duplicate search** — right-click image → pHash search (`PhashDeduplicator`, §4.6) of the user-configured directory + subdirectories; match list with thumbnails; optional auto-check on turbo downloads | ~4d | [extension.md §7.6](extension.md#76-in-browser-duplicate-search) |
| EXT.7 | **[Ext] 🔄 Send to Image Toolkit** — ingest with source URL/page metadata, immediate pHash + embedding indexing | ~3d | [extension.md §7.7](extension.md#77-send-to-image-toolkit) |
| EXT.8 | **[Ext] Visual similarity search from browser** — right-click → BGE-M3/CLIP vector search of local library (gated on §5.1 embedding index) | ~4d | [extension.md §7.8](extension.md#78-visual-similarity-search-from-browser) |
| EXT.9 | **[Ext] Bulk page grabber** — one-click download of all page images+videos; in-page click-to-select overlay with download/cancel bar; later: grid preview with size/format filters + dup-check badges | ~1w | [extension.md §7.9](extension.md#79-bulk-page-grabber) |
| EXT.10 | **[Ext] 🔄 Per-site folder rules + filename templating + metadata sidecar** — domain→profile rules, `{site}/{date}_{name}.{ext}` templates, optional provenance JSON sidecar | ~4d | [extension.md §7.10](extension.md#710-per-site-folder-rules-filename-templating--metadata-sidecar) |
| EXT.11 | **[Ext] 🔄 Full-resolution extraction** — srcset/`<picture>`/lazy-load/CSS-background/canvas candidates; per-site URL upgrade table | ~4d | [extension.md §7.11](extension.md#711-full-resolution-extraction) |
| EXT.12 | **[Ext] 🔄 Turbo mode polish** — capture flash + badge, modifier-key mode, per-site enable list, download history panel | ~3d | [extension.md §7.12](extension.md#712-turbo-mode-polish) |
| EXT.13 | **[Ext] ✅ Duplicate tab highlighter** — scan current window's tabs, group duplicates by normalized URL; colored tab groups on Chromium, badge + popup set list on Firefox; keep-first/close-rest actions | ~2d | [extension.md §7.13](extension.md#713-duplicate-tab-highlighter) |
| EXT.14 | **[Ext] App-powered CV operations** — right-click → BiRefNet background removal, Real-ESRGAN upscale-before-save, WD14 auto-tag on ingest, OCR extraction + local translation via the bridge | ~1.5w | [extension.md §7.14](extension.md#714-app-powered-cv-operations) |
| EXT.15 | **[Ext] Media capture suite** — native-res video frame grabber (+burst), GIF/APNG/WebP frame extractor, webtoon strip capture → ASP stitch, video clip → GIF/WebP, video downloader with time-range cutting (ffmpeg app-side) | ~2.5w | [extension.md §7.15](extension.md#715-media-capture-suite) |
| EXT.16 | **[Ext] 🔄 Image analysis utilities** — EXIF + embedded SD/ComfyUI prompt metadata inspector, reverse-search shortcuts (SauceNAO/trace.moe/Lens/IQDB), client-side pHash pre-check with app hash snapshot, local-ML reverse search (transformers.js fallback) | ~2w | [extension.md §7.16](extension.md#716-image-analysis-utilities) |

**Dependency order:** EXT.1 → EXT.2 → (EXT.3, EXT.4) foundation first; EXT.5A → EXT.6 → EXT.7 (bridge before integration features); EXT.11 → EXT.9 → EXT.12 (extractor before grabber/turbo); EXT.8 gated on §5.1; EXT.5B last.

---

## Phase Arch — Code Quality & Developer Experience (Days to 2 Weeks, No New Features)

Targeted refactors that reduce maintenance burden, improve onboarding, and prevent regressions. Items are ordered by ascending effort; all are independent and can be parallelised. Full detail in [architecture.md](architecture.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| A.1 | **[Arch] ✅ Pyright `basic` mode** — `typeCheckingMode = "basic"` in `pyproject.toml` | Done | [architecture.md §5.5B](architecture.md#55-gradual-static-type-safety-migration) |
| A.2 | **[Arch] ✅ Eliminate silent `print()` errors** — `conversion_worker.py` (3×), `duplicate_scan_worker.py` (2×), `gan_wrapper.py` (1×), `lo_ra_tuner.py` (1×); all replaced with `logger.warning/error` | Done | [architecture.md §5.15C](architecture.md#515-fault-isolation--error-boundary-protocol) |
| A.3 | **[Arch] ✅ Remove `# --- Relocated Nested Imports ---` comment blocks** — single grep-and-edit pass across all model wrappers; consolidate into standard PEP 8 import order | Done | [architecture.md §5.8D](architecture.md#58-model-wrapper-abstraction-layer-backendsrcmodels) |
| A.4 | **[Arch] ✅ `__all__` hygiene pass** — 15 `__init__.py` files updated: `backend/src/{models,web,core,pipeline,utils,controller,__init__}` and `gui/src/{utils,styles,helpers/{image,video,web,core},tabs,tabs/core/common}`; empty files get `[]`; populated files get explicit `__all__` lists | Done | [architecture.md §5.11D](architecture.md#511-circular-import-prevention--module-boundary-documentation) |
| A.5 | **[Arch] ✅ QSettings key validation at startup** — `SETTINGS_SCHEMA` dict + `SETTINGS_PREFIX_TYPES` + `_validate_settings()` in `app.py`; called after `QApplication()` creation; logs warnings for type-mismatched keys and clears them; unknown keys logged at DEBUG | Done | [architecture.md §5.14D](architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.6 | **[Arch] ✅ `@log_call` timing decorator** — `backend/src/utils/decorators.py`; logs entry/exit + elapsed ms at DEBUG; compatible with §5.4B trace JSON; exported via `backend/src/utils/__init__.py` | Done | [architecture.md §5.13C](architecture.md#513-decorator-library-for-cross-cutting-concerns-backendsrcutilsdecoratorspy) |
| A.7 | **[Arch] ✅ Metaclass docstring + `_load_thumbnail_size` extraction** — extended docstring in `meta_abstract_class_gallery.py` explaining Qt metaclass fusion + injection rationale; `save_thumbnail_size`/`load_thumbnail_size` extracted to `gui/src/utils/thumbnail_size.py`; both gallery base classes delegate to shared functions | Done | [architecture.md §5.10C](architecture.md#510-gallery-base-class-consolidation-guisrcclasses) |
| A.8 | **[Arch] ✅ TYPE_CHECKING guards for heavy GUI→backend imports** — `from __future__ import annotations` + `if TYPE_CHECKING:` for `AnimeStitchPipeline` and other PyTorch imports in GUI workers; reduces cold-start by ~2–4s | Done | [architecture.md §5.11B](architecture.md#511-circular-import-prevention--module-boundary-documentation) |
| A.9 | **[Arch] ✅ ML wrapper contract tests (mock-based)** — one `TestXxxWrapperContract` class per wrapper in `backend/test/models/`; verifies output shape/dtype, `unload()` idempotency, `loaded` property; no GPU required; <1s per test | Done | [architecture.md §5.16A](architecture.md#516-contract-testing-for-ml-model-wrappers-backendsrcmodels) |
| A.10 | **[Arch] ✅ mypy baseline config + TypedDict worker configs** — `[tool.mypy]` section in `pyproject.toml` (permissive baseline); `ConversionConfig`, `DeletionConfig`, `MergeConfig`, `StitchConfig` TypedDicts in `gui/src/helpers/core/config_types.py`; wired into `ConversionWorker`, `DeletionWorker`, `MergeWorker` | Done | [architecture.md §5.5A](architecture.md#55-gradual-static-type-safety-migration) |
| A.11 | **[Arch] ✅ `AppSettings` GUI facade** — `gui/src/utils/settings.py` singleton; replaces 20+ inline `QSettings("ImageToolkit","ImageToolkit")` constructor calls; typed properties per key; wired into both gallery base classes, `main_window.py`, `splitter_persistence.py`, `listings_common.py`, `thumbnail_size.py` | Done | [architecture.md §5.14A](architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.12 | **[Arch] ✅ `get_asp()` helper in `config.py`** — `get_asp(key, default="")` reads `os.environ[key]` with fallback; `ConfigError` raised in `validate_asp_config` strict mode; exported from `backend/src/animation/config.py` | Done | [architecture.md §5.14B](architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.13 | **[Arch] ✅ Custom exception hierarchy** — `backend/src/exceptions.py` with `ImageToolkitError` → `PipelineError`/`AlignmentFailedError`/`CanvasError`/`FallbackExhaustedError`/`ModelLoadError`/`ConfigError`; bare `RuntimeError`/`ValueError` replaced in `animation/pipeline.py`, `animation/canvas.py`, `animation/config.py`, `models/birefnet_wrapper.py`; `BaseQThreadWorker` three-tier handler routes `AlignmentFailed`/`Canvas` as WARNING, `Pipeline`/`Model`/`Config` as ERROR | Done | [architecture.md §5.15A](architecture.md#515-fault-isolation--error-boundary-protocol) |
| A.14 | **[Arch] ✅ `BaseQThreadWorker` + `BaseQRunnableWorker` + `_WorkerSignals`** — `gui/src/helpers/base.py`; uniform `cancel()`/`stop()`, exception routing; `SearchWorker` migrated to `BaseQRunnableWorker` | Done | [architecture.md §5.9](architecture.md#59-worker-thread-base-class--lifecycle-standardisation-guisrchelpers) |
| A.15 | **[Arch] NumPy-style docstrings + Mermaid class diagrams** — all public methods in `backend/src/models/` and `backend/src/animation/`; hierarchy diagrams in `backend/src/models/__init__.py` and `gui/src/classes/__init__.py` | ~3d | [architecture.md §5.12](architecture.md#512-codebase-documentation--diagrams) |
| A.16 | **[Arch] ✅ `AbstractGalleryBase` + real `common_*` methods** — `gallery_base.py` (574 lines); shared init state extracted; 9 injected `_common_*` functions → real inherited `common_*` methods; 10 duplicate helpers removed from both gallery files; `_on_layout_change`/`get_default_config`/`set_config` as `@abstractmethod`; metaclass 397→18 lines | Done | [architecture.md §5.10A](architecture.md#510-gallery-base-class-consolidation-guisrcclasses) |
| A.17 | **[Arch] ✅ `import-linter` contracts** — 3 contracts in `pyproject.toml`; enforces backend-core-no-GUI, gui.src.utils is leaf, gui.src.classes no-tabs; `import-linter>=2.0` added to dev deps; `PYTHONPATH=. lint-imports` runs clean; pydeps SVG deferred to a dedicated docs PR | Done | [architecture.md §5.11A](architecture.md#511-circular-import-prevention--module-boundary-documentation) |

**Dependency order:** A.1–A.7 are independent Quick Wins (batch in one PR each). A.8 depends on A.4 (`__all__` first). A.9 is independent. A.13 → A.14 (exception hierarchy makes error boundary meaningful). A.11 + A.12 can be done together (settings facade sprint). A.16 depends on A.7.

---

## Phase 6 — Long-term Research (Months, Exploratory)

Aspirational improvements requiring significant experimentation, external data, or architectural investment. No fixed timeline.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 6.1 | **[ASP] Online DRL agent for ECC/registration** — wire `rlhf_trainer.py` into Stage 8 | [Long-term] | [asp.md §1.10](asp.md#110-rlhf-loop-integration) |
| 6.2 | **[ASP] RANSAC/MAGSAC++ pre-filter for >40% outlier datasets** | [Research] | [asp.md §1.1](asp.md#11-bundle-adjustment-hardening) |
| 6.3 | **[ASP] ToonCrafter fill for overlap ghost reduction** — final-quality mode; see ML.4 for wiring plan | [Research] | [asp.md §3.6](asp.md#36-tooncrafter-seam-synthesis--wiring-the-generative-fallback-priority-medium) |
| 6.4 | **[ASP] Background histogram matching via CLAHE** for complex dark scenes | [Research] | [asp.md §1.4](asp.md#14-gain-clamp-widening-for-dark-scenes) |
| 6.5 | **[Feat] AnimeCLIP domain-specific CLIP fine-tune** — swap into §5.1 once validated | [Research] | [new_features.md §4.3](new_features.md#43-clip-based-semantic-image-search) |
| 6.6 | **[Feat] File system watcher auto-stitch** — `watchdog`/`inotify` triggered batch | [Research] | [new_features.md §4.1](new_features.md#41-batch-stitching) |
| 6.7 | **[Feat] Mobile remote wallpaper + push notifications** — depends on §5.6 REST API | [Exploratory] | [new_features.md §4.5](new_features.md#45-multi-monitor-wallpaper-support) |
| 6.8 | **[Arch] Hypothesis property-based tests for bundle_adjust and compositing** | [Research] | [architecture.md §5.1](architecture.md#51-asp-pipeline-unit-test-coverage) |
| 6.9 | **[Perf] CUDA seam DP via PyTorch scatter/gather** — GPU seam computation | [Research] | [asp.md §1.5](asp.md#15-stage-11-composite-performance) |
| 6.10 | **[Arch] Full mypy strict coverage** — all modules under `disallow_untyped_defs = true`; end state of §5.5 gradual migration | [Long-term] | [architecture.md §5.5](architecture.md#55-gradual-static-type-safety-migration) |

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

    P0["Phase 0\nASP Foreground Assembly\n(Priority 0)"]:::fix:::active
    PML["Phase ML\nML-Driven Modernisation\n(Research)"]:::research:::planned
    PCG["Phase CG\nContent Generation"]:::feature:::planned
    P1["Phase 1\nImmediate Wins"]:::augment:::active
    P2["Phase 2\nCore QoS"]:::augment:::planned
    P3["Phase 3\nFeature Enrichment"]:::feature:::planned
    P4["Phase 4\nPlatform Hardening"]:::infra:::planned
    PARCH["Phase Arch\nCode Quality"]:::refactor:::planned
    P5["Phase 5\nAdvanced Features"]:::feature:::planned
    P6["Phase 6\nLong-term Research"]:::research:::planned
    PEXT["Phase EXT\nBrowser Extension"]:::integration:::planned

    P0  ==>  PML
    P0  -->  P1
    P1  ==>  P2
    P2  -->  P3
    P2  -->  P4
    P2  -->  PARCH
    P3  -->  P5
    P4  -->  P5
    PARCH --- P3
    PARCH --- P4
    P5  -->  P6
    P1  -->  PCG
    PML -->  P3

    P4  -->|"4.5 OpenAPI + 4.6 phash\nunblock EXT.5/EXT.6"| PEXT
    PEXT -->|"EXT.8 similarity\nneeds 5.1 CLIP index"| P5

    %% key item-level dependencies
    P3 -->|"3.13 tests\nunblocks 3.14 CI"| P4
    P4 -->|"4.2 ModelWrapper\nunblocks A.9"| PARCH
    P2 -->|"2.5 quality gate\nunblocks 5.7 RLHF"| P5
```

---

## Advanced Feature Roadmap

### Overview

This roadmap defines the feature evolution and quality-of-life improvements for the Image-Toolkit ecosystem. It is grounded in a deep audit of the current codebase (May 2026) and covers every layer of the stack.

The application follows a **Tri-Interface Strategy**:
1. **PySide6 Desktop App** — The heavyweight native powerhouse for local ML inference, deep OS integration, and interactive image pipeline control.
2. **React / Tauri Web App** — The cross-platform, network-ready hub for library management, remote task dispatch, and device syncing.
3. **Android / iOS Mobile Apps** — Companion clients for remote monitoring, on-device preview, and library browsing.

Each item is tagged by priority: **[CRITICAL]**, **[HIGH]**, **[MEDIUM]**, or **[LOW]**.

---

### 1. PySide6 Desktop Application (The Pro Environment)

#### A. Advanced ML UI & Interactive Pipelines

##### [CRITICAL] SD3 ControlNet & IP-Adapter Support
`backend/src/models/sd3_wrapper.py:62` has a `TODO` for ControlNet. Switch the pipeline to `StableDiffusion3ControlNetPipeline` when a ControlNet model path is provided. In `DDMGenerateTab`, add a ControlNet image drop-zone, conditioning scale slider, and preprocessor selector (Canny, Depth, OpenPose). Separately, add IP-Adapter support via `diffusers`' `IPAdapterMixin` for reference-image conditioning — expose a reference image input and weight slider. Both unblock character-consistency and pose-guided workflows on the SD3 backbone.

##### [CRITICAL] Complete CLI Dispatcher Commands
`backend/dispatcher.py` has three disconnected dispatch paths: merge (line 56), database (line 91), and model (line 95) all either print a placeholder or are unreachable. Wire all three so the app is fully scriptable from the command line. The `--recursive` flag for batch conversion (line 46) also needs to be forwarded to `ImageFormatConverter.convert_batch()`.

##### [HIGH] Dynamic ComfyUI Dashboard
Build a native PySide6 dynamic form generator that parses `workflow_api.json` templates (like the 7-stage Illustrious XL pipeline in `backend/config/inference/sdxl_comfyui.yaml`) and auto-generates UI controls — sliders, dropdowns, seed spinboxes, and node-selection widgets — mapped to `parameters.json` keys. The `ComfyGenerateTab` currently requires hand-editing raw JSON; this replaces it with a generated form that calls the ComfyUI API transparently. Add a template browser to save, load, and share workflow presets.

##### [HIGH] Panorama Stitch UI (`StitchTab`)
Create a dedicated `StitchTab` using `QGraphicsView` to expose `stitch_net.py` and `loftr_wrapper.py` interactively. Users should be able to load two or more frames, preview LoFTR keypoint matches as an overlay, drag alignment anchors to correct stitching errors before rendering, preview the "Master-Cel" masking boundaries from `anime_stitch_pipeline.py`, and export stitched panoramas at up to 4× source resolution via `image_merger.rs`. Queue batch stitch jobs and monitor them via the existing `QThreadPool` worker pattern.

##### [HIGH] Interactive Background Removal (BiRefNet Integration)
Integrate `birefnet_wrapper.py` into the `ConvertTab` as an optional post-processing step. After format conversion, a "Remove Background" toggle passes each output image through BiRefNet. Add an interactive mask-refinement widget using QPainter brush strokes to correct matting errors before saving. Output alpha channel as transparent PNG. Run as a `QRunnable` to keep the main thread free.

##### [HIGH] Full Fine-Tune UI Tab (`FullFTTrainTab`)
`backend/src/models/full_finetune.py` exists but has no dedicated GUI tab. Add a `FullFTTrainTab` with dataset path, gradient checkpointing toggle, batch size, mixed precision selector, and DeepSpeed ZeRO stage selector. The `LoRATrainTab` partially covers this; full fine-tuning of SDXL/Flux needs its own surface.

##### [HIGH] Flux Dev Generation Tab
`backend/config/model/flux_dev.yaml` is configured but there is no dedicated generation tab for `FLUX.1-dev`. Extend the `DDMGenerateTab` model selector to include Flux, routing to a `FluxPipeline` backend path. Expose its unique CFG-free distilled guidance scale and step count parameters as first-class controls, not buried in an advanced JSON field.

##### [MEDIUM] DreamBooth Prior Preservation Training
`backend/config/training/dreambooth.yaml` exists but prior preservation loss is not surfaced in `LoRATrainTab`. Add a "DreamBooth Mode" toggle that unlocks a class images directory selector, prior loss weight slider, and num-class-images field. Wire these into `DreamBoothTuner.train()`.

##### [MEDIUM] Multi-GPU Training via Accelerate
Current training runs on a single device. Add Accelerate config generation into training tabs. When multiple CUDA devices are detected, expose a device-selection multi-check and auto-write an `accelerate_config.yaml`. Pass `--multi_gpu` to the training pipeline. Essential for multi-stage LoRA training on the 3090 Ti alongside other CUDA workloads.

##### [MEDIUM] R3GAN Evaluate Tab — Live Loss Curve Visualization
`r3gan_evaluate_tab.py` only shows scalar metrics. Embed a `pyqtgraph` line chart that reads from `training_hooks.py` diagnostics and plots discriminator loss, generator loss, and FID over epochs in real time during training.

##### [MEDIUM] LyCORIS / DoRA Method Selector
`lora_diffusion.py` supports LoCon, LoHa, LoKr, DoRA, and rsLoRA via PEFT but the `LoRATrainTab` only exposes a fraction of these. Add a method selector dropdown that surfaces all available PEFT methods with a brief description tooltip. Show the relevant method-specific hyperparameters (e.g., LoCon convolution dimension) only when that method is active.

##### [LOW] Video Wallpaper with mpv
Expand `WallpaperTab` to support video wallpapers. On Linux, manage an `mpv` subprocess alongside the existing `qdbus-qt6` D-Bus wallpaper daemon. On Windows, use the existing COM pathway. Add seamless-loop detection and per-monitor assignment. Use subprocess-based mpv (not libmpv) to avoid native C++ library conflicts with the JPype JVM.

##### [LOW] Training Run History Browser
Add a training history panel to `TrainTab` that reads checkpoint directories and surfaces: model name, architecture, dataset path, epoch count, final loss values, and sample generation grid. Let users resume a past run, compare metrics across runs, or delete old checkpoints with a single click.

---

#### B. OS Integration & Media Handling

##### [HIGH] Hardware-Accelerated Frame Extraction
Replace `cv2.VideoCapture` in the `ImageExtractorTab` and `task_extract_frames()` with a C++ FFmpeg binding. Extend `base/src/core/convert.cpp` with `extract_frames()` using `libavcodec`/`libavformat` for hardware-decode support (NVDEC, VAAPI). Expose via pybind11 as `base.core.extract_frames(path, output_dir, start_ms, end_ms, fps_limit, hw_device)`. This will be dramatically faster than OpenCV for high-resolution H.264/H.265 sources.

##### [HIGH] Video Converter — Quality & Codec Controls
`base/src/core/convert.cpp`'s `convert_video()` uses a subprocess to ffmpeg. Build it out with CRF/bitrate selection, hardware encode (NVENC, VAAPI), audio track control (copy / re-encode / strip), and a full container format matrix (mp4, mkv, webm, mov). Surface all options in a `VideoConvertTab` alongside the existing image conversion workflow.

##### [MEDIUM] System Tray Integration & Daemon Mode
Add a `QSystemTrayIcon` so the desktop app runs in the background while the slideshow daemon and wallpaper rotation are active. The tray menu should expose: pause/resume slideshow, add wallpaper folder, open main window, and quit. The slideshow daemon (`base/src/utils/slideshow_daemon.rs`) already runs as a separate process — the tray is the missing control surface.

##### [MEDIUM] Drag-and-Drop Desktop Integration
Enable OS-level drag-and-drop targets for all conversion, merge, and extraction tabs. Accept `text/uri-list` and `application/x-qabstractitemmodeldatalist` mime types so users can drag files directly from a file manager into gallery panels, bypassing the directory picker entirely.

##### [MEDIUM] Batch Rename with Pattern Templates
Add a `RenameTab` or toolbar action that applies pattern-based renames to selected files. Support tokens: `{index}`, `{date}`, `{resolution}`, `{group}`, `{tag}`, `{hash}`. Preview the rename mapping in a before/after table before committing. Support undo via the edit recipe system.

##### [LOW] macOS Wallpaper Support
Add a macOS variant for wallpaper setting using `NSWorkspace.setDesktopImageURL(_:for:options:)` via a small Swift helper binary. Guard it behind `sys.platform == "darwin"` in `backend/src/core/wallpaper.py`.

---

#### C. Gallery & Image Management QoL

##### [HIGH] Non-Destructive Edit Recipes
Implement an edit-history JSON format for color grade, crop, and resize. Rather than overwriting source pixels, store a `recipe.json` sidecar per image listing ordered operations with parameters. Apply the recipe chain in memory on open. "Bake" to disk only on explicit export (`Ctrl+E`). Support recipe sharing by exporting the JSON. Requires a `RecipeEngine` class in the backend and a `RecipeEditor` panel in `ConvertTab`.

##### [HIGH] Intelligent Duplicate Grouping with Visual Diff
Enhance `DuplicateFinder` to present near-duplicate collisions side-by-side:
- Pixel-level diff heatmap via OpenCV `absdiff()`.
- File metadata comparison (size, resolution, format, date) alongside the diff.
- Batch resolution actions: "Keep Largest", "Keep Newest", "Keep All Non-Watermarked" (using BiRefNet to detect watermark regions).
- Wire into the existing `PropertyComparisonDialog` component in `gui/src/components/`.

##### [HIGH] Global Keyboard Shortcuts & Command Palette
Add a command palette (`Ctrl+K`) with fuzzy-searchable access to all tab actions. Implement `QShortcut` bindings:
- `Ctrl+O` — Open directory picker in active tab.
- `Ctrl+Enter` — Run the active tab's primary action.
- `Ctrl+Z` / `Ctrl+Shift+Z` — Undo/Redo for edit recipes.
- `Space` — Toggle full-screen preview.
- `Delete` — Delete selected items with confirmation.
- `Ctrl+F` — Focus the search field.

##### [HIGH] Session State Persistence
Tab state (input paths, parameters, selected files) is lost on restart. Add a `SessionManager` that serializes all tab state to JSON on `QApplication.aboutToQuit` and restores it on launch. Include a configurable MRU list (last 10 paths) per tab.

##### [HIGH] Gallery Multi-Select with Batch Actions Toolbar
When multiple images are selected: show a floating action toolbar with Convert, Delete, Add to Group, and Export Captions actions. Add rubber-band marquee selection (click-drag), `Ctrl+A` to select all, `Ctrl+Shift+A` to invert selection.

##### [MEDIUM] Configurable Thumbnail Size Slider
Add a thumbnail size slider (64px → 512px) in the gallery toolbar that dynamically resizes thumbnails without reloading from disk. The `LRUImageCache` stores full `QImage` — use `QPixmap.fromImage().scaled()` at render time for instant resize.

##### [MEDIUM] Image Preview Enhancements
Expand `image_preview_window.py` to support pan and zoom (mouse wheel + drag), side-by-side A/B comparison mode (original vs. processed), EXIF/XMP metadata panel toggle, copy-to-clipboard shortcut, and "Open in external editor" action.

##### [MEDIUM] Unified Progress Overlay
Replace per-tab progress widgets with a unified bottom-anchored `ProgressOverlay` panel showing: a progress bar per active operation with label, ETA, and cancel button; a badge count on each tab's header showing pending/running operations; a notification bell for completions.

##### [MEDIUM] Dark/Light Theme Toggle
Add a theme toggle in `SettingsWindow`. Implement `dark.qss` and `light.qss` stylesheets applied via `QApplication.setStyleSheet()`. Persist the choice in the config file. Default to the system color scheme via `QGuiApplication.palette()`.

##### [LOW] LRU Cache Size Configurability
`gui/src/utils/lru_image_cache.py` hardcodes cache sizes (found=300, selected=200, single=300). Expose these in `SettingsWindow` with a memory usage readout in the status bar. Users with limited RAM can reduce; users with 32GB+ can increase for snappier gallery navigation.

##### [LOW] Onboarding & First-Launch Wizard
A `FirstLaunchWizard` dialog that guides new users through: setting the local source path, testing the PostgreSQL connection, unlocking VaultManager credentials, and selecting the default wallpaper folder.

---

### 2. React / Tauri Web Application (The Cross-Platform Hub)

#### A. Real-Time Network Architecture

##### [CRITICAL] Django Channels / WebSocket Live Progress
Upgrade the REST-only API to include WebSocket endpoints via Django Channels. Define a `TaskProgressConsumer` that forwards Celery progress events to the browser. Add a React `useTaskProgress(taskId)` hook that drives a live progress bar, ETA display, and stdout log stream for all long-running operations — batch conversion, crawling, training.

##### [HIGH] Virtualized Media Galleries
All gallery queries currently load entire result sets into the DOM. Implement `@tanstack/react-virtual` as the scroll engine for `WallpaperGallery` and every search result list. Fetch paginated slices from Django (page size 100), pre-fetch the next page on scroll, and dispose offscreen tiles. Essential for 100,000+ image libraries.

##### [HIGH] Missing API Endpoints
Several backend capabilities have no REST surface at all. Add:
- `GET /api/status/<task_id>/` — Celery task progress polling.
- `DELETE /api/tasks/<task_id>/` — Celery task cancellation.
- `GET /api/db/groups/` — List all groups and subgroups.
- `GET /api/db/search/` — Semantic vector search with query, filters, and pagination.
- `GET /api/db/stats/` — Image count, group count, vector coverage.
- `POST /api/db/embed/` — Trigger CLIP embedding for a given group or directory.
- `POST /api/train-lora/` — LoRA training task (only GAN training is wired today).
- `POST /api/run-birefnet/` — Batch background removal.
- `POST /api/stitch/` — Panorama stitching pipeline.

##### [HIGH] Saved Search Presets & History
Add a `SavedSearch` model and endpoints (`POST /api/search/presets/`, `GET /api/search/presets/`). In the React `SearchTab`, render a sidebar of saved searches that can be re-run or edited. Store the last 50 searches in `localStorage` as a quick-access history.

##### [MEDIUM] Batch Operation Pipeline Builder
Add a workflow-style drag-and-drop pipeline composer in the React frontend. Users build a sequence of operations (Crawl → Convert → Embed → Tag) into a named pipeline, then trigger it as a Celery `chain()`. Add a `POST /api/pipeline/` endpoint. The Celery primitive already supports chaining; the frontend just needs the composition UI.

##### [MEDIUM] LAN Remote Access Mode (mDNS)
Register the service as `_imagetoolkit._tcp.local` using the `zeroconf` Python library. Bind Django to `0.0.0.0` with token authentication. Display the LAN URL and QR code in the desktop app's `SettingsWindow` so mobile clients can connect without manual IP configuration.

##### [LOW] Progressive Web App (PWA) Manifest
Add a `manifest.json` and service worker to the React frontend so the web app can be installed as a PWA on desktop and Android Chrome. Cache the app shell and static assets, and implement a background-sync queue for offline task submission that drains when the connection restores.

---

#### B. UI & UX QoL

##### [HIGH] Dark Mode & Theme System
Add CSS custom properties (design tokens) for colors, spacing, and typography. Implement `prefers-color-scheme` auto-detection and a manual toggle stored in `localStorage`. All components should reference token variables rather than hardcoded hex values.

##### [HIGH] Virtual Album Browser
Add a "Virtual Albums" section to the `DatabaseTab` backed by live HNSW vector queries. Users type a natural language query (e.g., *"cyberpunk cityscapes at night with rain"*) and save it as a named album. The album auto-refreshes on a configurable schedule and shows a live image count badge. Render albums as a special group type distinct from manually curated groups.

##### [MEDIUM] Image Detail Panel (Slide-In)
When clicking any image in a gallery, slide in a detail panel (rather than a separate page) showing: full-size preview, EXIF metadata, tags, group membership, vector embedding visualization (a 2D UMAP projection of the image's neighbors), edit recipe history, and quick actions (Delete, Convert, Add to Group).

##### [MEDIUM] Keyboard Navigation Mode
Add a `useHotkeys` hook via `react-hotkeys-hook` replicating the desktop keyboard shortcuts in the web frontend. Arrow keys to navigate gallery, `Enter` to open detail panel, `Delete` to remove, `Space` to preview full-screen. Essential for power users managing large libraries from the browser.

##### [LOW] Localization (i18n) Foundation
Add `react-i18next` and extract all user-visible strings into `en.json` translation files. Structure the codebase so adding a new language requires only a new JSON file. Prioritize the Convert, Search, and Database tabs first.

---

### 3. Core Engine & AI Enhancements (Rust / Python Base)

#### A. Next-Generation AI Tagging & Search

##### [HIGH] VLM Auto-Tagging Pipeline
`backend/src/models/data/captioner.py` exists — build a full `VLMCaptioner` class on top of it backed by `Moondream2` or `LLaVA-1.5-7B-GGUF` (via `llama-cpp-python` for CPU / `transformers` for GPU). Run captioning as a background `QRunnable` after images are added to the database. Store captions in a new `captions` column. Surface captions as searchable metadata in `SearchTab` and as auto-populated tags in `DatabaseTab`. Add a "Re-caption All" batch task in `ScanMetadataTab`.

##### [HIGH] Smart Semantic Albums
Implement dynamic virtual albums backed by live `pgvector` HNSW queries. A `VirtualAlbum` table stores a natural-language query string, threshold, and cached member list. The `SearchTab` gains a "Save as Album" button. Albums auto-refresh on a configurable schedule (hourly or on new image ingestion). Pairs with the React Virtual Album Browser feature above.

##### [HIGH] HNSW Index Migration
Transition all `pgvector` `vector` columns from `ivfflat` to `hnsw` index type. This reduces similarity search latency from seconds to milliseconds at 100k+ image scale. Requires a new Django migration that drops the existing IVFFlat index and creates the HNSW index with `(m=16, ef_construction=64)`. Update `image_database.py` to set `hnsw.ef_search = 100` per query.

##### [MEDIUM] Perceptual Hash Completion
`task_scan_duplicates()` in `tasks/tasks.py` returns an empty `{}` placeholder for perceptual hash mode. Implement the full pipeline: compute pHash/dHash via the Rust `image_finder.rs` (which already has exact hash support), build a hamming distance matrix, and cluster images with distance ≤ threshold. Return grouped clusters, not a flat list.

##### [MEDIUM] CLIP Ensemble Search
Support multiple CLIP variants (OpenAI ViT-L/14, MetaCLIP ViT-H/14, SigLIP) stored as separate `vector` columns. Let users select the embedding model at search time, or enable an ensemble mode that averages cosine distances across all available models. Store the model identifier per embedding row so the database supports heterogeneous embedding sources.

##### [LOW] Hybrid Text + Vector Search
Add a `tsvector` GIN index over the captions and tags columns. Extend `SearchTab` to support hybrid search: cosine similarity from the vector column merged with `ts_rank` full-text relevance. This covers keyword-based search for users who don't have an embedding query in mind.

---

#### B. Database Performance & Indexing

##### [HIGH] Asynchronous Bulk Ingestion
Refactor `image_database.py` batch insertion to use `psycopg2.extras.execute_values()` with a single round-trip instead of per-row inserts. For very large directories (50,000+ images), add a `COPY FROM STDIN` path using `psycopg2.copy_expert`. Current single-insert path takes ~0.3s per 100 images; bulk should achieve < 0.05s per 100.

##### [MEDIUM] Incremental Embedding — Skip Already-Embedded Images
Add an `is_embedded` boolean column to the images table. During embedding passes, `SELECT ... WHERE is_embedded = FALSE`, process in batches, and flip the flag on success. This makes repeated scans of large libraries O(new images) rather than O(all images).

##### [MEDIUM] SafeTensors Model Inspector
`backend/src/utils/safetensors_metadata.py:80` has a silent `pass` in its metadata parsing. Complete the implementation to read LoRA rank, alpha, target modules, and trigger words from safetensors headers. Surface this as a model inspector panel in `MetaCLIPInferenceTab` and `LoRAGenerateTab` — users should be able to inspect a trained model's metadata without loading it into VRAM.

---

#### C. Rust Core Optimizations

##### [HIGH] Streaming Image Processing
`base/src/core/image_merger.rs` and `image_converter.rs` load full `DynamicImage` buffers before processing. The benchmark shows a 734MB peak for thumbnail generation. Refactor both to tile-based streaming: process output canvas rows in chunks and write to `BufWriter<File>` directly. Use `image::io::Reader`'s decoder API for scanline-chunk decoding on JPEG, PNG, and TIFF. Target ≤ 200MB peak RAM for a 1,000-image batch at 1080p.

##### [HIGH] Async HTTP Crawler in C++
`base/src/web/image_crawler.cpp` is a stub (Selenium-dependent). Add thread-pool-based HTTP crawling using cpp-httplib with configurable concurrency for direct-URL jobs. Reserve Python Selenium only for JS-rendered pages. This should improve direct-URL crawl throughput by ~10× and reduce WebDriver resource usage significantly.

##### [MEDIUM] Additional Image Board Crawlers
Extend the `base/src/web/board_crawler.cpp` framework with new platform crawlers: Twitter/X media downloads, ArtStation gallery scraper, Pixiv (with OAuth), and Pinterest board downloader. Each should subclass the `Crawler` interface and be selectable from the `ImageCrawlerTab` board-type dropdown.

##### [MEDIUM] Parallel Web Crawler Progress Reporting
The current crawlers run as opaque blocking operations with no mid-crawl feedback. Add a progress callback using a `std::function<void(const std::string&, size_t, const std::string&)>` callback parameter in `base/src/web/board_crawler.cpp` that emits per-download events (URL, file size, local path) back to Python via pybind11, so the `ImageCrawlerTab` progress bar reflects real-time download count rather than a spinner.

---

### 4. Quality of Life & Utilities

##### [HIGH] Non-Destructive Edit Recipes *(Desktop)*
*(See Section 1C — full description there.)*

##### [HIGH] Intelligent Duplicate Grouping with Visual Diff *(Desktop + Web)*
*(See Section 1C — full description there.)*

##### [HIGH] Safetensors Model Inspector *(Desktop)*
Standalone tool accessible from any training or generation tab: drop a `.safetensors` file to inspect LoRA rank, alpha, trigger words, and base model compatibility. Show a preview generation using the loaded LoRA at 3 different strength values (0.5, 0.75, 1.0) side-by-side.

---

## Cross-Roadmap Overview

*Big-picture status and dependency graph across all 9 roadmaps. Node fill = roadmap type; node border = current implementation status. Edges show inter-roadmap dependencies and complementary relationships.*

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

    %% ── CORE PIPELINE ────────────────────────────────────────────────────────
    subgraph CORE["Core Pipeline"]
        ASP["🎬 ASP Roadmap\n(§1–§4 shipped;\nrefinements active)"]:::feature:::active
        CPP["⚡ ASP C++ Migration\n(Phases 1–6 complete;\narchived)"]:::migration:::done
        PERF["🚀 Performance\n(§3.10–§3.15 done;\n§3.1–§3.7 planned)"]:::perf:::active
    end

    %% ── INTELLIGENCE ─────────────────────────────────────────────────────────
    subgraph INTEL["Intelligence"]
        ANALYTICS["📊 Analytics &\nInterpretability\n(in progress)"]:::research:::active
        CONTENT["🎨 Content Generation\n(planned)"]:::feature:::planned
    end

    %% ── PLATFORM ─────────────────────────────────────────────────────────────
    subgraph PLATFORM["Platform"]
        ARCH["🏗️ Architecture\n(§5.x planned;\nrefactors queued)"]:::refactor:::planned
        GUI["🖥️ GUI / UX\n(§2.1–§2.31 done;\n§2.29–§2.31 recent)"]:::feature:::done
        NEWF["✨ New Features\n(§4.1–§4.13 planned)"]:::feature:::planned
    end

    %% ── FOUNDATIONS ──────────────────────────────────────────────────────────
    subgraph FOUND["Foundations"]
        DOCS["📝 Documentation\n(§6.1–§6.14 done;\n§6.15 active)"]:::docs:::active
    end

    %% ── INTER-ROADMAP DEPENDENCIES ───────────────────────────────────────────
    ASP --> CPP
    CPP --> PERF
    ASP --> ANALYTICS
    ASP --> CONTENT
    PERF --> ASP
    ARCH --> GUI
    ARCH --> PERF
    NEWF --> ASP
    DOCS --- ASP
    DOCS --- ARCH
    DOCS --- GUI
    DOCS --- ANALYTICS
```

---

## Diagram Visual Language Reference

*Every `## Implementation Timeline` diagram in `moon/roadmaps/` uses the visual encoding defined here. Read this section to interpret any diagram, and follow it when updating or adding nodes.*

---

### Node Fill — Element Type

The node's **body color** identifies the category of work.

| Fill | Class | Type | Description |
|---|---|---|---|
| Blue `#2563eb` | `feature` | **New Feature** | A capability that did not previously exist |
| Violet `#7c3aed` | `augment` | **Augmentation** | Extends or improves an existing feature without replacing it |
| Red `#dc2626` | `fix` | **Bug Fix** | Corrects incorrect or broken behaviour |
| Cyan `#0891b2` | `infra` | **Infrastructure** | Build system, CI/CD, tooling, or project foundations |
| Orange `#ea580c` | `perf` | **Performance** | Optimises speed, memory, throughput, or latency |
| Slate `#475569` | `research` | **Research** | Exploratory; outcome uncertain; may not ship |
| Dark red `#7f1d1d` | `security` | **Security** | Hardens against vulnerabilities, audits, or compliance |
| Teal `#0f766e` | `refactor` | **Refactor** | Restructures internals without changing external behaviour |
| Indigo `#4338ca` | `migration` | **Migration** | Moves from one technology, format, or system to another |
| Amber-dark `#a16207` | `testing` | **Testing** | Test coverage additions or test infrastructure improvements |
| Dark green `#15803d` | `docs` | **Documentation** | Documentation-only work (no code change) |
| Pink `#9d174d` | `integration` | **Integration** | Connects to an external system, API, or third-party service |

---

### Node Border — Implementation Status

The node's **border color and thickness** show where the item currently stands.

| Border | Class | Status | Meaning |
|---|---|---|---|
| Thick green `#16a34a, 4px` | `done` | **✅ Complete** | Shipped and merged; no further action needed |
| Thick amber `#d97706, 4px` | `active` | **🔄 In Progress** | Actively being worked on right now |
| Thin slate `#64748b, 2px` | `planned` | **⬜ Planned** | Scoped and intended, but not yet started |
| Thick red `#dc2626, 3px` | `blocked` | **🚫 Blocked** | Cannot proceed — waiting on an unresolved external dependency |
| Medium purple `#9333ea, 3px` | `hold` | **⏸ On Hold** | Paused intentionally; may resume but not actively scheduled |

To update a node when its status changes: replace the second class suffix —
`:::planned` → `:::active` → `:::done`  (or `:::blocked` / `:::hold` as needed).

---

### Edge Style — Relationship Type

| Style | Syntax | Relationship | When to use |
|---|---|---|---|
| Bold thick arrow | `==>` | **Critical dependency** | Blocking prerequisite on the critical path; B cannot start without A |
| Solid thin arrow | `-->` | **Depends on** | A must be done before B, but B is not on the critical path |
| Dashed arrow | `-.->` | **Alternative to** | A and B solve the same problem differently — only one should be chosen |
| No arrowhead | `---` | **Complements** | A and B work well together but neither requires the other |
| Circle end | `--o` | **Optional dependency** | B can optionally use A, but does not require it |
| Cross end | `--x` | **Conflicts with** | A and B are mutually exclusive or A blocks B from shipping |
| Bidirectional | `<-->` | **Tightly coupled** | A and B must evolve together; changes to one require changes to the other |

Labels can be added to any edge for additional specificity: `A -->|"reason"| B`.

---

### Standard classDef Block

Copy this block verbatim into every `flowchart` diagram. Do not rename the classes — consistency across roadmaps lets readers build a shared mental model.

```
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
```

Apply both classes to every node: `NodeID["Label"]:::typeClass:::statusClass`

---

### Example Diagram

The diagram below demonstrates every element type, every status, and every edge relationship in a single coherent graph representing a hypothetical auth-platform development sequence.

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

    %% ── ✅ COMPLETE nodes (thick green border) ───────────────────────────────
    REQ["🔬 Requirements\nAnalysis"]:::research:::done
    THREAT["🔒 Threat Model\n& Audit"]:::security:::done
    DB["🏗 Database\nSchema v1"]:::infra:::done
    AUTH["✨ Auth Module\n(JWT / Session)"]:::feature:::done
    CACHE["⚡ Response\nCaching Layer"]:::perf:::done
    UNIT["🧪 Unit\nTest Suite"]:::testing:::done
    DOC1["📄 API Reference\nDocs"]:::docs:::done
    REFACT["♻ Auth Code\nRefactor"]:::refactor:::done

    %% ── 🔄 IN PROGRESS nodes (thick amber border) ────────────────────────────
    MIG["🔄 Schema v1→v2\nMigration"]:::migration:::active
    RATELIM["🔧 Rate\nLimiting"]:::augment:::active
    INTTEST["🧪 Integration\nTest Suite"]:::testing:::active

    %% ── 🚫 BLOCKED nodes (thick red border) ─────────────────────────────────
    GDPR["🔒 GDPR\nCompliance Audit"]:::security:::blocked

    %% ── ⏸ ON HOLD nodes (medium purple border) ──────────────────────────────
    SDK["🔌 Mobile\nSDK Client"]:::integration:::hold

    %% ── ⬜ PLANNED nodes (thin slate border) ─────────────────────────────────
    OAUTH2["✨ OAuth2\nProvider Support"]:::feature:::planned
    WEBHOOK["🔌 Webhook\nIntegration"]:::integration:::planned
    TOKENFIX["🐛 Token Refresh\nRace Condition"]:::fix:::planned
    GUIDE["📄 User Guide\n& Tutorials"]:::docs:::planned
    PERF2["⚡ Query\nOptimisation"]:::perf:::planned

    %% ── EDGES — all seven relationship types ─────────────────────────────────
    REQ    ==>         AUTH          %% ==>  critical dependency (research gates feature)
    THREAT ==>         AUTH          %% ==>  critical dependency (threat model gates auth)
    DB     ==>         AUTH          %% ==>  critical dependency (schema gates auth)
    AUTH    -->        OAUTH2         %% -->  depends on
    AUTH    -->        REFACT         %% -->  depends on
    REFACT  -->        UNIT           %% -->  depends on
    AUTH    -->        CACHE          %% -->  depends on
    AUTH    -->        DOC1           %% -->  depends on
    DB      -->        MIG            %% -->  depends on
    MIG     -->        PERF2          %% -->  depends on
    DOC1    -->        GUIDE          %% -->  depends on
    SDK     -->        WEBHOOK        %% -->  depends on
    CACHE   ---        RATELIM        %% ---  complements (both protect the API surface)
    UNIT   <-->        INTTEST        %% <--> tightly coupled (suites co-evolve)
    OAUTH2  -.->       WEBHOOK        %% -.-> alternative (OAuth push vs webhook pull)
    TOKENFIX --x       OAUTH2         %% --x  conflicts with (race condition blocks OAuth)
    GDPR    --o        OAUTH2         %% --o  optional dependency (GDPR may gate OAuth)

    %% ── LEGEND — status borders ──────────────────────────────────────────────
    subgraph SLEG["Status — Border Color + Width"]
        direction LR
        SL1["✅ Complete"]:::feature:::done
        SL2["🔄 In Progress"]:::feature:::active
        SL3["⬜ Planned"]:::feature:::planned
        SL4["🚫 Blocked"]:::feature:::blocked
        SL5["⏸ On Hold"]:::feature:::hold
    end

    %% ── LEGEND — element type fills ─────────────────────────────────────────
    subgraph TLEG["Type — Node Fill Color"]
        direction LR
        TL1["New Feature"]:::feature:::done
        TL2["Augmentation"]:::augment:::done
        TL3["Bug Fix"]:::fix:::done
        TL4["Infrastructure"]:::infra:::done
        TL5["Performance"]:::perf:::done
        TL6["Research"]:::research:::done
        TL7["Security"]:::security:::done
        TL8["Refactor"]:::refactor:::done
        TL9["Migration"]:::migration:::done
        TL10["Testing"]:::testing:::done
        TL11["Docs"]:::docs:::done
        TL12["Integration"]:::integration:::done
    end

    %% ── LEGEND — edge relationships ──────────────────────────────────────────
    subgraph ELEG["Edge — Relationship Type"]
        direction TB
        EA["A"]:::infra:::done ==>|"critical dep"| EB["B"]:::infra:::done
        EC["C"]:::infra:::done  -->|"depends on"|   ED["D"]:::infra:::done
        EE["E"]:::infra:::done -.->|"alternative"|  EF["F"]:::infra:::done
        EG["G"]:::infra:::done ---|"complements"|   EH["H"]:::infra:::done
        EI["I"]:::infra:::done --o|"optional dep"|  EJ["J"]:::infra:::done
        EK["K"]:::infra:::done --x|"conflicts"|     EL["L"]:::infra:::done
        EM["M"]:::infra:::done <-->|"bidirectional"| EN["N"]:::infra:::done
    end
```

*Created: 2026-06-23. Update the classDef block in any diagram by copying the Standard classDef Block above verbatim.*

##### [HIGH] Batch Rename with Pattern Templates
Add a rename tool (tab or toolbar action) that applies pattern-based renames to selected files. Support tokens: `{index}`, `{date}`, `{resolution}`, `{group}`, `{tag}`, `{hash}`. Preview the rename mapping in a before/after table before committing. Support undo via the edit recipe system.

##### [MEDIUM] Quick-Convert Context Menu in Gallery
Right-clicking any image in any gallery should show a context menu with "Quick Convert To…" sub-items (PNG, JPEG, WebP, AVIF). Each item immediately fires a single-file conversion without opening the `ConvertTab`. The output lands in the same directory with a user-configurable suffix.

##### [MEDIUM] Aspect Ratio Crop Assistant
Add a crop-to-ratio helper in `ConvertTab` that lets users specify a target aspect ratio (e.g., 16:9, 1:1, 3:4, SDXL 1024×1024) and shows a crop preview overlay on the source image. The crop anchor (top-center, center, face-detect) is selectable. Face-detection crop uses the existing Siamese network's face-embed pipeline.

##### [MEDIUM] Image Metadata Batch Editor
Add a metadata editor tab that can write EXIF/XMP fields (title, description, keywords, copyright, GPS) to a batch of selected images. Support "copy metadata from one image to many" for quick-tagging datasets. Wire into the `ScanMetadataTab` workflow.

##### [MEDIUM] Color Palette Extractor
Add a palette extraction feature accessible from image preview and `SearchTab`. Extract the N dominant colors from an image using k-means (backed by the C++ core, exposed as `base.core.extract_palette()`). Show swatches with hex values and copy-to-clipboard. Add "Search by Color" functionality that encodes the dominant palette into a query vector for pgvector similarity search.

##### [MEDIUM] Slideshow Queue Editor
The `SlideshowWindow` and `slideshow.cpp` daemon exist but queue management is basic. Add a queue editor panel with drag-to-reorder, per-image duration overrides, transition type selector (fade, cut, slide), and a "play from here" action on any item.

##### [LOW] Export Dataset Manifest
From `DatabaseTab`, add an "Export Dataset" action that writes a JSONL or CSV manifest of all images in a group or subgroup, including paths, tags, captions, and embedding norms. This feeds directly into `lora_dataset.py` and external training tools without manual file organization.

##### [LOW] Image Statistics Dashboard
A stats tab or panel showing library-wide metrics: total image count, format breakdown, resolution distribution histogram, tag frequency chart, last-crawled timestamps per source, and VRAM/RAM usage by the active model. Pull data from `GET /api/db/stats/` and render with `pyqtgraph` (desktop) or Recharts (web).
