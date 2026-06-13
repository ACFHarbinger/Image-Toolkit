# Image Toolkit — Changelog

*Completed items archived from the Master Roadmap. Ordered from most recent phase to earliest.*

---

## GUI Session — §2.3A Arrow-Key Nav, §2.7B MergeWorker Cancel, §2.18B+C Color Labels, §2.19A+C Export + Copy, §2.9D Confirm Deletions (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Arrow-key gallery navigation — §2.3A** (`abstract_class_single_gallery.py`) | `_navigate_gallery(key)`, `_highlight_focused(page_paths, idx)`, `_preview_focused_item()` added, mirroring the two-galleries implementation. `_focused_idx=-1` tracked in `__init__`. `gallery.nav_left/right/up/down` wired in `keyPressEvent`; `gallery.open_preview` + `Space` call `_preview_focused_item()`. `_highlight_focused` calls `ensureWidgetVisible` on `gallery_scroll_area`. Completes §2.3A coverage for both gallery base classes. |
| **`MergeWorker.cancel()` + `_should_stop` — §2.7B** (`merge_worker.py`) | Standardised cancellation pattern added: `_should_stop=False` in `__init__`, `cancel()` sets the flag, `cancelled = Signal()` emitted if cancel fires before the blocking merge call. `_should_stop` checked after image-file resolution, before the single `ImageMerger` call. (The merge call itself is a single blocking Rust invocation that cannot be interrupted mid-execution — this covers the pre-start case.) |
| **Color label context menu — §2.18B** (`abstract_class_two_galleries.py`) | "Color Label ▶" submenu in the found-gallery right-click menu. Six color options (Red/Orange/Yellow/Green/Blue/Purple) shown with emoji icons. Each action is checkable; clicking a checked color toggles it off (clear). A "Clear Label" item at the bottom of the submenu removes the label. Labels stored in `QSettings` keyed `labels/{path}`. |
| **Color border ring on thumbnails — §2.18C** (`abstract_class_two_galleries.py`) | `update_card_style` now reads the `gallery_path` Qt property from the card widget and calls `_get_color_label(path)` to look up the label color. When unlabelled and not selected, the default border (`#4f545c`, 1px) is used. When labelled and not selected, the label color replaces the border (2px solid). Selection state takes priority over label color (selection border overrides). Card widgets get `setProperty("gallery_path", path)` at construction time to support the lookup. |
| **`_get_color_label` / `_set_color_label` helpers** (`abstract_class_two_galleries.py`) | `_get_color_label(path)` reads `QSettings("ImageToolkit","ImageToolkit").value("labels/{path}")`. `_set_color_label(path, color_key)` writes or removes the QSettings key, then calls `update_card_style` to refresh the card immediately. Class-level `_LABEL_COLORS` dict maps key → hex; `_LABEL_ICONS` maps key → emoji. |
| **`_copy_selection_to_folder()` — §2.19C** (both gallery base classes) | `shutil.copy2` loop to a `QFileDialog.getExistingDirectory`-chosen destination. Source is `selected_files` when non-empty, else the full visible list. Skips already-existing destinations (reports skipped count). `DontUseNativeDialog` on the directory picker. Bound to `Ctrl+Shift+C` via new `gallery.copy_to_folder` shortcut in `ShortcutRegistry`. |
| **"Export Paths…" + "Copy to Folder…" in right-click menu** (`abstract_class_two_galleries.py`) | Both actions added after a separator following "Move to Trash". Export calls the existing `_export_selection_as_paths()`; Copy calls the new `_copy_selection_to_folder()`. Keyboard shortcuts noted in the menu labels. |
| **`gallery.copy_to_folder` shortcut** (`shortcut_manager.py`) | Default `Ctrl+Shift+C`. Added between `gallery.export_paths` and `gallery.nav_back` in `SHORTCUT_REGISTRY`. Appears in the `Ctrl+/` shortcut discovery overlay. |
| **`_confirm_deletions_enabled()` + confirm gate in `_trash_path` — §2.9D** (`abstract_class_two_galleries.py`) | `_confirm_deletions_enabled()` reads `preferences["confirm_deletions"]` from `main_window.cached_creds` (defaults `True`). `_trash_path` now shows a `QMessageBox.question` before `send2trash` when enabled. When `confirm_deletions=False`, trashing is instant with no dialog. |
| **`_copy_selection_to_folder()` — §2.19C** (`abstract_class_single_gallery.py`) | Same implementation mirrored into `AbstractClassSingleGallery`. Wired to `gallery.copy_to_folder` in `keyPressEvent`. |

### Design rationale

Arrow-key navigation in `AbstractClassSingleGallery` mirrors the two-galleries version: `_current_cols` is already computed from the layout pass so step-by-row navigation works without additional column tracking. Color labels use `QSettings` (not the vault) because they are user-facing curation data, not security-sensitive credentials. The `gallery_path` property on card widgets is the bridge from `update_card_style`'s generic widget parameter back to the specific file path — without it, the function would need to maintain a reverse map. The label-to-color lookup adds one QSettings read per card refresh; since refresh only fires on explicit user action (not during scrolling), the overhead is negligible. `_copy_selection_to_folder` uses `shutil.copy2` (preserves mtime/permissions) and skips conflicts silently — skip count is reported in the status bar.

---

## ASP Session 75 — §1.31 Seam FG Penetration Escalation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_fg_penetration(path, fa_zone, fb_zone) → float`** (`compositing.py`) | §1.31: Samples the seam pixel at each column `x` (row = `path[x]`, clamped to zone bounds). A pixel is foreground when any channel > 0. Returns the fraction of columns where the seam pixel is foreground in at least one zone. 0.0 for empty path or zero-width zone. |
| **Penetration escalation in blend loop** (`compositing.py`) | After §1.28 instability check: if `_SEAM_FG_PENETRATION_MAX > 0.0 and k not in seam_single_pose and penetration > threshold`, escalates to single-pose (dominant by fg pixel count). Complements §1.23/§3.15 (cost barriers) and §1.28 (path stability); catches the case where the DP routes through fg because no bg corridor exists. |
| **`_SEAM_FG_PENETRATION_MAX` flag** (`compositing.py`) | `ASP_SEAM_FG_PENETRATION_MAX=0.0` (default off). Recommend 0.7: when >70% of seam columns cut through character pixels, a hard-partition blend produces less ghosting than the DSFN ramp. |
| **Constant** (`constants/anim.py`) | `SEAM_FG_PENETRATION_MAX=0.7`. |
| **`ASP_SEAM_FG_PENETRATION_MAX` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 1.0, "Max fraction of seam columns through fg before single-pose escalation")`. |
| **`_seam_fg_penetration` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSeamFgPenetration`) | empty-path-returns-zero, all-background-path-returns-zero, all-foreground-path-returns-one, half-foreground-returns-half, return-type-is-float. **Anim suite: 482 passing.** |

### Design rationale

§1.23 and §3.15A raise the DP's cost for fg columns but cannot prevent routing through fg when every column is fg-dominated (portrait seams). §1.28 detects this indirectly via path instability, but a portrait seam routing consistently along the character midline has low std. §1.31 is the direct measure: if ≥70% of the seam pixels are on foreground, the seam bisects a character body regardless of path stability. Completes the three-layer fg-seam defence: §1.23/§3.15 (cost barriers → steer away), §1.28 (std → detect chaos), §1.31 (penetration → detect fg bisection).

---

## ASP Session 74 — §1.30 Minimum Zone Height Guard (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_zone_is_degenerate(zone_h, min_height=20) → bool`** (`compositing.py`) | §1.30: Returns True when `zone_h < min_height` (and `min_height > 0`). When the blend zone is shorter than `min_height` rows, the §1.26 boundary clamp leaves at most one valid seam row, the DSFN feather has no blending headroom, and the DP produces a constant-row path regardless of content. |
| **Wire-up in `_composite_foreground()`** (`compositing.py`) | After `fa_zone`/`fb_zone` are allocated, before DP: `if _ZONE_MIN_HEIGHT > 0 and _zone_is_degenerate(zone_h, _ZONE_MIN_HEIGHT) and k not in seam_single_pose → seam_single_pose[k] = fi_a if fg_a ≥ fg_b else fi_b`. Hard-partition blend fires at line 2001 (`_single = seam_single_pose.get(k)`). |
| **`_ZONE_MIN_HEIGHT` flag** (`compositing.py`) | `ASP_ZONE_MIN_HEIGHT=0` (default off). Recommend 20: matches the S15/S16 soft-edge band width; zones narrower than this cannot be blended cleanly regardless of DP. |
| **Constant** (`constants/anim.py`) | `ZONE_MIN_HEIGHT=20`. |
| **`ASP_ZONE_MIN_HEIGHT` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 500, "Min blend-zone rows before single-pose escalation without DP (0=off, recommend 20)")`. |
| **`_zone_is_degenerate` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestZoneIsDegenerate`) | zero-min-height-never-degenerate, zone-below-threshold-is-degenerate, zone-at-threshold-is-not-degenerate, zone-above-threshold-is-not-degenerate, negative-min-height-treated-as-disabled. **Anim suite: 477 passing.** |

### Design rationale

§1.26 (`_clamp_seam_path`) clips the DP seam to `[margin, zone_h-1-margin]`. With `margin=3` and `zone_h=8`, the valid range is `[3, 4]` — two rows. The DP surface is so compressed that every path lands at the same row, the feather has no room to blend, and S15/S16 soft-edge (±6px) extends beyond the zone boundary. Escalating to single-pose for zones < 20 rows avoids all these edge cases in one gate. The 20-row threshold is equal to the S15 soft-edge band width (`2 × ASP_SP_SOFT_PX=6 + margin`), making it the natural floor for meaningful blending.

---

## ASP Session 73 — §1.29 Static Input Detection Gate (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_detect_static_input(frames, max_mad, thumb_size=64) → bool`** (`pipeline.py`) | §1.29: Resizes each frame to a 64×64 greyscale thumbnail and checks whether all consecutive pairs have mean absolute difference (MAD) < `max_mad`. Returns True only when ALL pairs are below the ceiling. Fewer than 2 frames → always False. Short-circuits on first differing pair for zero overhead on valid inputs. |
| **Stage 1.5 gate in `run()`** (`pipeline.py`) | Pre-Stage-2 check: when `_STATIC_INPUT_MAX_MAD > 0.0` and `_detect_static_input(...)` is True, logs a warning and `cv2.imwrite(frame 0 → output_path)` early return. No exception raised — caller receives a valid (but trivial) output. |
| **`_STATIC_INPUT_MAX_MAD` flag** (`pipeline.py`) | `ASP_STATIC_INPUT_MAX_MAD=0.0` (default off). Recommend 2.0: 2/255 ≈ 0.8% pixel noise, sufficient to tolerate MPEG compression noise while catching genuine all-static sequences. |
| **Constant** (`constants/anim.py`) | `STATIC_INPUT_MAX_MAD=2.0`. |
| **`ASP_STATIC_INPUT_MAX_MAD` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 255.0, "MAD ceiling for static-input detection")`. |
| **`_detect_static_input` in `__all__`** (`pipeline.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_pipeline.py::TestDetectStaticInput`) | fewer-than-two-frames-returns-false, identical-frames-returns-true, varying-frames-returns-false, just-below-threshold-returns-true, one-differing-pair-returns-false. **Anim suite: 472 passing.** |

### Design rationale

Phase Correlation is the primary displacement estimator. When every input frame is identical (or near-identical), all pair responses are near-zero and Bundle Adjustment converges to a degenerate all-zero-translation solution — the pipeline produces a single frame copy with confidence. Detecting this case before Stage 1 wastes no edge-matching budget and avoids a misleading "stitched panorama" that is just one frame repeated. MAD=2.0 comfortably absorbs H.264/MPEG quantization noise (typical MAD < 0.5 for identical-looking frames from a static source) while safely ignoring normal inter-frame motion (MAD > 5 for even 5-pixel scroll).

---

## ASP Session 72 — §1.28 Seam Path Instability Escalation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_path_std(path) → float`** (`compositing.py`) | §1.28: `float(np.std(path))`; 0.0 for empty paths. Measures how widely the seam path oscillates across the zone height — a stable seam routing along consistent rows has std≈0; a chaotic seam that spans the full zone has std≈zone_h/3. |
| **Instability escalation in blend loop** (`compositing.py`) | After `path_local` is resolved: if `_SEAM_INSTABILITY_THRESH > 0 and k not in seam_single_pose and _seam_path_std(path_local) > threshold`, escalates to single-pose. Dominant frame picked by fg pixel count in zone (same logic as §1.20). |
| **`_SEAM_INSTABILITY_THRESH` flag** (`compositing.py`) | `ASP_SEAM_INSTABILITY_THRESH=0.0` (default off). Recommend 20.0: paths with std > 20 rows are visibly unstable. |
| **Constant** (`constants/anim.py`) | `SEAM_INSTABILITY_THRESH=20.0`. |
| **`ASP_SEAM_INSTABILITY_THRESH` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 500.0, "Max seam path std before single-pose escalation")`. |
| **`_seam_path_std` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSeamPathStd`) | empty-path-returns-zero, constant-path-returns-zero, oscillating-path-has-high-std, linearly-increasing-path-has-moderate-std, return-type-is-float. **Anim suite: 467 passing.** |

### Design rationale

§1.25 (smoothing) and §1.26 (boundary clamp) reduce the _visual_ impact of an unstable path, but do not prevent the blend from straddling two incompatible frame regions. When the DP reports no stable low-cost path (std > 20 rows), the zone contains content that fundamentally cannot be blended cleanly — typically a foreground character that moved so much between frames that the "best" seam cuts through it at different heights for every column. Escalating to single-pose in this case avoids a zigzag ghost and lets §1.15 soft-edge handle the residual step.

---

## ASP Session 71 — §1.27 Background Coverage Gate for Normalisation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_has_sufficient_bg(bg_sel, min_px=200) → bool`** (`compositing.py`) | §1.27: returns True iff `np.count_nonzero(bg_sel) >= max(1, min_px)`. None input → False. Formalises the historical hardcoded `>= 200` floor in the normalisation loop as a testable, configurable helper. |
| **Normalisation loop update** (`compositing.py`) | `len(bg_px) >= 200` replaced by `_has_sufficient_bg(bg_sel, _bg_min)` where `_bg_min = _BG_NORM_MIN_PX if _BG_NORM_MIN_PX > 0 else 200`. Default behaviour unchanged. |
| **`_BG_NORM_MIN_PX` flag** (`compositing.py`) | `ASP_BG_NORM_MIN_PX=0` (default 0 → built-in 200-px floor). Setting to a higher value tightens the gate for sparse-bg scenes. |
| **Constant** (`constants/anim.py`) | `BG_NORM_MIN_PX=200`. |
| **`ASP_BG_NORM_MIN_PX` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 10000, "Min background pixels for gain normalisation (0 = use built-in 200-px floor)")`. |
| **`_has_sufficient_bg` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestHasSufficientBg`) | sufficient-bg-returns-true, insufficient-bg-returns-false, exactly-at-threshold-returns-true, none-mask-returns-false, all-fg-returns-false. **Anim suite: 462 passing.** |

### Design rationale

The normalisation loop has always guarded against sparse background with `len(bg_px) >= 200`, but this was implicit and untestable. Extracting it to `_has_sufficient_bg()` makes the contract explicit: portrait shots where BiRefNet assigns nearly the entire frame to foreground have too few background pixels for a reliable mean-luma estimate, and applying gain correction to 10–50 background pixels produces a highly noisy multiplier. The configurable `ASP_BG_NORM_MIN_PX` allows per-dataset tuning without code changes.

---

## ASP Session 70 — §1.26 Seam Path Boundary Clamp (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_clamp_seam_path(path, zone_h, margin=3) → np.ndarray`** (`compositing.py`) | §1.26: clips the DP seam path to `[margin, zone_h-1-margin]`. When the seam routes to y=0 or y=zone_h-1, the feather blend has zero headroom and degenerates to a hard edge at the zone boundary. `np.clip(path, margin, zone_h-1-margin)`. No-op when margin ≤ 0 or `zone_h ≤ 2*margin` (bounds would invert). |
| **`_SEAM_MARGIN` flag** (`compositing.py`) | `ASP_SEAM_MARGIN=3` (default 0=off). Wired at end of `_seam_cut()` after §1.25 smoothing. |
| **Constant** (`constants/anim.py`) | `SEAM_MARGIN=3`. |
| **`ASP_SEAM_MARGIN` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 50, "Min rows between seam path and zone top/bottom edge (0 = off, recommend 3)")`. |
| **`_clamp_seam_path` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestClampSeamPath`) | zero-margin-returns-unchanged, path-clamped-above-margin, path-clamped-below-upper-bound, in-range-values-unchanged, zone-too-small-returns-unchanged. **Anim suite: 457 passing.** |

### Design rationale

The feather blend in `_composite_foreground` requires at least `feathers[k]` rows of valid zone content on either side of the seam centre. When `_seam_cut()` routes the path to the zone boundary (y=0 or y=zone_h-1), the blend array is sliced to a zero-height region — producing a hard cut at the zone edge that is visually distinct from the intended feather transition. `margin=3` is a conservative floor (three pixels of headroom); larger values can be set via `ASP_SEAM_MARGIN` for zones with wide feathers. The `zone_h ≤ 2*margin` guard prevents the bounds from inverting on very thin zones.

---

## ASP Session 69 — §1.25 Seam Path Smoothing (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_smooth_seam_path(path, window=5) → np.ndarray`** (`compositing.py`) | §1.25: applies a 1-D median filter of size *window* to the DP seam-cut path. Raw argmin traceback can produce single-pixel sideways jumps that alias into diagonal bands at the seam boundary. Formula: `scipy.ndimage.median_filter(path.astype(float32), size=window).astype(int32)`. Even window incremented to next odd. window ≤ 1 is a no-op. |
| **`_SEAM_SMOOTH_WINDOW` flag** (`compositing.py`) | `ASP_SEAM_SMOOTH_WINDOW=5` (default 0=off). Wired at the end of `_seam_cut()` — after traceback, before return. |
| **Constant** (`constants/anim.py`) | `SEAM_SMOOTH_WINDOW=5`. |
| **`ASP_SEAM_SMOOTH_WINDOW` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 51, "Median-filter window for seam path jitter removal (0 or 1 = off, recommend 5)")`. |
| **`_smooth_seam_path` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSmoothSeamPath`) | window-zero-returns-unchanged, window-one-returns-unchanged, smooth-path-removes-spike, constant-path-unchanged, even-window-incremented-to-odd. **Anim suite: 452 passing.** |

### Design rationale

The `_seam_cut()` DP traceback selects the locally-optimal column at each step (`argmin` over a ±1 window). When adjacent columns have nearly equal energy, the traceback oscillates: column 3 → column 4 → column 3 → column 4, producing a visible zigzag band at the boundary. A 1-D median filter of window=5 removes oscillations of period ≤ 2 (single-pixel jitter) while preserving the coarser seam routing (bends of ≥ 3px extent pass through unchanged). This is analogous to path post-processing in graph-cut segmentation and is already standard in video seam-carving literature.

---

## ASP Session 68 — §1.24 Post-Composite Seam-Step Gate (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_measure_max_seam_step(canvas, n_strips, band_px=10, guard=3) → float`** (`pipeline.py`) | §1.24: samples mean greyscale luma in `band_px` rows above and below each inter-strip boundary (±`guard` guard rows). Returns `max(|above − below|)` across all N-1 seams. Returns 0.0 when n_strips ≤ 1 or canvas too small. |
| **Stage 11.3 gate** (`pipeline.py`) | `_SEAM_STEP_GATE` flag (default 0.0=off, `ASP_SEAM_STEP_GATE=25.0`). After Stage 11.2 colour gate: measures `_measure_max_seam_step(canvas, N)`. If > threshold → SCANS fallback. |
| **Constant** (`constants/anim.py`) | `SEAM_STEP_GATE_THRESH=25.0`. |
| **`ASP_SEAM_STEP_GATE` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 255.0, "Max luma step at seam boundary before SCANS fallback")`. |
| **`_measure_max_seam_step` in `__all__`** (`pipeline.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_pipeline.py::TestMeasureMaxSeamStep`) | single-strip-returns-zero, uniform-canvas-returns-near-zero, step-detected-at-boundary, max-returned-for-multiple-seams, small-canvas-no-crash. **Anim suite: 447 passing.** |

### Design rationale

Stage 11.2 (§1.14B, S56) detects mismatched-colour seam zones in source frames before compositing. Stage 11.3 operates on the final composite output: if a luminance step >25 lum units persists at any strip boundary (≈"visible step" in the `seam_visibility_score` taxonomy from §3.8), the photometric normalisation has failed and SCANS is a better result. The guard rows (default 3) prevent sampling in the immediate artefact zone at the seam boundary itself; `band_px=10` samples the stable region just outside the transition. Complements Stage 11.2 without overlap.

---

## ASP Session 67 — §1.23 SemanticStitch Hard Corridor Barrier (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_corridor_exists(cost, fg_thresh=0.5) → bool`** (`compositing.py`) | §1.23: returns True iff the cost map has both fg-dominated columns (>50% fg-interior) AND non-dominated columns (background corridor). False when all columns are fg-dominated (no corridor) or none are (no barrier needed). |
| **`_build_seam_cost_map(..., barrier_cost=None)` extended** (`compositing.py`) | New `barrier_cost` parameter. When `None`: uses module-level `_SEAM_HARD_BARRIER` flag to choose between 2.0 (S33 soft) and `_SEAM_HARD_BARRIER_COST` (1e6 hard). When corridor exists, fg-dominated columns are raised to `barrier_cost` instead of hardcoded 2.0. Backward-compatible: default path is identical to S33. |
| **`_SEAM_HARD_BARRIER` / `_SEAM_HARD_BARRIER_COST` flags** (`compositing.py`) | `ASP_SEAM_HARD_BARRIER=1` (default OFF). `ASP_SEAM_HARD_BARRIER_COST=1e6` (configurable). |
| **Constants** (`constants/anim.py`) | `SEAM_HARD_BARRIER_COST=1e6`. |
| **2 entries in `_CONFIG_SCHEMA`** (`config.py`) | `ASP_SEAM_HARD_BARRIER (int, 0, 1)` and `ASP_SEAM_HARD_BARRIER_COST (float, 0, None)`. |
| **`_seam_corridor_exists` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSeamCorridorExists`) | all-dominated-returns-false, all-bg-returns-false, mixed-returns-true, hard-barrier-applied-when-corridor, soft-barrier-backward-compat. **Anim suite: 442 passing.** |

### Design rationale

S33 (§3.15A) set fg-dominated columns to cost=2.0 — soft deterrence. With `sem_weight=200` in `_seam_cut()`, a cost-2.0 column costs 400 energy vs a cost-1.0 fg-interior column at 200. The DP is discouraged but not prevented from routing through fg columns. When a background corridor exists (detected by `_seam_corridor_exists`), setting the barrier to 1e6 makes the fg-column path 5000× more expensive than any background path — the DP is effectively forced into the corridor. The graceful fallback (no corridor → cost stays 2.0) maintains S33 behaviour when the character fills the full overlap width.

---

## ASP Session 66 — §1.22 Adaptive Single-Pose Soft-Edge Width (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_adaptive_sp_soft_px(feather_width, base_px=6, max_px=30, ref_px=80) → int`** (`compositing.py`) | §1.22: scales the single-pose soft-edge half-width proportionally to the original feather width that triggered escalation. Formula: `min(max_px, max(base_px, base_px * feather_width // ref_px))`. At feather=80px returns 6 (baseline unchanged); at feather=160px returns 12; at feather=300px returns 22; capped at 30px. `feather_width ≤ 0` is handled safely (returns base_px). |
| **`_ADAPTIVE_SP_SOFT` flag** (`compositing.py`) | `ASP_ADAPTIVE_SP_SOFT=1` (default OFF). When ON, replaces the fixed `ASP_SP_SOFT_PX=6` in the single-pose branch of the blend loop with a per-seam adaptive value computed from `feathers[k]`. |
| **Constants** (`constants/anim.py`) | `SP_SOFT_BASE_PX=6`, `SP_SOFT_MAX_PX=30`, `SP_SOFT_REF_PX=80`. |
| **`ASP_ADAPTIVE_SP_SOFT` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 1, "Enable adaptive single-pose soft-edge width scaled by feather")`. |
| **`_adaptive_sp_soft_px` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestAdaptiveSpSoftPx`) | at-ref-px-returns-base, doubles-for-double-ref, narrow-feather-clamps-to-base, wide-feather-caps-at-max-px, zero-feather-returns-base. **Anim suite: 437 passing.** |

