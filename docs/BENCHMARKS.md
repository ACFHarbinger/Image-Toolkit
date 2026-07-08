# Image-Toolkit Backend & Base Performance Benchmarks

Comprehensive benchmark suite for measuring memory usage and compute time across
the Python backend, C++ base layer, and TypeScript analytics math backbone.

## Benchmark Suite Index

| Suite | Runner | Location | Output | CI job |
|---|---|---|---|---|
| **Database** | Python `benchmark/bench_database.py` | `backend/benchmark/` | `results/benchmark_*.json` | `benchmark.yml` |
| **ML Models** | Python `benchmark/bench_models.py` | `backend/benchmark/` | `results/benchmark_*.json` | `benchmark.yml` |
| **Image Processing** | Python `benchmark/bench_image_ops.py` | `backend/benchmark/` | `results/benchmark_*.json` | `benchmark.yml` |
| **C++ Base** | `just test-base-cpp` | `base/tests/` | ctest output | `benchmark.yml` |
| **ASP Corpus** | `backend/benchmark/bench_anime_stitch.py` | `backend/benchmark/` | `data/output/benchmark_report.md` | manual |
| **Frontend Math** | `npm test` / TypeDoc | `frontend/src/math/` | Jest output | `docs.yml` (type-check) |

## Prerequisites

```bash
# Install benchmark dependencies
pip install memory_profiler psutil pytest-benchmark matplotlib

# Build C++ base module
just build-base-release
```

## Running Benchmarks

### Quick Start (All Benchmarks)

```bash
# Python backend benchmarks
python benchmark/run_all.py

# C++ base tests (includes timing benchmarks)
just test-base-cpp

# Combined report
python benchmark/generate_report.py
```

### Individual Benchmark Suites

```bash
# Database operations
python benchmark/bench_database.py

# ML model inference
python benchmark/bench_models.py

# Image processing (Python wrappers)
python benchmark/bench_image_ops.py

# Memory profiling only
python benchmark/memory_profile.py
```

## Benchmark Categories

### 1. Database Operations (`bench_database.py`)

- Tag insertion (1k, 10k tags)
- Group/subgroup operations
- Vector similarity search (100, 1k, 10k images)
- Bulk image insertion
- `fetchall()` vs `fetchmany()` comparison

**Metrics**: Query time, peak RAM, PostgreSQL buffer usage

### 2. ML Model Inference (`bench_models.py`)

- Siamese network (ResNet-18) embedding generation
- GAN (AnimeGAN2) single-image generation
- Stable Diffusion 3 (if model available)
- Model load/unload time
- CUDA vs CPU comparison

**Metrics**: Inference time, VRAM usage, CPU RAM, model load time

### 3. Image Processing (`bench_image_ops.py`)

- Image conversion (single, batch of 100/1000)
- Image merging (horizontal, vertical, grid)
- Video thumbnail generation
- Duplicate detection (pHash, SIFT, SSIM, ORB)

**Metrics**: Processing time, peak RAM, throughput (images/sec)

### 4. C++ Base Operations (`base/tests/`)

- File system scanning (1k, 10k, 100k files)
- Image conversion (C++ native via OpenCV)
- Board crawler HTTP operations
- Cloud sync operations

**Metrics**: Execution time, peak RAM

### 5. Frontend Analytics Math (`frontend/src/math/`)

The TypeScript math backbone (`stats.ts`, `distance.ts`, `linalg.ts`, `signal.ts`,
`colormap.ts`, `graph.ts`, `benchmark.ts`) is validated by:

- **Type checking**: `npx tsc --noEmit` (run by `docs.yml` CI and `tsc-check` pre-commit hook)
- **TypeDoc generation**: `npx typedoc --entryPointStrategy expand --out site/api/typescript src/math`

`benchmark.ts` is the analytics computation layer — it is consumed by the Tauri
dashboard, not run standalone. Its key exports and what they compute:

| Export | What it computes |
|---|---|
| `computeEfficiency(benchmarks)` | Composite efficiency score (0–100) and throughput per benchmark |
| `computeMemoryVsTimeScatter(benchmarks)` | Memory vs time bubble chart data |
| `computeMemoryBreakdown(benchmarks)` | Stacked baseline/delta/leaked breakdown |
| `detectRegressions(current, baseline)` | Time and memory regression detection vs a stored baseline |
| `computeTimingBreakdown(timing)` | ASP stage-by-stage time breakdown as % of total |
| `computeMetricComparisons(datasets)` | ASP vs Simple per-metric deltas across all datasets |
| `computeSeamQualityHeatmap(datasets)` | Per-dataset seam quality scores in [0,1] space |
| `verdictSummary(datasets)` | Counts of `asp_better / simple_better / comparable / no_data` |
| `computeAlignmentDrift(datasets)` | Coefficient of variation for dy/dx steps per dataset |
| `computePhotometricProfile(datasets)` | Per-frame gain applied per dataset |
| `computePerSeamDetail(datasets)` | Per-seam ghost/NCC/color scores |
| `computeFallbackReasonDistribution(datasets)` | Fallback reason taxonomy with counts |
| `computeGtComparisons(datasets)` | SSIM/PSNR/aligned-SSIM vs ground truth |

## Output Formats

### Console Output (Real-time)

```
============================================================
Database Benchmarks — PostgreSQL 15.2, 10k test images
============================================================

Tag Operations:
  insert_tags_1k              0.234s    12.5 MB    4,273 tags/sec
  insert_tags_10k             2.156s    45.2 MB    4,638 tags/sec
  get_all_tags_fetchall       0.045s    2.1 MB     —
  get_all_tags_limit_1k       0.012s    0.5 MB     —

Vector Search:
  similarity_search_k10       0.089s    1.2 MB     112 queries/sec
  similarity_search_k100      0.234s    4.5 MB     —

Peak RAM: 125.4 MB
```

### JSON Report (`results/benchmark_YYYYMMDD_HHMMSS.json`)

```json
{
  "timestamp": "2026-03-01T14:23:45",
  "system": {
    "cpu": "AMD Ryzen 9 5950X",
    "ram": "64 GB",
    "gpu": "NVIDIA RTX 3090",
    "os": "Linux 6.18.0"
  },
  "benchmarks": {
    "database": { ... },
    "models": { ... },
    "image_ops": { ... },
    "rust_core": { ... }
  }
}
```

### HTML Report with Charts (`results/report.html`)

Interactive report with:
- Time-series comparison graphs
- Memory usage heatmaps
- Before/after optimization comparisons
- Regression detection

## Benchmark Data Setup

Run `benchmark/setup_test_data.py` to generate reproducible test datasets:

```bash
python benchmark/setup_test_data.py
```

This creates:
- `dump/images/` — 1k synthetic images (various formats, sizes)
- `dump/videos/` — 10 test videos (MP4, AVI)
- `dump/database.sql` — 10k pre-seeded database entries
- `dump/embeddings.npy` — Pre-computed embeddings for vector search

## Continuous Benchmarking

### GitHub Actions Integration

The `.github/workflows/benchmark.yml` workflow runs on:
- Every push to `main` (performance regression checks)
- Weekly schedule (long-term tracking)
- Manual trigger

Results are stored in `gh-pages` branch for historical comparison.

### Pre-commit Hook

```bash
# Install pre-commit benchmark (optional)
ln -s ../../benchmark/pre_commit_bench.py .git/hooks/pre-commit
```

Runs lightweight benchmarks before each commit, warns if performance degrades > 10%.

## Interpreting Results

### Memory Usage

- **Baseline**: Clean Python process + imported modules (~150 MB)
- **Acceptable growth**: < 500 MB for typical operations
- **Warning threshold**: > 1 GB for non-ML operations
- **Critical threshold**: > 4 GB (except SD3)

