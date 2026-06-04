# Image Toolkit — Changelog

*Completed items archived from the Master Roadmap. Ordered from most recent phase to earliest.*

---

## ASP Session 4 — ARAP Push Phase + BiRefNet Fg-Masked Pose Diff (2026-06-04)

### Shipped

| Item | Summary |
|------|---------|
| **ARAP Push phase** (`fg_register.py`) | Full Sýkora 2009 Push→Regularise algorithm. `_arap_push()`: per-cell SAD block matching via `cv2.matchTemplate` with 15% improvement threshold and 24px search range. Decouples cells for independent appearance-optimal displacement before global Regularise smoothing. Enabled by default (`ASP_ARAP_PUSH=1`). 2 new unit tests in `TestARAPPush`. |
| **BiRefNet fg-masked pose diff** (`bench_anime_stitch.py`, `frame_selection.py`) | When `ASP_POSE_WINDOW_PX > 0`, BiRefNet probes build both bg mask (for camera displacement) AND fg mask (union across probe frames). The fg mask weights the gradient diff so background edges are excluded from pose comparison. Still disabled by default (background-agnostic but gradient still limited). |
| **Composite gate env overrides** (`bench_anime_stitch.py`) | `ASP_GATE_SC` / `ASP_GATE_SB` env vars to tune or disable the composite gate for diagnostics. |

### Investigated and Found Non-Impactful

| Item | Finding |
|------|---------|
| **ARAP Push on benchmark** | Zero measurable GT-SSIM change (+0.001 test27, 0.000 elsewhere). Flow quality confirmed not the bottleneck; SSIM ceiling is animation timing mismatch from frame selection. |
| **BiRefNet fg-masked pose selection** | Slightly better than raw gradient (fewer spurious refinements) but still regresses test04 (-0.082→-0.026 magnitude reduction). GT reference coupling prevents reliable improvement: any frame substitution diverges from the GT's specific temporal selection. |
| **Composite gate calibration** | Gate verified correct: test04 ASP composite (sb=32.8) gives GT-SSIM 0.716 vs SCANS 0.742 — SCANS IS better for test04. Gate threshold 30 is appropriate. |

---

## ASP Session 3 — Pose-Consistent Frame Selection Infrastructure (2026-06-03)

### Shipped (disabled by default)

| Item | Summary |
|------|---------|
| **`backend/src/anim/frame_selection.py`** | New backend module exposing `smart_select_frames()` as a clean pipeline/GUI API. Two-pass architecture: Pass 1 (v1 greedy first-past-threshold), Pass 2 (local pose-consistent refinement). `_fg_center_diff()` gradient-magnitude L1 metric for pose similarity. |
| **Upgraded `_smart_select_frames()`** | Benchmark function now has the same two-pass architecture with `[PoseSelect]` logging per refined slot. `ASP_POSE_WINDOW_PX` env var (default `0` = disabled). |

### Tried and Disabled

| Item | Outcome |
|------|---------|
| **Gradient-based central-crop pose proxy** | Confounded by background structure: Sobel gradients in the central 50% crop include locker/wall edges that change as the camera pans, causing the selector to prefer same-scroll-position frames over same-pose frames. Regressions: test04 -0.043, test27 -0.026. Set `ASP_POSE_WINDOW_PX=0` (default). Needs foreground-only flow or a proper pose estimation model (DWPose/ViTPose) to work correctly. See `pipeline_analysis_report.md` §3. |

---

## Research Consolidation & Roadmap Restructure (2026-06-03)

### Consolidated research reports

The 14 image-stitching reports and 5 image/video-generation reports were merged into two comprehensive references and the **19 source reports were deleted** (their entire content is captured in the consolidations). Both new documents cover the **whole field** with deep anime-focused sections, sized to fully replace the originals.

