---
description: Step-by-step workflow for iterating on AnimeStitchPipeline output quality — diagnosing failures, fixing them, and verifying improvements across all test datasets.
---

You are improving `AnimeStitchPipeline` output quality. Work through the phases below in order. Each phase has an explicit success criterion before proceeding to the next.

---

## Phase 0 — Orient

**Read first, change nothing.**

1. Read `.agent/cache/anime_stitch_pipeline_issues.md` — full diagnostic report from prior sessions
2. Read `docs/ARCHITECTURE.md` — complete pipeline stage diagram
3. Read `backend/src/anim/compositing.py` — the primary file for seam issues
4. Read `backend/src/anim/rendering.py` — Stage 9 temporal render
5. Read `backend/src/anim/bundle_adjust.py` — alignment, currently broken for test2/, test5/, test7/, test8/, test9/

Check the current state of all three test datasets:

```bash
source .venv/bin/activate

# Run the fast compositing test (test1/ dataset, ~30s, no GPU)
python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/run_pipeline_v2.py 2>&1 | tail -30
```

View the output image and compare to the simple stitch reference:
- **Output:** `/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test1/output/panorama_v2.png`
- **Reference:** `/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test1/output/simple_stitch.png`
- **Failure baseline:** `/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test1/output/panorama.png` (original broken output)

Quick affine health check across all datasets before changing any code:
```bash
python3 -c "
import json, numpy as np, glob, os
BASE = '/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline'
for d in sorted(glob.glob(f'{BASE}/test*/output/panorama_stages/stage08_canvas_info.json')):
    with open(d) as f: data = json.load(f)
    aff = data['affines_final']
    tys = sorted(aff[i][1][2] for i in range(len(aff)))
    gaps = np.diff(tys)
    ratio = gaps.max()/np.median(gaps) if len(gaps) else 0
    tag = 'OK' if ratio < 3 else 'BROKEN'
    print(f'{tag} {os.path.dirname(os.path.dirname(os.path.dirname(d))).split(\"/\")[-1]} N={len(aff)} ratio={ratio:.1f}x gaps_min={gaps.min():.0f}')
"
```

**Success criterion:** You can articulate the specific visible artifact in the current output and map it to a root cause in the code before writing a single line of code. Expected: test1/test4/test6 show `OK`, others show `BROKEN`.

---

## Phase 1 — Fix Alignment (`test2/` dataset)

**Priority: highest.** The `test2/` pipeline output is completely garbled because bundle adjustment produced wrong frame ordering.

### 1.1 Diagnose the bad affines

```bash
python3 -c "
import json, numpy as np
with open('/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test2/output/panorama_stages/stage08_canvas_info.json') as f:
    d = json.load(f)
aff = d['affines_final']
tys = sorted([(i, aff[i][1][2]) for i in range(len(aff))], key=lambda x: x[1])
for rank, (fi, ty) in enumerate(tys):
    print(f'rank{rank}: frame{fi} ty={ty:.1f}')
gaps = np.diff([ty for _, ty in tys])
print('Gaps:', np.round(gaps, 1))
print('Max/median ratio:', f'{gaps.max()/np.median(gaps):.1f}x')
"
```

Expected healthy output: 10 frames with `ty` values ~300–400px apart. Actual broken output: frames clustered at the same position, large unexplained gaps, non-monotonic sequence.

### 1.2 Add affine validation after bundle adjust

In `backend/src/anim/canvas.py` or `pipeline.py`, add a post-bundle-adjust sanity check:

```python
def _validate_affines(affines, N, expected_step_min=50, max_gap_ratio=5.0):
    tys = sorted(aff[1, 2] for aff in affines)
    gaps = np.diff(tys)
    if len(gaps) == 0:
        return False
    median_gap = float(np.median(gaps))
    if median_gap < expected_step_min:
        return False
    if gaps.max() > max_gap_ratio * median_gap:
        return False
    return True
```

If validation fails, log the failure and fall back to `_merge_images_scan_stitch`.

### 1.3 Add outlier rejection to bundle_adjust

In `backend/src/anim/bundle_adjust.py`, after the initial LM solve, add residual-based edge pruning:

```python
# Compute residuals for each edge
residuals = compute_edge_residuals(edges, affines)
threshold = 3.0 * np.median(residuals)
clean_edges = [e for e, r in zip(edges, residuals) if r <= threshold]
if len(clean_edges) >= 2:
    affines = solve_bundle(clean_edges, N)  # re-solve with clean edges
```

### 1.4 Re-run full pipeline for `test2/`

```bash
python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/build_stages.py  # adapt for test2/ path
```

**Success criterion:** `stage08_canvas_info.json` for `test2/` shows monotonically increasing `ty` values with max/median gap ratio < 3×.

---

## Phase 1.5 — Fix Frame Clustering (`test8/`, `test9/`, `test5/`)

These datasets fail because LoFTR returns near-zero dy matches (< 50px) for pairs that should have 200–400px offsets. Multiple frames land at essentially the same canvas position, causing catastrophic Stage 9 ghosting.

### 1.5.1 Confirm the clustering pattern

```bash
python3 -c "
import json, numpy as np
for ds in ['test5', 'test8', 'test9']:
    path = f'/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/{ds}/output/panorama_stages/stage08_canvas_info.json'
    with open(path) as f:
        d = json.load(f)
    aff = d['affines_final']
    tys = sorted(aff[i][1][2] for i in range(len(aff)))
    gaps = np.diff(tys)
    print(f'{ds}: gaps_under_50={list(gaps[gaps<50].astype(int))} total_gaps={len(gaps)}')
"
```

### 1.5.2 Add near-zero dy rejection to `_filter_edges` in `pipeline.py`

After the velocity consistency filter in `_filter_edges`:
```python
MIN_EXPECTED_STEP = 50  # px — near-zero dy matches are wrong-direction or repeated-content
edges = [e for e in edges if abs(e['dy']) >= MIN_EXPECTED_STEP]
```

### 1.5.3 Rebuild and verify

Re-run the full pipeline for test8, test9, test5 (requires GPU). Verify the affines improve.

**Success criterion:** All three datasets show max/median gap ratio < 3× after rebuild.

---

## Phase 2 — Fix Stage 9 Ghosting (`test3/` dataset)

**The `test3/` dataset has 11 frames.** The temporal render shows heavy ghosting and partial frame transparency.

### 2.1 Verify source frame quality

```bash
# Check stage02 and stage03 frames are valid
python3 -c "
import cv2, glob
for p in sorted(glob.glob('/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test3/output/panorama_stages/stage03_basic_corrected_frame*.png')):
    img = cv2.imread(p)
    if img is None: print('MISSING:', p)
    elif img.mean() < 10: print('DARK:', p, img.mean())
    else: print('OK:', p.split('/')[-1], img.shape, f'mean={img.mean():.0f}')
"
```

### 2.2 Verify BiRefNet masks

```bash
python3 -c "
import cv2, glob, numpy as np
for p in sorted(glob.glob('/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test3/output/panorama_stages/stage04_bgmask_frame*.png')):
    m = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    if m is None: print('MISSING:', p)
    else:
        bg_frac = (m > 127).mean()
        print(p.split('/')[-1], f'bg_fraction={bg_frac:.2%}')
"
```

A mask with `bg_fraction=0%` (all foreground) or `bg_fraction=100%` (all background) is broken.

### 2.3 Verify affines for test3/

```bash
python3 -c "
import json, numpy as np
with open('/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test3/output/panorama_stages/stage08_canvas_info.json') as f:
    d = json.load(f)
aff = d['affines_final']
tys = [aff[i][1][2] for i in range(len(aff))]
print('ty values:', [f'{t:.0f}' for t in tys])
print('gaps:', [f'{tys[i+1]-tys[i]:.0f}' for i in range(len(tys)-1)])
"
```

### 2.4 Isolate render vs. composite

Run Stage 9 in isolation to check whether ghosting is from the render or from the composite:

```python
# Adapt run_pipeline_v2.py for test3/:
STAGE_DIR = '/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/test3/output/panorama_stages'
# Change range(8) to range(11)
# Only run _render_median and save stage09 output; skip _composite_foreground
```

If stage09 is already ghosted, the issue is in `_render_median`. If stage09 is clean and the ghosting appears in stage11, the issue is in `_composite_foreground`.