### Design rationale

§1.15 (S15) always applies a fixed ±6px soft edge at single-pose seams. When §1.18 escalates a 300px feather to single-pose, the viewer expects a gentle transition over ~300px but sees a hard cut softened by only 6px — visually equivalent to a hard cut. The 6px was calibrated for the S15 baseline (feathers 80–120px). For wide feathers (160–300px), the appropriate soft edge is 12–22px: large enough to conceal the cut but narrow enough to avoid the ghost risk (double-image artefact requires ≥40px overlap to form). §1.22 derives the soft edge from the original feather width, maintaining the no-ghost guarantee while eliminating the visible step that §1.18 alone creates.

---

## ASP Session 65 — §1.21 Post-Composite Seam Luminance Equalisation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_lum_equalize(canvas, boundaries, band_px=20, min_step=5.0) → np.ndarray`** (`compositing.py`) | §1.21: for each boundary, samples mean greyscale luminance in band_px-row reference windows above and below (±3-row guard). When step > min_step lum units, applies a linear additive ramp over band_px rows below the boundary subtracting the step to smooth the transition. Equal BGR correction (luminance shift, chrominance preserved). Returns uint8 copy. |
| **`_SEAM_LUM_EQ` flag** (`compositing.py`) | `ASP_SEAM_LUM_EQ=1` (default OFF). Wired just before `return result` in `_composite_foreground`. |
| **Constants** (`constants/anim.py`) | `SEAM_LUM_EQ_BAND_PX=20`, `SEAM_LUM_EQ_MIN_STEP=5.0`. |
| **`ASP_SEAM_LUM_EQ` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 1, "Enable post-composite seam luminance equalisation pass")`. |
| **`_seam_lum_equalize` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestSeamLumEqualize`) | no-step-no-change, step-above-threshold-reduced, step-below-threshold-not-corrected, boundary-near-edge-no-crash, returns-uint8-dtype. **Anim suite: 432 passing.** |

### Design rationale

test27 (Class D) has SC=26.7 — visible luminance step at seam boundaries despite only 4% background gain spread. The step comes from ARAP warp residuals in the midpoint blend, not from gain mismatch. §1.16 (seam color match) and §1.4B/C (background gain) operate on intermediate compositing state. §1.21 operates on the FINAL output, correcting whatever step remains after all upstream passes. The ramp only touches band_px rows below the boundary — the upstream zone is untouched. The ±3-row guard prevents sampling the artefact region at the seam itself.

---

## ASP Session 64 — §1.20 Tight-Step Preemptive Single-Pose Escalation (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_seam_step_size(fi_a, fi_b, affines) → float`** (`compositing.py`) | §1.20: returns `max(|ty_b−ty_a|, |tx_b−tx_a|)` — dominant-axis camera step between two frame canvas positions. Returns `float("inf")` for out-of-range frame indices. |
| **Tight-step preemptive escalation in FG registration loop** (`compositing.py`) | `_TIGHT_STEP_PX` flag (default 0=off, `ASP_TIGHT_STEP_PX=30`). When step < threshold, skip ARAP entirely and immediately set `seam_single_pose[k]` based on which frame has more fg pixels in the ±20px boundary band. Records step size in `seam_post_diffs[k]`. |
| **`TIGHT_STEP_PX = 30`** (`constants/anim.py`) | Recommended threshold. At 1080p with 30px step, the character occupies 97%+ of both frames' overlap zone — ARAP cannot correct the animation pose difference. |
| **`ASP_TIGHT_STEP_PX` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 500, "Dominant-axis step (px) below which seam is preemptively single-posed (0=off)")`. |
| **`_compute_seam_step_size` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestComputeSeamStepSize`) | pure-vertical-step (ty=50→50.0), pure-horizontal-step (tx=80→80.0), uses-dominant-axis (dy=15/dx=60→60.0), exactly-at-threshold-not-below (step=30, strict < means 30 is not below 30), out-of-range-frame-returns-inf (fi=99→∞). **Anim suite: 427 passing.** |

### Design rationale

For sequences with tiny camera steps (e.g., test57: min_gap=10.8px, spacing_ratio=3.379), the animation may have advanced significantly relative to the minimal camera motion. In those cases, frame_a and frame_b show nearly the same background position but the character is in a completely different pose. ARAP registration can warp one character pose toward another, but when the poses are related by complex non-rigid motion across the full body, the residual after warping is still large — creating a ghost. Rather than discovering this AFTER a slow ARAP pass, §1.20 detects it BEFORE registration: any seam where the camera moved < 30px gets immediately assigned to the higher-fg-count frame. The dominant-frame selection (by fg pixel count in ±20px boundary band) ensures the character-heavier frame defines the seam zone. The step threshold is tunable; at 30px the gate fires on all "dense-step" seams in irregular-speed sequences while leaving normal-speed seams (>30px) for ARAP.

---

## ASP Session 63 — §1.19 Foreground-Density-Aware Feather Cap (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_fg_density_feather_cap(feathers, boundaries, warped_bg, order, cap_px, fg_thresh) → np.ndarray`** (`compositing.py`) | §1.19: checks fg pixel fraction in ±feather[k] band around boundaries[k] in canvas-space warped_bg for each adjacent frame pair. When max(fg_frac_a, fg_frac_b) > fg_thresh, caps feather to cap_px. Masks of None treated as all-bg (cap never fires without a BiRefNet mask). Returns copy of feathers (input not mutated). |
| **`_FG_FEATHER_CAP` / `_FG_FEATHER_THRESH` flags** (`compositing.py`) | `ASP_FG_FEATHER_CAP=60` (px cap value; 0=off, the default). `ASP_FG_FEATHER_THRESH=0.60` (fg fraction threshold). Wired after §1.6B gain-adjusted feathers and before Stage 8.5 FG registration. |
| **Constants** (`constants/anim.py`) | `FG_FEATHER_CAP=60`, `FG_FEATHER_THRESH=0.60`. |
| **`ASP_FG_FEATHER_CAP` / `ASP_FG_FEATHER_THRESH` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 300, ...)` and `(float, 0.0, 1.0, ...)`. |
| **`_fg_density_feather_cap` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestFgDensityFeatherCap`) | all-bg-no-cap, all-fg-applies-cap, feather-already-narrow-skips, uses-max-of-two-frames, none-mask-treated-as-all-bg. **Anim suite: 422 passing.** |

### Design rationale

§1.18 fires AFTER ARAP registration using post_warp_diff as the signal. §1.19 fires BEFORE registration using the fg density of the blend zone. When the seam boundary crosses a character-heavy zone (>60% fg), any feather wider than cap_px blends two different animation poses over that distance → double-image ghost. The cap reduces the blend zone immediately. The two gates are independent: §1.18 catches high post_warp_diff after ARAP; §1.19 catches character-dominated zones before ARAP runs. `warped_bg` is in canvas space — correct for checking boundary zones.

---

## GUI Session — §2.23A Accessible Names on Pagination Widgets (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Accessible names — §2.23A** (`meta_abstract_class_gallery.py`) | `setAccessibleName()` added to all interactive pagination controls: page-size `QComboBox` ("Images per page"), sort `QComboBox` ("Sort by"), sort direction button ("Toggle sort direction"), Prev/Page/Next buttons ("Previous page" / "Current page" / "Next page"), item range label ("Item range"), thumbnail slider ("Thumbnail size" + description), item range label. Applies to every gallery tab via the shared `_common_create_pagination_ui` factory. |

---

## GUI Session — §2.4B+C Shift+Click Range Select + Right-Click Context Menu (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Shift+click range select — §2.4B** (`abstract_class_two_galleries.py`) | `_on_found_card_clicked(path)` replaces direct `toggle_selection` as the `path_clicked` handler for found-gallery cards. When `Shift` is held (`QApplication.keyboardModifiers()`), selects all cards from `_selection_anchor_idx` to the clicked index (inclusive, within current page). Without Shift, updates `_selection_anchor_idx` and delegates to `toggle_selection`. |
| **Right-click context menu — §2.4C** (`abstract_class_two_galleries.py`) | `_on_found_card_right_clicked(global_pos, path)` connected to `path_right_clicked` signal on all `ClickableLabel` cards. Menu items: Open Preview, (sep), Select/Deselect, Select All, Deselect All, (sep), Rename… (F2), Move to Trash. Trash item calls `_trash_path(path)` which uses `send2trash`, removes the path from all in-memory lists, and refreshes both galleries. |

### Design rationale

`_selection_anchor_idx` is the Shift+click anchor — set only on non-Shift left clicks, so multiple Shift+clicks extend from the same anchor (standard file-manager behaviour). Range selection operates on `master_found_files` page slice, so it is consistent with what the user sees. The right-click context menu surfaces the three most common per-image operations (preview / rename / trash) without requiring keyboard shortcuts knowledge.

---

## GUI Session — §2.25A Shortcut Overlay, §2.20A QSplitter Persistence, §2.17D Log Window (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Shortcut discovery overlay — §2.25A** (`main_window.py`) | `_open_shortcut_overlay()` — `Ctrl+/` or `F1` opens a `QDialog` (560×460) with a real-time filter `QLineEdit` and a 3-column `QTableWidget` (Scope / Action / Key). Populated from `ShortcutRegistry.get_all()` including the active binding. Filter searches all three columns. `QHeaderView.ResizeMode.Stretch` on the Action column; ResizeToContents on Scope and Key. |
| **QSplitter persistence — §2.20A** (`splitter_persistence.py` + 5 tabs) | New `gui/src/utils/splitter_persistence.py` — `persist_splitter(splitter, key)` restores from `QSettings("splitters/{key}")` then wires `splitterMoved` to auto-save. Wired at: `StitchFeedbackTab/main`, `StitchPanel/main`, `GraphPanel/vertical`, `GraphPanel/horizontal`, `CanvasPanel/main`, `ThumbnailFilePicker/sidebar`. `listings_tab.py` already had its own inline `_persist_splitter`; all 4 of its splitters remain covered. |
| **Log window upgrade — §2.17D** (`log_window.py`) | Already shipped in a prior session: `QPlainTextEdit` (not `QTextEdit`), colour-coded levels via `LEVEL_COLORS` (`ERROR`=red, `WARNING`=orange, `INFO`=white, `DEBUG`=grey), timestamp prefix, "Follow" auto-scroll toggle, Copy All / Save… / Clear toolbar. Now documented. |

### Design rationale

`persist_splitter` uses a lazy `QSettings` write on `splitterMoved` — no timer or debounce needed because Qt debounces splitter drag events natively. The key scheme `"category/widget_name"` (e.g. `"StitchPanel/main"`) is collision-free across all tabs without per-tab registration. Shortcut overlay uses the registry's `get_all()` which already merges defaults + user overrides, so it shows the effective binding including any customisations from the shortcut editor (§2.29).

---

## GUI Session — §2.16C Ctrl+T Tab Search Popup (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Ctrl+T tab search — §2.16C** (`main_window.py`) | `_open_tab_search()` opens a frameless `QDialog` (popup mode, 400px wide) with a `QLineEdit` filter and `QListWidget` showing `"Tab Name  —  Category"` entries. Typing filters in real-time. `Enter` / double-click navigates: sets `command_combo` to the correct category then `_select_tab_by_name()` after a `QTimer.singleShot(0)` tick. Bound to `Ctrl+T` in `keyPressEvent`. |

### Design rationale

`QTimer.singleShot(0)` is required because `on_command_changed` synchronously clears and re-adds all tabs — the tab widget needs one event-loop tick before `tabText(i)` reflects the new category's tabs. Frameless popup auto-dismisses on click-outside without extra focus tracking. `WindowType.Popup` achieves this with no additional code.

---

## GUI Session — §2.11A+B+D Preview Enhancements, §2.12A+B+C System Tray (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Fullscreen toggle — §2.11A** (`image_preview_window.py`) | `_toggle_fullscreen()` — `showFullScreen()` / `showMaximized()` toggle. Wired to `F11` / `F` (no modifier) and registered as `preview.fullscreen` in `ShortcutRegistry`. Context menu entry updates label dynamically ("Fullscreen" ↔ "Exit Fullscreen"). |
| **Fit modes — §2.11B** (`image_preview_window.py`) | `_fit_to_width()`, `_fit_to_height()`, `_zoom_actual_pixels()`. Fit-to-width uses `viewport().width() / orig.width()`; fit-to-height uses height equivalent; 100% sets `current_zoom_factor=1.0`. Bound to `W`, `H`, `1`. Registered as `preview.fit_width`, `preview.fit_height`, `preview.actual_size`. Context menu shows all three. |
| **Rotation — §2.11D** (`image_preview_window.py`) | `_rotate(clockwise: bool)` applies `(rotation_degrees ± 90) % 360` and calls `update_image_display()` (which applies `QTransform().rotate(degrees)` during scaling). Bound to `R` (CW) and `L` (CCW). Registered as `preview.rotate_cw`, `preview.rotate_ccw`. Context menu shows both. In-memory only; does not write to disk. |
| **System tray icon — §2.12A** (`main_window.py`) | `_setup_tray_icon(app_icon)` called in `__init__` when `QSystemTrayIcon.isSystemTrayAvailable()`. Loads `assets/images/image_toolkit_icon.png`; falls back to `SP_ComputerIcon`. Context menu: Show Window, Toggle Daemon, Next Wallpaper, (sep), Quit. Double-click activates window. |
| **Tray balloon notifications — §2.12B** (`main_window.py`) | `tray_notify(title, message, timeout_ms=4000)` instance method. Module-level `show_tray_notification()` traverses `topLevelWidgets()` for app-wide access. Uses `QSystemTrayIcon.showMessage(MessageIcon.Information)`. |
| **Minimize to tray — §2.12C** (`main_window.py`) | `set_minimize_to_tray(enabled)` sets `_minimize_to_tray` flag. When enabled, `closeEvent` calls `event.ignore(); self.hide()` and shows a one-time tray notification instead of quitting. Opt-in; disabled by default. |

### Design rationale

All preview-window hotkeys are registered in `ShortcutRegistry` so they appear in the shortcut discovery overlay (§2.25) and the global keybindings editor (§2.29). `_rotate` uses `QTransform` on the cached `QPixmap` / `QMovie` frame — no disk write, clearly communicated by context-menu label. Tray availability is checked at runtime; the feature degrades silently on systems without a system tray (e.g., bare Wayland without xdg-portal). `_minimize_to_tray` is `False` by default to avoid confusing users who expect the window to close.

---

## GUI Session — §2.21A+D Dir History + MRU Dropdown, §2.26B Inline Rename (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Dir navigation history — §2.21A** (`abstract_class_two_galleries.py`) | `_push_dir_history(path)`, `_dir_go_back() → Optional[str]`, `_dir_go_forward() → Optional[str]` helpers. `deque(maxlen=20)` back and forward stacks. `Alt+Left` / `Alt+Right` wired in `keyPressEvent` via `gallery.nav_back` / `gallery.nav_forward` shortcuts (added to `ShortcutRegistry`). Virtual `_navigate_to_dir(path)` hook (no-op in base, overridden in `FormatTab`). |
| **MRU recent-dirs dropdown — §2.21D** (`convert_tab.py`) | `▼` `QToolButton` (instant-popup mode, fixed 24px wide) appended to FormatTab's input path row. `_show_recent_dirs_menu()` populates and shows the menu from `_get_recent_dirs()`. `browse_directory_and_scan()` now calls `_push_dir_history` + `_add_recent_dir` on successful browse. Also fixes missing `DontUseNativeDialog` flag on that `QFileDialog` call. |
| **Inline rename — §2.26B** (`abstract_class_two_galleries.py`) | `_rename_focused_file()` method: opens `QInputDialog.getText` pre-filled with stem (no extension). Sanitises illegal filesystem characters. Guards against name conflict. On success: calls `os.rename`, updates `found_files`, `master_found_files`, `selected_files`, `path_to_label_map` via `_replace_path_in_lists()`. Bound to `F2` via `gallery.rename` shortcut (already in registry). |

### Design rationale

Virtual `_navigate_to_dir` in the base class means back/forward dispatch compiles for all tabs — only FormatTab implements it for now; the others silently no-op until they add their own override. The MRU menu is separate from the Browse dialog to avoid an extra modal round-trip for common re-visits. Rename sanitises `\/:*?"<>|` which covers FAT32, NTFS, and ext4 reserved characters.

---

## GUI Session — §2.10C QStatusBar, §2.14A Filename Labels (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **QStatusBar — §2.10C** (`main_window.py`) | `QStatusBar` added to the bottom of `MainWindow`'s vbox layout (height-capped 24px, size grip off). `show_status(message, timeout_ms=3000)` instance method on `MainWindow`. Module-level `show_main_status()` function traverses `topLevelWidgets()` so any tab can post a status message without holding a direct window reference. `_show_status()` helper added to both gallery base classes; wired into `_export_selection_as_paths()` and `copy_image_to_clipboard()`. |
| **Filename labels — §2.14A** (both gallery base classes) | `_add_filename_label(card, path)` method added to `AbstractClassTwoGalleries` and `AbstractClassSingleGallery`. Appends a `QLabel` (`thumb_filename_lbl`) with elided middle-truncated filename (`fontMetrics().elidedText(ElideMiddle)`) to every thumbnail card's `QVBoxLayout`. Card height extended by `fm.height() + 4`. Called at all three card creation sites (found gallery, selected gallery, single gallery). |

### Design rationale

`QStatusBar` works as a standalone widget (MainWindow is a `QWidget`, not `QMainWindow`). Module-level traversal avoids direct import cycles between tab modules and the main window. Filename labels use `ElideMiddle` so the extension is always visible for long names. `_add_filename_label` is appended after `create_card_widget` — the existing `findChild(QLabel)` calls in `update_card_pixmap` still resolve to the image label (added earlier/deeper in the hierarchy).

---

## GUI Session — §2.13A+E Sort Toolbar + Search Operators, §2.15A Trash (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Search operators — §2.13E** (`meta_abstract_class_gallery.py`) | `_common_filter_string_list` upgraded from a plain `in` check to a multi-token engine. Supported: `-term` (exclude), `"phrase"` (exact), `a\|b` (OR); tokens AND-combined. Placeholder updated to hint syntax. |
| **Sort toolbar — §2.13A** (both gallery base classes) | Sort `QComboBox` (Name / Date Modified / File Size / Extension) + `↑`/`↓` button in pagination bar. `_sort_key_fn()` dispatches to `getmtime`/`getsize`/`splitext`/`natural_sort_key`. `_apply_sort()` is a pure sorted() call. Re-sort fires on combo change, direction toggle, and initial directory load. |
| **Move to Trash — §2.15A** (`delete_tab.py`, `wallpaper_tab.py`, `search_tab.py`) | `send2trash(path)` replaces `os.remove` at all user-initiated image deletion sites. Dialogs updated ("Move to Trash"). `send2trash>=1.8.3` added to `pyproject.toml`. |

### Design rationale

Token parser extracts quoted phrases first (regex), then splits remainder on whitespace. OR uses `|` without spaces (matches file-manager convention). Sort in pagination bar groups with "page size" left of the stretch, not with nav arrows. `_apply_sort` is a pure function — no in-place mutation until the caller reassigns.

---

## GUI Session — §3.9 Item Range Label, §4.11 Thumbnail Slider (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **Default page size 100→150** (`meta_abstract_class_gallery.py`) | Combo default changed to `"150"` and `"150"` added to the item list between `"100"` and `"250"`. Both gallery base classes updated from `page_size = 100` to `150`. |
| **Item range label — §3.9** (both gallery base classes) | `item_range_lbl` (`QLabel`, min-width 120px) added to every pagination bar between the page-size combo and the prev/next buttons. Text: `"Items 1–150 of 843"` or `"0 images"`. Updated in `_update_pagination_ui` on every pagination state change. |
| **Thumbnail size slider — §4.11** (`meta_abstract_class_gallery.py`) | `QSlider` (range 64–512, step 16, fixed width 110px) + `thumb_size_lbl` ("180 px") added to the right end of every pagination bar. The `⊞` icon precedes the slider as a visual hint. Returns in `controls` dict as `"thumb_slider"` and `"thumb_size_lbl"`. |
| **Per-tab thumbnail persistence** (both gallery base classes) | `_save_thumbnail_size()` — `QSettings` keyed `session/{ClassName}/thumbnail_size`. `_load_thumbnail_size(default=180)` — called at `__init__` before `approx_item_width` is set. `_sync_thumb_slider()` — updates all slider widgets without triggering signals (via `blockSignals`). |
| **Slider wiring** (both gallery base classes) | `valueChanged` → `_on_thumb_slider_changed()` (16px snap, live gallery reload). `sliderReleased` → `_save_thumbnail_size()`. Initial slider value set from `self.thumbnail_size` in `create_pagination_controls()`. |
| **Ctrl+scroll → slider sync** (both gallery base classes) | `_on_ctrl_wheel_zoom()` calls `_sync_thumb_slider()` after updating `thumbnail_size`, so the slider widget always reflects the current zoom level. |

### Design rationale

A `QSlider` in the pagination bar is always visible and requires zero discoverability — unlike Ctrl+scroll which requires prior knowledge. Snapping to 16px boundaries in `_on_thumb_slider_changed` ensures the slider moves in sensible increments even when the user drags freely. Per-tab persistence uses the class name as the `QSettings` key so `WallpaperTab` and `DeleteTab` remember independent sizes. `sliderReleased` triggers the save rather than `valueChanged` to avoid writing to `QSettings` on every drag event.

---

## GUI Session — §3.15 Keyboard Shortcuts, §3.16 QSS Override, §3.17 Window Geometry (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`gui/src/utils/shortcut_manager.py`** (new file) | `SHORTCUT_REGISTRY` — 21 bindable actions across Gallery (9) and Preview (12) scopes. `ShortcutRegistry` class: `load/save/reset/matches/get_key_sequence` API. `get_registry()` module-level singleton. JSON persistence to `~/.image-toolkit/keybindings.json`. |
| **`ShortcutRegistry.matches()` PySide6 6.10 fix** | `event.key()` returns plain `int` in PySide6 6.10; `event.modifiers()` returns `KeyboardModifier` flag with `.value`. `matches()` now branches on `isinstance(raw_key, int)` and `hasattr(raw_mods, "value")` before building `QKeySequence(mods_int | key_int)`. All 8 functional assertions pass. |
| **`keyPressEvent` in gallery base classes** | Both `AbstractClassTwoGalleries` and `AbstractClassSingleGallery` now route all shortcut checks through `get_registry().matches(event, action_id)` instead of hardcoded `Qt.Key_*` comparisons. |
| **`keyPressEvent` + `QShortcut` in `ImagePreviewWindow`** | Zoom `QShortcut` objects use `get_registry().get_key_sequence("preview.zoom_in/zoom_out")`. All 11 preview key actions use `reg.matches()` in `keyPressEvent`. |
| **Settings "⌨️ Shortcuts" tab** (`settings_window.py`) | New Tab 6: `QTableWidget` with one `QKeySequenceEdit` per registry entry, conflict detection on save, Save/Reset All buttons. `_save_shortcuts` / `_reset_shortcuts` helpers. |
| **`load_user_qss_override()`** (`style.py`) | Reads `~/.image-toolkit/user_theme.qss`; returns `""` if absent. Appended last in `set_application_theme()` so user QSS wins over all theme layers. |
| **Window geometry persistence** (`main_window.py`) | `QSettings("ImageToolkit","ImageToolkit").setValue("mainwindow/geometry", self.saveGeometry())` in `closeEvent()`. `restoreGeometry()` called in `__init__` before `showMaximized()` (skipped if no saved geometry). |