| Item | Summary |
|------|---------|
| **`reports/Image_Stitching_Research.md`** | Replaces all 14 stitching reports. 22 sections: geometric foundations & DoF; Perfect-Stitch-vs-Scan-Stitch mathematical audit (pushbroom/X-slits, APAP rank-deficiency proof); feature matching (SIFT/AKAZE/MSER → SuperPoint/SuperGlue/LightGlue/ALIKED → LoFTR/EfficientLoFTR/RoMa/JamMa/EDM); registration & sub-pixel (RANSAC/MAGSAC, translation-only BA, ECC, phase correlation); optical flow (RAFT/SEA-RAFT/AnimeInterp SGM+RFR); spatially-varying warps (APAP/Moving-DLT, TPS/MLS/CPW, LSD line preservation, SEAGULL); **foreground assembly** (motion decomposition `F_fg=T_camera+A_animation`, Sýkora ARAP push/regularise, symmetric midpoint warp, two-channel selection, Eden single-pose fallback, HDR/VSR analogy); photometric (Harding broadcast-dimming reversal, BaSiC flat-fielding, Brown–Lowe gain, region-stratified Reinhard, palette harmonisation); segmentation (BiRefNet/ToonOut 99.5%/SAM-2/trapped-ball); seam-finding (graph-cut MRF, Agarwala, DSeam, semantic/SAM); blending (multi-band, Poisson/Modified-Poisson+MTOR, DSFN soft-seam); background reconstruction (temporal median, ProPainter/RAFT, latent-diffusion outpainting, VidPanos); unified frameworks (UDIS++/NIS/SRStitcher); SR (Real-ESRGAN anime_6B/APISR); video (StabStitch/++, Unwrap Mosaics); shot detection (OmniShotCut); the 14-stage pipeline spec; evaluation metrics; failure/fallback taxonomy; ASP implementation status. |
| **`reports/Image_Generation_Research.md`** | Replaces all 5 generation reports. 16 sections: diffusion math (ε/v/x0-prediction, Rectified Flow Matching + Reflow, progressive distillation); architecture lineages (SD1.5, SDXL dual-encoder, Animagine XL 4.0, Illustrious XL 2.0 token-dilution, NoobAI v-pred + RF conversions, Pony score-tag Clever-Hans, FLUX MM-DiT/T5XXL/Chroma/Kaleidoscope, SD3.5) with comparison table; conditioning & prompting (Danbooru/score/natural-language, Florence-2 vs WD14); fine-tuning (LoRA dim/alpha, LyCORIS LoCon/LoHa/LoKr, DreamBooth, full-FT, kohya_ss settings, optimisers); the 4K-video→character-LoRA pipeline; inference (ComfyUI/Forge/A1111, samplers, fp16-fix VAE, ControlNet, IP-Adapter); upscaling (Real-ESRGAN anime/APISR/SUPIR); video (AnimateDiff 5D-tensor architecture + motion-module table + anime beta_schedule=linear fix, AnimeInterp, ToonCrafter Toon-Rectification/Dual-Reference-3D-Decoder/Sparse-Sketch, ToonComposer DiT/SLRA, Wan2.1/SVD, prompt-travel/context-sliding); hardware deployment (uv, TensorRT static compilation, FP8/NF4/GGUF quantisation tables for 3090 Ti / 4080 / 4080-mobile); Image-Toolkit implementation status; settings cheat-sheet. |

### Roadmap restructure

| Item | Summary |
|------|---------|
| **ASP roadmap refocus** | `moon/roadmaps/asp.md` header now references the consolidated stitching report; §0.1 updated with implementation status — A2/A4 prototype (`backend/src/anim/fg_register.py`: DIS dense flow → residual → symmetric midpoint warp, integrated into Stage 11, validated on test09) shipped; A1 (SEA-RAFT), A3 (full ARAP+LSD), A5 (bg-only median), A6 (single-pose fallback), and segment-guided flow remain. |
| **New Content Generation roadmap** | `moon/roadmaps/content_generation.md` created — grounded in the existing stack (`LoRATuner` on Illustrious-XL, `SD3Wrapper`, `ComfyUIManager`, `backend/src/models/data/`). Phased CG-1…CG-4: captioning (WD14+Florence-2), shared anime upscaler, ComfyUI control workflows, video→LoRA guided flow, LyCORIS, AnimateDiff, v-pred/ztSNR, ToonCrafter, FLUX, Wan2.1/SVD. |
| **Master roadmap update** | `moon/ROADMAP.md` adds the two consolidated reports and the Content Generation section-roadmap to its index; new **Phase 0 (ASP Foreground Assembly, items 0.1–0.8)** and **Phase CG (Content Generation, items CG.1–CG.10)** added with effort estimates and links. |

---

## Roadmap Continuation Batch — Phase 1 & Phase 2 Items (Completed 2026-05-31)

### ASP Pipeline Fixes (Phase 1 items 1.1–1.5)

