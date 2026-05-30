# Image Toolkit — Master Roadmap

*Last updated: 2026-05-30. Intended as a living brainstorming guide, not a strict execution queue.
Items within each section are unordered unless otherwise noted.*

---

## How to Use This Document

Each section lists ideas with:
- **Why it matters** — the motivation or pain point
- **Options** — concrete implementation paths, including trade-offs
- **Status** — `✅ Done`, `🔄 In Progress`, `⬜ Idea`

Entries marked **[Quick Win]** should take a day or less to implement.
Entries marked **[Research]** require significant experimentation before committing to an approach.

---

## 1. Anime Stitch Pipeline (ASP) — Quality & Reliability

The ASP is the most algorithmically complex subsystem. Benchmark baseline (2026-05-30): **22/22 success, avg sharpness 33.14, avg ghosting 22.17**.

### 1.1 Bundle Adjustment Hardening

**Why it matters:** The pre-Phase-3 fallback rate was 55% (12/22 tests), driven almost entirely by one or two catastrophically wrong LoFTR matches poisoning the entire bundle solution (tests 3, 10, 13: single first-pair error of 1654–3653px). The 2-pronged outlier rejection added in Phase 3 brought this to 0 fallbacks, but the rejection heuristics are tuned to the current 22-test corpus.

**Options:**
- **A — Post-solve residual pruning (current approach):** After the initial LM solve, compute per-edge predicted-vs-actual translation; reject edges where `|residual| > 3 × median`; re-solve. Simple, fast (~0.15s), proven effective.
- **B — RANSAC inside bundle adjustment:** Before LM, run consensus-based robust estimation (e.g. RANSAC or MAGSAC++) across all edges to find the inlier set. Slower but more principled. Especially useful if future datasets contain >30% bad edges.
- **C — Graduated non-convexity (GNC):** Replace the L2 residual with a robust loss (Geman-McClure, Cauchy) that down-weights outliers automatically during optimization. No separate rejection step needed. Requires scipy's least_squares `loss` parameter — one-line change if the Jacobian structure is compatible.

**Recommendation:** Keep A as baseline, prototype C as a drop-in replacement for the cost function. If C reaches parity on the 22-test corpus it generalises better to unseen data.

---

### 1.2 Near-Zero / Zero-Translation Edge Filter

**Why it matters:** Tests 4, 9, 16, 21 failed `min_gap < 50px` because co-located frames (or frames with near-zero inter-frame motion) got placed at the same canvas row, causing temporal median collapse.

**Options:**
- **A — Pre-bundle edge rejection:** Drop any edge where `|dy| < 50px AND |dx| < 50px` before the LM solve. Fast, zero dependencies.
- **B — Source frame deduplication:** Before matching, drop frames whose mean luma difference from the previous frame is below a threshold (e.g. `luma_diff < 3.0`). Already done for exact duplicates (Pre-5 dedup) — extend to near-duplicates using SSIM or histogram distance. This prevents the bad edge from ever being added.
- **C — Adaptive min-step from frame count:** Estimate the expected step as `canvas_height / N_frames`; flag edges where the step is < 10% of expected. Automatically scales to different video resolutions and scroll speeds.

**Recommendation:** B is the cleanest fix (removes the bad source rather than papering over it downstream). C generalises B's threshold to be content-adaptive. These are complementary; implement B first.

---

### 1.3 Scale and Rotation Handling

**Why it matters:** test5 (scale_dev=0.121, max_rotation=6.35°) represents zoom-and-pan sequences that the current translation-only canvas model cannot handle. The affine validator correctly rejects these, but the rejection throws away a potentially good output.

**Options:**
- **A — Full 2×3 affine warp per frame:** If `max_scale_dev > 0.05` or `max_rotation > 0.03`, replace translation-only placement with per-frame `cv2.warpAffine`. This allows scale and rotation to be compensated. Higher compute cost; may introduce more resampling blur near edges.
- **B — Projective OpenCV stitcher fallback:** When the affine validator detects scale/rotation, fall back to OpenCV's `Stitcher_create(Stitcher::PANORAMA)` instead of SCANS. Handles perspective, fisheye, and scale changes natively. The existing simple stitch in `image_merger.py` already uses this path — the change is routing the affine-rejection fallback here instead of SCANS.
- **C — Normalise scale then translate:** Before bundle adjustment, warp each frame to the reference frame's scale (using the detected per-frame scale factor). This converts a zoom sequence into a pure-translation sequence that the existing pipeline handles. Introduces blur proportional to the scale difference.

**Recommendation:** B is the lowest effort: it reuses existing infrastructure and handles arbitrary affine distortions. Reserve A/C for cases where projective stitching still falls short.

---

### 1.4 Gain Clamp Widening for Dark Scenes

**Why it matters:** 17/22 tests hit the `[0.88, 1.14]` gain clamp. Dark scenes (ref_lum < 70) have proportionally larger gain swings, leaving some frames under-corrected. The per-frame gain correction already uses BT.601 luma (hue-safe), so widening the clamp is safe.