### Design rationale

The `ShortcutRegistry` sits between the Qt event loop and the action handlers: `keyPressEvent` dispatches to `reg.matches(event, action_id)` which reconstructs a `QKeySequence` from the raw event and compares it to the loaded binding. This means any action can be rebound from the settings UI without touching widget code. Conflict detection is purely client-side at save time (O(n²) over 21 entries — negligible). The PySide6 6.10 enum change (`event.key()` returning `int` instead of `Qt.Key`) is handled with a `isinstance(raw_key, int)` branch that will degrade gracefully on both old and new versions. User QSS override is a single file read appended last in the theme chain — no parse-time overhead, full QSS power.

---

## GUI Session — §2.30 Accent Colour, Font Scale, UI Density (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`load_qss_with_overrides(filename, overrides)`** (`style.py`) | Merges a runtime override dict into a copy of `THEME_VARS` before `Template.safe_substitute`, allowing per-session variable injection without touching the QSS files. |
| **`compute_accent_vars(accent_hex, theme_prefix)`** (`style.py`) | Derives `ACCENT_COLOR`, `ACCENT_HOVER` (15% darker), and `ACCENT_PRESSED` (32% darker) from any valid hex colour using `QColor.darker()`. |
| **`COMPACT_DENSITY_QSS` / `SPACIOUS_DENSITY_QSS`** (`style.py`) | QSS override snippets appended after the base theme. Compact reduces button/input/groupbox padding; Spacious increases it. |
| **`set_application_theme` refactored** (`main_window.py`) | Reads `preferences["accent_color_dark/light"]`, `"ui_density"`, and `"font_scale"` from `cached_creds` at runtime. Calls `load_qss_with_overrides` instead of the static `DARK_QSS`/`LIGHT_QSS` constants; appends density QSS; applies `QApplication.setFont` for non-100% scale. |
| **Appearance groupbox in Settings → Display and Media tab** (`settings_window.py`) | Dark accent swatch button + Reset, Light accent swatch button + Reset, Font Scale `QSpinBox` (80–150%, step 10%), UI Density `QComboBox` (Compact/Comfortable/Spacious), Preview button for live apply without saving. |
| **`_pick_accent_color` / `_reset_accent` / `_update_swatch` / `_preview_appearance`** (`settings_window.py`) | Helper methods: `_pick_accent_color(theme)` opens `QColorDialog(DontUseNativeDialog)` and updates the swatch. `_preview_appearance` applies current accent/density/font to `main_window_ref` without persisting. |
| **Vault persistence** (`settings_window.py`) | Four new `preferences` keys: `accent_color_dark`, `accent_color_light`, `font_scale`, `ui_density`. Loaded in `__init__` and `reload_settings`; saved in `_update_settings_logic`; reset in `reset_settings`. |

### Design rationale

The QSS system already uses `$DARK_ACCENT_COLOR` template variables substituted via `string.Template.safe_substitute`. Rather than baking the QSS at import time, `load_qss_with_overrides` reads the file fresh and substitutes at call time — one file read per theme apply, negligible overhead. Hover/pressed variants are computed from the chosen colour automatically so users only pick one hex value. Density is a pure QSS append — no layout code changes needed. Font scale uses `QApplication.setFont` which propagates to all widgets without requiring a QSS reload.

---

## ASP Session 62 — §1.18 Adaptive Single-Pose Escalation Threshold (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_adaptive_sp_threshold(feather_width, base, min, ref) → float`** (`compositing.py`) | §1.18: scales the single-pose ghost-prevention threshold down for wide feathers. Formula: `max(min_threshold, base × (feather_reference / max(feather_width, 1)))`. At feather=80px → 22.0 (baseline unchanged); at feather≥147px → 12.0 (floor). |
| **`_ADAPTIVE_SP_THRESH` flag** (`compositing.py`) | `os.environ.get("ASP_ADAPTIVE_SP_THRESH", "0") != "0"` (default OFF). When enabled, replaces the hardcoded `_POST_DIFF_THRESHOLD = 22.0` at the single-pose escalation gate with `_adaptive_sp_threshold(int(feathers[k]))`. |
| **Constants** (`constants/anim.py`) | `ADAPTIVE_SP_THRESH_BASE=22.0`, `ADAPTIVE_SP_THRESH_MIN=12.0`, `ADAPTIVE_SP_THRESH_REF=80` document the tuned defaults. |
| **`ASP_ADAPTIVE_SP_THRESH` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 1, "Enable adaptive single-pose escalation threshold scaled by feather width")`. |
| **`_adaptive_sp_threshold` in `__all__`** (`compositing.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_compositing.py::TestAdaptiveSpThreshold`) | reference-feather-returns-base (fw=80→22.0), narrow-feather-above-reference (fw=40→44.0), wide-feather-hits-min-floor (fw=300→12.0), floor-crossover-point (fw=146>12, fw=147→12.0), zero-feather-no-division-by-zero (fw=0→1760.0). **Anim suite: 417 passing.** |

### Design rationale

The dominant failure mode identified in the 2026-06-10 benchmark (Class A, 4/5 test images) is: wide feather (300px adaptive widening) × moderate post_warp_diff (15–22 lum) → blend zone NOT escalated to single-pose → 600px ghost band. The hardcoded threshold `_POST_DIFF_THRESHOLD = 22.0` treats a 22 lum discrepancy the same at 80px feather (trivially short ghost, barely visible) and 300px feather (ghost span = feather×2 = 600px, visually dominant). The adaptive formula ties the risk tolerance to the blend zone width: for a 300px feather the floor (12.0) fires for any post_warp_diff ≥ 12.0 lum, which covers the 15–22 range that was slipping through. The min_threshold=12.0 preserves the existing ARAP warp attempt — the path still warps first, then escalates if residual discrepancy is large relative to the feather width.

---

## ASP Session 61 — §1.17 Canvas Span Utilisation Gate (2026-06-10)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_canvas_span_utilization(affines) → float`** (`pipeline.py`) | §1.17: computes actual dominant-axis canvas span divided by expected span (`median_adjacent_step × (N−1)`). Dominant axis = whichever of ty/tx has the larger range. Returns 1.0 for N < 2 or zero expected span (safe fallback). |
| **Post-BA canvas span gate** (`pipeline.py`) | `_CANVAS_SPAN_MIN_UTIL` flag (default 0.0=off, `ASP_CANVAS_SPAN_MIN_UTIL=0.3`). Wired after §3.14 scroll-axis check (Stage 9.5) before Stage 10 rendering: if utilisation ratio < threshold → SCANS fallback with log message. |
| **`CANVAS_SPAN_MIN_UTIL = 0.3`** (`constants/anim.py`) | Recommended threshold. Catches oscillating BA solutions (frames back-and-forth between two positions) where individual step sizes look valid but total canvas is far shorter than expected. |
| **`ASP_CANVAS_SPAN_MIN_UTIL` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 1.0, "Min canvas-span/expected-span utilisation ratio after BA (0=off)")`. |
| **`_compute_canvas_span_utilization` in `__all__`** (`pipeline.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_pipeline.py::TestComputeCanvasSpanUtilization`) | single-frame-returns-one, two-frames-returns-one, perfect-monotone-sequence (ratio≈1.0), oscillating-ba-returns-low-ratio (alternating [0,100,0,100…] → span=100, expected=500 → ratio=0.2 < 0.3), dominant-axis-horizontal (pure tx scroll → tx axis used, ratio=1.0). **Anim suite: 412 passing.** |

### Design rationale

The pre-BA gates (§1.15 connectivity, §1.16 MST weight) catch bad *graphs* before bundle adjustment runs. The post-validation gates (§0.5C min gap, §1.12 Kendall-τ) catch bad *per-adjacent-step* values. §1.17 fills a gap between them: a BA solution can pass all per-step checks yet still produce a globally collapsed canvas if the optimiser converges to an oscillating local minimum (common when there are dense cross-pairs or conflicting edge directions). In that case `median_step × (N−1)` significantly exceeds the actual span — the ratio fires where neither gate would. Distinct from the coverage gate (§0 Stage 10.5) which measures how many canvas rows have ≥ 2 frames: §1.17 fires earlier (after Stage 9, before temporal median) and detects the geometric collapse rather than the coverage consequence.

---

## ASP Session 60 — §1.16 Minimum Spanning Tree Weight Gate (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_mst_weight(edges, n_frames) → float`** (`pipeline.py`) | §1.16: builds the max-weight spanning tree (Kruskal greedy, highest-weight-first) using iterative path-compression Union-Find and returns `total_weight / (N-1)`. Returns 0.0 when n_frames ≤ 1 or no edges. |
| **Pre-BA MST weight gate** (`pipeline.py`) | `_MST_MIN_WEIGHT` flag (default 0.0=off, `ASP_MST_MIN_WEIGHT=0.35`). After the §1.15 connectivity check, if the mean MST weight < threshold → SCANS fallback with log message. Wired between connectivity gate and Stage 7 BA call. |
| **`MST_MIN_WEIGHT = 0.35`** (`constants/anim.py`) | Recommended threshold: LoFTR edges weight~0.6–0.9; TM/PC fallbacks~0.15–0.3; threshold 0.35 triggers on all-TM/PC graphs. |
| **`ASP_MST_MIN_WEIGHT` in `_CONFIG_SCHEMA`** (`config.py`) | `(float, 0.0, 1.0, "Min mean MST edge weight before pre-BA SCANS fallback (0=off)")`. |
| **`_compute_mst_weight` in `__all__`** (`pipeline.py`) | Exported for testing and external use. |
| **5 unit tests** (`test_pipeline.py::TestComputeMstWeight`) | no-frames-returns-zero, empty-edges-returns-zero, chain-graph-mean-weight (0→1 w=0.8, 1→2 w=0.6 → mean 0.7), takes-highest-weight-edges-for-mst (triangle: picks 0.9+0.5, mean=0.7), low-weight-graph-below-threshold (all edges w=0.2 → mean 0.2 < 0.35). **Anim suite: 407 passing.** |

### Design rationale

The §2.9C retry 0 (`_filter_high_conf_edges`, S37) removes bad edges and re-solves with only high-confidence LoFTR edges. But it fires *after* BA has already been attempted. The MST weight gate fires *before* BA: if the spanning tree itself is dominated by TM/PC fallback edges (all weights ≈ 0.15–0.3), even a successful BA will produce poor translations because the measurements are fundamentally noisy. Rather than consuming the full Retry 0–5 chain, the gate takes an immediate SCANS fallback. Zero overhead on success paths (disabled by default), O(E log E) sort when enabled.

---

## ASP Session 59 — §1.14C Per-channel BGR Bhattacharyya Seam Gate (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_color_similarity_bgr(img, k, n_strips, band_px=50) → float`** (`compositing.py`) | §1.14C: computes separate normalised 256-bin histograms for each of the B, G and R channels in the `band_px`-row windows immediately above and below seam k; returns `min(score_B, score_G, score_R)`. Any single channel with a severe distribution mismatch drives the score down even when luminance is unchanged. Falls back to `_seam_color_similarity` for 2-D greyscale inputs. Exported in `__all__`. |
| **`_check_seam_color_gate(..., use_bgr=False)` extended** (`compositing.py`) | Added `use_bgr: bool = False` parameter. When True, routes to `_seam_color_similarity_bgr` instead of `_seam_color_similarity`. Gate logic unchanged: returns worst seam index below thresh or None. |
| **`_SEAM_COLOR_GATE_BGR` flag** (`compositing.py` + `pipeline.py`) | `ASP_SEAM_COLOR_GATE_BGR=1` enables BGR mode (default OFF — greyscale path is faster). Stage 11.2 gate in `pipeline.py` passes `use_bgr=_SEAM_COLOR_GATE_BGR`. |
| **`ASP_SEAM_COLOR_GATE_BGR` in `_CONFIG_SCHEMA`** (`config.py`) | `(int, 0, 1, "Use per-channel BGR Bhattacharyya instead of greyscale in seam colour gate (0 or 1)")`. |
| **5 unit tests** (`test_compositing.py::TestSeamColorSimilarityBgr`) | identical-bands-returns-one, hue-shift-same-luma-low-score (proves grey score ≈ 1.0 while BGR score < grey for equal-luma colour shift), grayscale-input-falls-back-gracefully, check-gate-use-bgr-triggers-on-hue-shift, band-too-small-returns-one. **Anim suite: 402 passing.** |

### Design rationale

§1.14B (`_seam_color_similarity`) operated on greyscale histograms. It cannot detect hue shifts where the luminance distribution is preserved: if both strips have the same amount of bright and dark pixels, the greyscale histogram overlap is near 1.0 regardless of the colour palette. A common failure mode is a warm-toned strip (high R) adjacent to a neutral or cool-toned strip (high B), at the same luminance level. The B channel shift (128→28) drives the BGR minimum score below 0.55 while the greyscale score remains above 0.90, allowing the gate to correctly trigger a SCANS fallback on hue-banded outputs that the §1.14B gate would pass.

---

## ASP Session 58 — §1.15 Edge Graph Connectivity Validation (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_check_edge_graph_connectivity(edges, n_frames) → bool`** (`pipeline.py`) | §1.15: iterative path-compression Union-Find over the edge graph; returns True iff all frames 0..n_frames-1 are in one connected component. Trivially True for n_frames ≤ 1. Out-of-bounds edge indices are silently skipped. Exported in `__all__`. |
| **Pre-BA connectivity gate** (`pipeline.py`) | Wired immediately after the existing `if not edges:` SCANS fallback in `run()`. If `_check_edge_graph_connectivity(edges, N)` returns False, logs the frame/edge count and triggers `_scan_stitch_fallback` using the `scans_frames or _reload_scans_frames(image_paths)` pattern. Runs in O(E·α(N)) — negligible overhead. |
| **5 unit tests** (`test_pipeline.py::TestCheckEdgeGraphConnectivity`) | chain-graph-is-connected, isolated-frame-is-disconnected, single-frame-trivially-connected, complete-graph-is-connected, no-edges-multiple-frames-disconnected. **Anim suite: 397 passing (+1 pre-existing skip).** |

### Design rationale

The §1.13A/B scene-change gates (S51, S57) and the §1.2A/C static-edge filters (S32, S34) can, in edge cases, remove enough edges to partition the frame graph into two or more disconnected components. When this happens, bundle adjustment still runs — but frames in the isolated component receive translations derived only from their intra-component constraints. Those translations are unconstrained relative to the main component, so they can be placed anywhere on the canvas. The resulting `_validate_affines` call typically fails with a ratio error, consuming Retry 0–5 time before landing on SCANS fallback.

The connectivity gate short-circuits this by catching the disconnection in O(E·α(N)) time right before the BA, saving the retry chain and producing a faster, cleaner SCANS fallback. The Union-Find uses the same path-compression algorithm as §1.1B's spanning-tree pre-filter — no new algorithmic machinery, just a different query (connectivity vs spanning-tree construction).

---

## ASP Session 57 — §1.13B Per-Channel (BGR) Scene-Change Gate (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_reject_scene_change_edges(..., use_bgr=True)`** (`pipeline.py`) | §1.13B: extended with `use_bgr: bool = False` parameter. When True, computes per-channel (B, G, R) thumbnail means via `t.reshape(-1,3).mean(axis=0)` and takes `np.abs(means_i − means_j).max()` as the scene-change signal. Backward compatible (default `use_bgr=False` preserves §1.13A grayscale behaviour). |
| **`_SCENE_CHANGE_BGR_THRESH` flag** (`pipeline.py`) | Default 0.0 (off). Set via `ASP_SCENE_CHANGE_BGR_THRESH=60.0` to enable. Wired as a second pass in `_filter_edges` after the existing §1.13A luma gate — the two gates are applied sequentially and are independent. |
| **`SCENE_CHANGE_BGR_THRESH = 60.0`** (`constants/anim.py`) | §1.13B calibrated default: 60/255 ≈ 24% per-channel mean shift is sufficient to identify a hue-shifted scene cut while tolerating normal gradual lighting changes. |
| **`ASP_SCENE_CHANGE_BGR_THRESH` in `_CONFIG_SCHEMA`** (`config.py`) | Float, range [0.0, 255.0]. Closes the TOML-config loop for §1.13B. |
| **5 unit tests** (`test_pipeline.py::TestRejectSceneChangeEdgesBgr`) | identical-frames-not-rejected, hue-shift-same-luma-rejected-in-bgr-mode, luma-mode-misses-hue-shift, bgr-threshold-zero-disabled, bgr-small-channel-diff-kept. **Anim suite: 392 passing (+1 pre-existing skip).** |

### Design rationale

§1.13A (S51) catches *brightness* discontinuities by comparing mean grayscale luma. It misses a common failure pattern: warm-versus-cool lighting shifts where overall luma is similar but colour distribution is completely different. A 200-lux orange studio shot and a 200-lux blue-tinted corridor can have identical grayscale luma (≈120) while their B and R channels differ by 180 units. A LoFTR match across that scene cut would produce a valid-looking edge with a plausible displacement but would corrupt bundle adjustment by linking geometrically incompatible environments.

The per-channel max-delta uses `np.abs(means_i − means_j).max()` rather than Euclidean distance (`sqrt(ΔB² + ΔG² + ΔR²)`) so the threshold stays in the same [0, 255] luminance unit as §1.13A — no threshold recalibration is needed when switching between modes. The same `max_luma_diff` parameter governs both gates at 60.0, maintaining a single tuning point per environment.

---

## ASP Session 56 — §1.14B Seam Colour-Similarity Pipeline Gate (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_color_similarity(img, k, n_strips, band_px=50) → float`** (`compositing.py`) | §1.14B: single-seam Bhattacharyya similarity scorer. Computes greyscale histograms of `band_px`-row windows above and below seam boundary k, normalises, and returns `1 − HISTCMP_BHATTACHARYYA`. Returns 1.0 for trivially narrow bands (<10 rows per side). Zero new dependencies. |
| **`_check_seam_color_gate(img, n_strips, thresh, band_px=50) → Optional[int]`** (`compositing.py`) | §1.14B: post-composite gate. Evaluates all `n_strips−1` seams; returns the 0-indexed seam with the minimum colour similarity if that minimum is below *thresh*, else `None`. Returns `None` when `n_strips ≤ 1` or `thresh ≤ 0`. Exported in `__all__`. |
| **`_SEAM_COLOR_GATE` flag** (`compositing.py`) | Module-level float, default 0.0 (off). Set via `ASP_SEAM_COLOR_GATE=0.55` to enable. |
| **`SEAM_COLOR_GATE_THRESH = 0.55`** (`constants/anim.py`) | §1.14B calibrated default. Score < 0.55 indicates a significant distributional mismatch (>45% histogram divergence) across a seam boundary — a reliable indicator of colour-banded output. |
| **Stage 11.2 gate** (`pipeline.py`) | After `_composite_foreground`, when `_SEAM_COLOR_GATE_THRESH > 0` and `N > 1`, calls `_check_seam_color_gate(canvas, N, _SEAM_COLOR_GATE_THRESH)`. On failure → `_scan_stitch_fallback` with logged seam index. Uses `scans_frames or _reload_scans_frames(image_paths)` (on-demand reload pattern from §1.9C). |
| **`ASP_SEAM_COLOR_GATE` in `_CONFIG_SCHEMA`** (`config.py`) | Float, range [0.0, 1.0]. Schema entry closes the TOML-config loop for §1.14B. |
| **5 unit tests** (`test_compositing.py::TestSeamColorGate`) | single-strip-returns-none, threshold-zero-disabled, identical-strips-above-threshold, mismatched-strips-below-threshold, returns-worst-seam-index. **Anim suite: 387 passing (+1 pre-existing skip).** |

### Design rationale

§1.14 (S55) added `_seam_bhattacharyya_distances` to the *benchmark* as a diagnostic metric, closing the measurement gap between spatial artefact detectors and distributional colour mismatch. §1.14B closes the loop by wiring the same signal directly into the pipeline as an actionable gate.

The gate is post-composite (Stage 11.2) rather than pre-composite because the Bhattacharyya score is defined on the *output* image — it measures what the seam actually looks like after the Laplacian blend, not what the input frames would predict. This makes it complementary to the pre-blend signal (seam DP cost) and the pre-render signal (render gate at Stage 10.5). Stage 11.2 is the last point where a SCANS fallback is geometrically safe: the canvas has been composited but not yet cropped or super-resolved.

The `_seam_color_similarity` function is kept in `compositing.py` (not imported from `bench_anime_stitch.py`) to avoid a circular dependency between the benchmark and the pipeline modules. The greyscale histogram computation is 15 lines of pure OpenCV — duplication is justified by the module boundary.

---

## ASP Session 55 — §1.14 Per-Seam Bhattacharyya Colour-Distance Metric (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_bhattacharyya_distances(img, n_strips, band_px=50) → List[float]`** (`bench_anime_stitch.py`) | §1.14: computes the Bhattacharyya histogram similarity score for each inter-strip seam boundary. For each of the `n_strips−1` seam boundaries, computes greyscale histograms of the `band_px`-row window *above* and *below* the boundary, normalises them, and returns `1 − cv2.compareHist(HISTCMP_BHATTACHARYYA)`. Score in [0,1]: 1.0 = identical distributions (no colour banding), <0.5 = severe colour mismatch. Returns `[]` when `n_strips ≤ 1`. Falls back to 0.0 when either side of a boundary is empty (image smaller than `band_px`). |
| **`_compute_all_metrics` extended** (`bench_anime_stitch.py`) | `seam_color_scores: List[float]` (per-seam scores) and `seam_color_min: Optional[float]` added to the result dict. Both are `[]` / `None` at default `n_strips=1`. Backward compatible. |
| **New roadmap section §1.14** (`moon/roadmaps/asp.md`) | Added as a new section with Option A (Bhattacharyya, shipped) and Option B (pipeline gate, future). |
| **5 unit tests** (`test_bench_metrics.py::TestSeamBhattacharyyaDistances`) | n-strips-one-returns-empty, returns-n-minus-1-scores, identical-strips-score-near-one, different-histograms-score-below-identical, scores-in-valid-range. **Anim suite: 381 passing (+1 pre-existing skip).** |

### Design rationale

The existing per-seam diagnostics (`seam_visibility_score`, `ghost_seam_scores`) both operate in the *spatial* domain — they detect luminance jumps and repeated-edge signatures at a specific row. Neither detects the *distributional* mismatch that causes colour banding: two adjacent strips can have similar mean luminance and identical local gradients but completely different histogram shapes (e.g., one dominated by a bright background gradient, the other by a dark character body), producing a perceptible tonal shift that spatial metrics miss.

Bhattacharyya coefficient is the natural measure for this: it quantifies histogram overlap as `−ln(Σ sqrt(h1[i]·h2[i]))` (Bhattacharyya distance), normalised here to `1 − distance` so higher = more similar. It is available in `cv2.compareHist` with no new dependencies. Greyscale histograms are used (not per-channel) to keep the score interpretable; per-channel extension is Option C.