| Item | Summary |
|------|---------|
| 1.1 SCANS fallback purity | `scans_frames = list(frames)` is captured at Stage 2 (before any ML corrections). All four `_scan_stitch_fallback()` call-sites in `pipeline.py` and the `_ProgressPipeline` subclass now pass `scans_frames`, ensuring the fallback always receives the original unmodified frames. |
| 1.2 Dark scene gain clamp widening | `_ref_lum_scalar` threshold is 80.0. When met, gain clamp is `[0.80, 1.25]` instead of the tighter `[0.88, 1.14]`. Both code paths confirmed present in `pipeline.py` lines 566–570. |
| 1.3 Static edge pre-bundle rejection | `MIN_EXPECTED_STEP = 50` is defined in `backend/src/constants/anim.py` and exported via `backend/src/constants/__init__.py`. It was never imported in `pipeline.py` — causing a `NameError` every time the min-step guard ran. Added `MIN_EXPECTED_STEP` to the `from backend.src.constants import (...)` block. |
| 1.4 Content-aware minimal bounding crop | `_crop_to_valid()` in `canvas.py` already uses `_largest_valid_rect` when `valid_ratio < 0.80`. SCANS fallback also uses `_largest_valid_rect` after stitching. Both verified operational — item confirmed done. |
| 1.5 Restrict seam search window | `_seam_dp()` in `stateless.py` gains a `search_half: int | None = None` parameter. When set, the cost matrix is masked to `±search_half` pixels around the image midpoint via a `np.full(..., np.inf)` mask with the window left unmasked. `de_seam()` in `mfsr/de_seam.py` propagates `search_half` to both its `_seam_dp` calls (baseline + fallback). |

### ML Model Memory Management (Phase 1 item 1.8)

| Item | Summary |
|------|---------|
| 1.8 `unload()` on all model wrappers | Added `unload()` to seven model wrappers that lacked it: `BiRefNetWrapper` (pops from `_models` class dict, calls `del model`, `gc.collect()`), `LoFTRWrapper` (`del self.matcher`, sets to `None`), `EfficientLoFTRWrapper` (deletes both `_model` and `_processor`), `RoMaWrapper`, `ALIKEDLightGlueWrapper` (deletes `_matcher`), `JamMaWrapper` (deletes `_model`), `BaSiCWrapper` (clears NumPy arrays). All call `torch.cuda.empty_cache()` and `gc.collect()`. `AnimeStitchPipeline.run()` now calls `unload()` (with `offload()` fallback) instead of the weaker `offload()` at cleanup points after Stages 4 and 5–6. |

### Logging Standardisation (Phase 1 item 1.13)

| Item | Summary |
|------|---------|
| 1.13 Python `logging` + rotating file handler | `_setup_logging()` added to `backend/src/app.py`. Called at the start of `launch_app()`. Creates: a `RotatingFileHandler` at `~/.image-toolkit/logs/image_toolkit.log` (5 MB per file, 5 backups, DEBUG level) and a `StreamHandler` on stdout (INFO level by default, DEBUG with `--verbose`). `logger = logging.getLogger(__name__)` added to: `backend/src/anim/pipeline.py` (58 print calls migrated), `canvas.py` (5), `matching.py` (8), and all 7 model wrappers including `birefnet_wrapper.py`, `efficient_loftr_wrapper.py`, etc. `print(..., file=sys.stderr)` → `logger.error()`; `print(f"[Stitch] Warning…")` → `logger.warning()`; remaining stage logs → `logger.info()` or `logger.debug()`. Third-party loggers (PIL, transformers, urllib3) capped at WARNING. |

### Worker Cancellation Standardisation (Phase 2 item 2.7)

| Item | Summary |
|------|---------|
| 2.7 `_should_stop` flag | `WallpaperWorker` and `TrainingWorker` previously used only `self.is_running` for cancellation. Both now also set `self._should_stop = False` on init and `self._should_stop = True` in `stop()`, alongside the existing `is_running` flag. Existing callers that check `is_running` continue to work; tooling that checks the standardised `_should_stop` pattern now also works. |

### Settings Window Completion (Phase 2 item 2.16D/F/G)

| Item | Summary |
|------|---------|
| 2.16 D/F/G Settings fully wired | Audit confirmed all three remaining sub-items are already wired in `settings_window.py`: §D `confirm_deletions` (checkbox, load/save/reset at lines 74, 248, 1318, 1361); §F `file_logging_enabled` + log level combo (lines 85, 391–403, 1328–1329, 1385); §G `restore_last_dir` (lines 78, 280, 1322, 1370). Item marked Done. |