**Options:**
- **A — Conditional clamp based on ref_lum:** Use `[0.82, 1.22]` when `ref_lum < 80`, `[0.88, 1.14]` otherwise. Targeted fix for dark scenes with minimal risk of over-correction in normal scenes.
- **B — Per-frame adaptive clamp:** Compute the desired correction factor per frame; if the clamp would cut it short by > 20%, apply the full correction only to the background mask (BG-only mode) and leave foreground pixels un-corrected. Avoids character skin tone shifts.
- **C — Multi-scale gain:** Apply large gain corrections at low frequency (blurred) and fine-tune at high frequency. Inspired by tone-mapping operators. More complex but avoids the hard boundary artifact.
- **D — Histogram equalisation reference:** Instead of per-frame scalar gain, match each frame's histogram to the reference using CLAHE on the background mask. Better correction for scenes with non-uniform lighting (half-dark, half-bright panels).

**Recommendation:** A is a one-line config change and sufficient for most cases. D is a [Research] item worth prototyping for dark/complex lighting scenes.

---

### 1.5 Stage 11 Composite Performance

**Why it matters:** Stage 11 (hard-partition composite) averages 24.5s and peaks at 41.9s, accounting for ~35% of total ASP runtime. The seam DP and feather computation are the bottlenecks.

**Options:**
- **A — Vectorise the seam DP with NumPy:** The per-row minimum-cost path accumulation can be expressed as a cumulative minimum over a 2D array, avoiding the Python row-by-row loop. Expected speedup: 5–10×.
- **B — CUDA seam DP:** Implement the DP on GPU using PyTorch scatter/gather operations. Fastest but requires a GPU; adds code complexity.
- **C — Restrict seam search window:** Current ±250px search window scans 500 columns per row. Reduce to ±100px for sequences with low horizontal drift (dx_cv < 5). Auto-detect from bundle adjustment output. Reduces the DP grid by 60%.
- **D — Cache seam path across iterations:** When re-processing the same frame set with different parameters (e.g. RLHF fine-tuning), cache the seam mask for identical frame pairs. Avoids recomputing if only the blending weights changed.

**Recommendation:** A is the highest-leverage change and requires no new dependencies. Combine with C for scenes where it applies.

---

### 1.6 Ghosting Reduction in Composite Zone

**Why it matters:** ASP-succeeded tests consistently have higher ghosting than simple stitch (8 out of 10 tests). The temporal median should deghost, but Stage 11's hard-partition seam reintroduces ghost-like edge artifacts when seams bisect character bodies.

**Options:**
- **A — Foreground mask cost in seam DP:** Weight seam paths through BiRefNet-masked foreground pixels with a high cost (e.g. 10×) so the DP routes seams through background wherever possible. Already partially implemented via `sem_cost` in `_seam_cut` (P2.4) — increase the foreground penalty weight.
- **B — Wider adaptive feather zone:** Proportionally widen `_FADE_ROWS` when the absolute luminance difference across the seam boundary is large. Currently `_FADE_ROWS=40` is fixed; make it a function of `|gain_A - gain_B|`. Smoother transitions reduce the perceptual ghosting near boundaries.
- **C — Poisson blending at seam zone:** Replace the linear feather with Poisson editing (gradient-domain seamless cloning) in a ±20px band around the seam. Eliminates the brightness step even when gain correction is at its limits. OpenCV has `cv2.seamlessClone`. Medium effort, measurable improvement.
- **D — ToonCrafter fill for overlap regions:** In high-overlap zones where multiple frames contribute (tight scroll sequences like test22 at 90px steps), use the ToonCrafter animation fill (`anim/anim_fill.py`, implemented in P3.3) to generate synthetic intermediate frames that reduce ghosting. High compute cost, best reserved for final-output mode.

**Recommendation:** A is the first priority (lowest effort, directly addresses the seam-through-character problem). C is a [Quick Win] for seam-zone smoothness. B and D are follow-on improvements.

---

### 1.7 RecDiffusion Border Rectangling

**Why it matters:** The current hard 30px edge crop leaves irregular black borders on outputs with diagonal or non-uniform scroll motion. P2.7 in the old ROADMAP was never implemented because it requires a diffusion backbone.

**Options:**
- **A — SRStitcher inpainting (already available):** The `anim/sr_stitcher.py` module (P3.4) already implements seam+border inpainting via diffusers. Route the `_crop_to_valid` output through `sr_stitcher.inpaint_borders()` instead of the hard 30px crop.
- **B — OpenCV inpainting fallback:** Use `cv2.inpaint(INPAINT_TELEA)` for border fill. Faster than diffusion; quality is lower but avoids the diffusion model dependency in standard mode.
- **C — Content-aware border crop:** Instead of a fixed 30px crop, compute the minimal bounding box of valid pixels and crop to that. Some outputs may be slightly smaller but always fully valid. Zero dependencies, instant.
- **D — RecDiffusion (original paper approach):** Fine-tune a conditional diffusion model on rectangle-completion from the output corpus. Best quality but requires training data and GPU time.

**Recommendation:** C immediately (no dependencies, always safe). A as the enhanced-quality path when `sr_mode=True`. Skip D — A subsumes it with existing infrastructure.

---

### 1.8 ASP Pipeline Configuration File

