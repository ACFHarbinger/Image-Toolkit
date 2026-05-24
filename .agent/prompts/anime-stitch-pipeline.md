# Anime Stitch Pipeline — Context Prompt

**Intent:** Initialize a high-context session for working on `AnimeStitchPipeline`. Load all architectural knowledge, known bugs, and test infrastructure before making any changes.

---

## The Prompt

You are an expert computer vision engineer working on the `AnimeStitchPipeline` in Image-Toolkit. This is a 13-stage research pipeline that stitches sequential anime/manga frame captures into vertical panoramas.

### Architecture in one sentence

Frames → BaSiC photometric correction → BiRefNet foreground masking → LoFTR/TemplateMatch pairwise matching → bundle adjustment → ECC sub-pixel refinement → canvas geometry → temporal median render → (optional MFSR) → hard-partition foreground composite → crop.

### Key source files

| File | Stage | What it does |
|------|-------|-------------|
| `backend/src/anim/pipeline.py` | Orchestrator | Full 13-stage flow; also `_filter_edges` |
| `backend/src/anim/compositing.py` | Stage 11 | Hard-partition composite — **primary source of seam issues** |
| `backend/src/anim/rendering.py` | Stage 9 | Temporal median render with per-pixel gain |
| `backend/src/anim/bundle_adjust.py` | Stage 7 | Global bundle adjustment (LM) |
| `backend/src/anim/matching.py` | Stages 5–6 | Pairwise LoFTR + TemplateMatch |
| `backend/src/anim/canvas.py` | Stage 8 | Canvas geometry, `_compute_canvas`, `_crop_to_valid` |
| `backend/src/anim/masking.py` | Stage 4 | BiRefNet foreground masks |
| `backend/src/anim/ecc.py` | Stage 8 | ECC sub-pixel refinement |
| `backend/src/core/image_merger.py` | Reference | Simple stitch (`_merge_images_scan_stitch`) — the quality target |

### Full architecture reference

Read `docs/ARCHITECTURE.md` — it has complete Mermaid diagrams for both the simple stitch and the 13-stage pipeline with all parameters and branch conditions.

### Research context

Read the relevant reports in `reports/` before proposing algorithmic changes:
- `Anime Image Stitching Pipeline Analysis.md` — analysis of the pipeline's design choices
- `Advanced Methodologies for Flawless Image Stitching in Digital Animation*.md` — multi-scale blending, exposure correction, Laplacian pyramid
- `Anime Screenshot Stitching Improvement Research.md` — comparison of approaches
- `AI_OR Research Assistant for Anime Stitching.md` — automated research notes

### Overmix reference implementation

`Overmix/src/` contains a production C++ image stitching tool. Key files to consult:
- `aligners/RecursiveAligner.cpp` — hierarchical alignment (robust to bad pairwise matches)
- `aligners/AverageAligner.cpp` — average-frame-based alignment
- `comparators/MultiScaleComparator.cpp` — multi-scale matching comparator
- `renders/AverageRender.cpp` — weighted average rendering
- `renders/StatisticsRender.cpp` — median/statistics-based rendering

### Known issue summary

See `.agent/cache/anime_stitch_pipeline_issues.md` for the full diagnostic report. Summary by dataset:

| Dataset | Frames | Alignment | Status |
|---------|--------|-----------|--------|
| `asp_test1/` | 8  | good (1.1×) | Subtle brightness gradient at B0/B1 — mostly fixed |
| `asp_test2/` | 10 | broken      | Wrong frame ordering (wrong-direction matches) |
| `asp_test3/` | 11 | unknown     | Stage 9 ghosting + hard seam |
| `asp_test4/` | 7  | good (1.0×) | `_crop_to_valid` overcropping −393px |
| `asp_test5/` | 6  | degraded (1.3×) | Frame spacing compressed → Stage 9 ghosting |
| `asp_test6/` | 9  | good (1.4×) | **Clean output — positive baseline** |
| `asp_test7/` | 14 | broken (4.7×) | Non-monotonic order + diagonal scroll (tx) unsupported |
| `asp_test8/` | 11 | broken (5.9×) | Catastrophic frame clustering (16–21px gaps) |
| `asp_test9/` | 9  | broken (11.8×) | Severe frame clustering → −1609px height loss |
| `asp_test10/` | 14 | degraded (3.2×) | Uneven gaps; ss uses full perspective model |
| `asp_test11/` | 7  | **good (1.1×)** | **Clean — positive baseline** |
| `asp_test12/` | 6  | borderline (2.9×) | Visually clean despite ratio |
| `asp_test13/` | 9  | degraded (2.3×) | Mild seam at large-gap boundary |
| `asp_test14/` | 7  | **good (1.1×)** | **Clean — positive baseline** |
| `asp_test15/` | 7  | **good (1.1×)** | **Clean — positive baseline** |
| `asp_test16/` | 10 | broken (6.1×) | Frame clustering (min_gap=12px) |
| `asp_test17/` | 7  | borderline (1.5×) | Mild seam at one boundary |
| `asp_test18/` | 6  | anomalous (1.1×) | Good ty/tx but bad Stage 9 — affine rotation issue |
| `asp_test19/` | 10 | **good (1.1×)** | **Clean — positive baseline** |
| `asp_test20/` | 7  | broken (H) | Pure horizontal scroll — unsupported scroll axis |
| `asp_test21/` | 10 | partial (1.0×) | 3 co-located duplicate frames → top-strip ghosting |
| `asp_test22/` | 11 | **good (1.0×)** | **Clean — positive baseline** |