### Stage-Level Progress Signals (Phase 2 item 2.6)

| Item | Summary |
|------|---------|
| 2.6 Stage signals | Audit confirmed `_ProgressPipeline` in `gui/src/helpers/models/stitch_worker.py` already emits `sig_stage(idx, total_stages, label)` at the start of all 13 pipeline stages via `_emit()`. `StitchWorker.TOTAL_STAGES = 13`. Item marked Done. |

### Pipeline Execution Trace JSON (Phase 2 item 2.13)

| Item | Summary |
|------|---------|
| 2.13 Execution trace | `_ProgressPipeline.run()` now writes a per-run JSON file to `~/.image-toolkit/traces/stitch_YYYYMMDD_HHMMSS.json`. Fields: `started_at`, `finished_at` (ISO 8601), `elapsed_seconds`, `frames_input` (N frames loaded), `edges_found` (after direction-consensus filter), `canvas_size` ([H, W]), `fallback_used` (SCANS mode triggered?), `success`, `error`, `stage_timings` (list of `{stage, label, elapsed_s}` entries — one per `_emit()` call). The trace is also written when the SCANS fallback is used. Stage timings measure wall time between consecutive `_emit()` calls. |

### Dispatcher Completion (features/ROADMAP.md — CRITICAL)

| Item | Summary |
|------|---------|
| CLI dispatcher — database | `dispatch_database()` in `dispatcher.py` was a single-line stub. Now implements the `search` sub-command: loads `PgvectorImageDatabase`, calls `search_images(filename_pattern=query, limit=limit)`, and prints tabular results (id, filename, group, subgroup, tags). |
| CLI dispatcher — model | `dispatch_model()` was a single-line stub. Now implements the `generate` sub-command: instantiates `SD3Wrapper`, calls `wrapper.generate(prompt, output_path)`, and reports the output path. |
| CLI `--recursive` flag | `dispatch_core()` now reads `args.get("recursive", False)` and forwards it to `ImageFormatConverter.convert_batch(recursive=recursive)`. The `# TODO: add recursive to backend` comment removed. |

### Database Bulk Insert (Phase 2 DB performance)

| Item | Summary |
|------|---------|
| Bulk tag insert via `execute_values` | `add_image()` in `image_database.py` replaced the per-row tag insert loop (`for tag_name in tags: cur.execute(insert_image_tag, ...)`) with `psycopg2.extras.execute_values()`. Tag IDs are still resolved one by one via `_get_or_create_tag()` (which is itself an upsert), but the subsequent insertion is now a single round-trip `INSERT ... VALUES %s ON CONFLICT DO NOTHING`. |

### pgvector HNSW Index Tuning (Phase 2 item 2.14)

| Item | Summary |
|------|---------|
| 2.14 HNSW tuning | `schema.sql`: `idx_images_embedding` index updated to `USING hnsw ... WITH (m = 32, ef_construction = 128)`. Previous defaults were `m=16, ef_construction=64`. `search_images()`: when `query_vector` is provided, issues `SET LOCAL hnsw.ef_search = 80` in a preceding cursor to tune the search beam for this query without affecting other connections. |

### Multi-Select in Gallery (Phase 2 item 2.9)

| Item | Summary |
|------|---------|
| 2.9 Shift+click / Ctrl+click | Audit confirmed `handle_marquee_selection()` in `AbstractClassTwoGalleries` (lines 601–633) already implements Shift (additive) and Ctrl (subtractive) multi-select. Item marked Done. |

---

## GUI/UX Phase 1 — Quick Wins (Completed 2026-05-31)