### Compute Time

- **Database queries**: < 100ms for single operations
- **Batch conversions**: > 50 images/sec (depends on size)
- **ML inference**:
  - Siamese: < 50ms/image (CPU), < 10ms (GPU)
  - GAN: < 1s/image (GPU)
  - SD3: 5–30s/image (depends on steps)

### Regression Criteria

A benchmark fails if:
- Memory usage increases > 15% vs baseline
- Execution time increases > 20% vs baseline
- Throughput decreases > 15% vs baseline

## Troubleshooting

**"psycopg2.OperationalError: could not connect to server"**
- Ensure PostgreSQL is running: `sudo systemctl start postgresql`
- Check connection params in `env/vars.env`

**"CUDA out of memory"**
- Reduce batch sizes in `bench_models.py`
- Set `CUDA_VISIBLE_DEVICES=""` to force CPU mode

**C++ base tests not found**
- Run `just build-base-release` first
- Ensure Catch2 is available (fetched automatically by CMake FetchContent)

## Adding New Benchmarks

### Python Backend

```python
# benchmark/bench_custom.py
from benchmark.utils import BenchmarkRunner, measure_memory

runner = BenchmarkRunner("Custom Operations")

@runner.benchmark("my_operation", iterations=100)
@measure_memory
def bench_my_op():
    # Your code here
    result = my_expensive_function()
    return result

if __name__ == "__main__":
    runner.run()
    runner.print_results()
```

### C++ Base

Add a new `TEST_CASE` with a `[benchmark]` tag in `base/tests/`:

```cpp
// base/tests/math/test_math_bench.cpp
#include <catch2/catch_test_macros.hpp>
#include <catch2/benchmark/catch_benchmark.hpp>
#include "base/math/stats.hpp"
#include "base/math/distance.hpp"

TEST_CASE("mean 10k", "[math][benchmark]") {
    std::vector<double> data(10000);
    std::iota(data.begin(), data.end(), 0.0);
    BENCHMARK("mean_10k") {
        return base::math::stats::mean(data);
    };
}

TEST_CASE("cosine_similarity 768d", "[math][benchmark]") {
    std::vector<double> a(768), b(768);
    for (int i = 0; i < 768; ++i) { a[i] = i / 768.0; b[i] = (768 - i) / 768.0; }
    BENCHMARK("cosine_768d") {
        return base::math::distance::cosine_similarity(a, b);
    };
}
```

**Run**:

```bash
just test-base-cpp          # all tests including benchmarks
# or directly:
cmake --build build/base --target base_tests && ctest --test-dir build/base -V
```

---

## C++ Math Micro-benchmarks

The `base/include/math/` headers (`stats.hpp`, `distance.hpp`, `information.hpp`) back
the Python ML pipeline and Recommendation Engine. Catch2 benchmarks live in
`base/tests/math/` alongside unit tests.

**Baselines** (to be established once benchmarks are added — see CI §6.12 guidance below):

| Function | Input size | Expected time (Ryzen 9 5950X) |
|---|---|---|
| `mean` | 10k f64 | < 5 µs |
| `euclidean` | 768-d f64 | < 2 µs |
| `cosine_similarity` | 768-d f64 | < 3 µs |
| `shannon_entropy` | 256 bins | < 2 µs |

---

## Anime Stitch Pipeline Benchmark

The anime stitch benchmark runs both the **Anime Stitch Pipeline (ASP)** and the
**OpenCV SCANS Simple Stitch** on every `dump/asp_testX/` dataset, computes CV
metrics for each output, saves intermediate visualisations, and generates a
structured Markdown report for human review and LLM-assisted iteration.

### ASP Benchmark Corpus