### 2.5 Fix rendering

In `backend/src/anim/rendering.py`, check:
- The `_render_median` function correctly identifies strip ownership for 11 frames
- The gain clamp `(0.88, 1.12)` is not over-darkening certain strips
- The median accumulation loop handles the larger number of overlapping frames correctly

**Success criterion:** `stage09_temporal_render.png` for `test3/` shows a clean (no ghosting) rough composite before Stage 11.

---

## Phase 3 — Improve Stage 11 Compositing (`test1/` dataset)

**The `test1/` dataset has most bugs fixed.** A subtle brightness gradient remains at the upper-middle area (B0/B1 boundary region, natural scene content difference). Use this dataset for compositing refinement.

### 3.1 Establish baseline

```bash
python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/run_pipeline_v2.py 2>&1
# View output vs. reference
```

Note the current state of:
- LS gains (should all be near 1.0 with tight clamp)
- Feather sizes (B0/B1 should have wide, overlapping feathers)
- Per-zone gains (should all be 1.000)

### 3.2 Evaluate remaining band

Look at the background (curtain) in the upper-middle area of the output. If a brightness step is visible:

1. Identify which boundary it corresponds to (B0 at y≈988, B1 at y≈1157)
2. Check whether it's a genuine scene brightness step or a stitching artifact by comparing with the simple stitch reference — if the simple stitch shows the same gradient, it's natural
3. If it's a genuine artifact: check whether the hard-partition assigns rows above the feather zone (y < 738 for B0=250px feather) to F7 with a different brightness than F5 below the zone

### 3.3 Try Laplacian pyramid blend (if gradient remains unacceptable)

Replace the cosine alpha blend in the feather zone with a Laplacian pyramid blend as described in `reports/Advanced Methodologies for Flawless Image Stitching*.md`. This distributes brightness steps across multiple frequency bands:

```python
def _laplacian_blend(fa, fb, alpha, levels=4):
    """Blend two image strips using Laplacian pyramid."""
    # Build Gaussian pyramids
    gp_a = _gaussian_pyramid(fa, levels)
    gp_b = _gaussian_pyramid(fb, levels)
    gp_mask = _gaussian_pyramid(alpha, levels)
    # Build Laplacian pyramids
    lp_a = _laplacian_pyramid(gp_a)
    lp_b = _laplacian_pyramid(gp_b)
    # Blend at each level
    blended = [m * la + (1 - m) * lb for la, lb, m in zip(lp_a, lp_b, gp_mask)]
    return _reconstruct_from_laplacian(blended)
```

Reference: `Overmix/src/renders/AverageRender.cpp` for the weighted average framework.

### 3.4 Verify no regressions

After any compositing change, check all boundaries in the output, not just the one being fixed:

```bash
# Check log for all boundaries
python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/run_pipeline_v2.py 2>&1 | grep -E "Boundary|Feathers|DP path"
```

**Success criterion:** The output image shows no visible horizontal bands or brightness discontinuities that are not present in the simple stitch reference. Character edges are sharp (no ghosting).

---

## Phase 4 — Validate All Datasets

Run the affine health check first to see which datasets are now healthy:

```bash
python3 -c "
import json, numpy as np, glob, os
BASE = '/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline'
for d in sorted(glob.glob(f'{BASE}/test*/output/panorama_stages/stage08_canvas_info.json')):
    with open(d) as f: data = json.load(f)
    aff = data['affines_final']
    tys = sorted(aff[i][1][2] for i in range(len(aff)))
    gaps = np.diff(tys)
    ratio = gaps.max()/np.median(gaps) if len(gaps) else 0
    tag = 'OK' if ratio < 3 else 'BROKEN'
    name = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(d))))
    print(f'{tag} {name} N={len(aff)} ratio={ratio:.1f}x min_gap={gaps.min():.0f}')
"
```

Then run compositing on each dataset that shows `OK` alignment:

```bash
# test1/ — fast compositing test (pre-computed stages)
python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/run_pipeline_v2.py

# test4/, test6/ — adapt run_pipeline_v2.py (change STAGE_DIR and frame count)
# test3/ — adapt run_pipeline_v2.py for 11 frames
# test2/, test5/, test7/, test8/, test9/ — only after Phase 1/1.5 alignment fixes + rebuild
```