**Why it matters:** Many pipeline constants (gain clamp, `_FADE_ROWS`, `min_gap_threshold`, ECC pyramid levels, etc.) are hardcoded in `constants.py` or inline in `pipeline.py`. Tuning them requires code changes.

**Options:**
- **A — TOML/YAML config per pipeline run:** Load a `asp_config.toml` from the working directory or a default location. Override any constant at runtime. Use `tomllib` (stdlib in Python 3.11) with a typed dataclass. Low effort, high flexibility.
- **B — GUI settings panel for ASP params:** Expose the most-tuned constants (gain clamp, fallback thresholds, seam width, SR mode) as sliders/checkboxes in the StitchTab UI. Persisted in the app's settings store. Better UX for non-developer users.
- **C — Per-dataset profile system:** Save a successful pipeline config alongside each output panorama. Load it on re-processing the same dataset. Enables experimentation without losing working configurations.

**Recommendation:** A first (backend only, unblocks research iteration). B when the pipeline stabilises further.

---

### 1.9 Fallback Path Purity

**Why it matters:** When ASP falls back to SCANS, the fallback runs on BiRefNet-preprocessed, ECC-normalised frames rather than the original source frames. For tests 13 and 16 this caused sharpness degradation (~14–15 points) vs running SCANS on originals.

**Options:**
- **A — Pass original frames to SCANS fallback:** Store original (pre-BiRefNet, pre-ECC) frames in the pipeline context; use those when triggering SCANS. Simple change in `pipeline.py`.
- **B — Dual path from Stage 1:** Fork the pipeline at Stage 1 — one path applies preprocessing, the other keeps originals. Only merge at the fallback decision point. Slightly higher memory cost (two sets of frames in memory).

**Recommendation:** A is a one-line fix in the fallback branch. Ship it.

---

### 1.10 RLHF Loop Integration

**Why it matters:** The RLHF infrastructure exists (`rlhf/` module, `StitchFeedbackTab`, reward model CNN, DRL agent) but is not wired into the main pipeline evaluation loop. Collected feedback cannot yet improve future runs automatically.

**Options:**
- **A — Post-run quality gate:** After each pipeline run, call `reward_model.predict(output)` and log the score alongside benchmark metrics. If score < 0.6, flag the output for manual review in the feedback tab.
- **B — Parameter search with reward signal:** Use the reward model as the objective for a simple grid search or Bayesian optimisation over the gain clamp, feather width, and seam cost weights. Run offline on the 22-test corpus to find better defaults than the current hand-tuned values.
- **C — Online DRL agent for ECC/registration:** Wire the DRL agent (`rlhf_trainer.py`) into Stage 8 (ECC sub-pixel refinement) so it can adaptively adjust pyramid levels and ECC convergence criteria based on the reward signal. [Research] — requires significantly more feedback data to train reliably.

**Recommendation:** A is the immediate next step — it closes the feedback loop without requiring the DRL agent to be production-ready. B is the most promising path to measurable quality improvement from the existing RLHF infrastructure.

---

## 2. GUI / UX

### 2.1 Virtual Scroll Gallery

**Why it matters:** The current page-based gallery requires manual forward/back navigation. For large libraries (1000+ images), page browsing is cumbersome. LRU cache eviction on page change causes ~50–200ms thumbnail reloads.

**Options:**
- **A — QListView with QAbstractItemModel + virtual scrolling:** Replace the grid layout of `QLabel` widgets with a `QListView` in `IconMode`, backed by a model that loads thumbnails on-demand via `fetchMore()`. Qt handles viewport culling automatically. Large refactor of gallery base classes; best long-term approach.
- **B — QGraphicsView scene with item culling:** Place `QGraphicsPixmapItem` objects on a `QGraphicsScene`; only load pixmaps for items within the viewport rect. Moderate effort; easier to add zoom/pan interactions.
- **C — Keep page system, increase page size + smooth scroll indicator:** Increase default page size from 50 to 150–200 images (the LRU cap now makes this safe); add a visual scroll indicator showing current position in the total collection. Minimal refactor; acceptable for most use cases.

**Recommendation:** C is the fastest improvement with no architecture change. A is the right long-term direction — worth prototyping against the existing `AbstractClassTwoGalleries`.

---

### 2.2 Gallery Thumbnail Size Control

**Why it matters:** The fixed thumbnail size suits neither high-resolution 4K monitors nor small laptop screens. Users managing large libraries want smaller thumbnails to see more at once; users doing quality review want larger ones.

**Options:**
- **A — Persistent slider in gallery toolbar:** A `QSlider` that updates the `thumbnail_size` parameter live. Store the value in `QSettings`. Re-triggers the batch loader with the new size.
- **B — Ctrl+scroll zoom:** Intercept `wheelEvent` with `Ctrl` modifier to resize thumbnails in place. Familiar pattern from OS file managers.
- **C — Preset buttons (S/M/L/XL):** Simpler than a slider; four fixed sizes (64/128/192/256px). Less flexible but harder to mis-click.

**Recommendation:** B is the most intuitive (no UI chrome). Combine with A for explicit control.

---

### 2.3 Keyboard Navigation

**Why it matters:** Common operations (select next/previous image, open preview, trigger conversion) currently require mouse interaction. Power users expect keyboard shortcuts.