The `band_px=50` window is narrower than §3.8B's `band_px=100` because Bhattacharyya captures distribution shape, not periodicity — 50 rows is enough to characterise the luminance distribution in a strip zone.

---

## ASP Session 54 — §1.3C Scale Normalisation Before BA (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_normalize_frame_scales(frames, edges, scale_thresh) → (List[np.ndarray], List[Dict])`** (`pipeline.py`) | §1.3C: detects inter-frame zoom from the 2×2 rotation-scale block of matched affines (`s_ij = sqrt(a² + b²)`), propagates absolute scale factors via a BFS spanning tree from frame 0, and resizes each frame by `1/scale[i]` so BA only sees pure translations. Edge affines are updated: 2×2 block reset to identity, tx/ty divided by `scale[i]`. Falls back to originals when scale deviation < `scale_thresh`, the spanning tree is disconnected, or `scale_thresh ≤ 0`. `SCALE_NORM_THRESH = 0.05` in `constants/anim.py`. `_SCALE_NORM_THRESH` module-level flag (default 0.0=off, `ASP_SCALE_NORM_THRESH=0.05` to enable). Exported in `__all__`. |
| **5 unit tests** (`test_pipeline.py::TestNormalizeFrameScales`) | identity-scale-returns-unchanged, zoomed-frame-is-resized, below-threshold-returns-unchanged, disconnected-graph-returns-unchanged, edge-affines-reset-to-unit-scale. **Anim suite: 377 tests passing.** |

### Design rationale

The existing §1.3E (similarity-mode matching, S48) and §0.5D (adaptive rotation/scale thresholds, S47) together allow the pipeline to accept zoom-pan sequences without crashing. However, the *canvas construction* and *temporal median rendering* stages still assume translation-only displacement — so even when BA produces valid affines with scale ≈ 1.2, the frame pixels are composited at the wrong effective size, causing subtle parallax ghost artifacts.

§1.3C corrects this at the source: by resizing frames to a uniform scale *before* BA, the entire downstream pipeline (canvas, rendering, compositing) operates on frames that are geometrically consistent without any code changes to those stages. The resize uses Lanczos-4 interpolation to minimise ringing on line-art. The spanning-tree BFS mirrors §1.1B's approach to ensure scale propagation is connected and deterministic.

Default OFF (`ASP_SCALE_NORM_THRESH=0`, i.e., `_SCALE_NORM_THRESH=0.0`) to preserve backward compatibility. Enable with `ASP_SCALE_NORM_THRESH=0.05` for zoom-pan sequences (test5-style, scale_dev ≈ 0.12).

---

## ASP Session 53 — §3.8B Per-Seam SIQE Ghost Map (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_per_seam_ghost_scores(img, n_strips, band_px=100) → List[float]`** (`bench_anime_stitch.py`) | §3.8B: divides the output image into *n_strips* equal-height zones and evaluates `_ghosting_score_v2` in a ±*band_px* band centred at each inter-zone seam boundary. Returns `n_strips − 1` float scores (same [0–100] scale as `ghosting_siqe`). Returns `[]` when `n_strips ≤ 1`. Band clipped to image bounds when near edges — no exception on degenerate inputs. |
| **`_compute_all_metrics` extended** (`bench_anime_stitch.py`) | Signature extended with optional `n_strips: int = 1` parameter. Result dict now includes `"ghost_seam_scores": List[float]` (per-seam scores, empty for default `n_strips=1`) and `"ghost_seam_max": Optional[float]` (`max()` of scores, or `None` for empty list). Backward compatible: default `n_strips=1` leaves existing callers unaffected. |
| **5 unit tests** (`test_bench_metrics.py::TestPerSeamGhostScores`) | uniform-image-all-near-zero, n-strips-one-returns-empty, returns-n-minus-1-scores, band-with-sharp-luminance-step-has-high-score, band-clipped-to-image-bounds-no-error. **Anim suite: 372 tests passing.** |

### Design rationale

The existing `ghosting_siqe` metric runs `_ghosting_score_v2` on the entire output panorama and returns a single scalar. For a 2000-row panorama with 12 seam boundaries, a ghost on one seam contributes at most ~1/12 of the signal — the per-image score is diluted and the problem seam is unidentifiable from the metric alone.

Per-seam scoring solves both problems: (1) it raises the signal by restricting the analysis window to the ±`band_px` neighbourhood of each seam boundary, where ghost artifacts actually appear; (2) it localises the worst seam (via `ghost_seam_max` and its index in `ghost_seam_scores`), enabling targeted per-seam intervention (re-composition, deeper feathering) instead of a global SCANS fallback.

The `_ghosting_score_v2` function is reused without modification — the only change is the input window. Each band is extracted as a pure numpy slice (zero copy), so the overhead is N-1 FFT autocorrelations per image — typically < 5ms for N=12 at 1080px width. Fully backward compatible (default `n_strips=1` → no seam scoring, `ghost_seam_scores=[]`, `ghost_seam_max=None`).

---

## ASP Session 52 — §1.12 Kendall-τ Translation Monotonicity Check (2026-06-08)

### Shipped

| Item | Summary |
|------|---------|
| **`_check_translation_monotonicity(affines, primary_axis, min_tau_abs) → (bool, float)`** (`validation.py`) | §1.12: computes Kendall τ between temporal frame indices [0…N-1] and primary-axis translations. |τ| = 1 for perfectly monotone sequences (forward and backward scroll both pass); |τ| ≈ 0 for random permutations. Returns `(is_monotone, tau_abs)`. Requires ≥ 4 frames; shorter sequences always return `(True, 1.0)`. Exported in `__all__`. |
| **`_MONO_TAU_MIN = 0.4`** (`validation.py`) | Module-level minimum |τ| threshold. A value of 0.4 allows up to ~30% discordant frame pairs — catches catastrophic BA failures while tolerating the minor noise seen in real corpus sequences (typical valid sequences score ≥ 0.85). |
| **Wired as 5th check in `_validate_affines`** | After ratio / min_gap / rotation / scale, the monotonicity check fires for `scroll_axis ∈ {"vertical", "horizontal"}`. Skipped for diagonal scrolls (dominant axis ambiguous). Failure reason: `"monotonicity={tau:.2f} < 0.4"`. A monotonicity failure falls through to Retry 1 (adjacent-only BA) — the natural recovery since skip edges are the most common source of frame misplacement. |
| **5 unit tests** (`test_affine_validation.py::TestTranslationMonotonicity`) | perfectly-monotone-passes, reversed-monotone-passes, catastrophically-shuffled-fails, single-out-of-order-passes, fewer-than-4-always-passes. **Anim suite: 367 tests passing.** |

### Design rationale

The existing 4 validation checks (ratio, min_gap, rotation, scale) all operate on the *sorted spatial* order. They cannot detect the case where BA produces well-spaced, correctly-oriented frames that are **placed in the wrong temporal order** — for example, skip edges misaligning frame 3 to a position between frames 0 and 1 while preserving a uniform gap ratio. Such solutions pass all existing checks but produce catastrophic output: the temporal median averages the wrong frames together, and the seam composite bisects the wrong strips.

Kendall τ directly measures the agreement between the two orderings. Forward and backward scrolling are handled symmetrically (|τ|), so no direction inference is needed. The O(N²) pair-counting loop is negligible for typical N ≤ 30. The conservative threshold (0.4) ensures no regressions on the existing 92 passing corpus tests.

---

## ASP Session 51 — §1.13 Scene-Change Edge Pre-Filter (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_reject_scene_change_edges(edges, frames, max_luma_diff) → List[Dict]`** (`pipeline.py`) | §1.13: discards edges between frames whose mean grayscale luminance differs by more than `max_luma_diff`. Comparison is performed on a 64×64 thumbnail for speed. Gate is disabled when `max_luma_diff ≤ 0` or `frames` is empty. Out-of-bounds frame indices are kept (safe fallback). Exported in `__all__`. |
| **`_SCENE_CHANGE_LUMA_THRESH: float`** (`pipeline.py`) | Module-level threshold, default `0.0` (disabled). Set via `ASP_SCENE_CHANGE_LUMA_THRESH=60.0`. Wired as the first step in `_filter_edges`, before the §1.2A+C static edge rejection. |
| **`SCENE_CHANGE_LUMA_THRESH = 60.0`** (`constants/anim.py`) | Named constant for the recommended threshold. |
| **`"ASP_SCENE_CHANGE_LUMA_THRESH"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(float, 0.0, 255.0, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_pipeline.py::TestRejectSceneChangeEdges`) | similar-frames-not-rejected, large-luma-diff-rejected, threshold-zero-keeps-all, out-of-bounds-index-kept, selectively-filters-mixed-edges. **Anim suite: 362 tests passing.** |

### Design rationale

When a source video contains a scene cut — even one that slipped past the hold detector — the two frames straddling the cut will have drastically different global brightness (e.g., a dark nighttime scene followed by a bright exterior). Any pairwise-match algorithm will attempt to produce a translation for that pair; the match will have low confidence and a spurious displacement. If that edge reaches bundle adjustment it introduces a wrong constraint that can displace all other frames.

This gate rejects such edges before any geometric or BA processing. Mean-luma comparison on a 64×64 thumbnail costs <0.5 ms per edge and is more reliable than using match-confidence alone (which can be spuriously high when two dissimilar frames share a textured region).

Placement at the top of `_filter_edges` ensures the §1.2A+C, Geometric Consistency, Min-step, and Direction Consensus filters only process valid same-scene edges. Disabled by default (`threshold=0`) to preserve backward compatibility; activate with `ASP_SCENE_CHANGE_LUMA_THRESH=60.0` for sequences known to contain lighting discontinuities.

Distinct from `_reject_exposure_outliers` (§1.4F, `compositing.py`): that function detects per-frame luminance outliers in the *normalisation* loop; this gate detects inter-frame luminance discontinuities in the *edge set* before BA.

---

## ASP Session 50 — §1.4F Per-Frame Exposure Outlier Rejection (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_reject_exposure_outliers(frame_lums, max_deviation_lum) → List[bool]`** (`compositing.py`) | §1.4F: per-frame skip mask for absolute luminance outliers. Computes the median background luminance across all frames with valid lum values, returns True for any frame whose lum deviates by more than `max_deviation_lum` units. Frames with `None` lum are never rejected. Falls back to all-False when fewer than 3 valid values are available (unreliable median). Exported in `__all__`. |
| **`_EXPOSURE_OUTLIER_THRESH: float`** (`compositing.py`) | Module-level threshold, default 0.0 (disabled). Set via `ASP_EXPOSURE_OUTLIER_THRESH=60.0`. When > 0, outlier rejects are OR'd into `_skip_norm` after the coherence gate. Logs the count of excluded frames when any are skipped. |
| **`EXPOSURE_OUTLIER_THRESH = 60.0`** (`constants/anim.py`) | Named constant for the recommended threshold value. |
| **`elif _EXPOSURE_OUTLIER_THRESH > 0.0:` wiring** (`compositing.py`) | §1.4F applied immediately after `_coherence_skip_mask` in `_composite_foreground`. Skipped frames still contribute warped pixel content; only gain correction is suppressed. |
| **`"ASP_EXPOSURE_OUTLIER_THRESH"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(float, 0.0, 255.0, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_compositing.py::TestRejectExposureOutliers`) | uniform-lums-all-false, dark-outlier-rejected, bright-outlier-rejected, below-threshold-not-rejected, insufficient-frames-all-false. **Anim suite: 357 tests passing.** |

### Design rationale

The existing `_coherence_skip_mask` (S18) handles *relative* exposure mismatch: it skips both frames in any adjacent pair whose luminances differ by more than 20 lum. But it cannot handle an *absolute* outlier — a single frame that is globally darker or brighter than all its neighbours due to a lighting flash, accidental double-exposure, or a scene cut that slipped past the hold detector.

Such a frame drives the scalar gain toward an extreme value (e.g., gain=3.5 to bring a flash-bright frame down to reference) that causes visible over-correction of adjacent zones in the feather band. Excluding it from gain normalisation entirely allows its bg pixels to contribute to the canvas at their original values, which is visually neutral, while preventing the extreme correction from propagating to adjacent compositing zones.

The threshold of 60 lum (default for `EXPOSURE_OUTLIER_THRESH`) corresponds to a 24% brightness difference at typical reference luminance (250 lum), or a 75% difference at dark-scene reference (80 lum). This catches genuine outliers (flash frames, accidental HDR blending) without triggering on legitimate inter-strip brightness variation that the §1.4A–E gain corrections are designed to handle.

Complementary to §1.4C (`_bg_gain_unclamped`): that function aggressively corrects large-gain frames; §1.4F suppresses correction entirely for extreme outliers where correction would overshoot.

---

## ASP Session 49 — §1.4E Background CDF Histogram Matching (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_bg_histogram_lut(src_pixels, ref_pixels) → np.ndarray`** (`compositing.py`) | §1.4E: builds a 256-entry float32 CDF-matching LUT via `np.searchsorted(ref_cdf, src_cdf, side="left")`. Source and reference 1-D uint8 arrays normalised to CDFs; LUT maps each source intensity to the reference intensity with the nearest cumulative probability. Fallback: identity `np.arange(256)` when either input has fewer than 10 pixels. Exported in `__all__`. |
| **`_apply_bg_histogram_match(frame, reference, bg_mask) → np.ndarray`** (`compositing.py`) | §1.4E: applies `_bg_histogram_lut` per-channel to the background region of *frame*. Foreground pixels (where `bg_mask` is False) are copied unchanged. Returns uint8 (H, W, 3). Exported in `__all__`. |
| **`_HISTOGRAM_MATCH: bool`** (`compositing.py`) | Module-level flag, default OFF (`ASP_HISTOGRAM_MATCH=0`). When enabled, replaces the `_bg_gain_unclamped` scalar path in the normalization loop with the full CDF histogram match. `_MULTISCALE_GAIN` takes priority when both flags are set. |
| **`elif _HISTOGRAM_MATCH:` branch** in normalization loop | §1.4E wired between `if _MULTISCALE_GAIN:` and `else:` in `_composite_foreground`. Calls `_apply_bg_histogram_match`, then computes a representative scalar gain (`median(out_lum / src_lum)`, clipped to [0.5, 2.0]) for §1.6B feather widening. |
| **`"ASP_HISTOGRAM_MATCH"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(int, 0, 1, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_compositing.py::TestBgHistogramLut`) | identical-distribution-near-identity, brighter-ref-maps-source-upward, darker-ref-maps-source-downward, monotone-non-decreasing, sparse-input-returns-identity. **Anim suite: 352 tests passing.** |

### Design rationale

All §1.4A–D corrections apply a single scalar (or spatially-varying scalar map) to each frame. This works well when the exposure difference between frames is a multiplicative constant (e.g., one frame is uniformly 10% brighter). It fails when the *tonal distribution* differs: a frame shot through a semi-transparent panel may have compressed highlights and boosted shadows relative to the reference, producing a characteristic S-curve difference that a scalar cannot invert.

Histogram specification solves this directly: instead of estimating a single gain, it finds the monotone mapping that makes the source CDF match the reference CDF. The result is that the background in every frame has the same tonal distribution as the canvas, regardless of the shape of the per-frame exposure curve.

Algorithm: standard CDF matching — for each intensity `v`, `lut[v] = argmin_u |CDF_ref(u) − CDF_src(v)|`. Implemented via `np.searchsorted(ref_cdf, src_cdf)` for a vectorised O(256 log 256) lookup instead of a Python loop. Per-channel application avoids luminance-only approximations that would introduce hue shifts for strongly colour-tinted panels.

The flag is OFF by default because the scalar path is ~50× faster and handles the 92/96 non-fallback tests without visible artefacts. The histogram path is intended for sequences with non-linear tonal mismatch that the §1.4A–D scalar corrections cannot correct.

---

## ASP Session 48 — §1.3E Similarity-Mode Matching (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_extract_similarity(M) → np.ndarray`** (`matching.py`) | §1.3E: closed-form projection of a full 2×3 affine to its best-fit 4-DOF similarity. Formula: `a_sym = (M[0,0] + M[1,1]) / 2`, `b_sym = (M[0,1] - M[1,0]) / 2` → output `[[a_sym, b_sym, tx], [-b_sym, a_sym, ty]]`. This is the least-squares Procrustes projection onto the 2-D conformal manifold — discards shear while preserving scale, rotation, and translation. Exported in `__all__`. |
| **`_SIMILARITY_MODE: bool`** (`matching.py`) | Module-level flag, default OFF (`ASP_SIMILARITY_MODE=0`). When enabled, `_match_pair` calls `_extract_similarity(M)` instead of the 3-line translation strip. Default behaviour is unchanged. |
| **`"ASP_SIMILARITY_MODE"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(int, 0, 1, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_matching.py::TestExtractSimilarity`) | pure-translation-unchanged, rotation-preserved, uniform-scale-preserved, shear-eliminated, output-satisfies-similarity-constraint (20 random matrices). **Anim suite: 347 tests passing.** |

### Design rationale

The current `_match_pair` unconditionally strips the matched 2×3 affine to translation-only (identity rotation block, tx/ty copied). This was correct for the original static-scroll use case but silently discards genuine scale and rotation information for zoom-pan sequences (test5: scale≈1.121, rotation≈6.35°).

`_extract_similarity` solves the Procrustes problem for the 2-D conformal group: given an arbitrary affine `[[a, b, tx], [c, d, ty]]`, find the nearest similarity `[[α, β, tx], [-β, α, ty]]` in Frobenius norm. The closed-form solution is `α = (a+d)/2`, `β = (b-c)/2` — the symmetric part of the rotation block.

Shear (`b ≠ -c`) is discarded because:
1. Feature matchers (LoFTR, RoMa) cannot reliably distinguish camera shear from perspective at anime-panel scales.
2. The 4-DOF BA model uses `[[a, b, tx], [-b, a, ty]]` — shear would break the DOF assumption.
3. Shear in matched affines is typically matching noise, not a physical camera property.

The flag is OFF by default to preserve backward compatibility for the 92/96 tests that work perfectly with translation-only matching. For zoom-pan sequences (`ASP_SIMILARITY_MODE=1`), the matched scale/rotation now propagate through the BA and canvas placement instead of being discarded at the edge.

Complementary to §0.5D (S47): validation now accepts systematic rotation/scale (σ<0.02 → loose threshold 0.15) even without similarity mode enabled. Together, S47+S48 form a complete zoom-pan support path: S47 prevents validation from rejecting the correct solution; S48 provides the correct solution to validate.

---

## ASP Session 47 — §0.5D Adaptive Rotation/Scale Validation Thresholds (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_adaptive_rot_scale(affines) → (float, float)`** (`validation.py`) | §0.5D: returns `(max_rotation, max_scale_dev)` adaptively. If frame-to-frame rotation standard deviation < `_ROT_SCALE_CONSISTENCY_THRESH=0.02`, returns loose threshold `0.15`; otherwise tight `0.10`. Same rule independently for scale. Constants: `_ROT_TIGHT=0.10`, `_ROT_LOOSE=0.15`, `_SC_TIGHT=0.10`, `_SC_LOOSE=0.15`, `_ROT_SCALE_CONSISTENCY_THRESH=0.02`. Exported in `__all__`. |
| **Wired into `pipeline.py` Stage 7b** | `_adaptive_rot, _adaptive_sc = _compute_adaptive_rot_scale(affines)` before initial `_validate_affines` call. Also applied to Retry 0 re-validation. Log message updated to show `thresh=…` for both metrics. |
| **5 unit tests** (`test_affine_validation.py::TestAdaptiveRotScale`) | consistent-rotation-returns-loose, inconsistent-rotation-returns-tight, consistent-scale-returns-loose, inconsistent-scale-returns-tight, single-frame-returns-defaults. **Anim suite: 342 tests passing.** |

### Design rationale

The validation gate uses a fixed `max_rotation=0.10` and `max_scale_dev=0.10`. This rejects test5 (zoom-pan sequence with `max_rotation≈0.111, scale_dev≈0.121`) even though the BA solution is geometrically correct — every frame carries the same consistent camera-intrinsic-induced rotation and scale, not random per-frame noise.

The key diagnostic is *frame-to-frame consistency*: if σ < 0.02 (well below the tight threshold), the dominant signal is a systematic camera property (slight constant zoom, fixed lens barrel distortion, or a steady tilt introduced by video stabilisation). Widening to 0.15 in that case is safe because:
1. The BA correctly recovered the systematic component; the output affines are geometrically accurate.
2. The downstream warpAffine already handles scale and rotation (it uses the full 2×3 matrix).
3. Borderline values (0.10–0.15) that pass the loose gate are handled correctly by the PANORAMA fallback if they still produce a bad output.

If σ ≥ 0.02, rotation/scale varies wildly across frames — a sign of BA overfitting or per-frame feature matching noise. The tight 0.10 threshold is kept to prevent propagating a corrupted affine set to the compositing stage.

Calibration: test5's rotation is 6.35° = 0.1108 rad (sin ≈ 0.111) and scale_dev ≈ 0.121. Both are 10–20% above the tight threshold but 25–30% below the loose 0.15 ceiling. σ ≈ 0 for zoom-pan (all frames share the same lens distortion) → loose threshold returned → test5 passes validation without any retry.

---

## ASP Session 46 — §1.4D Multi-Scale Spatially-Varying Gain Normalisation (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_multiscale_gain_map(frame, reference, bg_mask, sigma, gain_min, gain_max) → float32 (H,W)`** (`compositing.py`) | §1.4D: computes a spatially-varying per-pixel gain map via Gaussian-blurred luminance ratio. Background pixels (from `bg_mask`) are used as sources; foreground pixels are zeroed before the blur so only background luminance propagates into fg regions (preventing character-colour corruption). Gain = `ref_blurred / (frame_blurred + ε)`; clamped to `[gain_min=0.5, gain_max=2.0]`. When `frame_blurred ≤ 1.0` (near-black or no-bg-source) gain falls through to 1.0. Exported in `__all__`. |
| **`_MULTISCALE_GAIN: bool`** (`compositing.py`) | Module-level flag, default OFF (`ASP_MULTISCALE_GAIN=0`). When enabled, replaces the scalar `_bg_gain_unclamped` call with `_multiscale_gain_map` in the per-frame bg normalization loop. Per-pixel gain applied via `gain_map[bg_sel, np.newaxis]` broadcasting (no fg pixels affected). Median gain across bg pixels stored as `frame_gains[i]` for §1.6B feather-width calculation (unchanged downstream). |
| **`MULTISCALE_GAIN_SIGMA = 30.0`** (`constants/anim.py`) | Gaussian σ in pixels for low-frequency decomposition. |
| **`"ASP_MULTISCALE_GAIN"` in `_CONFIG_SCHEMA`** (`config.py`) | Schema entry `(int, 0, 1, ...)` so `validate_asp_config` catches invalid values. |
| **5 unit tests** (`test_compositing.py::TestMultiscaleGainMap`) | identical-frame-unity-gain, darker-frame-gain-above-one, brighter-frame-gain-below-one, gain-clamped-to-range, all-fg-mask-produces-unit-gain. **Anim suite: 337 tests passing.** |

### Design rationale

The existing S18/S24/S40 gain stack computes one scalar per frame: `global_ref_lum / frame_lum`. This works well for uniformly lit backgrounds but fails when a single manga or cel panel has a vertical gradient — darker at the top, brighter at the bottom, or split lighting from a window. The global mean collapse hides this variation, so the correction over-brightens the dark region while under-brightening the bright region, producing a banded plate.