Expected results by dataset:
| Dataset | Expected after fixes |
|---------|---------------------|
| test1 | Clean except subtle brightness gradient at B0/B1 |
| test4 | Clean; verify height is not over-cropped |
| test6, test11, test14, test15, test19, test22 | Clean (positive baselines — should already work) |
| test2, test5, test8, test9, test16 | Clean after alignment fix (Priority 1/1.5) |
| test13, test17 | Improved after RANSAC outlier rejection |
| test18 | Requires affine rotation validation (Priority 3b) |
| test20 | Requires horizontal scroll detection (Priority 3c) |
| test21 | Requires co-located frame deduplication |
| test7, test10 | Diagonal scroll / perspective distortion — separate architectural work |

**Success criterion for all datasets:**
- No hard horizontal seams or brightness bands
- Character edges sharp (no ghosting/blur from averaging)
- Natural scene brightness gradient preserved (not artificially flattened)
- Panorama height comparable to simple stitch (within ~10%)
- test6 output must match or exceed its simple stitch quality

---

## Phase 5 — Integration Test

Run the full 13-stage pipeline end-to-end on `test1/` and `test6/` to verify nothing in the early stages breaks with the compositing changes:

```bash
python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/build_stages.py
```

Check that:
- Stage outputs (`stage02_normalised_frame*.png`, `stage04_bgmask_frame*.png`, `stage09_temporal_render.png`) look the same as before
- Final output matches the quality achieved in the fast iteration loop
- `test6/` output remains clean (regression check)

---

## Appendix: Key Commands

```bash
# Fast compositing iteration (test1/, ~30s)
source .venv/bin/activate && python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/run_pipeline_v2.py

# Full pipeline rebuild from source frames (test1/, ~10–30min with GPU)
source .venv/bin/activate && python3 /home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/build_stages.py

# Check affine quality for any dataset
python3 -c "
import json, numpy as np, sys
with open(sys.argv[1]) as f: d = json.load(f)
aff = d['affines_final']
tys = sorted([(i, aff[i][1][2]) for i in range(len(aff))], key=lambda x: x[1])
[print(f'rank{r}: frame{fi} ty={ty:.0f}') for r, (fi, ty) in enumerate(tys)]
gaps = np.diff([ty for _, ty in tys])
print('Gaps:', np.round(gaps).astype(int), 'max/median:', f'{gaps.max()/np.median(gaps):.1f}x')
" /path/to/stage08_canvas_info.json

# Grep compositing constants
grep -n "_FEATHER\|_GAIN_CLAMP\|_SEAM" backend/src/anim/compositing.py | head -20

# Run linting after changes
source .venv/bin/activate && ruff check backend/src/anim/compositing.py
```

## Appendix: Test Dataset Paths