**Options:**
- **A — Arrow keys for gallery navigation:** Left/right/up/down select the adjacent thumbnail. Enter opens the full-size preview. Delete triggers the deletion workflow.
- **B — Global hotkey table in settings:** Let users configure custom bindings for any tab action. Store in a JSON file under `~/.config/image-toolkit/`. Use Qt's `QShortcut`.
- **C — Vim-style motion keys (hjkl):** For users comfortable with modal navigation. Optional mode toggle.

**Recommendation:** A is the baseline expectation for any image browser. B is the right architecture for a power-user tool. Skip C unless there's demand.

---

### 2.4 Bulk Selection and Operations

**Why it matters:** There is no way to select multiple images across the gallery and apply operations (convert, delete, tag) to all of them at once. Every operation is per-image or per-directory.

**Options:**
- **A — Checkbox select mode:** Toggle a "select mode" button that shows checkboxes on all thumbnails. Selected images are passed to any operation via a "batch apply" button.
- **B — Shift+click range select + Ctrl+click multi-select:** Standard file manager pattern. Works without a dedicated mode toggle.
- **C — Context menu on selection:** Right-click shows a context menu with available batch operations when multiple images are selected.

**Recommendation:** B + C together. Standard patterns users already know.

---

### 2.5 Session Persistence

**Why it matters:** Every app restart requires re-browsing to the last directory. For users managing consistent workflows, this is repetitive friction.

**Options:**
- **A — Remember last browsed path per tab:** Store in `QSettings`; restore on startup. One-line change per tab.
- **B — Session file:** Save the full app state (open tabs, loaded directories, gallery scroll position, active filters) to a `session.json`. Restore on startup. More complex; enables "workspaces".
- **C — Recent directories list:** Show the 10 most recently browsed directories in a dropdown. No auto-restore; user chooses. Lower friction than B, covers 80% of the use case.

**Recommendation:** A immediately. C as a follow-on. B is overkill for now.

---

### 2.6 Stitch Tab UX — Before/After Comparison

**Why it matters:** The StitchTab shows the output panorama but provides no side-by-side comparison with the simple stitch fallback. Users can't judge whether ASP actually improved the result without opening both outputs manually.

**Options:**
- **A — Split-view with draggable divider:** Display ASP result on the left, SCANS result on the right, separated by a draggable vertical line. Both images are registered to the same canvas coordinates.
- **B — Overlay toggle button:** A single button that swaps between ASP and SCANS output with a highlight effect. Faster than a split-view for single-image judgement.
- **C — Quality metric overlay:** Show sharpness, ghosting, and seam gradient scores on top of the preview image. No image comparison — just the numbers.

**Recommendation:** B + C. The metrics give context; the toggle lets the user see the actual visual difference.

---

### 2.7 Progress and Cancellation

**Why it matters:** Long-running operations (duplicate scan with SIFT, ASP pipeline on large inputs, database scan) show minimal progress feedback and cannot be cancelled mid-run without killing the process.

**Options:**
- **A — Stage-level progress bar for ASP:** Emit a stage-name signal at the start of each of the 13 pipeline stages. Display current stage name + a per-stage progress percentage in the StitchTab status bar.
- **B — Cancellable QThread with `_should_stop` flag:** Add a `cancel()` method to all worker QThreads that sets a `_should_stop` flag. Workers check the flag between stages and emit a `cancelled` signal when it is set.
- **C — ETA estimate:** Based on timing data from the benchmark (per-stage avg seconds), display a "~Xs remaining" estimate that updates as each stage completes.

**Recommendation:** A + B. Cancellation is a correctness feature (prevents zombie workers). Stage progress is the minimum viable feedback for a 90-second operation.

---

### 2.8 Theme Support

**Why it matters:** The app uses the system Qt palette, which produces an inconsistent look across platforms and doesn't respect dark-mode OS settings reliably.

**Options:**
- **A — Dark/light mode toggle using QSS:** Write a `dark.qss` and `light.qss`; toggle via a settings checkbox. Loaded at startup from `~/.config/image-toolkit/theme.qss`.
- **B — qdarkstyle / qt-material integration:** Drop-in third-party stylesheets. Fastest path to a polished dark theme. Adds a dependency.
- **C — Follow OS dark mode setting:** Use `QPalette.ColorScheme` (Qt 6.5+) to detect and follow the OS preference automatically. No user setting needed; just works.

**Recommendation:** C first (zero effort, respects user OS setting). A as a power-user override. Skip B — adds a dependency for minimal gain.

---

## 3. Performance

*Note: All Tier 1–5 items from `RAM_REDUCTION_ROADMAP.md` are fully implemented (✅). The items below are new opportunities.*

### 3.1 Rust Streaming Image Merger

**Why it matters:** `base/src/core/image_merger.rs` loads all input images into a `Vec<DynamicImage>` before compositing. Merging 100 × 4K images temporarily consumes 2–4 GB of RAM.