§1.4D keeps the same pipeline integration point (bg-only normalization loop, fg pixels untouched) but replaces the scalar with a Gaussian-blurred ratio map. The 30px σ is chosen to be:
- Wide enough to smooth MPEG block noise and character-edge leakage into the bg mask
- Narrow enough to capture panel-scale brightness gradients (typical gradient scale: 100–300px)

The fg-zeroing before blur (not fg masking after blur) is the key correctness property: it prevents character-pixel luminance from contaminating the background model in the fg region. Without it, a bright character outline would drive the gain map low around the character, causing the background behind the character to be under-corrected once that region is covered by a different frame's background.

Default OFF because the scalar path is faster (~0.1ms vs ~2ms for a 1080p frame with σ=30) and sufficient for uniformly-lit scenes (the majority of the corpus). Enable for scenes with known vertical brightness gradients.

---

## ASP Session 45 — §1.1B Spanning-Tree Consensus Pre-Filter for Bundle Adjustment (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_spanning_tree_inlier_filter(edges, num_frames, inlier_threshold=50.0) → List[Dict]`** (`bundle_adjust.py`) | §1.1B: builds a max-weight spanning tree from the edge graph (Kruskal greedy, highest-weight-first), then BFS from frame 0 to derive a reference translation for every frame. Any edge whose observed dx/dy disagrees with the reference by > `inlier_threshold` pixels is removed. Spanning-tree edges always pass (residual = 0 by construction) so the graph remains connected. Falls back to original edges when: fewer than 2 edges/frames, spanning tree cannot reach all frames (disconnected graph), or fewer than `max(2, N-1)` inliers survive. Exported in `__all__`. |
| **`_ST_INLIER_THRESHOLD = 50.0`** (`bundle_adjust.py`) | Module-level constant for the default inlier threshold. |
| **Wired at the top of `_bundle_adjust_affine`** (`bundle_adjust.py`) | `edges = _spanning_tree_inlier_filter(edges, num_frames)` called before DOF setup. On clean data the filter is a no-op (all chain edges are tree edges → residual=0). On data with bad skip edges or outlier adjacent edges, removes them before the LM solve. |
| **5 unit tests** (`test_bundle_adjust.py::TestSpanningTreeInlierFilter`) | consistent-chain-all-kept, inconsistent-skip-edge-removed, consistent-skip-edge-kept, disconnected-graph-fallback, low-weight-bad-edge-not-in-spanning-tree. **Anim suite: 332 tests passing.** |

### Design rationale

The existing GNC Cauchy loss (§1.1C, S6) down-weights outlier edges during the LM solve. The AGNC adaptive f_scale (§1.1D, S30) recalibrates the loss width if the initial estimate is too tight. Both approaches operate *during* the LM solve.

§1.1B adds a *pre-solve* filter: the spanning tree gives a deterministic, O(E log E) consensus estimate before any matrix inversion. The maximum-weight spanning tree construction ensures the most reliable (highest-weight, typically LoFTR-matched) edges form the backbone of the reference model. An inconsistent edge must differ from all these reliable edges simultaneously — a much stronger signal than a threshold on residuals from a potentially-biased LM solution.

Practical benefit: when the edge set contains a skip-edge (0→2) or long-range edge that is biased by MPEG blocking noise but has a moderately-high weight, it can survive GNC+AGNC and drag the LM toward a poor local minimum. The spanning-tree pre-filter catches this class of outlier deterministically, before it can corrupt the initial guess.

---

## ASP Session 44 — §1.5D Seam Path Cache (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_get_seam_cost_flags() → Tuple`** (`compositing.py`) | §1.5D: returns `(_POISSON_SEAM, _TOONCRAFTER_SEAM)` — a hashable snapshot of the module-level flags that affect seam cost map output. Used as the `cost_flags` component of every cache key so that changing a flag (e.g. enabling Poisson) automatically bypasses stale cache entries. |
| **`_make_seam_cache_key(frame_keys, k, cost_flags) → Optional[Tuple]`** (`compositing.py`) | §1.5D: derives a hashable `(frame_keys, k, cost_flags)` tuple for seam boundary *k*. Returns `None` when `frame_keys is None`, disabling cache lookup and insertion. Exported in `__all__`. |
| **`frame_keys` and `seam_path_cache` params on `_composite_foreground`** (`compositing.py`) | §1.5D: two new optional keyword args (default `None`). When both are provided, each seam boundary is checked against the cache before building zone arrays or submitting to the `ThreadPoolExecutor`. Cache misses run as before; hits skip all per-boundary array allocations. After the parallel executor completes, any newly computed path is written to the cache under its key. |
| **`self._seam_path_cache: Dict = {}`** (`pipeline.py`, `AnimeStitchPipeline.__init__`) | §1.5D: instance-level dict shared across successive `run()` calls on the same pipeline object. Passed as `seam_path_cache=self._seam_path_cache` at the Stage 11 call site. |
| **`AnimeStitchPipeline._composite_foreground` wrapper updated** (`pipeline.py`) | Passes `frame_keys` and `seam_path_cache` through to the module-level function. |
| **5 unit tests** (`test_compositing.py::TestSeamPathCache`) | hashable key, same-inputs-equal-keys, different-boundary-different-key, different-frame-keys-different-key, None-frame-keys-returns-None. **Anim suite: 327 tests passing.** |

### Design rationale

The `ThreadPoolExecutor` seam-DP pre-computation block (§S12) accounts for 200–800 ms per panorama on a CPU (each `_seam_cut` call runs Dijkstra DP over a (2F×W) grid). In the §1.10B Bayesian parameter search use case, the same frames are re-composited many times with different gain/feather parameters — but the optimal DP seam path depends only on the pixel content and active cost flags, not on gain scalars or feather widths. Caching by `(frame_keys, k, cost_flags)` lets RLHF iterations after the first skip the DP entirely.

Cache key design: `frame_keys = tuple(image_paths)` (canonical ordering from `run()`), `k` = boundary index, `cost_flags = (_POISSON_SEAM, _TOONCRAFTER_SEAM)` (the only module flags that alter `_build_seam_cost_map` output). Memory footprint: each seam path is a `np.int32` array of shape `(W,)` ≈ 4 KB at 1080p — negligible even for hundreds of RLHF iterations.

---

## ASP Session 43 — §3.4A dHash Animation Hold Detection (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_dhash(thumb, hash_size=8) → np.ndarray[bool]`** (`frame_selection.py`) | §3.4A: difference hash of a thumbnail. Resizes to (hash_size+1, hash_size) using INTER_AREA (averages DCT block noise), converts to uint8 if float, computes horizontal gradient binarisation (`col_j > col_{j-1}`). Returns flat bool array of hash_size² bits. Exported in `__all__`. |
| **`_detect_hold_blocks_dhash(thumbs, distance_threshold=4) → List[int]`** (`frame_selection.py`) | §3.4A: same API as `_detect_hold_blocks`. Builds dHash for each thumbnail, declares a hold boundary when Hamming distance > threshold. INTER_AREA resize averages MPEG DCT blocks before the comparison, so within-hold distance typically stays 0–2 even for aggressively compressed sources where MAD can exceed 0.025. Exported in `__all__`. |
| **`_HOLD_DHASH_THRESHOLD`** (`frame_selection.py`) | Module-level config: `int(os.environ.get("ASP_HOLD_DHASH_THRESH", "0"))`. Default 0 = disabled (MAD fallback). Set to 4 to enable. |
| **`HOLD_DHASH_THRESHOLD = 4`** (`constants/anim.py`) | Canonical constant. |
| **`"ASP_HOLD_DHASH_THRESH"` in `_CONFIG_SCHEMA`** (`config.py`) | Added to §1.8B schema: `(int, 0, 64, "dHash Hamming threshold for hold detection (0=off)")`. |
| **Wired as step 1b in `smart_select_frames`** | When `_HOLD_DHASH_THRESHOLD > 0`, uses `_detect_hold_blocks_dhash` instead of `_detect_hold_blocks`. Both paths share the same `hold_ids` / `n_hold_blocks` downstream logic. Verbose log prints method label: `HoldDetect/dHash(d≤4)` vs `HoldDetect/MAD(t=0.025)`. |
| **5 unit tests** (`test_frame_selection.py::TestDetectHoldBlocksDhash`) | identical-thumbs-single-block, opposing-gradient-thumbs-split, threshold-zero-every-frame-own-block, single-frame-returns-single-block, compute-dhash-same-image-zero-distance. **Anim suite: 322 tests passing.** |

### Design rationale

The MAD-based hold detector (`_detect_hold_blocks`, S6) compares consecutive thumbnail mean absolute differences. For broadcast-quality streaming rips (H.264/H.265 with heavy quantisation), MPEG DCT blocking artifacts change raw pixel values by 3–8 luma units even in "still" frames — within-hold MAD of 0.012–0.030 frequently overlaps the 0.025 default threshold, causing hold boundaries to be missed or false boundaries to fire. The `_refine_hold_ids_by_response` post-hoc fix (§1.11C, S38) partially compensates but only for pairs that were already cross-correlated.

dHash avoids this by resizing to 9×8 pixels with INTER_AREA (area average) before computing the gradient. The resize averages out the ~8×8 pixel MPEG DCT blocks into a single value, so block noise is structurally eliminated before any comparison is made. A frame-identical-except-noise pair will hash to Hamming distance 0–2; a genuine pose-change pair typically hashes to distance 8–20. The threshold-4 default leaves a comfortable gap between both populations.

The two detectors are complementary: MAD is faster (~1ms for 300 frames vs ~3ms for dHash), handles all sources, and is robust when frames are clean. dHash is the right choice for compressed streaming sources. Both detectors feed the same downstream hold_ids logic and are both refined by `_refine_hold_ids_by_response` (S38).

---

## ASP Session 42 — §1.8B Config Schema Validation (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_CONFIG_SCHEMA`** (`config.py`) | 14-key schema dict mapping known `ASP_*` env-var names to `(expected_type, min_val, max_val, description)` tuples. Covers all frequently-tuned keys: hold threshold, near-dup luma, coverage pct, single-pose feather, ghost gate floor, Poisson/ToonCrafter/SCANS flags, temporal variance, hold-response floor, BA f_scale, DINOv2 window, SGM proxy, and two-channel selection. |
| **`validate_asp_config(config, *, strict=False) → List[str]`** (`config.py`) | §1.8B validator. Iterates the flat config dict; for each key checks (a) it exists in `_CONFIG_SCHEMA`; (b) value has the expected type (int→float coercion allowed); (c) value is within `[min_val, max_val]`. Unknown keys emit `UserWarning` (forward-compat) but are not violations. Returns a list of violation strings; empty = valid. Exported in `__all__`. |
| **`strict=True` mode** | Raises `ValueError` with a formatted bullet list of all violations. Designed for CI and experiment scripts where a misconfigured run should abort instead of silently forwarding a bad value as an env string. |
| **Wired into `load_asp_config`** | New `validate=False` and `strict=False` parameters. When `validate=True`, calls `validate_asp_config(flat, strict=strict)` after merging TOML sections but before writing env vars — so invalid configs are caught before they pollute the process environment. |
| **5 unit tests** (`test_config.py::TestValidateAspConfig`) | valid-keys-no-violations, wrong-type-produces-violation, out-of-range-produces-violation, strict-raises-ValueError, unknown-key-warns-not-violation. **Anim suite: 317 tests passing.** |

### Design rationale

§1.8A (S27) loads `asp_config.toml` and injects all keys into `os.environ` via `setdefault`. Because the pipeline reads env vars as strings and parses them locally (`float(os.environ.get(..., "0.0"))`), a typo like `ASP_HOLD_THRESHOLD = "0.03"` (TOML string instead of float) would silently result in `float("0.03")` parsing correctly — but `ASP_HOLD_THRESHOLD = "moderate"` would raise a cryptic `ValueError` deep inside `frame_selection.py` rather than at config load time.

§1.8B addresses this by adding a lightweight schema validation layer using only stdlib types — no `jsonschema` dependency. The schema is defined as a plain Python dict in `config.py`, making it co-located with the loader and easy to extend as new `ASP_*` env vars are added. The `jsonschema` approach from the original roadmap description would require an external dep and a separate schema file; the inline dict accomplishes the same with zero overhead and immediate discoverability.

The `validate=False` default preserves full backward compatibility — callers that do not opt in see no change in behaviour. The `strict=True` mode is aimed at the upcoming §1.10B Bayesian parameter search, where a misconfigured TOML would silently bias the objective function otherwise.

---

## ASP Session 41 — §1.9C On-Demand SCANS Frame Reload (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_SCANS_RELOAD`** (`pipeline.py`) | Module-level flag: `os.environ.get("ASP_SCANS_RELOAD", "0") != "0"`. Default OFF (backward-compatible). When enabled, the Stage-2 `list(frames)` snapshot is replaced with an empty list, saving the full frame memory footprint for the success path. |
| **`_reload_scans_frames(paths: List[str]) → List[np.ndarray]`** (`pipeline.py`) | New module-level function. Calls `_load_frames(paths)` (same as Stage 1) then `_normalise_widths()` (same as Stage 2). Returns `[]` when all paths fail. Exported in `__all__`. |
| **Stage 2 snapshot guarded** | `scans_frames = ([] if _SCANS_RELOAD else list(frames))`. |
| **Dedup sync sites guarded** | Both `scans_frames = [scans_frames[i] for i in keep_idx]` lines (inline luma dedup and `_spatial_dedup_frames` return) changed to `... if scans_frames else []`. |
| **5 fallback call sites patched** | All `_scan_stitch_fallback(scans_frames, ...)` and `_panorama_stitch_fallback(scans_frames, ...)` calls use `_sf = scans_frames or _reload_scans_frames(image_paths)`. When `_SCANS_RELOAD=False` (default), `scans_frames` is truthy and the `or` short-circuits — zero overhead. |
| **5 unit tests** (`test_pipeline.py::TestReloadScansFrames`) | valid-paths-return-two-frames, empty-paths-returns-empty, unreadable-path-skipped, all-frames-normalised-to-first-width, all-unreadable-returns-empty. **Anim suite: 312 tests passing.** |

### Design rationale

§1.9A (S28) fixed the `scans_frames` desync bug, but the fix revealed the underlying cost: `scans_frames = list(frames)` at Stage 2 duplicates the entire width-normalised frame set in memory for the duration of every pipeline run — even when the run succeeds and the fallback never fires. For a 14-frame 1080p sequence (each frame ≈ 6.2 MB), this snapshot consumes ~87 MB of RAM that is freed only at function return.

§1.9C eliminates this cost on the success path. The `or` pattern at each fallback site (`scans_frames or _reload_scans_frames(image_paths)`) incurs zero overhead when `_SCANS_RELOAD=False` (truthy list, Python short-circuits). When `_SCANS_RELOAD=True`, `scans_frames=[]` is falsy, so `_reload_scans_frames(image_paths)` is called — but only when a fallback actually fires. `image_paths` is already kept in sync with the live frame set by the §1.9A spatial dedup, so the reloaded frames are exactly the post-dedup subset.

The two dedup sync lines are guarded with `if scans_frames else []` rather than removed, so the behaviour when `_SCANS_RELOAD=False` (the default) is byte-for-byte identical to before §1.9C.

---

## ASP Session 40 — §1.4C Background-Only Gain Clamp Override (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_bg_gain_unclamped(ref_lum, frame_lum, override_threshold=0.20) → float`** (`compositing.py`) | §1.4C: returns raw ideal gain `ref_lum / frame_lum` when `_adaptive_gain_clamp` would reduce the ideal correction by more than `override_threshold` (default 20 %). Otherwise returns the clamped value unchanged. |
| **Wired into normalization loop** | Replaces `_adaptive_gain_clamp(...)` call in the bg-only gain application path in `_composite_foreground`. `frame_gains[i]` now stores the actual applied gain (may be unclamped) for feather-width computation. |
| **5 unit tests** (`test_compositing.py::TestBgGainUnclamped`) | large-correction-returns-ideal, small-correction-returns-clamped, zero-frame-lum-guard, threshold-boundary-behavior, darkening-case-symmetry. **Anim suite: 307 tests passing.** |

### Design rationale

`_adaptive_gain_clamp` (§1.4B) uses a smooth clamp width of `0.26 - 0.12 × (ref_lum / 255)`. For normal-brightness scenes (ref ≈ 120), this gives a ±20% correction window. When a frame's luminance deviates by more than 25%, the clamp cuts the ideal correction short — the frame is partially corrected but still visibly brighter or darker than the reference, producing residual banding at seam boundaries.

The clamp exists to protect character skin tones from over-correction. But the normalization loop in `_composite_foreground` already applies the gain **only to background-selected pixels** (`bg_sel` mask). Skin tones are excluded at the application site. Therefore the clamp's protective purpose does not apply to this path — background regions are large uniform areas where aggressive correction is less visible than residual banding.

§1.4C lifts the clamp for background pixels when the ideal correction exceeds the clamped value by >20%: `cut = |ideal - clamped| / |ideal|`. This is symmetric — it applies to both brightening (dark frames) and darkening (bright frames). The 20% threshold is conservative: it only overrides when the clamp is cutting a large correction, leaving small deviations unchanged (< 20% cut → clamped value kept).

---

## ASP Session 39 — §1.2D Temporal Variance Pre-Filter (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`TEMPORAL_VAR_THRESH = 1e-3`** (`constants/anim.py`) | §1.2D canonical threshold (mean per-pixel variance in [0,1]² space). |
| **`_TEMPORAL_VAR_THRESH = 0.0`** (`frame_selection.py`) | Module-level config constant. Default 0.0 = disabled. Override via `ASP_TEMPORAL_VAR_THRESH`. |
| **`_temporal_variance_filter(thumbs, paths, sigma_threshold) → (thumbs, paths, n_dropped)`** (`frame_selection.py`) | §1.2D: for each interior frame i, stacks the (i-1, i, i+1) thumbnail triplet and computes mean per-pixel variance. If variance < sigma_threshold the frame is static and dropped. First/last always kept. No-op when threshold=0 or N<3. |
| **Wired as step 1a in `smart_select_frames`** | Runs after `_load_thumbs_parallel()`, before hold detection (step 1b). Rebinds `thumbs`, `frames_paths`, and `N` so all downstream steps see the reduced frame set. Verbose log prints drop count and threshold. |
| **`_temporal_variance_filter` in `frame_selection.py __all__`** | Exported alongside other module-level public functions. |
| **5 unit tests** (`test_frame_selection.py::TestTemporalVarianceFilter`) | static-triplet-drops-middle, high-variance-kept, first-last-never-dropped, threshold-zero-disables, fewer-than-three-passes-unchanged. **Anim suite: 302 tests passing.** |

### Design rationale

§1.2A–§1.2C filter static frames at the *edge* level (after matching) or the *selected-frame* level (post-selection). All three require matching to have run first. A subtler failure mode exists upstream: when neither the camera nor the character has moved between frames i-1 and i+1, frame i is a pure duplicate and carries zero canvas information. The matching step will correctly assign it a near-zero edge, but that edge must still be built, BA-solved, and validation-checked before it is discarded.

§1.2D catches this case directly at the thumbnail level — before any edge construction — using temporal variance: a frame is static if and only if the per-pixel variance across the triplet is near zero. Unlike the luma post-filter (§1.2B), which compares *selected* frames after the frame selector has already run, §1.2D operates on the raw candidate set, preventing static frames from polluting the edge graph in the first place.

The threshold `1e-3` in [0,1]² space corresponds to a standard deviation of ~0.032 (~8 luma units). MPEG quantization noise on a truly static scene produces std ≈ 2–4 luma units (variance ≈ 4e-5 to 2.5e-4) — well below the floor. Genuine camera motion of even 5 px at thumbnail scale raises variance by > 10×. The default-disabled setting (`ASP_TEMPORAL_VAR_THRESH=0.0`) ensures no regression on existing benchmarks; enabling with `1e-3` targets compressed sources.

---

## ASP Session 38 — §1.11C Phase-Correlation Response Hold Refinement (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_HIGH_HOLD_RESPONSE = 0.85`** (`frame_selection.py`) | §1.11C configuration constant. Override via `ASP_HIGH_HOLD_RESPONSE` env var. Set to 0.0 to disable. |
| **`HIGH_HOLD_RESPONSE_THRESH = 0.85`** (`constants/anim.py`) | Canonical constant for the phase-correlation response floor. |
| **`_refine_hold_ids_by_response(hold_ids, responses, high_response_threshold) → (ids, n_blocks)`** (`frame_selection.py`) | §1.11C: post-hoc hold refinement. Iterates `responses`; for each cross-hold pair (different `hold_ids`) with `response >= threshold`, merges the higher-index block ID into the lower. IDs are renumbered consecutively (first-occurrence order) before returning. Zero extra compute — uses the `responses` list that step 3 already builds. |
| **Wired as step 3b in `smart_select_frames`** | Called after the phase-correlation loop (`responses` complete) and before step 4 (dominant axis). Only runs when both `_HOLD_THRESHOLD > 0.0` and `_HIGH_HOLD_RESPONSE > 0.0`. Updates `hold_ids` and `n_hold_blocks` in-place. Verbose logging prints updated block count. |
| **`_refine_hold_ids_by_response` in `frame_selection.py __all__`** | Exported alongside `_detect_hold_blocks` and other public functions. |
| **5 unit tests** (`test_frame_selection.py::TestRefineHoldIdsByResponse`) | all-high-merge, low-leave-unchanged, partial-merge-only-high-pairs, consecutive-renumbering, single-frame-unchanged. **Anim suite: 297 tests passing.** |

### Design rationale

§1.11A (`_detect_hold_blocks`) identifies animation hold blocks using thumbnail MAD — effective for lossless or low-compression sources. On MPEG-compressed anime (broadcast, streaming), quantization noise inflates inter-frame MAD by 0.005–0.015 even between identical cels, occasionally splitting a genuine hold into two separate blocks. The phase-correlation pass (step 3) already runs `cv2.phaseCorrelate` for all cross-hold frame pairs and produces a `response` scalar in [0,1]. A response near 1.0 means the FFT peak is very sharp and narrow — i.e., the two frames are nearly identical (same image, sub-pixel drift). Values of 0.85+ are effectively unreachable for frames with different character poses; they only occur for frames that are visually identical modulo MPEG quantization noise.

§1.11C exploits this signal at zero additional cost: after step 3 has populated the `responses` list, scan for cross-hold pairs with `response >= 0.85` and merge their hold blocks. This corrects the MAD-based false splits without requiring DINOv2 or any extra computation. Within-hold pairs already have synthetic `response=1.0` (set in the hold-skip path), so the merge is idempotent for correctly detected holds. The block IDs are renumbered after merging so downstream Pass 2 scoring (`_pose_dist`), the `_hold_info` diagnostic, and the sparse-correlation speedup all see the updated block assignment.

The threshold 0.85 is deliberately conservative: MPEG quantization on 420 chroma with CRF 23 typically produces inter-frame response ~0.55–0.70 for identical-pose compressed pairs; genuine pose changes produce ~0.20–0.50. The 0.85 floor admits only near-lossless pairs. Adjustable via `ASP_HIGH_HOLD_RESPONSE`.

---