**Corpus size**: 97 test datasets (`dump/asp_test01/` – `dump/asp_test97/`).
Each contains 4–20 source frames captured from scroll-through anime content.
The safe test runner (no GPU, uses pre-computed fixtures) is:

```bash
pytest backend/test/animation/ --skip-gpu -q
```

**Failure taxonomy** (established across S1–S45 of ASP development):

| Cluster | Detection condition | Root cause |
|---|---|---|
| **Ghost / double-edge** | `ghosting_siqe > 30` | Pose gap at seam + overly wide feather |
| **Hard seam step** | `seam_visibility > 25` | Colour discontinuity at boundary (fix: S16 colour match, S21 Poisson blend) |
| **Low structural similarity** | `ssim < 0.70` vs ground truth | Misaligned panels, incorrect bundle-adjust solution |
| **SCANS fallback** | `method == 'scans'` | Pipeline validation failure (target: ≤ 5 genuine fallbacks) |

**Baseline metric values** (after S11 fallback-elimination fixes, CPU-only):

| Metric | ASP median | Simple median | Threshold | Direction |
|---|---|---|---|---|
| `sharpness` (Laplacian var) | > 120 | > 80 | — | higher better |
| `coverage` | > 0.90 | > 0.85 | < 0.70 = failure | higher better |
| `edge_energy_score` (sharpness proxy; NOT ghosting) | — | — | diagnostic only | — |
| `ghosting_siqe` (FFT autocorr, true ghost metric) | < 20 | — | GhostGate at `max(40, 2× sim)`; flag > 30 | lower better |
| `seam_visibility` | < 12 | — | flag > 25 | lower better |
| `aligned_ssim` vs GT | > 0.75 | > 0.65 | < 0.70 = regression | higher better |
| SCANS fallback rate | 4/96 tests | — | target ≤ 5 | lower better |

**Corpus interactive analysis**: see `docs/notebooks/benchmark_analysis.ipynb` — loads
all `backend/benchmark/results/*.json` files and produces metric distributions, failure
taxonomy bar charts, and a styled per-test table.

### Prerequisites

```bash
# Activate the virtual environment (required)
source .venv/bin/activate

# Optional — enables SSIM metric
pip install scikit-image

# Optional — enables all visualisations
pip install matplotlib
```

GPU (CUDA) is used automatically for BiRefNet and LoFTR if available; both fall
back to CPU otherwise.

### Running the Benchmark

```bash
# From the repository root, with the venv active:
python -m backend.benchmark.bench_anime_stitch   # or: just asp-benchmark
```

The script processes every `data/asp_test*` directory in natural sort order.
Each dataset takes roughly 1–5 minutes depending on GPU availability and the
number of source frames.

To run a single dataset during development, edit the `__main__` block:

```python
# backend/benchmark/bench_anime_stitch.py — bottom of file
datasets = sorted(glob.glob(os.path.join(base_dir, "asp_test1")))  # pin to test1
```

### Output Directory Layout

```
data/
├── output/                              # Central flat directory
│   ├── asp_testN_anime_stitch.png       # ASP final panorama
│   ├── asp_testN_simple_stitch.png      # OpenCV SCANS baseline
│   └── benchmark_report.md             # ← Full report (generated here)
│
└── asp_testN/
    └── output/
        ├── panorama.png                 # Per-dataset ASP output
        ├── simple_stitch.png            # Per-dataset simple stitch
        ├── plots/                       # Per-dataset visualisations
        │   ├── canvas_frame_placement.png
        │   ├── translation_vectors.png
        │   ├── overlap_map.png
        │   ├── gains.png
        │   ├── asp_seam_heatmap.png
        │   ├── simple_seam_heatmap.png
        │   ├── asp_3d_surface.png
        │   ├── simple_3d_surface.png
        │   ├── temporal_render_3d.png
        │   ├── metrics_comparison.png
        │   └── mask_overlay_frame0N.png
        └── panorama_stages/             # Intermediate stage images
            ├── stage02_normalised_frame0N.png
            ├── stage03_basic_corrected_frame0N.png
            ├── stage04_bgmask_frame0N.png
            ├── stage08_canvas_info.json
            ├── stage09_temporal_render.png
            └── stage11_fg_composite.png
```