| Item | Summary |
|------|---------|
| G1.9 Session persistence | `_save_last_dir` / `_load_last_dir` helpers added to both `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. Each tab class stores its last browsed directory in `QSettings("ImageToolkit","ImageToolkit")` under `session/<ClassName>/last_dir`. The saved path is restored on next launch, eliminating the need to re-browse to the previous directory after an app restart. |
| G1.10 OS dark mode follow | `MainWindow.__init__` now reads `QGuiApplication.styleHints().colorScheme()` when the vault stores no explicit theme preference. Falls back to `"dark"` when the OS reports `Unknown`. Connects `colorSchemeChanged` signal to auto-switch themes when the user toggles dark/light mode in the OS while the app is running (only takes effect when no vault override is set). |
| G1.11 Ctrl+scroll thumbnail zoom | `MarqueeScrollArea` intercepts wheel events with `Qt.ControlModifier` and emits a `ctrl_wheel(int)` signal (positive = scroll up = zoom in, negative = scroll down = zoom out). Both gallery base classes connect this signal lazily on the first layout-change tick, keeping concrete tab code untouched. Each Ctrl+scroll step changes `thumbnail_size` by ±16 px (clamped to 64–512 px) and reloads the current gallery page at the new size. |

## MAL Auto-Fill — Entity Auto-Association (2026-05-31)

| Item | Summary |
|------|---------|
| Jikan multi-endpoint fetch | `fetch_mal_anime_data` now makes two additional rate-limited requests (0.4 s gap each): `/anime/{id}/characters` for character names + Japanese voice-actor names, and `/anime/{id}/staff` for director/producer/etc. names. Studios and producers are read from the main endpoint response. All names are normalised from Jikan's `"Last, First"` format to `"First Last"` via `_normalize_name`. |
| Entity auto-association | `_on_mal_finished` now calls `_auto_associate_entities(data)` which: builds a case-insensitive name → entity-id index from `entities.json`; tries both the normalised and the `"Last, First"` form of each incoming name; adds every matched entity ID to `assoc_entities_ids` without duplicates; refreshes the Associated Entities display. The five entity lists checked are: studios, producers, characters, voice_actors, staff. Non-matching names are silently skipped. |

## GUI/UX Phase 2 — Core QoS (Continued 2026-05-31)

| Item | Summary |
|------|---------|
| G2.8 Arrow-key gallery navigation | `AbstractClassTwoGalleries.keyPressEvent` extended: Left/Right/Up/Down move `_focused_found_idx` (column-aware via `_current_found_cols`); Enter/Space emits `path_double_clicked` on the focused label, delegating to whatever preview handler the concrete tab has wired. Focus is scrolled into view via `ensureWidgetVisible`. |
| G2.10 Recent-dirs MRU helpers | `_add_recent_dir(path)` / `_get_recent_dirs()` added to both gallery base classes (backed by `QSettings`). Every browsed directory can be pushed to a per-class, capped-at-10 MRU list. Concrete tabs can now build a recent-dirs dropdown by calling `_get_recent_dirs()` and `_add_recent_dir()` on each browse. |
| G2.20A QSplitter persistence | `_persist_splitter(splitter, key)` module-level utility added to `listings_tab.py`. Restores state from `QSettings` on creation; saves on every `splitterMoved`. Applied to all three splitters in `listings_tab`: directory-import dialog, `ContentListingsSubTab`, and `EntityListingsSubTab`. |
| G2.26B F2 Rename | `_rename_focused_file()` added to `AbstractClassTwoGalleries` (F2 renames whichever file is focused by the arrow-key cursor `_focused_found_idx`). `_rename_selected_file()` added to `AbstractClassSingleGallery` (F2 renames the most-recently-selected item). Both: open `QInputDialog.getText` pre-filled with the stem; sanitise illegal filesystem characters; guard against name conflicts; call `os.rename`; patch `found_files`, `master_found_files`, `selected_files`, and the label/card widget map so the UI reflects the new path without a reload. |
| G2.19A Export selection as paths | `_export_selection_as_paths()` added to both `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. Triggered by Ctrl+E. Exports `selected_files` if any are selected, otherwise exports all loaded files (`found_files` / `gallery_image_paths`). Saves to user-chosen `.txt` / `.csv` via `QFileDialog` (native dialog disabled to avoid JVM RTTI conflict on Linux). |
| G2.24A Thumbnail hover border | `DraggableLabel` and `ClickableLabel` now paint a 2-px cyan (`#00bcd4`) border overlay via `paintEvent` when the cursor is over them (`WA_Hover` + `enterEvent`/`leaveEvent` toggle). Non-destructive: drawn on top of whatever the current stylesheet state is, so selected/found/loading styles are unaffected. |
| G2.16A–C+E Settings wiring | `_apply_startup_preferences()` extended: §A+C as before (thumbnail/page size, startup category); §B replaces each gallery tab's `_found_pixmap_cache`, `_selected_pixmap_cache`, `_initial_pixmap_cache` with new `LRUImageCache` instances sized from vault prefs; §E sets `WallpaperTab` slideshow spinboxes and order combo from vault prefs. Items D (confirm_deletions), F (logging), G (restore_last_dir) remain. |
| G2.17D LogWindow upgrade | `LogWindow` rewritten: `QPlainTextEdit` (monospace, readable font), five colour-coded levels (ERROR=red, WARNING=orange, INFO=grey-white, DEBUG=grey, SUCCESS=green), ISO timestamp prefix on each line, Copy All / Save to File / Clear buttons, Follow toggle for auto-scroll. |
| G2.21A Directory nav history | `_push_dir_history`, `_dir_go_back`, `_dir_go_forward` added to both gallery base classes using a `deque(maxlen=20)`. Concrete tabs call `_push_dir_history(current_path)` before loading a new directory; `Alt+Left` / `Alt+Right` (or toolbar Back/Forward buttons, once wired in concrete tabs) can navigate the stack. |