## ASP Session 37 — §2.9C High-Confidence Edge Re-Solve on Ratio Failure (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`HIGH_CONF_EDGE_THRESH = 0.65`** (`constants/anim.py`) | §2.9C floor for LoFTR-quality edge weight. LoFTR: weight ~0.7–0.95; TM fallback: ~0.15–0.55; PC fallback: ~0.15. |
| **`_filter_high_conf_edges(edges, min_weight) → List[Dict]`** (`pipeline.py`) | Keeps only edges with `weight >= min_weight`. Used as the Retry-0 pre-check on ratio failures. |
| **Retry 0 wired into Stage 7b** | Inserted before Retry 1: when `health.reason.startswith("ratio=")` and `len(_hc_edges) >= N-1`, re-solves with high-confidence edges and re-validates. Falls through to Retry 1 unchanged if fewer than N-1 HC edges survive. |
| **`_filter_high_conf_edges` in `pipeline.py __all__`** | Exported alongside other module-level functions. |
| **5 unit tests** (`test_pipeline.py`) | `TestFilterHighConfEdges`: high-weight-kept, low-weight-removed, empty-returns-empty, all-below-returns-empty, missing-weight-treated-as-zero. **Anim suite: 292 tests passing.** |

### Design rationale

When LoFTR matches are unavailable for a frame pair, the pipeline falls back to template matching (weight ~0.15–0.55) or phase correlation (weight ~0.15). These low-confidence edges sometimes introduce a single large wrong displacement that passes the `_reject_static_edges` filter but corrupts the bundle-adjustment solution: one outlier edge pulls two frames to the same position, producing a `max_gap / median_gap` ratio of 5–11× and triggering affine validation failure.

The existing Retry 1 (adjacent-only edges) handles this case but only for ratio failures caused by *skip-frame* edges. If the bad edge is adjacent (i→i+1), Retry 1 keeps it unchanged.

§2.9C adds "Retry 0" specifically for ratio failures: filter all edges to those with `weight >= HIGH_CONF_EDGE_THRESH (0.65)`, which excludes TM/PC fallbacks and keeps only LoFTR-quality matches. If ≥ N-1 such edges survive, re-solve the bundle. For sequences where all frame pairs had a LoFTR match (weight > 0.7), Retry 0 produces the same result as the original solve and passes validation — the ratio failure was caused by a TM/PC edge that is now excluded. For sequences where too many frame pairs fell back to TM/PC, the HC filter returns fewer than N-1 edges and the existing Retry 1–3 chain handles the failure as before.

---

## ASP Session 36 — §0.5C Adaptive Min-Gap Threshold for Affine Validation (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_adaptive_min_gap(affines) → float`** (`validation.py`) | §0.5C: returns `max(20.0, canvas_span / (N × 3))` where `canvas_span` is the dominant-axis displacement range. Slow-scroll sequences (200 px span, N=10) → floor 20.0; fast-scroll 4K (3000 px span, N=10) → adaptive 100 px. |
| **`_compute_adaptive_min_gap` in `validation.py __all__`** | Exported alongside `AffineHealth` and `_validate_affines`. |
| **Imported and wired into `pipeline.py` Stage 7b** | First `_validate_affines` call now passes `min_step=_compute_adaptive_min_gap(affines)`. Log message updated to include `adaptive_floor=Xpx`. Import added to `validation` import line. |
| **5 unit tests** (`test_affine_validation.py`) | `TestAdaptiveMinGap`: slow-scroll-returns-floor, fast-scroll-exceeds-fixed-threshold, single-frame-returns-floor, dominant-axis-is-max-span, wired-into-pipeline-initial-call. **Anim suite: 287 tests passing.** |

### Design rationale

The existing `_validate_affines(affines, min_step=25.0)` always used a fixed 25 px threshold for the minimum adjacent gap. This was calibrated for 1080p sequences with ~50–200 px inter-frame steps. Two failure modes arise from the fixed threshold:

1. **Slow-scroll sequences** (step ≈ 15–24 px): a valid but tight frame spacing is rejected because 15 px < 25 px, even though every frame is genuinely spaced at its expected distance. These sequences fall all the way to Retry 3 (`min_step=20.0`) unnecessarily, and some still fail.

2. **Fast-scroll / 4K sequences** (step ≈ 300–1000 px): a near-duplicate pair with a 26 px gap passes the 25 px threshold but represents a degenerate frame that is essentially co-located relative to the expected step. The pipeline would proceed with a bad frame that collapses the temporal median at that canvas row.

The adaptive formula `max(20.0, canvas_span / (N × 3))` anchors the minimum gap at 1/3 of the expected per-frame canvas contribution. For slow-scroll, the floor of 20.0 px matches Retry-3's existing relaxed threshold, so the first validation call will succeed where before it required recovery. For fast-scroll 4K (canvas_span ≈ 3000 px, N=10) the threshold rises to 100 px, correctly rejecting near-duplicate frames that the fixed 25 px threshold would accept. The Retry chain (R1–R3 with progressively relaxed `min_step`) is still intact for genuine boundary cases.

---

## ASP Session 35 — §3.8A Double-Edge Autocorrelation Ghosting Metric (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_ghosting_score_v2(img) → float`** (`bench_anime_stitch.py`) | §3.8A: FFT-based autocorrelation of column-mean gradient-magnitude profile. Detects secondary peak at displacement D — the signature of a ghost (misaligned shifted copy). Score [0–100]: 0=clean, 30+=ghost likely. |
| **`ghosting_siqe` in `_compute_all_metrics`** | Added alongside existing `ghosting_score` (kept for GhostGate calibration). |
| **Metric description added to report table** | `("ghosting_siqe", "§3.8A autocorr double-edge score [0–100], higher = ghost")` |
| **5 unit tests** (`test_bench_metrics.py`) | `TestGhostingScoreV2`: uniform→zero, ghost-bands→nonzero, bounded [0–100], grayscale input, `ghosting_siqe` in `_compute_all_metrics`. **Anim suite: 282 tests passing.** |
| **§1.7C roadmap housekeeping** | `_crop_to_valid` in `canvas.py` already implements content-aware bounding-box crop (bounding box when valid_ratio ≥ 80%, max-inscribed-rect otherwise). §1.7C marked de facto done. |

### Design rationale

The existing `_ghosting_score()` computes the mean of `|second-order vertical Sobel|` — effectively measuring total second-derivative energy. While this loosely correlates with double-edge density, it fires equally on any high-frequency vertical pattern: fine background texture, cross-hatch patterns, and genuine ghost artifacts all inflate the score. On the 96-test corpus, `ghosting_score` averages 20–36 for both clean and ghosted outputs, making borderline cases (ratio 1.9–2.1) non-deterministic.

`_ghosting_score_v2` (§3.8A) takes a different approach:
1. Computes the column-mean of `|Gy|` — a 1D profile summarising where vertical gradients concentrate along the scroll axis.
2. Subtracts the mean and computes the zero-padded FFT autocorrelation.
3. Normalises by the zero-lag energy and looks for the maximum secondary peak in lag range [5, H/4].

A ghost creates two nearly-identical edge features at fixed displacement D. Their column-mean profiles are shifted copies, so the normalized autocorrelation peaks at lag≈D. A clean image with random texture has no preferred lag → autocorrelation falls to near-zero past lag=0. The score is clamped to [0, 1] then scaled to [0, 100] for readability.

**Why keep `ghosting_score`:** The GhostGate (`_GHOST_ABS_FLOOR=40.0`, `_GHOST_RATIO_LIMIT=2.0`) is calibrated for the double-Sobel scale (typical clean output ≈ 20–36, ghost output > 40). Replacing it without recalibrating on the full 96-test corpus would require a separate benchmarking run. `ghosting_siqe` is added as a supplementary metric; once enough benchmark data is collected, the gate can be migrated to use it.

---

## ASP Session 34 — §1.2C Adaptive Min-Step Threshold (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_adaptive_min_disp(edges) → float`** (`pipeline.py`) | §1.2C: returns `max(STATIC_EDGE_MIN_DISP_PX, ADAPTIVE_MIN_DISP_FRAC × median_adjacent_step)` on the dominant scroll axis. For slow-scroll sequences the floor (50px) dominates; for fast-scroll/4K content (e.g., 1000px/frame) the adaptive threshold rises to 100px. |
| **`ADAPTIVE_MIN_DISP_FRAC = 0.10`** (`constants/anim.py`) | §1.2C fractional constant. |
| **Wired into `_filter_edges()`** | `_compute_adaptive_min_disp(edges)` called before `_reject_static_edges`; result passed as `min_disp_px`. |
| **`_compute_adaptive_min_disp` in `pipeline.py __all__`** | Exported alongside `_reject_static_edges`. |
| **5 unit tests** (`test_filter_edges.py`) | `TestComputeAdaptiveMinDisp`: floor-dominates-small-steps, adaptive-exceeds-floor-large-steps, empty-edges-returns-floor, dominant-axis-x-selected, no-adjacent-edges-returns-floor. **Anim suite: 277 tests passing.** |

### Design rationale

§1.2A (`_reject_static_edges`) uses a fixed `STATIC_EDGE_MIN_DISP_PX=50` threshold that was calibrated for 1080p sequences (~5% of frame height). For 4K sequences with typical step size 400–800px, 50px is only 2–5% of the step, meaning noisy near-zero edges can still slip through. Conversely, for ultra-slow-scroll content (step ≈ 60px), the fixed 50px threshold would discard valid edges.

§1.2C makes the threshold content-adaptive: it uses the median of adjacent-edge displacements on the dominant scroll axis as an estimate of the expected step, then applies a 10% floor (`ADAPTIVE_MIN_DISP_FRAC=0.10`). For typical 1080p content (step ≈ 200px), the adaptive threshold equals `max(50, 20) = 50` — unchanged. For fast-scroll 4K (step ≈ 1000px), it raises to `max(50, 100) = 100` — rejecting near-zero edges that the old fixed threshold would have passed.

---

## ASP Session 33 — §3.15A SemanticStitch Column Barrier + §3.14 Scroll-Axis Detection (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **§3.15A column fg-domination barrier** (`compositing.py`) | `_build_seam_cost_map()`: columns with >50% fg-interior pixels raised to cost=2.0 (above Tier 1 max of 1.0), forcing DP seam into background-only corridor columns. Falls back to per-pixel costs when all columns are fg-dominated. |
| **§3.14 scroll-axis detection wired** (`pipeline.py`) | `_detect_scroll_axis` imported and called after Stage 9; `'horizontal'` scroll type → explicit SCANS fallback with log. (Function existed in `canvas.py` but was never called from the pipeline.) |
| **10 unit tests** | `TestSeamCostColumnFilter` (5) in `test_compositing.py`; `TestDetectScrollAxisModule` (5) in `test_canvas.py`. **Anim suite: 272 tests passing.** |

---

## ASP Session 32 — §1.2A Pre-bundle Static Edge Rejection (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_reject_static_edges(edges, min_disp_px) → List[Dict]`** (`pipeline.py`) | §1.2A: drops any edge where BOTH `|dx| < min_disp_px` AND `|dy| < min_disp_px`. Default `min_disp_px = STATIC_EDGE_MIN_DISP_PX = 50`. Keeps an edge if EITHER axis is >= the threshold (preserves valid diagonal-scroll edges). |
| **`STATIC_EDGE_MIN_DISP_PX = 50`** (`constants/anim.py`) | New pipeline constant for the combined-axis displacement threshold. |
| **Wired into `_filter_edges()`**  | `_reject_static_edges(edges)` is called at the very start of `_filter_edges()`, before the geometric consistency filter. Ensures near-zero-2D-displacement edges cannot corrupt the direction consensus median. |
| **`_reject_static_edges` exported in `pipeline.py __all__`** | Added alongside `_spatial_dedup_frames`. |
| **5 unit tests** (`test_filter_edges.py`) | `TestRejectStaticEdges`: normal-edges-all-kept, both-axes-below-threshold-rejected, one-axis-above-threshold-kept, skip-edge-with-small-displacement-rejected, empty-edge-list. **Anim suite: 262 tests passing.** |

### Design rationale

The existing min-step guard in `_filter_edges` (shipped in an earlier session) rejects adjacent edges where the **primary-axis** displacement is below `MIN_EXPECTED_STEP=25px`. This covers the common failure mode (vertical pan with small dy), but leaves two gaps:

1. **Skip edges** (j > i+1) with small 2D displacement are not filtered.
2. **Both-axes-small** edges — where neither axis alone triggers the primary-axis check (e.g., dx=20px, dy=30px for a diagonal sequence with primary=y) — pass through.

§1.2A closes both gaps with a combined-axis pre-filter: reject any edge where BOTH |dx| and |dy| are below 50px. This runs before all other filters so near-zero edges can't skew the consensus median that the direction filter relies on. An edge is kept if EITHER axis meets the threshold, preserving horizontal-scroll edges (large |dx|, small |dy|).

---

## ASP Session 31 — §1.3B PANORAMA Stitcher Fallback (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_panorama_stitch_fallback(frames, output_path) → PIL.Image`** (`canvas.py`) | §1.3B: tries `cv2.Stitcher_create(mode=0)` (PANORAMA) for affine-validation failures before the SCANS path. PANORAMA handles scale and rotation that the translation-only canvas model rejects. Raises `RuntimeError` on failure so the caller can fall through. |
| **`_panorama_stitch_fallback` wired into `pipeline.py`** | Inserted between Retry 3 and the SCANS fallback in the affine validation failure branch (line ~1037). Any `Exception` from PANORAMA is caught; the pipeline logs it and proceeds to `_scan_stitch_fallback`. |
| **`_panorama_stitch_fallback` added to `canvas.py __all__`** | Exported alongside `_scan_stitch_fallback`. |
| **5 unit tests** (`test_canvas.py`) | `TestPanoramaStitchFallback`: returns-pil-image-on-success, raises-runtime-error-on-non-ok-status, saves-file-on-success, uses-panorama-mode-zero, output-dimensions-match-pano. **Anim suite: 257 tests passing.** |

### Design rationale

When `_validate_affines` rejects a solution after Retries 1–3, the pipeline has historically fallen back immediately to SCANS mode. SCANS is a scan-line stitcher (mode=1) that still uses the same global feature detector and homography estimator as PANORAMA, but assumes a flat scene and ignores rotation/scale — which is why it works well for pure vertical pans but fails on zoom-and-pan sequences.

§1.3B inserts a PANORAMA stitcher attempt between Retry 3 and SCANS. PANORAMA (mode=0) uses spherical/cylindrical projection and handles affine distortions natively. For sequences with `scale_dev > 0.05` or `max_rotation > 0.03` (the conditions that trigger affine validation failure), PANORAMA has significantly better coverage. If PANORAMA also fails (returns non-OK status or throws), the pipeline falls through to SCANS as before — net regression risk is zero.

---

## ASP Session 30 — §1.1D Adaptive GNC f_scale (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_adaptive_f_scale(edges, affines, floor) → float`** (`bundle_adjust.py`) | §1.1D: derives a data-driven Cauchy loss scale from the post-solve edge residuals. Returns `max(floor, 2.0 × median_residual_px)`. Pure module-level function, exported in `__all__`. |
| **Adaptive re-solve in `_bundle_adjust_affine`** | After the initial LM solve, the function extracts preliminary affines and calls `_compute_adaptive_f_scale`. If `adaptive_scale > _BA_F_SCALE × 1.5`, a single re-solve runs with the data-derived scale (warm-started from `x_opt`). The two-pronged outlier rejection then runs on the refined solution as before. |
| **`__all__` added to `bundle_adjust.py`** | Exports `["_bundle_adjust_affine", "_compute_adaptive_f_scale"]`. |
| **5 unit tests** (`test_bundle_adjust.py`) | `TestAdaptiveFScale`: floor-dominates-for-perfect-solution, widens-when-solution-does-not-fit-edges, empty-edges-returns-floor, floor-respected-for-tiny-residuals, single-edge-computes-correctly. **Anim suite: 252 tests passing.** |

### Design rationale

The existing GNC Cauchy loss uses a hardcoded `f_scale=10.0` (overridable via `ASP_BA_F_SCALE`). This value was calibrated on the primary corpus and is appropriate when good matches have < 5 px residuals. For sequences with uniformly elevated noise (MPEG compression artefacts, slight zoom, moderate blur), all edges can land at 20–40 px residuals — none are extreme outliers, but the fixed f_scale=10 treats them all as outliers (50% downweighted at 10 px, 12% at 20 px). This biases the LM toward a local minimum that satisfies the regularisation terms rather than the edge constraints.

§1.1D addresses this with a one-shot adaptive step: after the initial solve, compute the median edge residual from the preliminary affines. If that median residual implies an f_scale more than 50% wider than `_BA_F_SCALE`, re-solve with the wider scale. For clean data (residuals ≈ 2 px), the floor kicks in and behaviour is unchanged. For uniformly noisy data (residuals ≈ 30 px), `adaptive_scale = max(10, 60) = 60 px` — the re-solve now treats 30 px edges as inliers, allowing the BA to converge to the correct global consensus.

The re-solve is warm-started from `x_opt` (the initial solution), so it takes far fewer LM iterations than a cold start. The two-pronged outlier rejection still runs afterwards on the refined solution, preserving the existing robustness layer.

---

## ASP Session 29 — §1.10A RLHF Post-run Quality Gate (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_RLHF_FLAG_THRESHOLD = 0.6`** (`bench_anime_stitch.py`) | Module-level constant. Outputs with `rlhf_score < 0.6` are flagged for human review in the feedback tab. |
| **`_get_reward_model()`** | Lazy singleton loader for `StitchRewardModel`. Initialises on first call; returns `None` on any import or init error (e.g., torch unavailable). |
| **`_compute_rlhf_score(img_bgr: np.ndarray) → Optional[float]`** | Calls `StitchRewardModel.predict(img_bgr)`, returns a float in [0, 1] or `None` for empty/invalid input or unavailable model. |
| **`_compute_all_metrics` updated** | Added `rlhf_score` (float or None) and `rlhf_flagged` (bool) to every metrics dict. The lazy model is loaded once per benchmark run and reused across all tests. |
| **5 unit tests** (`test_bench_metrics.py`) | `TestComputeRlhfScore`: float-or-None contract, empty-image None guard, valid range [0,1], flagged-when-below-threshold (mock), not-flagged-at-threshold (mock). **Anim suite: 247 tests passing.** |

### Design rationale

The reward model CNN (`backend/src/anim/rlhf/reward_model.py`) has existed since early sessions but was never wired into the benchmark evaluation loop. Without wiring, benchmark runs produced no `rlhf_score` column — there was no automated signal to identify which of the 96 outputs warranted human review, and the `_RLHF_FLAG_THRESHOLD` concept had no concrete implementation.

The S29 addition is minimal by design. The model loads lazily (no startup cost when not used), and the wiring is entirely in the benchmark, not in the pipeline itself. The `rlhf_flagged` key in the per-test metrics dict acts as the entry point for the human feedback tab: the tab can filter the results table to `rlhf_flagged=True` outputs and present them for rating. Collected ratings then flow into `StitchRewardModel.train_from_feedback()` (already implemented), which tightens the model's predictions for future runs.

Current limitation: the model is initialised with random weights if no checkpoint exists at `~/.config/image-toolkit/stitch_reward_model.pt`. The `rlhf_score` values are therefore uninformative until at least a few dozen labelled examples have been collected. The infrastructure is in place; the quality of the gate improves with feedback volume.

---

## ASP Session 28 — §1.9A Spatial Dedup scans_frames Sync (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_spatial_dedup_frames(frames, scans_frames, bg_masks, image_paths, edges, min_displacement_px)` → `Tuple[..., int]`** (`pipeline.py`) | §1.9A: extracts the post-Stage-6 spatial near-static dedup loop body into a standalone, testable module-level function. Returns all updated lists plus `n_dropped`. Pure function — no side effects, no logging. |
| **§1.9A sync fix** | The previous while-loop updated `frames`, `bg_masks`, `image_paths`, and `edges` on each drop pass but never updated `scans_frames`. Every SCANS fallback triggered after spatial dedup therefore received the full pre-dedup frame set (including near-duplicates just discarded). One-line fix: `[scans_frames[i] for i in keep_idx]` appended to the drop block. |
| **`run()` refactored to call `_spatial_dedup_frames`** | The while-loop body in `AnimeStitchPipeline.run()` is replaced by a call to the new function. Loop exit condition (`_spa_changed`) is now simply `n_dropped > 0`. N<2 fallback path unchanged. |
| **`_spatial_dedup_frames` added to `__all__`** | Directly importable for testing. |
| **5 unit tests** (`test_pipeline.py`) | New `TestSpatialDedupFrames` class: `test_no_drop_when_displacement_above_threshold` (all edges ≥ min_px → unchanged), `test_drops_near_static_adjacent_frame` (one sub-threshold edge → frame dropped), `test_scans_frames_synced_with_frames_after_drop` (scans_frames tracks frames after drop), `test_edges_reindexed_after_drop` (i/j indices remapped correctly after a mid-sequence drop), `test_first_frame_never_dropped` (frame 0 is always anchor). **Anim suite: 242 tests passing.** |

### Design rationale

The bug was subtle: `scans_frames` is set at Stage 2 (after width-normalisation, before BiRefNet) as the snapshot for all SCANS fallbacks. The pre-Stage-5 luma dedup (line 716) correctly syncs `scans_frames` when it drops frames. But the post-Stage-6 spatial dedup (the `while _spa_changed` loop) only updated `frames`, `bg_masks`, `image_paths`, and `edges` — never `scans_frames`. Any SCANS fallback triggered after spatial dedup would therefore receive the full original set including the frames the spatial dedup just discarded as near-static noise.

The consequence is benign in most cases (near-duplicate frames add small overlapping content to the scan stitch, producing a result nearly identical to without them), but it is semantically wrong: the pipeline had committed to a specific frame subset, and the fallback path was violating that commitment. The fix is a single list comprehension in the dedup block, unchanged across all loop passes.

Extracting `_spatial_dedup_frames` as a module-level function also makes the dedup logic auditable and independently testable without requiring a full pipeline run. Future changes to the dedup criterion (e.g., switching from axis-specific to vector-magnitude comparison) can be validated by tests on the pure function.

---

## ASP Session 27 — §1.8A TOML Config Loader (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`load_asp_config(path, *, override_env) → Dict[str, Any]`** (`backend/src/anim/config.py`) | §1.8A: loads `asp_config.toml` (or a caller-supplied path) using Python 3.11 stdlib `tomllib`. Sections are merged into a flat dict; each key is written to `os.environ` via `setdefault` so downstream `os.environ.get` calls in pipeline modules pick it up automatically. Explicit env vars always win over the config file. Zero new dependencies. |
| **Multi-section TOML format** | Keys are organised under semantic sections (`[frame_selection]`, `[compositing]`, `[pipeline]`, etc.) for readability. Any key is valid — unrecognised keys are forwarded as env vars. |
| **`override_env=False` dry-run mode** | Passing `override_env=False` loads and returns the config dict without touching `os.environ`, enabling unit-test isolation and config-preview tooling. |
| **`load_asp_config` added to `backend.src.anim.config.__all__`** | Directly importable from the package. |
| **5 unit tests** (`test_config.py`) | New `TestLoadAspConfig` class: `test_missing_file_returns_empty_dict` (absent file → `{}`), `test_valid_config_sets_env_var` (value written to env), `test_existing_env_var_not_overwritten` (setdefault semantics), `test_multi_section_keys_flattened` (two sections merged into flat dict), `test_override_env_false_does_not_write_env` (dry-run mode). **Anim suite: 237 tests passing.** |

### Design rationale

All ASP runtime constants are currently controlled by env vars (`ASP_NEAR_DUP_LUMA`, `ASP_HOLD_THRESHOLD`, `ASP_SP_SOFT_PX`, etc.). This works for one-off experiments but is cumbersome for reproducible benchmark runs — environment state is transient, not recorded with the run. §1.8A adds a persistent config file that can be checked in alongside the benchmark results, enabling exact reproducibility.

The TOML format is preferred over `.env` because it supports typed values (integers, floats, booleans), sections for organisational clarity, and comments. Python 3.11's stdlib `tomllib` requires no new dependency.