### CV Metrics

The following metrics are computed for every final output image and included
in `benchmark_report.md`.

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| **Sharpness** | Variance of Laplacian (`cv2.Laplacian`) | Higher = sharper edges. Low values indicate blur from over-blending or misalignment. |
| **Coverage** | Fraction of pixels with any channel > 8 | Lower = heavy black-border crop or a severely malformed output. Values below 70% signal a structural failure. |
| **Seam Gradient** | Mean absolute Sobel-Y gradient across seam rows ±5 px | Higher = abrupt brightness transitions at seam locations. A well-blended stitch should score close to the global image mean. |
| **Color Entropy** | Shannon entropy of the luma histogram | Lower = washed-out or globally dimmed image. Very high values may indicate colourful noise/artifacts. |
| **Ghosting Score** | Mean absolute value of 2nd-order vertical gradient (Sobel-Y applied twice) | Higher = double-edge bands, which are the computational signature of ghosting artifacts caused by insufficient temporal overlap. |
| **SSIM** | Structural Similarity Index between ASP and Simple outputs (skimage) | Measures perceptual similarity between the two pipelines. Low SSIM + high ghosting in ASP = clear regression vs baseline. |
| **PSNR** | Peak Signal-to-Noise Ratio (dB) between ASP and Simple | A sanity-check complement to SSIM; less perceptually meaningful for stylised content but useful for detecting catastrophic failures (< 10 dB). |

The automated **verdict** field in the report is computed from a weighted score:

```
score = sharpness × 0.4 + coverage × 100 × 0.3 − ghosting × 0.2 − seam_gradient × 0.1
```

`asp_better` / `simple_better` / `comparable` is assigned when one score exceeds
the other by > 10%.

### Visualisation Tools

All plots are saved as PNG files inside `data/asp_testN/output/plots/` and
embedded in the report with relative paths (so the report renders correctly when
opened from `data/output/`).

#### 2-D Visualisations

| File | What it shows |
|------|---------------|
| `canvas_frame_placement.png` | Rectangles for every source frame positioned on the final canvas, coloured by frame index (plasma palette). Reveals frame ordering, gaps, and overlap zones at a glance. |
| `translation_vectors.png` | tx and ty translation per frame as separate line plots. A uniform staircase = clean pan; a flat or reversed segment = alignment failure. |
| `overlap_map.png` | Heatmap counting how many frames contribute to each canvas pixel. The temporal median needs ≥ 3 overlapping frames to suppress foreground occlusion; bright yellow zones indicate high overlap (good), dark red zones indicate sparse coverage (ghosting risk). |
| `gains.png` | Two bar charts: raw background luminance per frame (left) and the scalar gain multiplier applied (right). Gains clipped to [0.88, 1.14]. Large deviations from 1.0 on many frames indicate scene-wide exposure drift that the current correction may not fully compensate. |
| `asp_seam_heatmap.png` / `simple_seam_heatmap.png` | Gradient-magnitude heatmap of the final output image, using the `inferno` colourmap. Bright horizontal bands at seam rows indicate abrupt exposure transitions; diffuse brightness indicates smooth blending. |
| `mask_overlay_frame0N.png` | First three source frames with BiRefNet foreground regions highlighted in red. Useful for checking over-dilation (too much red erodes background reference pixels used by the matcher). |
| `metrics_comparison.png` | Side-by-side normalised bar chart comparing all five primary metrics for ASP vs Simple. Raw values annotated above each bar. |

#### 3-D Visualisations