### Image Preview Window — Quick Wins (2026-05-31)

| Item | Summary |
|------|---------|
| G2.11A Fullscreen toggle | `F` / `F11` toggles `showFullScreen()` ↔ `showMaximized()`. Context menu label dynamically reads "Fullscreen (F11)" or "Exit Fullscreen (F11)" depending on current state. |
| G2.11B Zoom modes | `W` = fit-to-width (zoom = viewport_width / image_width); `H` = fit-to-height; `1` = 100% actual pixels. All three are also accessible from the right-click context menu. |
| G2.11D Rotation | `R` rotates 90° clockwise; `L` rotates 90° counter-clockwise. Rotation state (`_rotation_degrees`) is maintained per preview session; applied via `QTransform().rotate(...)` before scaling. Context menu entries for both directions. GIFs are not rotated (QMovie doesn't support `QTransform` scaling). |

### Listings Tab — Summary/Review Split (2026-05-31)

| Item | Summary |
|------|---------|
| Summary writable | Summary field is now fully editable — the placeholder text clarifies that it can be auto-filled from MAL or typed manually. The previously applied `setReadOnly(True)` and grey styling are removed; the field uses the standard theme style like all other inputs. |
| Summary + Review fields | `_DetailPanel` now has two text fields: **Summary** (read-only, grey background, 75 px tall — auto-filled by MAL with the official synopsis) and **Review / Notes** (editable, user's personal review). Old entries that stored everything in `"review"` still load correctly; new saves write both `"summary"` and `"review"` keys. The `_on_mal_finished` slot now targets `f_summary` instead of `f_review`, so MAL auto-fill never overwrites a personal review. |

### Listings Tab — Rating Split & MAL Enhancements (2026-05-31)

| Item | Summary |
|------|---------|
| QDoubleSpinBox style fix | Added `QDoubleSpinBox` to the input-field selector in both `dark.qss` and `light.qss`. Previously the Community Rating field inherited the OS native spinbox chrome because the global stylesheet didn't cover it. |
| Dual ratings | `_DetailPanel` in `ContentListingsSubTab` now has two separate rating fields: **My Rating** (`QSpinBox`, 0–10, integer stars) and **Community Rating (MAL)** (`QDoubleSpinBox`, 0.00–10.00). Old single-`rating` keys in stored JSON are transparently migrated to `personal_rating` on first load. Card thumbnails display personal rating as gold stars and MAL community score as a purple badge. |
| MAL web link auto-fill | `_on_mal_finished` now populates `f_web_link` with the anime's MAL page URL from `anime["url"]` in the Jikan response, but only when the field is currently empty (avoids overwriting a manually entered link). |
| MAL score as float | Jikan client returns `score` as a raw `float` (e.g., `7.85`) instead of a rounded `int`, matching MAL's own precision. |

---

## Phase 3 — ASP Advanced Pipeline (Completed 2026-05-30)

| Item | Summary |
|------|---------|
| P3.1 EfficientLoFTR drop-in | Replaced original LoFTR with EfficientLoFTR for faster keypoint matching with equivalent accuracy. |
| P3.2 JamMa O(N) Mamba matcher | Mamba-based O(N) sequence matching integrated (pending CUDA rebuild for latest toolkit). |
| P3.3 ToonCrafter ghost fill | `anim/anim_fill.py` — ToonCrafter-based synthetic frame generation for deghosting in high-overlap zones. |
| P3.4 SRStitcher diffusion fusion | `anim/sr_stitcher.py` — diffusion-based seam and border inpainting for final-quality outputs. |
| P3.5 SEA-RAFT fine-tune pipeline | Fine-tuning pipeline for SEA-RAFT optical flow on domain-specific scroll sequences. |
| P3.6 EfficientLoFTR fine-tune pipeline | Fine-tuning pipeline for EfficientLoFTR on scroll-frame keypoint pairs. |

---

## Phase 2 — ASP Intermediate Pipeline (Completed 2026-05)

| Item | Summary |
|------|---------|
| P2.1 SEA-RAFT optical flow | SEA-RAFT flow for robust large-displacement inter-frame motion estimation. |
| P2.2 Real-ESRGAN super-resolution | `anim/super_res.py` — Real-ESRGAN 4× upscale post-processing mode. |
| P2.3 ALIKED + LightGlue matching | ALIKED feature detector paired with LightGlue for accurate keypoint matching. |
| P2.4 BiRefNet seam routing | BiRefNet foreground mask integrated into seam DP cost (`sem_cost`) to route seams away from character regions. |
| P2.5 Soft-seam diffusion blending | Diffusion-based soft seam blending for smooth panorama transitions. |
| P2.6 Per-segment photometric correction | Per-foreground-segment gain correction using BiRefNet segmentation masks. |
| P2.8 RoMa v2 matcher | RoMa v2 dense matcher added as a high-accuracy fallback tier. |
| P2.9 Segment-guided matching | Matching restricted to background segments to reduce noise from dynamic foreground content. |

---

## Phase 1 — ASP Foundation Pipeline (Completed 2026-04)

| Item | Summary |
|------|---------|
| P1.1 Animation phase clustering | Temporal clustering to separate distinct animation phases (scene transitions vs. scroll). |
| P1.2 Variable-step renderer | Renderer adapted to handle non-uniform inter-frame scroll steps. |
| P1.3 Confidence-weighted median | Temporal median weighted by per-frame quality confidence scores. |
| P1.4 EfficientLoFTR initial integration | First integration of EfficientLoFTR as the primary feature matcher. |
| P1.5 Grid sampling | Uniform grid keypoint sampling as a fallback when detector-based sampling is sparse. |
| P1.6 StabStitch BA regularisation | Bundle adjustment regularisation borrowed from StabStitch for video stabilisation priors. |
| P1.7 Auto-MFSR | Automatic multi-frame super-resolution triggered on low-resolution inputs. |
| P1.8 Auto-inpaint | Automatic inpainting triggered on detected border artefacts. |
| P1.9 Bidirectional midplane | Bidirectional midplane estimation for symmetric canvas placement. |

---

## RAM Reduction Campaign (Tier 1–5, Completed)

| Item | Summary |
|------|---------|
| Gallery LRU caches | `AbstractClassTwoGalleries` and `AbstractClassSingleGallery` — all three caches converted to bounded `LRUImageCache` (OrderedDict-backed, QImage storage). WallpaperTab, ImageExtractorTab, ReverseSearchTab fixed. |
| QPixmap threading violation | `ImageLoaderWorker` now emits `QImage` from worker thread instead of `QPixmap` (QPixmap is main-thread only). |
| DuplicateScanWorker chunked compare | SIFT/SSIM use `_chunked_compare(chunk_size=500)` to cap live descriptors in memory. |
| `_loaded_results_buffer` → QImage | `scan_metadata_tab.py` buffer stores `QImage` instead of `QPixmap`. |
| Tag checkboxes → QListWidget | Both `scan_metadata_tab.py` and `search_tab.py` use virtual `QListWidget` instead of individual `QCheckBox` widgets. |
| `source_path_to_widget` cleanup | Map entries popped on page changes in `image_extractor_tab.py` to prevent unbounded growth. |
| ML model `unload()` on finish | Siamese, GAN, SD3 wrappers call `unload()` after inference completes to free GPU memory. |
| Weak-reference lambda captures | `abstract_class_two_galleries.py` signal closures use `weakref.ref` to prevent circular reference memory leaks. |
| PostgreSQL server-side cursors | `bulk_export_cursor` pattern for unbounded queries; avoids loading full result sets into Python memory. |
| N+1 tag query elimination | `get_tags_for_images_bulk` batch fetch replaces per-image tag queries. |