**Options:**
- **A — Two-pass streaming:** First pass: metadata read only (image size via header parsing — no pixel load). Compute final canvas dimensions. Allocate output buffer. Second pass: load each image, paste into canvas at precomputed offset, immediately drop. Peak RAM = 1 image at a time (~30 MB for 4K RGBA).
- **B — Rayon-parallel with bounded semaphore:** Keep the parallel load but limit concurrent live images to `N_cores` using a semaphore. Balances throughput vs memory. Peak RAM = `N_cores × image_size`.
- **C — Memory-mapped output buffer:** Use `memmap2` to map the output file directly. Write each frame directly to disk rather than accumulating in RAM. Zero extra RAM for the output; useful for very large panoramas.

**Recommendation:** A for correctness. C as an optional flag for very large (>10K pixel) outputs.

---

### 3.2 ASP Render Stage GPU Acceleration

**Why it matters:** The temporal median render (Stage 10) averages 20.78s and is single-threaded NumPy. The 10-frame, large-canvas case (test19: 33.8s) is the bottleneck.

**Options:**
- **A — PyTorch stack + median on GPU:** Load the frame strips as a CUDA tensor stack; call `torch.median(stack, dim=0)`. For a 4K × 4K canvas with 10 frames, this should reduce render time from ~30s to ~1–2s. Requires GPU; falls back to NumPy if unavailable.
- **B — Numba JIT for NumPy path:** Decorate the median computation with `@numba.jit(nopython=True, parallel=True)`. No CUDA required; ~3–5× speedup on CPU. Adds a Numba dependency.
- **C — C extension via Cython:** Write the inner median loop in Cython. More effort than B; similar result.

**Recommendation:** A for machines with the RTX 3090 Ti (already in the system). B as the CPU fallback for environments without CUDA.

---

### 3.3 BiRefNet Inference Batching

**Why it matters:** BiRefNet runs once per frame in sequence. For a 14-frame dataset (test7), 14 serial inference passes add up. The GPU is underutilised between each call.

**Options:**
- **A — Batch all frames in one forward pass:** Collate all frames into a single tensor batch; one model call returns all masks. Memory cost: `N_frames × frame_size × 3` (e.g. 14 × 1080 × 1920 × 3 bytes ≈ 87 MB). Feasible on the 3090 Ti.
- **B — Fixed-size mini-batches (e.g., 4 frames):** Compromise between latency and memory. Process 4 frames at a time. Works on lower-VRAM GPUs.

**Recommendation:** A when VRAM allows (auto-detect based on frame count × resolution). B as fallback.

---

### 3.4 Database Query Optimisation

**Why it matters:** The `image_database.py` already uses server-side cursors for similarity search, but several common operations are still suboptimal.

**Options:**
- **A — Connection pooling with pgbouncer or psycopg3:** Replace single-connection `psycopg2` with `psycopg3`'s async connection pool. Reduces connection overhead for frequent small queries. Particularly useful for the database tab's search loop.
- **B — Prepared statements for hot paths:** Use `cursor.execute(prepared_stmt, params)` for queries called in tight loops (e.g. tag lookup per image). Avoids repeated query parsing overhead.
- **C — Partial index on `images.path`:** If searching by path prefix is common, a `CREATE INDEX idx_images_path_prefix ON images(path varchar_pattern_ops)` speeds up LIKE queries significantly.
- **D — Embedding index tuning:** Current pgvector index may use default params. Tune `ef_construction` and `m` for the HNSW index based on the collection size. For collections > 100k images, better index params can improve search latency by 5–10×.

**Recommendation:** A if the database tab is under latency pressure. D is the highest-impact single change for large collections.

---

### 3.5 WebDriver Lifecycle Management

**Why it matters:** Selenium WebDriver instances are not guaranteed to be closed on Python exceptions, leaving orphaned browser processes that consume hundreds of MB.

**Options:**
- **A — Context manager wrapper in Python crawlers:** Wrap each crawler session in `with CrawlerSession(driver) as s:` where `__exit__` always calls `driver.quit()`. Clean, Pythonic, handles exceptions automatically.
- **B — Rust RAII guard (scopeguard):** In the PyO3 bindings, use `scopeguard::defer!` to call `quit()` on unwind. Handles panics as well as normal exits.
- **C — Crawler health monitor thread:** A background thread that periodically checks the WebDriver process list and kills orphans that have been running > timeout. Heavier but catches failures in `driver.quit()` itself.

**Recommendation:** A immediately. B if the Rust crawlers are the primary execution path.

---

### 3.6 DynamicImage Move Semantics in Rust

**Why it matters:** Several Rust functions clone `DynamicImage` unnecessarily (apply_ar_transform, fast_resize no-op path). A 4K RGBA clone is ~32 MB per call.

**Options:**
- **A — Change signatures to take ownership:** `fn apply_ar_transform(img: DynamicImage, ...) -> Result<DynamicImage>`. Return `img` directly in the no-transform branch. Zero-cost when no transformation is needed.
- **B — Cow<DynamicImage>:** Return `Cow::Borrowed(&img)` for no-op paths. Avoids a move in the common case where the caller still needs the original.

**Recommendation:** A. The call sites can afford the move; B adds complexity with minimal benefit.

---

## 4. New Features

### 4.1 Batch Stitching

**Why it matters:** Users with large screenshot libraries (e.g., novel reading sessions generating 50+ groups of frames) currently process each group one at a time in the StitchTab.