| File | What it shows |
|------|---------------|
| `asp_3d_surface.png` | 3-D surface plot of the ASP output's luma channel (downsampled, Gaussian-smoothed). Exposure ridges at seam rows appear as sharp vertical steps; a perfectly blended stitch is a smooth surface. |
| `simple_3d_surface.png` | Same for the OpenCV simple stitch. Useful as a reference: the simple stitch typically has lower-frequency exposure variation but more pronounced blurring at seams. |
| `temporal_render_3d.png` | 3-D surface of the Stage 9 temporal render (before foreground compositing). Comparing this with the final ASP surface isolates artifacts introduced by the compositing step. |

### The Markdown Report

`data/output/benchmark_report.md` is designed to be read in any Markdown viewer
(GitHub, Obsidian, VS Code preview) with images rendering inline.

#### Structure

1. **YAML front matter** — report version, date, dataset count.
2. **Global summary table** — one row per test: sizes, coverage, ghosting, SSIM, verdict, fallback flag.
3. **Failure mode counts** — automated tally of detected issue categories across all ASP outputs.
4. **Per-test sections** — for each `asp_testN`:
   - Final outputs side by side
   - CV metrics table
   - Alignment health YAML block
   - Photometric correction summary
   - All visualisation images (2-D and 3-D)
   - Stage intermediate outputs (normalised frames, masks, temporal render, composite)
   - Automated analysis paragraph and issue list
   - `<!-- FEEDBACK … /FEEDBACK -->` block
5. **Global Feedback section** — a single `<!-- GLOBAL_FEEDBACK … /GLOBAL_FEEDBACK -->` block.
6. **Appendix** — full raw metrics as a JSON code block.

#### Reviewing and Marking Feedback

Each per-test section ends with a structured feedback block that is both
human-readable and machine-parseable:

```markdown
<!-- FEEDBACK
status: pending
asp_issues:
  - high_ghosting: score=18.3 (double-edges detected)
  - seam_discontinuity: gradient=22.1 (abrupt transitions)
simple_issues:
  - none_detected
verdict: "simple_better"
human_notes: |
  (Edit this section — confirm, correct, or extend the CV analysis above)
/FEEDBACK -->
```

**To review a test:**

1. Open `data/output/benchmark_report.md` in your Markdown viewer.
2. Look at the side-by-side images and the automated analysis.
3. Edit the `<!-- FEEDBACK … /FEEDBACK -->` block directly in the raw file:
   - Set `status:` to one of: `pending` · `correct` · `incomplete` · `incorrect`
   - Correct or extend `asp_issues:` / `simple_issues:` with your own observations
   - Write free-form notes in `human_notes:`

**Example of a completed block:**

```markdown
<!-- FEEDBACK
status: correct
asp_issues:
  - high_ghosting: score=18.3 — confirmed, clearly visible double-edge on the arm
  - seam_discontinuity: gradient=22.1 — confirmed, bright band between frames 3-4
simple_issues:
  - none_detected
verdict: "simple_better"
human_notes: |
  The ghosting here is caused by insufficient overlap depth (frames 5-6 cover the
  arm region only once). The 3D surface shows a sharp ridge at y≈420.
  Potential fix: increase frame density in this zone, or switch to Laplacian blend
  when overlap_count < 3 in any region.
/FEEDBACK -->
```

The feedback data is preserved across benchmark re-runs because the benchmark
only **appends** new sections; it does not overwrite existing `status` or
`human_notes` values. Re-running the benchmark regenerates metrics, images, and
the automated `asp_issues` list, but leaves your manual edits intact.

The global section follows the same pattern:

```markdown
<!-- GLOBAL_FEEDBACK
status: pending
overall_asp_rating: null
overall_simple_rating: null
most_common_asp_failure: null
priority_fixes:
  - null
human_notes: |
  (Your analysis here)
/GLOBAL_FEEDBACK -->
```

### Interactive Analysis: Jupyter Notebook

For deep per-stage analysis, use the companion notebook:

```bash
# From repo root with venv active
jupyter notebook notebooks/anime_stitch_pipeline_analysis.ipynb
# or
jupyter lab notebooks/anime_stitch_pipeline_analysis.ipynb
```

**Selecting a dataset:** Change `TEST_ID = N` in the second cell. All subsequent
cells re-run against that dataset automatically.

**Notebook sections:**

| Section | What you can do |
|---------|-----------------|
| Stages 1–2 (load & normalise) | Inspect trim deltas per frame; check for over-trim in dark scenes |
| Stage 3 (BaSiC) | Toggle BaSiC and compare sharpness before/after |
| Stage 4 (BiRefNet masks) | Visualise mask overlays; check background coverage % — below 35% per frame is a matcher risk |
| Stage 4.5 (gains) | Bar charts of raw luminance and applied gains; histogram comparison of most-corrected frame |
| Stage 5 (matching) | Scatter plots of matched keypoints; spread diagnostics (low std_y = collinear matches = unstable affine) |
| Stage 6/7 (bundle-adjust + ECC) | Translation vectors; inter-frame Δty coefficient of variation (> 0.5 = irregular pan or matching errors) |
| Stage 8 (canvas) | Frame-placement 2-D plot; overlap count map |
| Stage 9 (temporal render) | Render output + valid-mask; overlap depth histogram; 3-D surface |
| Stage 10 (FG composite) | Before/after compare; amplified difference image |
| Stage 11 (crop) | Size before/after; seam heatmap + 3-D surface of final output |
| Section 14 (global metrics) | Sharpness and ghosting bar charts for all 22 tests; failure-mode taxonomy with root-cause mapping |
| Section 15 (root causes) | Edge connectivity check; per-seam luminance mismatch table |
| Section 16 (experiments) | Toggleable experiments — see below |

**Experiments (Section 16):**

| Flag | Experiment | Research basis |
|------|-----------|----------------|
| `RUN_HISTOGRAM_MATCH` | LAB-space CDF histogram matching (frame → frame 0) before rendering | Region-stratified colour transfer; Brown–Lowe gain compensation |
| `RUN_LAPLACIAN_BLEND` | `_render_laplacian` instead of `_render_median` | Burt–Adelson multi-band blending; low-freq blending zone suppresses exposure drift |
| `RUN_AKAZE_MATCHING` | AKAZE keypoints + BFMatcher + estimateAffinePartial2D instead of LoFTR/template | AKAZE nonlinear-diffusion scale-space is more stable on cartoon edges than SIFT DoG |
| `RUN_OVERLAP_PHOTOMETRIC` | Sequential per-channel gain/bias correction in overlap zones (`_compute_sequential_color_gains`) | Brown–Lowe 2007 overlap photometric matching; Overmix temporal correction |

Each experiment renders a side-by-side comparison against the original ASP output
and prints Δghosting and Δsharpness so you can track whether the change helps.

**Saving findings:** Use the **My Notes** Markdown cell at the bottom of the
notebook to record observations, hypotheses, and next-step proposals for each
test. These notes survive kernel restarts because they are stored as cell source.

### Interpreting Alignment Health

The `stage08_canvas_info.json` and the alignment health block in the report each
contain:

| Field | Healthy range | Meaning if out of range |
|-------|--------------|-------------------------|
| `valid` | `true` | `false` → SCANS fallback used; ASP result is identical to Simple |
| `spacing_ratio` | < 3.0 | Frame spacing is uneven; one gap is > 3× larger than the median — likely a missed match |
| `min_gap_px` | ≥ 50 px | Frames are nearly co-located — the canvas will have severe duplication |
| `max_rotation` | < 0.1 | Rotation component in the affine exceeds tolerance — ECC or matching introduced spurious rotation |
| `max_scale_dev` | < 0.1 | Scale component deviates from 1.0 — zooming or lens distortion not accounted for |
| `used_scans_fallback` | `false` | `true` → all ASP stages were bypassed |