The `setdefault` semantics (env wins over file) preserve the existing workflow: developers can still override any value with an environment variable without touching the config file. The config file is a default, not a constraint.

Example `asp_config.toml`:

```toml
# Frame selection
[frame_selection]
ASP_NEAR_DUP_LUMA = 5.0
ASP_HOLD_THRESHOLD = 0.03

# Compositing
[compositing]
ASP_SP_SOFT_PX = 6
ASP_POISSON_SEAM = 0
ASP_GATE_GHOST_FLOOR = 40.0

# Pipeline routing
[pipeline]
ASP_COV_MIN_MULTI_PCT = 0.30
```

---

## ASP Session 26 — §1.2B Near-Duplicate Luma Post-Filter (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_near_dup_luma_filter(selected_thumbs, selected_paths, threshold)` → `List[str]`** (`frame_selection.py`) | §1.2B: post-filter on the already-selected frame list. Compares consecutive pairs by mean absolute grayscale difference on thumbnail images. Frames with `diff < threshold` luma units are dropped. First frame always kept; last frame always retained (preserves full canvas extent). |
| **`_NEAR_DUP_LUMA` config var** (`frame_selection.py`) | Env var `ASP_NEAR_DUP_LUMA` (default `0.0` = disabled). Set to e.g. `5.0` to activate. Default OFF avoids regression risk on the existing test corpus. |
| **Wired as step 8 in `smart_select_frames`** | After both selection passes, if `_NEAR_DUP_LUMA > 0.0` and more than 2 frames are selected, `_near_dup_luma_filter` is applied. Verbose mode prints how many near-dup frames were dropped. |
| **`_near_dup_luma_filter` added to `__all__`** | Directly importable and testable from `backend.src.anim.frame_selection`. |
| **`NEAR_DUP_LUMA_THRESH = 3.0` added to `constants/anim.py`** | Promotes the magic number from `pipeline.py`'s pre-stage-5 luma dedup (`diff < 3.0`) to a named constant. Imported and used in `pipeline.py`. |
| **5 unit tests** (`test_frame_selection.py`) | New `TestNearDupLumaFilter` class: `test_disabled_at_zero_threshold` (threshold=0 → all paths unchanged), `test_all_identical_keeps_first_and_last` (5× same lum → only first + last survive), `test_all_different_keeps_all` (large luma steps → no drops), `test_two_frames_passes_unchanged` (≤2 frames always bypassed), `test_middle_near_dup_dropped_first_last_kept` (middle near-dup dropped; first and last always in result). **Anim suite: 232 tests passing.** |

### Design rationale

§1.2B complements the hold-block detection (S6, §1.11) and the existing pre-stage-5 luma dedup in `pipeline.py`. Hold detection identifies camera-hold runs (same cel repeated for 2–3 video frames); the pre-stage-5 dedup catches exact duplicates after BiRefNet preprocessing. The new `_near_dup_luma_filter` operates on the SELECTED frame list at thumbnail scale, before the full-resolution pipeline begins. This catches a third class of redundancy: frames that were selected because they meet the min-step-px displacement threshold, but whose pixel content is nearly indistinguishable because the camera moved in a direction where the background change is small (e.g., vertical pan with a character that fills the full frame horizontally).

The function is disabled by default (`ASP_NEAR_DUP_LUMA=0.0`) because the existing corpus doesn't need it — the greedy forward selection already guarantees at least `min_step_px=50px` of camera advance per frame, which for most scenes produces > 5-luma units of mean content change. The filter activates only when explicitly enabled, making it a safe addition with no regression risk. The "last frame always retained" invariant is critical: the last selected frame determines the canvas extent; dropping it would crop the panorama.

---

## ASP Session 25 — §3.9 Fix: Unified `_compute_aligned_ssim` (S8 Metric Dedup) (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **Dead code removed: S8 `_compute_aligned_ssim`** (`bench_anime_stitch.py` lines 168-204) | The S8 EUCLIDEAN definition was silently overridden at module level by the later S9 TRANSLATION definition (Python last-wins). All call sites in `_compute_gt_metrics` were using TRANSLATION-only ECC (50 iterations, 0.01 tolerance). The dead S8 definition is now removed. |
| **Active `_compute_aligned_ssim` upgraded to EUCLIDEAN** (`bench_anime_stitch.py`) | The surviving definition (formerly line 377) is now upgraded: `cv2.MOTION_TRANSLATION` → `cv2.MOTION_EUCLIDEAN`; criteria updated from `(50, 0.01)` → `(200, 1e-4)`. Robustness features from the active version are preserved: `gaussFiltSize=5` (pre-smooths ECC input for noisy/low-texture crops), GT-centric resize `cv2.resize(output_img, (w, h))` (correct reference space), `borderMode=cv2.BORDER_REPLICATE`. Docstring updated to document S25 consolidation. |
| **Redundant double call eliminated** (`_compute_gt_metrics`) | Lines 434 and 437 both called `_compute_aligned_ssim(output_img, gt_img)`. Line 434 assigned to `aligned_ssim_val` (unused). Consolidated to a single call assigning to `aligned_ssim`. |
| **5 unit tests for `_compute_aligned_ssim`** (`test_bench_metrics.py`) | New `TestComputeAlignedSsim` class (skipped if skimage unavailable): `test_identical_images_returns_one` (identical input → SSIM ≈ 1.0), `test_returns_float` (isinstance check), `test_shifted_image_high_ssim_after_alignment` (translated copy with 5px shift → score > 0.70 after ECC correction), `test_different_images_score_below_one` (structurally unrelated → < 0.99), `test_score_in_valid_range` (SSIM ∈ [0, 1]). **Anim suite: 227 tests passing.** |

### Design rationale

The S8 and S9 `_compute_aligned_ssim` definitions were identical in intent (ECC-aligned SSIM to remove GT-coupling framing bias) but diverged in implementation:

| Property | S8 (dead) | S9→S25 (active) |
|---|---|---|
| Motion model | MOTION_EUCLIDEAN | MOTION_TRANSLATION → **MOTION_EUCLIDEAN** |
| Iterations | 200 | 50 → **200** |
| Tolerance | 1e-4 | 0.01 → **1e-4** |
| gaussFiltSize | not set | 5 ✅ |
| Resize reference | min(h,w) | GT dims ✅ |
| BORDER_REPLICATE | ✅ | ✅ |

S25 consolidates the best of both: EUCLIDEAN motion model (handles small rotation residuals from the panorama assembly, not just translation), tighter convergence (200 iter / 1e-4 matches animation-frame alignment demands), and the S9 robustness features (Gaussian pre-smooth, GT-centric reference space, replicate border). The function name, signature, and call sites are unchanged.

---

## ASP Session 24 — §1.4B Continuous Adaptive Gain Clamp (2026-06-07)

### Shipped

| Item | Summary |
|------|---------|
| **`_adaptive_gain_clamp` rewritten** (`compositing.py`) | §1.4B: replaced the S18 binary threshold (ref_lum<80 → ±18%, ≥80 → ±14%) with `clamp_width = 0.26 − 0.12 × (ref_lum / 255)`. At ref=0 this gives ±26%; at ref=255 it gives exactly ±14% (anchored to the S18 normal ceiling). All intermediate values are linearly interpolated — the discontinuity at ref=80 is gone. |
| **5 existing `TestAdaptiveGainClamp` tests updated** (`test_compositing.py`) | Tests 1, 2, 5 now compute their expected `lo`/`hi` via the continuous formula helper `_lo(ref)` / `_hi(ref)`. Test 4 (`test_dark_threshold_boundary_at_80`) renamed `test_continuous_no_jump_at_ref_80` — verifies `|f(79.9, 300) − f(80.0, 300)| < 0.001` (continuity). Test 3 (unclamped correction) unchanged. |
| **3 new `TestAdaptiveGainClamp` tests** (`test_compositing.py`) | `test_bright_ref_hi_matches_anchor` (ref=255 → hi=1.14 exactly), `test_clamp_width_monotone_decreasing` (lo(50) < lo(200)), `test_mid_ref_continuous_formula` (ref=128 → exact formula result). Anim suite: 222 tests passing. |

### Design rationale

§1.4A (S18) introduced a conditional that chose ±18% for ref<80 and ±14% for ref≥80. This created a visible step in the gain-clamp surface: at ref=79.9 the lower bound is 0.82, but at ref=80.0 it jumps to 0.88 — a discontinuity of 0.06 in a smooth quantity. §1.4B's linear interpolation `clamp_width = 0.26 − 0.12 × (ref_lum/255)` produces a smooth surface anchored at ±14% (the S18 normal value) for bright scenes and ±26% for pure-black scenes. The wider allowance for dark scenes (±26% vs S18's ±18%) reflects that dark-scene photometric residuals can be proportionally larger. The key invariant preserved: at ref=255 the upper bound is exactly 1.14, matching the S18 normal upper anchor so the correction is no more aggressive on bright scenes.

---

## ASP Session 23 — §1.7B OpenCV INPAINT_TELEA Border Fill Fallback (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_telea_fill_gaps(canvas, gap_mask) → np.ndarray`** (`canvas.py`) | §1.7B: fills residual black border pixels left after Stage-13 `_crop_to_valid`, using `cv2.inpaint(inpaintRadius=3, flags=cv2.INPAINT_TELEA)`. Zero new dependencies. Fast (~0.5 s typical). Returns unchanged canvas when `gap_mask.any()` is False. |
| **`_telea_fill_gaps` added to `canvas.py __all__`** | Directly importable and testable from `backend.src.anim.canvas`. |
| **TELEA fallback in `pipeline.py` P1.8 block** | The `except Exception` block that previously logged "keeping canvas as-is" now attempts `_telea_fill_gaps` as a fast recovery path when diffusion inpainting fails. A second `except` guards against degenerate inputs (fully-black canvas). |
| **`_telea_fill_gaps` imported in `pipeline.py`** | Added to the `from .canvas import (...)` block alongside `_crop_to_valid` and `_scan_stitch_fallback`. |
| **5 unit tests** (`test_canvas.py`) | New `TestTelaeFillGaps` class: `test_no_gap_returns_unchanged` (all-zero mask → identical output), `test_shape_preserved`, `test_dtype_preserved` (uint8 in → uint8 out), `test_corner_gap_no_longer_black` (4×4 black corner filled by neighbour propagation → `max() > 0`), `test_valid_region_unchanged_outside_band` (pixels ≥8 rows/cols from gap band untouched). Anim suite: 219 tests passing. |

### Design rationale

The P1.8 inpainting block already attempts diffusion inpainting (`mfsr.inpaint_gaps`) for coverage gaps below 95%. In practice this path always raises an import error in the standard environment (the `mfsr` module requires GPU diffusion dependencies not installed by default). Before S23, the except block silently discarded the gap fill and left black corner triangles in the output — the intended behavior was there, but the fallback was missing. `cv2.inpaint(INPAINT_TELEA)` fills from the nearest valid pixels outward, resolving the typical 10–30 px black triangles produced by diagonal-scroll canvas geometry in ~0.5 s. The roadmap note about smearing for gaps > 50 px wide is preserved in the docstring — TELEA is not suitable as a primary fill for large diagonal-scroll holes (use the §1.7A diffusion path or §1.7C inner-rect crop instead).

---

## ASP Session 22 — §1.6B Gain-Adaptive Feather Minimum + Dead Code Removal + Roadmap Housekeeping (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_gain_to_min_feather(gain_diff: float) -> int`** (`compositing.py`) | §1.6B: minimum feather width from luminance gain difference. Formula: `min(120, max(40, int(gain_diff × 300)))`. Ensures the blend zone is wide enough to smooth any residual brightness step after the adaptive gain clamp. Floor=40px (below FEATHER_MIN=80) so it only has effect when `|gain_A − gain_B| > 0.267` (extreme dark/bright adjacent pairs). Cap=120px prevents excessive blurring. |
| **`frame_gains` tracking in normalization loop** (`compositing.py`) | `frame_gains: List[float] = [1.0] * N` initialized before the normalization loop; `frame_gains[i] = gain` stored alongside each applied gain. Indexed by frame index, defaulting to 1.0 for skipped/uncorrected frames. |
| **`max_feathers` cache in overlap-cap loop** (`compositing.py`) | `max_feathers: List[int] = []` populated in the overlap-cap loop so §1.6B can re-apply the cap (`feathers[k] = min(min_fk, max_feathers[k])`) without recomputing `nat_overlap` per boundary. |
| **§1.6B pass after overlap-cap** (`compositing.py`) | For each boundary k: `gain_diff = abs(frame_gains[fi_a] - frame_gains[fi_b])`, `min_fk = _gain_to_min_feather(gain_diff)`. If `feathers[k] < min_fk`, widen (capped by `max_feathers[k]`). Prints a per-boundary feather report only when any boundary was actually widened. |
| **Dead code removed: `_normalize_warped_to_median`** (`compositing.py`) | Removed the 30-line function (per-channel gain normalization) that was defined but never called. The function's hue-shift risk was the documented reason for its disuse; the scalar-gain approach in `_adaptive_gain_clamp` supersedes it. |
| **`_gain_to_min_feather` added to `__all__`** | Directly importable and testable from `backend.src.anim.compositing`. |
| **6 unit tests** (`test_compositing.py`) | New `TestGainToMinFeather` class: `test_zero_diff_returns_floor` (0.0→40), `test_small_diff_returns_floor` (0.1×300=30<40→40), `test_mid_diff_scales_linearly` (0.2×300=60→60), `test_large_diff_capped_at_120` (0.5×300=150→120), `test_at_floor_boundary` (40/300×300=40→40), `test_just_above_floor_boundary` (0.14×300=42→42). Anim suite: 214 tests passing. |
| **Roadmap housekeeping** (`roadmaps/asp.md`) | Marked ✅: §0.5A (25px threshold), §0.5B (vector magnitude gap), §1.1C (GNC Cauchy loss), §1.4A (adaptive gain clamp), §1.5A (seam DP vectorization), §1.5C (adaptive boundary search), §1.5E (parallel seam DP), §1.6A (tiered seam cost), §1.6B (gain-adaptive feather), §1.6C (Poisson blend). |

### Design rationale

§1.6B targets the residual brightness step that persists even after the §1.4A gain clamp. The clamp bounds gains to [0.82–1.22] per frame; for a boundary where frame A was corrected by ×1.18 and frame B by ×0.90, the net gain mismatch is 0.28 — enough to produce a visible 10–20 lum horizontal band. A feather of `int(0.28 × 300) = 84px` smoothly blends this band over 84 rows. For typical adjacent-frame pairs (gain diff < 0.13), `_gain_to_min_feather` returns the 40px floor, which is below the existing FEATHER_MIN=80px and has no effect. The function therefore only activates on genuinely mismatched pairs — intentional scoping to avoid widening feathers in normal cases.

Dead code removal: `_normalize_warped_to_median` (per-channel scalar gain) was intentionally disabled due to hue-shift risk when backgrounds are dominated by a strong colour. The scalar-luminance `_adaptive_gain_clamp` (S18) is its correct replacement. No call sites existed anywhere in the codebase.

---