**Key insights:**
- Stage 9 ghosting is almost always downstream of bad affines — but test18 is the confirmed exception (good ty/tx, bad rotation components).
- Seven positive baselines confirm the pipeline works well when alignment is correct: test4, test6, test11, test14, test15, test19, test22.
- Two new unsupported scroll modes: horizontal (test20: ty≈0, tx=0–1857px) and pure diagonal (test7).
- Always check `min_gap` in addition to `ratio` — a ratio of 1.0× with min_gap=0 still indicates co-located frames (test21).

### Quality target

The simple stitch (`_merge_images_scan_stitch` in `backend/src/core/image_merger.py`) produces seam-free results with natural brightness but has ghosting and blur from linear alpha blending. The pipeline output must match or exceed this: no horizontal seam bands, no brightness discontinuities, sharp character edges.

### Fast iteration loop

Do NOT re-run GPU-heavy stages (BiRefNet, LoFTR) when iterating on compositing. Use the pre-computed stage outputs:

```bash
source .venv/bin/activate

# asp_test1/ dataset — 8 frames, all stages pre-computed
python3 archive/run_pipeline_v2.py
# Output: data/asp_test1/output/panorama_v2.png

# asp_test3/ dataset — 11 frames (adapt run_pipeline_v2.py, change STAGE_DIR + frame count)
# Stage outputs: data/asp_test3/output/panorama_stages/

# asp_test2/ dataset — 10 frames (alignment broken, fix bundle_adjust first)
# Stage outputs: data/asp_test2/output/panorama_stages/

# Full re-build from source frames (runs all GPU stages — slow)
python3 archive/build_stages.py
```

### Unit test suite

A comprehensive test suite covers all pipeline issue categories without GPU. Run it after any change to `backend/src/anim/`:

```bash
source .venv/bin/activate
pytest backend/test/anim/ -q          # all 105 tests (~7s)
pytest backend/test/anim/ -k "canvas" # run a specific module
```

Test files and their coverage:

| File | Covers |
|------|--------|
| `test_bundle_adjust.py` | Stage 7 LM solver — frame clustering, anchor frame, outlier edges |
| `test_filter_edges.py`  | `_filter_edges` — wrong-sign, gross outliers, geometric consistency |
| `test_canvas.py`        | `_compute_canvas`, `_crop_to_valid` — overcrop, horizontal scroll |
| `test_affine_validation.py` | `_validate_affines` spec — ratio, min_gap, rotation, scale |
| `test_compositing.py`   | `_diff_to_feather`, `_global_gain_normalize`, `_composite_foreground` |
| `test_rendering.py`     | `_render_median`, `_render_first`, ghosting detection, baselines |

The `conftest.py` at `backend/test/conftest.py` provides shared helpers: `make_frame`, `make_edge`, `make_translation_affine`, `make_rotation_affine`, `compute_ty_gaps`.

### Constraints

- NEVER skip MFSR by default in the production pipeline — only skip it in test scripts. The GUI exposes an "enable MFSR" toggle.
- Do NOT add `QPixmap`, Qt, or GUI imports inside any `backend/src/anim/` file.
- Keep all `_composite_foreground` signature unchanged — it is called by the pipeline, the GUI worker, and test scripts.
- Gains applied in `_render_median` and `_composite_foreground` are independent — do not confuse them.

My first task is: read the anime pipeline issues report file in `.agent/cache/anime_stitch_pipeline_issues.md`, analyze the pipeline code in  `backend/src/anim` and tests in `backend/test/anim`, understand the current issues and the architectural design choices, and come up with a plan to diagnose the root cause of the issues and improve the pipeline.
