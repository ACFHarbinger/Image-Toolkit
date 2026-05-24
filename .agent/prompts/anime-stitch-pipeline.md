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
| `test1/` | 8  | good (1.1×) | Subtle brightness gradient at B0/B1 — mostly fixed |
| `test2/` | 10 | broken      | Wrong frame ordering (wrong-direction matches) |
| `test3/` | 11 | unknown     | Stage 9 ghosting + hard seam |
| `test4/` | 7  | good (1.0×) | `_crop_to_valid` overcropping −393px |
| `test5/` | 6  | degraded (1.3×) | Frame spacing compressed → Stage 9 ghosting |
| `test6/` | 9  | good (1.4×) | **Clean output — positive baseline** |
| `test7/` | 14 | broken (4.7×) | Non-monotonic order + diagonal scroll (tx) unsupported |
| `test8/` | 11 | broken (5.9×) | Catastrophic frame clustering (16–21px gaps) |
| `test9/` | 9  | broken (11.8×) | Severe frame clustering → −1609px height loss |
| `test10/` | 14 | degraded (3.2×) | Uneven gaps; ss uses full perspective model |
| `test11/` | 7  | **good (1.1×)** | **Clean — positive baseline** |
| `test12/` | 6  | borderline (2.9×) | Visually clean despite ratio |
| `test13/` | 9  | degraded (2.3×) | Mild seam at large-gap boundary |
| `test14/` | 7  | **good (1.1×)** | **Clean — positive baseline** |
| `test15/` | 7  | **good (1.1×)** | **Clean — positive baseline** |
| `test16/` | 10 | broken (6.1×) | Frame clustering (min_gap=12px) |
| `test17/` | 7  | borderline (1.5×) | Mild seam at one boundary |
| `test18/` | 6  | anomalous (1.1×) | Good ty/tx but bad Stage 9 — affine rotation issue |
| `test19/` | 10 | **good (1.1×)** | **Clean — positive baseline** |
| `test20/` | 7  | broken (H) | Pure horizontal scroll — unsupported scroll axis |
| `test21/` | 10 | partial (1.0×) | 3 co-located duplicate frames → top-strip ghosting |
| `test22/` | 11 | **good (1.0×)** | **Clean — positive baseline** |

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

# test1/ dataset — 8 frames, all stages pre-computed
python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/run_pipeline_v2.py
# Output: /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test1/output/panorama_v2.png

# test3/ dataset — 11 frames (adapt run_pipeline_v2.py, change STAGE_DIR + frame count)
# Stage outputs: /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test3/output/panorama_stages/

# test2/ dataset — 10 frames (alignment broken, fix bundle_adjust first)
# Stage outputs: /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test2/output/panorama_stages/

# Full re-build from source frames (runs all GPU stages — slow)
python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/build_stages.py
```

### Constraints

- NEVER skip MFSR by default in the production pipeline — only skip it in test scripts. The GUI exposes an "enable MFSR" toggle.
- Do NOT add `QPixmap`, Qt, or GUI imports inside any `backend/src/anim/` file.
- Keep all `_composite_foreground` signature unchanged — it is called by the pipeline, the GUI worker, and test scripts.
- Gains applied in `_render_median` and `_composite_foreground` are independent — do not confuse them.

My first task is: [INSERT TASK HERE]