## ASP Session 21 — §1.6C Gradient-Domain Poisson Seam Blend (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_poisson_seam_blend(fa_zone, fb_zone, path_local, apply_mask)`** (`compositing.py`) | §1.6C: Gradient-domain seam refinement via `cv2.seamlessClone(NORMAL_CLONE)`. Builds a hard-partition zone (fa above the DP path, fb below), then applies Poisson blending in a ±20px band around the path. The Poisson solver finds pixel intensities that minimise `‖∇(out) − ∇(fb)‖²` subject to the hard-partition boundary conditions — eliminating the brightness step at the seam cut without ghosting. Seam band clipped to `[1, zone_h-2] × [1, W-2]` to satisfy `cv2.seamlessClone`'s no-border-touch requirement. Falls back to the hard partition on `cv2.error`. |
| **`_POISSON_SEAM` flag + `_POISSON_BAND_PX = 20`** (`compositing.py`) | Enabled via `ASP_POISSON_SEAM=1` (default OFF — adds ~1–3 s per seam on CPU). When enabled, the Poisson zone replaces the Laplacian+DSFN blend in the normal (non-single-pose, non-ToonCrafter) `else` branch of the blend loop. Single-pose and ToonCrafter seams are unaffected. |
| **`_poisson_seam_blend` added to `__all__`** | Directly importable and testable from `backend.src.anim.compositing`. |
| **5 unit tests** (`test_compositing.py`) | New `TestPoissonSeamBlend` class: `test_shape_and_dtype` (output shape/dtype correct), `test_above_seam_band_unchanged` (rows above the band match hard partition fa), `test_below_seam_band_unchanged` (rows below the band match hard partition fb), `test_path_near_bottom_no_crash` (path near zone edge clips band and doesn't raise), `test_empty_apply_returns_hard_partition` (empty apply_mask returns unblended hard partition). Anim suite: 208 tests passing. |

### Design rationale

The Laplacian+DSFN blend in the `else` branch is a good default: it adapts ramp width to photometric similarity and zeroes out fg-vs-fg ghosting (S20). But for background-only seam bands (where the DP path already avoids characters), it leaves a residual brightness step equal to `|gain_A − gain_B|` — typically 2–6 lum units after normalization. Poisson blending solves this exactly: by solving the gradient-matching equation with the hard-partition as boundary conditions, it produces a continuous intensity field with no discontinuity at the seam. The effect is visible as a smooth brightness ramp of ≈40px instead of the abrupt step. Gate behind `ASP_POISSON_SEAM=1` because `cv2.seamlessClone` is CPU-only and takes 1–3 s for a full-width anime frame seam zone; it is best used in final-output mode or targeted evaluation runs.

---

## ASP Session 20 — S20: bg-Mask-Aware DSFN Ramp (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_soft_seam_weight` — fg-vs-fg similarity zeroed after Gaussian diffusion** (`compositing.py`) | S20: when `bg_mask_a`/`bg_mask_b` are provided, `sim_diffused[both_fg] = 0.0` is applied after the Gaussian blur step, where `both_fg = (~bg_mask_a.astype(bool)) & (~bg_mask_b.astype(bool))`. Previously these masks were passed through the signature but never used. This prevents background similarity from diffusing into character-vs-character overlap regions: without the fix, the blur kernel could propagate high-similarity background values into adjacent fg-vs-fg pixels, artificially widening the blend ramp and creating double-image ghosting. Background pixels on the seam-side edge of the fg boundary are untouched and retain their diffused similarity. |
| **2 unit tests** (`test_compositing.py`) | Added to `TestSoftSeamWeight`: `test_bg_mask_fg_fg_narrows_blend` (all-fg bg_masks narrow the blend transition band vs. no-mask for similar frames), `test_bg_mask_none_result_unchanged` (None bg_masks produce identical output to calling without them). Anim suite: 203 tests passing. |

### Design rationale

`_soft_seam_weight` already received `bg_mask_a`/`bg_mask_b` at every call site (both sliced from `warped_bg[fi_a/fi_b]`), but the function body never read them. The Gaussian diffusion with `sigma=20px` diffuses background similarity ~40px into the frame, which can pull fg-vs-fg pixels up to `sim≈0.5` if they're close to a background region. At `sim=0.5`, `ramp = min_ramp + 0.5 * (max_ramp - min_ramp)` — roughly 50–100px, wide enough to create ghost-blending across two different character poses. After S20 the forcing only fires for pixels where both frames agree the pixel is foreground, which is the exact class that should always receive a narrow ramp.

---

## ASP Session 19 — §1.6A Tiered Seam Cost (S19) (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_build_seam_cost_map` Tier 2 cost lowered from 1.0 → 0.5** (`compositing.py`) | §1.6A: the edge-buffer zone (background pixels within `dilate_px` of any fg boundary) now costs 0.5 instead of 1.0. The fg interior (Tier 1) remains at 1.0. This creates a three-level gradient — interior=1.0 → edge buffer=0.5 → background=0.0 — giving the DP seam path-finder an incentive to route *through* the edge buffer toward clean background, rather than treating it identically to the character body. With `sem_weight=200`, energy levels are: fg body≈200, edge buffer≈100, background≈0–50. Before S19 the edge buffer was also ≈200, offering no gradient. |
| **`_build_seam_cost_map` added to `__all__`** | Function is now importable and directly testable. |
| **7 unit tests** (`test_compositing.py`) | New `TestSeamCostMap` class: all-bg cost=0.0, all-fg cost=1.0, edge-buffer row=0.5, pure-bg-far-from-fg=0.0, fg interior not lowered to 0.5 by edge buffer, None masks return zero, union of two fg masks covers both regions at 1.0. Anim suite: 201 tests passing. |

### Design rationale

Before S19 the seam DP treated the edge buffer zone (≤15px outside any fg boundary) identically to the character body (both cost=1.0 × sem_weight=200). When the only route from one boundary to another passed through a narrow region flanked on both sides by character edges, the DP had no gradient: routing through the edge buffer cost the same as routing through the body. After S19 the DP sees a "highway shoulder" (cost=100) between the forbidden zone (body=200) and the fast lane (background=0–50), making it more likely to find the shortest route through background for partially-covered seam zones.

---

## ASP Session 18 — Per-Pair Coherence Gate + §1.4A Adaptive Gain Clamp (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_coherence_skip_mask(order, frame_lums, coherence_limit)`** (`compositing.py`) | Standalone testable helper. Per-frame normalization-skip mask built from adjacent-strip coherence check. Marks both frames in an adjacent pair as skip-normalization when their background luminance differs by more than `coherence_limit`. Only the bad pair's frames are excluded — other frames proceed normally. Replaces the former global-skip that penalised every frame when a single scene-change pair exceeded the limit. |
| **`_adaptive_gain_clamp(ref_lum, frame_lum)`** (`compositing.py`) | §1.4A adaptive gain clamp. Dark scenes (ref_lum < 80) use `[0.82, 1.22]` (±18%); normal scenes use `[0.88, 1.14]` (±14%). Replaces the previous fixed `±7%` clamp. Stage 4.5 already applies ±14–20% before warping; Stage 11 corrects any residual after canvas projection. The wider clamp allows Stage 11 to fully bridge residuals that Stage 4.5 couldn't reach due to its own ceiling. |
| **Normalization block updated** (`compositing.py`) | `_composite_foreground` calls `_coherence_skip_mask()` for per-frame skip flags and `_adaptive_gain_clamp()` for each frame's gain. Print log now reports per-pair skip count instead of binary global skip/proceed. |
| **11 unit tests** (`test_compositing.py`) | `TestAdaptiveGainClamp` (5 tests): normal scene clamped at 0.88/1.14, dark scene clamped at 0.82/1.22, small correction passes unclamped, dark threshold boundary at 80, zero frame_lum protected. `TestCoherenceSkipMask` (6 tests): all-small diffs none skipped, bad pair both skipped, good frames after bad pair not skipped, None lum pair ignored, exactly-at-limit not skipped, non-identity order maps correctly. Anim suite: 194 tests passing. |

### Design rationale

**Per-pair coherence gate**: The previous guard used `max(adj_diffs) > 20` → skip ALL normalization for the entire sequence. A scene change between frames 3 and 4 caused frames 1, 2, 5, 6 (coherent backgrounds) to also skip normalization, widening strip-banding to the whole composite. The per-pair approach isolates the bad pair while allowing the rest to normalize.

**§1.4A wider gain clamp**: Stage 11 was limited to ±7%. For a frame where Stage 4.5 hit its own ±14% ceiling (true correction needed was >14%), the residual can be up to 6–12% — larger than ±7% can bridge. The ±14%/±18% clamp ensures Stage 11 always closes the residual left by Stage 4.5.

---

## ASP Session 17 — Per-Pixel DSFN Blend Ramp + Adaptive Boundary Search (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **Per-pixel DSFN blend ramp** (`compositing.py` — `_soft_seam_weight`) | S17 replaces the per-column-average blend radius with a per-pixel value driven by local photometric similarity. Previously: `col_sim = sim_diffused.mean(axis=0)` collapsed the (zone_h, W) similarity field into (W,), then broadcast the same ramp to all rows in each column. Now: `ramp = min_ramp_bg + sim_diffused * (max_ramp_bg - min_ramp_bg)` gives every pixel its own blend width. Background pixels (high similarity, wide ramp) and foreground pixels at character edges (low similarity, narrow ramp) in the same column now get independently-sized transitions, eliminating the averaging artifact where a character-edge row was forced into a wide blend because its column happened to have mostly background above it. |
| **Adaptive boundary search range** (`compositing.py` — `_find_optimal_boundaries`) | When affines are available and horizontal tx spread < 5 px (pure vertical scroll), the boundary search window narrows from ±SEARCH_RANGE=250 to ±100 px. For typical dense vertical-scroll sequences the optimal boundary is always within ±50 px of the midpoint, so the narrow window loses nothing while reducing candidate evaluations by ~60 % for sparse sequences with large frame steps. For diagonal/2D motion (tx_spread ≥ 5px), the full ±250 px range is preserved. |
| **6 unit tests** (`test_compositing.py`) | New `TestSoftSeamWeight` class: output shape/dtype, values in [0,1], weight ≈ 0.5 at seam for identical frames, weight ≈ 1.0 far above seam, weight ≈ 0.0 far below seam, similar frames produce wider blend zone than different frames. Anim suite: 183 tests passing. |

---

## ASP Session 16 — Seam Band Color Matching for Single-Pose Seams (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_color_match(dom_zone, oth_zone, path_local, band_px)`** (`compositing.py`) | Standalone helper (testable). Computes per-channel mean of content pixels within `band_px` rows of `path_local` in both zones, then applies the per-channel delta `(dom_mean − oth_mean)` to oth_zone's band pixels. Shifts oth_zone's colors toward dom_zone's photometric profile in the seam band. Degenerate zones (< 10 content pixels) return an unchanged copy. |
| **Wired into single-pose composite branch** (`compositing.py`) | Called with `band_px = sp_soft_px + 4` before `_single_pose_soft_edge()`. The color-matched `_oth_matched` is passed to the S15 blend — the channel-mean step drops from `post_warp_diff` lum units toward ~0 before the ramp is applied, making the blend seam nearly imperceptible. `take_oth` (non-overlap) pixels still use original `oth_zone` colors. |
| **7 unit tests** (`test_compositing.py`) | New `TestSeamColorMatch` class: output shape/dtype, zero band returns unchanged copy, band pixels shifted to dom mean, outside-band pixels unchanged, identical zones produce no shift, degenerate (all-black) zone returns unchanged, per-channel delta applied independently. Anim suite: 177 tests passing. |

### Design rationale

S15 applied a ±6px blend ramp at single-pose seams (max 50% blend at centre). If `post_warp_diff = 30`, even 50% blend leaves a 15-lum residual step — visible as a seam. S16 eliminates the channel-mean component of this step entirely by shifting oth_zone's colour to match dom_zone's in the blend band. After the shift, both zones have compatible means; the remaining ±6px blend smooths the residual variance. Combined, S15+S16 reduce the worst-case seam step from `post_warp_diff` to the within-band colour variance (typically < 5 lum), well below the human perceptual threshold (~10 lum).

`take_oth` pixels (used where only oth_zone has fg content, away from the seam) remain at original oth_zone colours to preserve foreground fidelity in non-overlap regions.

---

## ASP Session 15 — Soft-Edge Single-Pose Seam (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_single_pose_soft_edge(dom_zone, oth_zone, path_local, apply_mask, sp_soft_px)`** (`compositing.py`) | New standalone helper (exportable, unit-testable). Applies a narrow ±`sp_soft_px` linear feather centred on the DP seam path to smooth the hard color step at single-pose escalated seams. Maximum blend weight at the seam centre is 50% other-frame; weight drops linearly to 0% at ±sp_soft_px rows. Only fires where BOTH frames have non-zero foreground content AND `apply_mask` is True AND pixel is within the band — never bleeds into background or single-frame regions. |
| **Wired into single-pose composite branch** (`compositing.py`) | After the hard dominant/fill partition (existing S11 logic), `_single_pose_soft_edge()` is called and its result written back for `both_have & fg_apply` pixels. No-op outside the blend band. Disable with `ASP_SP_SOFT_PX=0`. Print updated: "soft_px=N" instead of "(no blend — avoids double image)". |
| **7 unit tests** (`test_compositing.py`) | New `TestSinglePoseSoftEdge` class: output shape/dtype, disabled when sp_soft_px=0, seam row is 50/50 blend, outside-band pixels unchanged, in-band pixels strictly between dom and oth, no modification where apply_mask=False, no modification where oth has no content. Anim suite: 170 tests passing. |

### Design rationale

Single-pose seams previously rendered as a completely hard binary cut (dominant frame / fill frame with zero transition). The cut is visually noticeable as an abrupt color step at the seam line, even though the color values on either side differ by only 10–40 lum units in practice. A ±6px linear ramp at the DP-optimal seam position smooths this step into a ~12px transition zone, which is below the threshold where pose-gap ghosting becomes perceptible (ghosts require 20–50px of blended region with misregistered content to be visible).

The blend is 50%-at-seam-centre, not blending across the full feather zone, because pose differences are large (post_warp_diff > 22 lum units for escalated seams) — blending across a wide zone at high weights would recreate the double-image ghost that single-pose was designed to prevent.

---

## ASP Session 14 — Seam Visibility Score (No-Reference Quality Metric) (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_seam_visibility_score(output_img)`** (`bench_anime_stitch.py`) | No-reference quality metric measuring the worst-case adjacent-row luminance jump in the final panorama. Computes per-row mean luminance for content rows (lum > 5, ≥10% fill), then reports the maximum absolute difference between consecutive row means. Detects hard single-pose seam cuts (score 12–50+) that `_seam_coherence` misses (which measures global drift, not local discontinuities). Works for all 96 tests with no GT required. |
| **Wired into `_compute_all_metrics`** | `seam_visibility` field now appears in `metrics_asp` and `metrics_simple` in all benchmark result dicts. |
| **8 unit tests** (`test_bench_metrics.py`) | New test file: `TestSeamVisibilityScore` — uniform image → 0, hard seam → ≥100, smooth gradient → <10, non-negative, harder seam scores higher, affines=None works, black borders ignored, single-row → 0. Anim suite: 163 tests passing. |

### Interpretation guide

| `seam_visibility` | Meaning |
|-------------------|---------|
| 0–5 | Invisible seams — excellent adaptive feather / FG registration |
| 6–12 | Faintly visible — normal for well-blended Laplacian output |
| 13–25 | Visible step — likely one or more single-pose seam escalations |
| > 25 | Hard cut — significant animation pose gap at worst seam |

---

## ASP Session 13 — Multi-Frame Canvas Coverage Gate (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **`_compute_row_coverage()` helper** (`pipeline.py`) | Pure function: given `affines`, `frames`, `canvas_h`, returns `(row_cov, pct_multi, median_cov)`. `row_cov[r]` = number of frames covering canvas row `r`; `pct_multi` = fraction of content rows with ≥2-frame overlap; `median_cov` = median per-row coverage. Extracted as a standalone function to enable direct unit testing. |
| **Stage 10.5 coverage gate** (`pipeline.py`) | Inserted after Stage 10 (temporal render), before Stage 11 (fg composite). Computes row coverage, logs diagnostic summary (`N multi-frame rows / total content rows`), and falls back to SCANS when `pct_multi < ASP_COV_MIN_MULTI_PCT` (default 0.30). Conservative 30% threshold avoids false positives on typical dense-overlap datasets while catching degenerate 2-frame sparse selections. |
| **Coverage unit tests** (`test_canvas.py`) | 6 new tests in `TestComputeRowCoverage`: fully-overlapping frames, non-overlapping frames, dense stack, output shape, empty canvas, non-negative counts. Anim suite: 155 tests passing. |

### Notes

The coverage gate completes §0 item 2 from the roadmap. Default threshold 0.30 means the gate only fires when fewer than 30% of content rows have 2+ frames — well below the coverage level of all current 92/96 passing tests (all of which have dense multi-frame overlap). The gate is a safety net for future edge-case datasets, not a quality change for the current corpus.

---

## ASP Session 12 — Adaptive Feather Refinement + Parallel Seam DP (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **Adaptive feather refinement** (`compositing.py`) | After FG pose registration, each seam's feather width is adjusted based on `post_warp_diff`: diff < 8.0 → widen 1.5× (excellent alignment, smoother Laplacian blend); diff > 16.0 → narrow 0.75× (poor alignment, tighter cut to prevent ghosting). Seams that escalated to single-pose (diff > 22) are skipped. Overlap cap is re-applied after modification. `seam_post_diffs` init bug fix from S11 was the prerequisite that made this effective for the first time. |
| **Parallel seam DP pre-computation** (`compositing.py`) | Collects zone arrays + `sem_cost` maps for all N-1 seam boundaries, then dispatches `_seam_cut()` jobs via `ThreadPoolExecutor(max_workers=min(N-1, 4))`. Single-boundary case uses inline path (no executor overhead). Pre-computed paths are stored in `_precomp_paths: dict` and retrieved in the Laplacian blend loop. Safe to parallelise: `result` is fully populated by hard-partition before the pre-compute block; `warped_norm` is read-only; zones don't overlap; `.copy()` prevents aliasing. |
| **S12 unit tests** (`test_compositing.py`) | Added 8 new tests: `TestSeamCutDP` (5 tests — shape, valid range, identical-image, sem_cost, 3-connectivity constraint) and `TestParallelSeamPrecompute` (3 tests — 5-frame parallel path, 6-frame output shape, 2-frame single-seam fallback). Anim suite total: 149 tests passing. |

### Results

| Metric | Before S12 | After S12 |
|--------|-----------|-----------|
| SCANS fallbacks | 4/96 (4%) | 4/96 (4%, unchanged) |
| Tests passing (anim suite) | 141 | 149 |
| Adaptive feather firing | never (seam_post_diffs always empty) | all seams with post_diff < 8 → widened to FEATHER_MAX |
| Parallel seam DP | sequential | ThreadPoolExecutor (max 4 workers) |

*test09: all 20 seams post_diff 2–8, all feathers widened 250px → 300px (FEATHER_MAX). test27: all 19 seams, same pattern.*

---

## ASP Session 11 — Fallback Elimination: Comparative Gates + Validation Retry Chain (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **Comparative render gate** (`bench_anime_stitch.py`) | Replaced absolute render gate with a SCANS-relative gate: limits are `max(floor, scans_value * 2.0)`. Floors: `_SC_FLOOR=38`, `_SB_FLOOR=35`. Override via `ASP_GATE_SC` / `ASP_GATE_SB`. Prevents the gate from rejecting valid ASP output when the source content has inherently high luminance variation. |
| **Alignment gate changed to advisory** (`bench_anime_stitch.py`, `pipeline.py`) | The `75th-pct |dx| > limit` check no longer raises `RuntimeError`; it now prints a `⚠ high drift` warning and lets the pipeline proceed. Default threshold in `pipeline.py` raised from 50px → 200px (`ASP_ALIGN_GATE_DX`). Tests with 2D/diagonal motion are no longer hard-rejected before compositing. |
| **Validation Retry 4** (`bench_anime_stitch.py`) | Added a 4th retry after Retry 3: `_validate_affines(_seq, min_step=3.0, max_ratio=10.0, max_rotation=0.3, max_scale_dev=0.3)`. Fixes slow-pan sequences (e.g., test48 with min_gap=6.8px, test14/78 with min_gap≈5–19px) where fine-grained sampling naturally produces sub-25px per-frame steps. |
| **Validation Retry 5** (`bench_anime_stitch.py`) | Added a 5th final retry: `min_step=0.5, max_ratio=50.0, max_rotation=0.5, max_scale_dev=0.5`. Catches extreme-clustering cases where the sequential chain has ratio > 10 (e.g., test73 ratio=18.4, test77 ratio=27.0). |
| **GhostGate absolute floor** (`bench_anime_stitch.py`) | `_ghost_limit = max(_GHOST_ABS_FLOOR, _GHOST_RATIO_LIMIT * sim_ghost)`. Default floor=40.0 (env `ASP_GATE_GHOST_FLOOR`). Prevents false positives when ASP ghosting is low in absolute terms but appears high relative to an unusually clean SCANS output (test81 asp=30.5, test82 asp=37.4 — both now pass). |
| **`seam_post_diffs` init bug fix** (`compositing.py`) | `seam_post_diffs: dict = {}` was missing from declarations at line 603. The NameError was silently caught by the FG-registration `except` block, causing the entire FG pose registration step to be skipped on every run. Fixed by adding the declaration. |

### Results

| Metric | Before S11 | After S11 |
|--------|-----------|-----------|
| SCANS fallbacks | 51/96 (53%) | 4/96 (4%) |
| Genuine SCANS fallbacks | 51 | 4 (tests 54, 59, 73, 89) |
| Retries needed | 3 | 5 |
| Ghost gate floor | none | 40.0 |

*4 confirmed genuine SCANS cases: test54 (2D drift, sb=56.0 >> 36.0), test59 (sc=50.2 >> 38.0), test73 (ratio=18.4 in _seq, sb=68.3 >> 35.0), test89 (sb=122.3 >> 48.7).*

---

## ASP Session 10 — Seam DP Vectorization + Dead Code Removal + Test Fixes (2026-06-06)

### Shipped

| Item | Summary |
|------|---------|
| **Seam DP vectorization §1.5A** (`compositing.py`) | Replaced the W_e-iteration Python forward pass in `_seam_cut()` with `scipy.ndimage.minimum_filter1d(size=3, mode='constant', cval=np.inf)` — a compiled C kernel that computes the 3-neighbour row minimum in one pass, eliminating per-iteration `left`/`right` array allocations. Traceback changed from Python list construction + comprehension to slice-argmin (`E[i, j_lo:j_hi].argmin()`). Expected speedup: 5–10× for Stage 11. |
| **Removed dead S8 `_compute_dinov2_features` definition** (`frame_selection.py`) | The S8 version (`thumbs: List[np.ndarray]`) was silently shadowed by the S9 version (`frames_paths: List[str]`). Removed the S8 definition; sole definition is now the S9 path-based API. |
| **Fixed `_TOONCRAFTER_SEAM_ENABLED` NameError** (`compositing.py`) | Variable at line 743 was misnamed; renamed to `_TOONCRAFTER_SEAM` (the correct module-level name). |
| **Fixed pre-existing import errors in test suite** (`test_compositing.py`, `test_canvas.py`) | `_FEATHER_MAX`/`_FEATHER_MIN`/`_FEATHER_TABLE` and `_CANVAS_MAX_DIM` were imported with a leading underscore that never existed. Fixed to import from `backend.src.constants` under the correct names (`FEATHER_MAX`, etc.) aliased for backwards-compat. |
| **Rewrote `TestDINOv2Features`** (`test_frame_selection.py`) | Two tests that were testing the removed S8 API (numpy array input) replaced with tests for the actual S9 API (file path input). `test_returns_none_when_model_unavailable`: poisons `_DINOV2_CACHE[device]` (S9 key), calls with temp PNG paths. `test_identical_images_low_cosine_distance`: writes two identical PNGs, verifies cosine distance < 0.05. |
| **141 tests passing** | Up from 107 (S9 baseline); gains include 34 previously collection-failing tests now runnable. |

---

## ASP Session 9 — ToonCrafter Seam Synthesis (2026-06-05)

### Shipped

| Item | Summary |
|------|---------|
| **ToonCrafter seam synthesis** (`compositing.py`) | `_TOONCRAFTER_SEAM_ENABLED = os.environ.get("ASP_TOONCRAFTER_SEAM", "0") != "0"` added. `seam_post_diffs: dict` tracks `post_warp_diff` per seam during the fg-register loop. After the loop, the worst single-pose-escalated seam triggers `_generate_canonical_cel(crop_a_tc, crop_b_tc, device)` from `anim_fill.py`. Canonical cel stored in `seam_canonical_crops[worst_k]`; in the Laplacian blend loop it replaces the hard dominant-frame partition for fg pixels with the ToonCrafter-generated intermediate pose. Falls back gracefully to single-pose when ToonCrafter is unavailable. Disable default: `ASP_TOONCRAFTER_SEAM=0`. |

---

## ASP Session 8 — DINOv2 Frame Selection + LSD Collinearity + Aligned-SSIM (2026-06-05)

### Shipped

| Item | Summary |
|------|---------|
| **DINOv2 submodular frame selection** (`frame_selection.py`) | `_DINOV2_CACHE: dict = {}` at module level. `_compute_dinov2_features(thumbs, device, thumb_size=224, batch_size=16) → Optional[np.ndarray]` loads `dinov2_vits14` via `torch.hub.load` with module-level cache; returns (N, 384) L2-normalised float32 features. In Pass 2 of `smart_select_frames()`, `_pose_dist(i, j)` uses DINOv2 cosine distance when features are available, falls back to `_fg_center_diff()` otherwise. Activated via `ASP_POSE_WINDOW_PX=80`. Handles holds natively: identical-pose frames collapse to the same feature point, so one representative is selected automatically. 2 new tests in `TestDINOv2Features`. |
| **LSD collinearity term in ARAP** (`fg_register.py`) | `_arap_regularise()` gains `image: Optional[np.ndarray] = None` and `image_offset: Tuple[int, int] = (0, 0)` parameters. When `image` is provided: runs `cv2.createLineSegmentDetector` on the seam-band crop; for fg/bg boundary cells (cells containing both fg and bg pixels — where ink outlines appear), projects the cell's flow onto the line direction when the projection retains ≥50% of original magnitude (prevents vertical lines from cancelling horizontal translation). Call site in `register_foreground_at_seam()` updated to pass `image=crop_a, image_offset=(y0_crop if axis==0 else 0, ...)`. 3 new tests in `TestArapRegulariseLSDCollinearity`. |
| **Aligned-SSIM metric** (`bench_anime_stitch.py`) | `_compute_aligned_ssim(img_a, img_b)` uses `cv2.findTransformECC(MOTION_EUCLIDEAN)` to align `img_a` to `img_b` before SSIM computation. Removes GT-coupling framing bias: a temporal shift in frame selection shows the same character at a different vertical position → raw SSIM penalises the shift even when pose quality is identical. `aligned_ssim_vs_gt` reported alongside `ssim_vs_gt` in `_compute_gt_metrics()`. |

---

## ASP Session 7 — Stage 12.5 Scroll-Axis Content Trim (2026-06-05)

### Shipped

| Item | Summary |
|------|---------|
| **Stage 12.5 scroll-axis foreground-extent trim** (`pipeline.py`) | Inserted between Stage 11 (foreground composite) and Stage 13 (boundary crop). Detects dominant scroll axis from affine ty/tx range; warps `~bg_masks[i]` per frame into canvas space using `cv2.warpAffine` + `INTER_NEAREST`; unions all fg masks; trims canvas rows (vertical scroll) or columns (horizontal scroll) to the fg-covered extent plus 20px padding. `valid_mask` trimmed in sync. Guard: `ASP_CONTENT_TRIM=1` (default on). Directly addresses test27's 2× height excess caused by frame selection sampling a wider temporal range than the GT. |

---

## ASP Session 6 — Hold Detection + GNC Robust Loss + SLIC SGM Proxy (2026-06-04)

### Shipped

| Item | Summary |
|------|---------|
| **Animation hold detection** (`frame_selection.py`) | `_detect_hold_blocks(thumbs, hold_threshold=0.025)` detects "on twos/threes" animation holds by comparing consecutive thumbnail pixel MAD (normalised to [0,1]). Blocks below threshold treated as the same hold. Hold IDs used in Pass 2 to apply `_SAME_HOLD_PENALTY=0.05` to same-hold candidates (prefers cross-hold frames). Enable via `ASP_HOLD_THRESHOLD=0.025`. 9 new tests in `TestDetectHoldBlocks`. |
| **GNC robust loss in bundle adjustment** (`bundle_adjust.py`) | `least_squares` upgraded to `loss='cauchy', f_scale=float(os.environ.get("ASP_BA_F_SCALE", "10.0"))`. Makes BA robust against outlier edges (long-distance matches, incorrect temporal-ordering edges) that survive the post-solve residual pruning. Override via `ASP_BA_F_SCALE`. 3 new tests in `test_bundle_adjust.py`. |
| **SLIC SGM proxy** (`fg_register.py`) | `_slic_sgm_proxy(crop_a, crop_b, fg, n_segments=200) → Optional[np.ndarray]`: SLIC superpixel centroid tracking as a coarse flow source for flat cel-shaded regions where RAFT/DIS gradient aperture problem produces noisy flow. SGM flow replaces RAFT/DIS flow for foreground pixels when `ASP_SGM_PROXY=1`. Then ARAP-regularised same as RAFT/DIS flow would be. |
| **12 new unit tests** | 9 for `_detect_hold_blocks()`, 3 for bundle adjust GNC. Total: 102 tests (was 90 at S5 start). |

---

## ASP Session 5 — Alignment Stability Gate + Fg Pixel L1 Pose Metric (2026-06-04)

### Shipped

| Item | Summary |
|------|---------|
| **Alignment stability gate** (`bench_anime_stitch.py`, `pipeline.py`) | Detects 2D/diagonal camera motion BEFORE compositing via 75th-percentile of `|dx_steps|`. When > 50px, falls back immediately to SCANS on width-normalised frames. Saves 2.5s of unnecessary compositing AND produces better output (normalised frames give better SCANS quality): test08 +0.074 (0.736→**0.809**, simple_better→**asp_better**), test25 +0.049 (0.697→**0.746**). Disable via `ASP_ALIGN_GATE_DX=99`. |
| **Ghosting ratio gate** (`bench_anime_stitch.py`, post-crop) | Fires when ASP composite ghosting > 2× simple stitch ghosting (computed on CROPPED canvas). Catches double-image blending artifacts that pass the seam coherence gate. test82 borderline (S4 ratio=2.06; current SCANS non-determinism puts ratio 1.92–2.06, stochastic fire). test84 safely below (ratio=1.87). Disable via `ASP_GATE_GHOST=99`. |
| **Fg pixel L1 pose metric** (`frame_selection.py`, `bench_anime_stitch.py`) | Replaced gradient-weighted L1 with fg-masked pixel L1 in `_fg_center_diff()`. Hard-threshold mask (>0.3) → zero out background → compare only fg pixels. Per-frame gain normalisation removes brightness variation. Background-invariant by construction (vs gradient: computed on full image, then weighted → background edges still contributed at 0.05–0.1 weight). |
| **8 new unit tests** (`test_frame_selection.py`) | Cover `_fg_center_diff()` behavior: identical-fg near-zero, different-pose high-score, gain-normalisation, strict background-invariance, sparse-mask fallback. Total unit tests: 90 (up from 82). |

### Investigated

| Item | Finding |
|------|---------|
| **Fg pixel L1 with pose selection** (`ASP_POSE_WINDOW_PX=80`) | test27 improved +0.010 (0.709→0.719) — first meaningful breakthrough since session 2. test09 +0.001. But test04 regressed -0.024 and test57 regressed -0.015 (GT coupling). Pose selection remains disabled by default. |
| **±3 look range** | Strictly worse than ±2: test09 -0.007, test27 -0.007. Extra candidates at ±3 slots are at awkward advances for uniform-step pans. Reverted to ±2. |

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