| Dataset | Source frames | Stage outputs | Simple stitch | Pipeline output |
|---------|--------------|---------------|---------------|-----------------|
| `test1/` (8 frames)  | `.../test1/*.png`  | `.../test1/output/panorama_stages/`  | `.../test1/output/simple_stitch.png` | `.../test1/output/panorama_v2.png` | Partial fix — subtle brightness gradient |
| `test2/` (10 frames) | `.../test2/*.png`  | `.../test2/output/panorama_stages/`  | `.../test2/output/simple_stitch.png` | `.../test2/output/panorama.png`    | Broken alignment (wrong direction) |
| `test3/` (11 frames) | `.../test3/*.png`  | `.../test3/output/panorama_stages/`  | `.../test3/output/simple_stitch.png` | `.../test3/output/panorama.png`    | Stage 9 ghosting + hard seam |
| `test4/` (7 frames)  | `.../test4/*.png`  | `.../test4/output/panorama_stages/`  | `.../test4/output/simple_stitch.png` | `.../test4/output/panorama.png`    | Good alignment; −393px overcrop |
| `test5/` (6 frames)  | `.../test5/*.png`  | `.../test5/output/panorama_stages/`  | `.../test5/output/simple_stitch.png` | `.../test5/output/panorama.png`    | Degraded alignment → Stage 9 ghosting |
| `test6/` (9 frames)  | `.../test6/*.png`  | `.../test6/output/panorama_stages/`  | `.../test6/output/simple_stitch.png` | `.../test6/output/panorama.png`    | **Positive baseline — mostly clean** |
| `test7/` (14 frames) | `.../test7/*.png`  | `.../test7/output/panorama_stages/`  | `.../test7/output/simple_stitch.png` | `.../test7/output/panorama.png`    | Broken alignment + diagonal scroll |
| `test8/` (11 frames) | `.../test8/*.png`  | `.../test8/output/panorama_stages/`  | `.../test8/output/simple_stitch.png` | `.../test8/output/panorama.png`    | Catastrophic frame clustering |
| `test9/` (9 frames)  | `.../test9/*.png`  | `.../test9/output/panorama_stages/`  | `.../test9/output/simple_stitch.png` | `.../test9/output/panorama.png`    | Frame clustering → −1609px height loss |
| `test10/` (14 frames) | `.../test10/*.png` | `.../test10/output/panorama_stages/` | `.../test10/output/simple_stitch.png` | `.../test10/output/panorama.png`  | Uneven gaps (3.2×); ss uses perspective model |
| `test11/` (7 frames)  | `.../test11/*.png` | `.../test11/output/panorama_stages/` | `.../test11/output/simple_stitch.png` | `.../test11/output/panorama.png`  | **Clean — positive baseline** |
| `test12/` (6 frames)  | `.../test12/*.png` | `.../test12/output/panorama_stages/` | `.../test12/output/simple_stitch.png` | `.../test12/output/panorama.png`  | Borderline (2.9×); visually clean |
| `test13/` (9 frames)  | `.../test13/*.png` | `.../test13/output/panorama_stages/` | `.../test13/output/simple_stitch.png` | `.../test13/output/panorama.png`  | Uneven gaps (2.3×); mild seam |
| `test14/` (7 frames)  | `.../test14/*.png` | `.../test14/output/panorama_stages/` | `.../test14/output/simple_stitch.png` | `.../test14/output/panorama.png`  | **Clean; pipeline taller than ss** |
| `test15/` (7 frames)  | `.../test15/*.png` | `.../test15/output/panorama_stages/` | `.../test15/output/simple_stitch.png` | `.../test15/output/panorama.png`  | **Clean; ss has staircase borders** |
| `test16/` (10 frames) | `.../test16/*.png` | `.../test16/output/panorama_stages/` | `.../test16/output/simple_stitch.png` | `.../test16/output/panorama.png`  | Clustering (min_gap=12px) → catastrophic ghosting |
| `test17/` (7 frames)  | `.../test17/*.png` | `.../test17/output/panorama_stages/` | `.../test17/output/simple_stitch.png` | `.../test17/output/panorama.png`  | Mild seam at one boundary (1.5×) |
| `test18/` (6 frames)  | `.../test18/*.png` | `.../test18/output/panorama_stages/` | `.../test18/output/simple_stitch.png` | `.../test18/output/panorama.png`  | Good ty/tx but catastrophic Stage 9 — affine rotation |
| `test19/` (10 frames) | `.../test19/*.png` | `.../test19/output/panorama_stages/` | `.../test19/output/simple_stitch.png` | `.../test19/output/panorama.png`  | **Clean — positive baseline** |
| `test20/` (7 frames)  | `.../test20/*.png` | `.../test20/output/panorama_stages/` | `.../test20/output/simple_stitch.png` | `.../test20/output/panorama.png`  | Pure horizontal scroll (ty≈0, tx=0–1857px) |
| `test21/` (10 frames) | `.../test21/*.png` | `.../test21/output/panorama_stages/` | `.../test21/output/simple_stitch.png` | `.../test21/output/panorama.png`  | 3 co-located frames → top-strip ghosting |
| `test22/` (11 frames) | `.../test22/*.png` | `.../test22/output/panorama_stages/` | `.../test22/output/simple_stitch.png` | `.../test22/output/panorama.png`  | **Clean — positive baseline** |

All paths are relative to `/home/pkhunter/Downloads/data/Anime_Stitch_Pipeline/`.