**Options:**
- **A — Directory-level batch mode:** Scan a root directory for subdirectories matching a naming pattern (e.g., `scene_*/`). Run the ASP pipeline on each, save outputs to a `stitched/` subfolder. Show a batch progress list in the UI.
- **B — Queue-based with priority:** A persistent queue (backed by the PostgreSQL database) where each item is a frame group. Workers process items in order; the queue survives app restarts.
- **C — CLI-only batch mode:** `python main.py stitch --batch-dir /path/to/groups/`. No GUI needed; suitable for scheduled/overnight runs.

**Recommendation:** C first (leverages existing `argparse` infrastructure). A as a GUI counterpart when C is validated.

---

### 4.2 Export Stitched Panorama to Scrolling Video

**Why it matters:** Stitched manga/visual novel pages are long-form content that users may want to share as videos (e.g., on social platforms that don't support long images). A scrolling video export is a natural derived product.

**Options:**
- **A — OpenCV VideoWriter with pan-and-scan:** Crop a sliding window across the panorama and write each position as a video frame. Parameterise scroll speed (px/frame) and output resolution.
- **B — FFmpeg pipe in Rust:** Pipe frame bytes to `ffmpeg` via stdout. Handles codec selection, hardware encoding, and container formats. Higher quality than OpenCV VideoWriter.
- **C — Export as animated WebP/GIF (small panoramas only):** For panoramas < 1500px wide, `imageio` + `PIL` can produce a looping animated WebP. Zero new dependencies.

**Recommendation:** B for full-resolution output. C as a quick-share option.

---

### 4.3 CLIP-Based Semantic Image Search

**Why it matters:** The database currently supports vector search via pgvector, but the embeddings are ResNet-18 Siamese features tuned for duplicate detection, not semantic content. A CLIP embedding enables natural-language queries ("find images with red sunset backgrounds") or image-similarity search across the full semantic space.

**Options:**
- **A — OpenCLIP text + image encoder:** Generate CLIP embeddings during database ingest; store a second embedding column in PostgreSQL. Support both text queries and image queries via the search tab. `open-clip-torch` is a drop-in, no API key required.
- **B — AnimeCLIP / WaifuDiffusion CLIP fine-tune:** Use a domain-specific CLIP variant fine-tuned on anime content for better accuracy on the primary use case.
- **C — Dual-column search:** Run both Siamese (for exact duplicate detection) and CLIP (for semantic similarity) embeddings in parallel. Show results from both in the search tab with a toggle.

**Recommendation:** A as the initial implementation. B as a model swap once A is validated.

---

### 4.4 Auto-Tagger Integration

**Why it matters:** The database supports tags, but tagging is manual. The crawlers already fetch Danbooru/Gelbooru tags for downloaded images, but locally-sourced images have no tags.

**Options:**
- **A — WD-1.4 (WaifuDiffusion Tagger):** Run the ONNX model locally on each image during database ingest. Generates booru-style tags at ~50–100ms/image. Widely used in the anime/manga domain.
- **B — MetaCLIP / CLIP-ViT with a tag vocabulary:** Use zero-shot classification against the full Danbooru tag vocabulary. Lower accuracy than a fine-tuned tagger but no separate model download needed if CLIP is already present.
- **C — Human-in-the-loop tagging queue:** Show untagged images in a queue; present top-N auto-tag suggestions (from A or B) as checkboxes; user confirms or corrects. Persistent queue backed by PostgreSQL.

**Recommendation:** A for accuracy. C for quality control — don't fully automate without a review step.

---

### 4.5 Multi-Monitor Wallpaper Support

**Why it matters:** The wallpaper tab sets a wallpaper on the primary monitor via `qdbus-qt6`. Users with multi-monitor setups want per-monitor control.

**Options:**
- **A — Enumerate monitors with `QScreen.availableScreens()`:** For each screen, call the appropriate `qdbus-qt6` or Plasma `org.kde.PlasmaShell` D-Bus method with the screen identifier. KDE supports per-monitor wallpapers via `setWallpaper(screen_id, path)`.
- **B — GNOME support via `gsettings`:** GNOME doesn't natively support per-monitor wallpapers without extensions (e.g., HydraPaper). Fall back to a single wallpaper but use a composited image (stitch multiple source images side-by-side to match the total monitor resolution).
- **C — Virtual desktop rotation:** Rotate through multiple wallpapers across monitors on a schedule; each monitor gets a different image from the queue.

**Recommendation:** A for KDE (primary target given `qdbus-qt6` is in the codebase). B as a fallback for GNOME.

---

### 4.6 Image Deduplication Across Directories

**Why it matters:** Duplicate detection currently operates within a single directory scan. Users who maintain multiple collections (local, synced from Dropbox, downloaded from crawlers) accumulate cross-directory duplicates.

**Options:**
- **A — Cross-directory phash index in PostgreSQL:** On database ingest, store phash alongside the embedding. A periodic deduplication job queries pairs with hamming distance ≤ 4. No re-scanning needed.
- **B — GUI cross-directory duplicate scan:** Extend the existing `DuplicateScanWorker` to accept multiple source directories as input. Results show which directory each duplicate is in.

**Recommendation:** A integrates cleanly with the existing database. B is the fastest UX path if users don't use the database.

---

### 4.7 Slideshow Improvements

**Why it matters:** The slideshow daemon exists (`base/src/utils/slideshow_daemon.rs`) but has minimal configuration. Users want more control over transition effects and timing.

**Options:**
- **A — Configurable timing and order:** Expose interval (seconds), shuffle mode, and filter (by tag/group) as settings. Currently these are likely hardcoded.
- **B — Transition effects:** Fade, slide, zoom-in transitions between wallpapers. Implemented by pre-rendering a short animated sequence and advancing the wallpaper in rapid succession.
- **C — Schedule-based wallpaper rotation:** Different wallpaper categories at different times of day (e.g., bright in the morning, dark at night). Uses system time.

**Recommendation:** A is the highest-value improvement. B requires significant effort for questionable return — skip for now.

---

### 4.8 ComfyUI Workflow Integration for Post-Processing

**Why it matters:** The `comfy_generate_tab.py` and `comfy_manager.py` exist but are limited to generation. ComfyUI workflows could also be used for post-processing stitched outputs (upscaling, style transfer, inpainting).

**Options:**
- **A — "Send to ComfyUI" button in StitchTab:** After stitching, allow the user to load the output directly into a pre-configured ComfyUI workflow (e.g., img2img for cleanup, upscale, or inpaint).
- **B — ComfyUI as a post-processing backend for ASP:** Replace the `anim/super_res.py` Real-ESRGAN path with a ComfyUI API call to a user's configured workflow. More flexible; allows any post-processing model the user has installed.
- **C — Drag-and-drop image to ComfyUI queue:** Allow dragging any gallery image to a "ComfyUI" drop target that sends it to the running ComfyUI instance's queue via the API.

**Recommendation:** C is the most generally useful (not tied to stitching). A as a stitching-specific QoL improvement.

---

### 4.9 Safetensors Metadata Viewer

**Why it matters:** The codebase includes `safetensors_metadata.py` but this functionality is not exposed in the GUI. Users managing LoRA and checkpoint files want to inspect their metadata (training parameters, trigger words, base model) without external tools.

**Options:**
- **A — "Inspect Model" button in LoRA train/generate tabs:** Load any `.safetensors` file and display its metadata in a read-only dialog.
- **B — Drag-and-drop model inspector panel:** A dedicated mini-panel where users can drag `.safetensors`, `.ckpt`, and `.pt` files to see their metadata, architecture summary, and estimated VRAM usage.

**Recommendation:** A is a quick-win improvement to existing tabs. B is better UX but a larger investment.

---

## 5. Architecture and Infrastructure

### 5.1 ASP Pipeline Unit Test Coverage

**Why it matters:** The `backend/test/anim/` suite tests end-to-end ASP runs but has limited unit tests for individual pipeline stages. Regressions in `bundle_adjust.py` or `compositing.py` are hard to catch without running the full benchmark.

**Options:**
- **A — Unit tests for each stage in isolation:** Synthetic test cases (e.g., known translation pairs for bundle adjustment, known frame strips for composite). Each test runs in < 1s.
- **B — Property-based testing with Hypothesis:** Generate random translation sequences with known properties (monotonic, bounded ratio) and verify the pipeline produces valid affines. Catches edge cases that hand-crafted tests miss.
- **C — Benchmark diff testing:** Run the 22-test benchmark on every PR and fail if any metric regresses by > threshold. Slower (20 min) but catches integration issues.

**Recommendation:** A + C. Unit tests catch regressions early; the benchmark gate prevents quality regressions from slipping into main.

---

### 5.2 Benchmark Regression CI

**Why it matters:** The benchmark suite exists in `backend/benchmark/` with baseline comparison, but it is not yet wired into GitHub Actions for automatic regression detection on every push.

**Options:**
- **A — GitHub Actions workflow on push to main:** Run `python run_all.py --baseline results/baseline/` and fail the build if `time > baseline × 1.2` or `memory > baseline × 1.15`.
- **B — Weekly scheduled run with Slack/email notification:** For expensive benchmarks (Rust criterion, full ASP), run weekly rather than per-push. Report a summary diff vs the previous week.
- **C — Pre-commit hook for lightweight checks:** A subset of fast benchmarks (phash, db queries) runs locally on commit. Full suite is optional.

**Recommendation:** A for the Python benchmarks (fast enough). B for the full ASP + Rust benchmarks.

---

### 5.3 Plugin System for Matchers and Compositors

**Why it matters:** The matching and compositing stages have grown a large number of fallback tiers (TM, PC, ALIKED+LightGlue, RoMa, segment-guided). Adding new matchers requires editing `matching.py` directly.

**Options:**
- **A — Matcher registry with priority list:** A dict mapping matcher name → callable. Pipeline tries matchers in priority order until one returns enough inliers. Adding a new matcher = registering it in the dict. No changes to the pipeline loop.
- **B — Abstract `Matcher` base class with a `match(frame_a, frame_b) → List[MatchPair]` interface:** Each matcher is a subclass. The pipeline calls `matcher.match()` without knowing which implementation it's using. Enables future drop-in replacement of any stage.
- **C — External plugin discovery via entry_points:** Allow third-party packages to register matchers. Overkill for now but future-proof.

**Recommendation:** B. The formal interface prevents the current situation where each matcher has subtly different return signatures.

---

### 5.4 Logging and Diagnostics

**Why it matters:** The current pipeline logs to stdout with print statements. Diagnosing failures in production requires replaying the entire run.

**Options:**
- **A — Structured logging with Python `logging` module:** Replace `print()` calls with `logging.getLogger(__name__).info/debug/warning`. Add a `FileHandler` that saves per-run logs to `~/.config/image-toolkit/logs/`. Log level controlled by config.
- **B — Pipeline execution trace JSON:** At the end of each ASP run, dump a structured JSON summary (stage timings, intermediate metrics, affine health scores, match counts) to the output directory. Already partially done by the benchmark runner — standardise and always enable it.
- **C — GUI log panel:** A collapsible log panel in the main window that shows the last N log lines in real-time during operations. Less cluttered than console output; filterable by level.

**Recommendation:** A + B immediately. C as a quality-of-life follow-on.

---

### 5.5 Vault Manager Modernisation

**Why it matters:** `vault_manager.py` starts a JVM via JPype before Qt initialises. This is the root cause of the known `libstdc++` RTTI conflicts with GTK native dialogs and QtWebEngine. The JVM startup adds ~1–2s to app launch.

**Options:**
- **A — Rewrite the Kotlin AES-256-GCM implementation in Python using `cryptography`:** The `cryptography` package (already likely in the venv for TLS-related code) provides AES-GCM natively. Eliminates the JVM dependency entirely. Requires verifying `.vault` format compatibility with the Kotlin implementation.
- **B — Subprocess-based vault operations:** Keep the Kotlin implementation but call it via `subprocess` rather than JPype. Avoids JVM-in-process RTTI conflicts; small per-call overhead (~100ms) is acceptable for infrequent credential operations.
- **C — Rust implementation via PyO3:** Implement AES-256-GCM in Rust using the `aes-gcm` crate. Compile into the existing `base` extension module. Zero overhead, no JVM, same security guarantees.

**Recommendation:** C is the architecturally cleanest solution — it consolidates security-critical code into the already-existing Rust extension. A is the fastest path if the `.vault` format is documented.

---

### 5.6 Mobile App Feature Parity Backlog

**Why it matters:** The Android app (`app/`) exists but its relationship to the desktop app's feature set is unclear from the code.

**Options (brainstorm):**
- Remote wallpaper control: set the desktop wallpaper from the phone (via REST API layer in `api/`).
- Gallery browsing via the web frontend exposed on LAN.
- Push notifications when a long-running desktop operation completes (e.g., ASP batch job).

**Recommendation:** These are exploratory — no immediate action. Worth defining the mobile app's scope explicitly before adding new features.

---

## 6. Completed (Archived from Previous Roadmaps)

These items are fully implemented and no longer require tracking.

| Area | Summary |
|---|---|
| Gallery LRU caches | `AbstractClassTwoGalleries` and `AbstractClassSingleGallery` — all three caches converted to bounded `LRUImageCache`. WallpaperTab, ImageExtractorTab, ReverseSearchTab fixed. |
| QPixmap threading violation | `ImageLoaderWorker` now emits `QImage` from worker thread. |
| DuplicateScanWorker chunked compare | SIFT/SSIM use `_chunked_compare(chunk_size=500)` to cap live descriptors. |
| `_loaded_results_buffer` → QImage | `scan_metadata_tab.py` buffer stores `QImage` instead of `QPixmap`. |
| Tag checkboxes → QListWidget | Both `scan_metadata_tab.py` and `search_tab.py` use virtual QListWidget. |
| `source_path_to_widget` cleanup | Map entries popped on page changes in `image_extractor_tab.py`. |
| ML model `unload()` on finish | Siamese, GAN, SD3 wrappers call `unload()` after inference completes. |
| Weak-reference lambda captures | `abstract_class_two_galleries.py` signal closures use `weakref.ref`. |
| PostgreSQL server-side cursors | `bulk_export_cursor` pattern for unbounded queries. |
| N+1 tag query | `get_tags_for_images_bulk` batch fetch replaces per-image tag queries. |
| ASP Phase 1 (P1.1–P1.9) | Animation phase clustering, variable-step renderer, confidence-weighted median, EfficientLoFTR, grid sampling, StabStitch BA regularisation, auto-MFSR, auto-inpaint, bidirectional midplane. |
| ASP Phase 2 (P2.1–P2.6, P2.8–P2.9) | SEA-RAFT flow, Real-ESRGAN SR, ALIKED+LightGlue, BiRefNet seam routing, soft-seam diffusion, per-segment photometric correction, RoMa v2, segment-guided matching. |
| ASP Phase 3 (P3.1–P3.6) | EfficientLoFTR drop-in, JamMa O(N) Mamba (pending CUDA rebuild), ToonCrafter ghost fill, SRStitcher diffusion fusion, SEA-RAFT fine-tune pipeline, EfficientLoFTR fine-tune pipeline. |