### Troubleshooting

**`simple_stitch.png` is not generated**

The benchmark always regenerates it at Step 0. If it still fails, check the
console for `[Simple stitch] FAILED:`. The most common cause is an OpenCV SCANS
error (`status != 0`) on datasets where frames are too dissimilar for the
built-in stitcher — this is expected for degenerate test cases.

**`BiRefNet failed … using None masks`**

BiRefNet requires a CUDA-capable GPU with ≥ 4 GB VRAM, or will run (slowly)
on CPU if the wrapper supports it. Without masks, the matcher uses the full frame
including any foreground character, which degrades matching quality. The benchmark
continues with `None` masks rather than aborting.

**`LoFTR not available`**

LoFTR requires `kornia` and a matching weights file. Without it, the benchmark
falls back to template matching and phase correlation. The report will show
`method: template` or `method: phase_corr` in the edge list.

**Visualisations not saved (`_MPL_OK = False`)**

Install `matplotlib`: `pip install matplotlib`. The benchmark continues without
plots but the report will reference missing image files.

**SSIM column shows `—`**

Install `scikit-image`: `pip install scikit-image`.

**Report images do not render in Obsidian / GitHub**

The report uses relative paths from `data/output/`. Open or preview the file
from that directory. In VS Code, use the built-in Markdown preview (`Ctrl+Shift+V`)
with the workspace root set to `data/output/`, or use the absolute path override:

```bash
# Re-generate with absolute paths (edit generate_report() if needed)
REPORT_ABS_PATHS=1 python -m backend.benchmark.bench_anime_stitch   # or: just asp-benchmark
```

## Registering a New Benchmark with CI

### Python benchmark

1. Create `backend/benchmark/bench_<name>.py` following the `BenchmarkRunner` / `@measure_memory` pattern.
2. Import and call it from `benchmark/run_all.py`:

   ```python
   from benchmark.bench_<name> import runner as <name>_runner
   ALL_RUNNERS.append(<name>_runner)
   ```

3. The existing `.github/workflows/benchmark.yml` discovers all runners via `run_all.py` automatically.
   No workflow changes needed for Python benchmarks.

### C++ base benchmark

1. Add a `TEST_CASE` with `[benchmark]` tag in `base/tests/` (see §above).
2. In `.github/workflows/benchmark.yml`, add a step:

   ```yaml
   - name: Run C++ base benchmarks
     run: just test-base-cpp
   ```

4. Optionally store the criterion HTML reports as a workflow artifact:

   ```yaml
   - uses: actions/upload-artifact@v4
     with:
       name: criterion-<name>
       path: base/target/criterion/
   ```

### Frontend math benchmark

Frontend math functions are covered by TypeDoc type-checking (see `docs.yml` Job 4).
For performance micro-benchmarks of `stats.ts` / `distance.ts`:

```ts
// frontend/src/math/__tests__/bench_stats.test.ts
import { mean } from '../stats';
describe('perf: mean', () => {
  it('10k numbers in < 1ms', () => {
    const xs = Array.from({ length: 10000 }, (_, i) => i);
    const t0 = performance.now();
    mean(xs);
    expect(performance.now() - t0).toBeLessThan(1);
  });
});
```

Run with `npm test` from `frontend/`. Jest is already configured in `package.json`.

### Connecting to the ASP RLHF reward model (§1.10A)

The `StitchRewardModel.predict()` path in `bench_anime_stitch.py` emits `rlhf_score`
and `rlhf_flagged` for each test. Once human feedback is collected and the model is
trained (the current weights are random), RLHF scores should track alongside the CV
metrics above. A benchmark is considered **RLHF-flagged** when `rlhf_score > 0.6`
(configurable via `ASP_RLHF_FLAG_THRESHOLD`).

---

## License

Same as parent project (see root LICENSE file).
