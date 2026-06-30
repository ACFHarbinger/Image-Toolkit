"""
test_pipeline_diagnostics.py
============================
Stage-isolated diagnostic tests for AnimeStitchPipeline.

Design principles
-----------------
- Every test operates on pre-saved stage artefacts (JSON + PNG) so GPU-heavy
  stages (BiRefNet, LoFTR) are never re-run unless explicitly requested.
- Each test produces a numeric score AND a plain-text verdict so results can be
  consumed both programmatically and visually.
- Tests are grouped by the failure categories documented in the issue report:
    A  — Seam / brightness bands (Stage 11)
    B  — Stage 9 temporal render ghosting
    C  — Alignment failure (bad affines from Stage 7)
    D  — Diagonal scroll / tx drift (Stage 9/canvas model)
    E  — Canvas overcrop / height loss
    F  — MFSR block artefacts (skipped by default)

Usage
-----
    # Run all tests on all datasets:
    python test_pipeline_diagnostics.py --data-root /path/to/Anime_Stitch_Pipeline

    # Run only alignment tests on test8:
    python test_pipeline_diagnostics.py --data-root /path/... --datasets test8 --categories C

    # Run with full-pipeline re-run for a specific dataset (requires GPU):
    python test_pipeline_diagnostics.py --data-root /path/... --datasets test6 --rerun

    # Dump a machine-readable JSON report:
    python test_pipeline_diagnostics.py --data-root /path/... --json report.json

Expected directory layout per dataset
--------------------------------------
<data-root>/
  <dataset>/
    frames/          ← source PNG/JPG frames (used only when --rerun)
    output/
      panorama.png              ← pipeline final output
      simple_stitch.png         ← OpenCV SCANS reference
      panorama_stages/
        stage02_normalised_frame{N}.png
        stage04_bgmask_frame{N}.png
        stage08_canvas_info.json
        stage09_temporal_render.png
        stage11_composite.png
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    name: str
    category: str        # A-F
    dataset: str
    passed: bool
    score: float         # 0.0 (worst) .. 1.0 (best), or -1.0 for N/A
    verdict: str         # one-line human summary
    detail: str = ""     # optional multi-line diagnostic info


@dataclass
class DatasetReport:
    dataset: str
    results: List[TestResult] = field(default_factory=list)

    def add(self, r: TestResult) -> None:
        self.results.append(r)

    def summary(self) -> str:
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        lines = [f"\n{'='*60}", f"Dataset: {self.dataset}  ({passed}/{total} passed)"]
        for cat in "ABCDEF":
            cat_results = [r for r in self.results if r.category == cat]
            if not cat_results:
                continue
            lines.append(f"  [{cat}] " + "  ".join(
                ("✓" if r.passed else "✗") + f" {r.name} ({r.score:.2f})"
                for r in cat_results
            ))
            for r in cat_results:
                if not r.passed:
                    lines.append(f"       → {r.verdict}")
                    if r.detail:
                        for dl in r.detail.splitlines():
                            lines.append(f"         {dl}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Image / JSON helpers
# ---------------------------------------------------------------------------

def _load_gray(path: Path) -> Optional[np.ndarray]:
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return img


def _load_bgr(path: Path) -> Optional[np.ndarray]:
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    return img


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def _row_mean(img: np.ndarray) -> np.ndarray:
    """Per-row mean brightness (float32)."""
    return img.astype(np.float32).mean(axis=(1, 2) if img.ndim == 3 else (1,))


def _brightness_band_score(img: np.ndarray) -> Tuple[float, float]:
    """
    Detect horizontal brightness bands by computing the high-frequency content
    of the per-row mean profile.

    Returns
    -------
    (band_score, max_step)
      band_score : 0.0 = severe banding, 1.0 = perfectly smooth
      max_step   : largest single-row brightness jump (0-255 scale)
    """
    row_m = _row_mean(img)
    # Remove the slow scene gradient (low-pass) to isolate bands
    kernel_size = max(3, len(row_m) // 20) | 1   # odd
    lp = cv2.GaussianBlur(row_m.reshape(-1, 1), (1, kernel_size), 0).flatten()
    residual = row_m - lp
    # A visible band shows as a step in residual
    steps = np.abs(np.diff(residual))
    max_step = float(steps.max()) if len(steps) else 0.0
    # Visible threshold: ~3 brightness units after LP removal is clearly visible
    band_score = float(np.clip(1.0 - max_step / 15.0, 0.0, 1.0))
    return band_score, max_step


def _ghosting_score(img: np.ndarray) -> Tuple[float, float]:
    """
    Estimate ghosting by measuring edge-pair doubling.

    Strategy: for each row, compute a 1-D edge profile and look for duplicated
    high-frequency events at ±N pixel offsets.  Ghosted content produces
    correlated edge profiles shifted by the ghost offset.

    Returns (ghost_score, ghost_strength):
      ghost_score    : 1.0 = no ghosting, 0.0 = severe
      ghost_strength : autocorrelation peak at non-zero lag (0-1)
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    # Laplacian edge map
    lap = np.abs(cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F))
    # Vertical profile of edge energy
    profile = lap.mean(axis=1)
    profile = profile - profile.mean()
    if profile.std() < 1e-6:
        return 1.0, 0.0
    profile /= profile.std()
    # Autocorrelation for lags 10..300px
    n = len(profile)
    lags = range(10, min(300, n // 4))
    ac_vals = []
    for lag in lags:
        ac = float(np.corrcoef(profile[:-lag], profile[lag:])[0, 1])
        ac_vals.append(abs(ac))
    ghost_strength = float(np.max(ac_vals)) if ac_vals else 0.0
    ghost_score = float(np.clip(1.0 - ghost_strength / 0.5, 0.0, 1.0))
    return ghost_score, ghost_strength


def _mask_quality_score(mask: np.ndarray) -> Tuple[float, str]:
    """
    Basic sanity-check for a BiRefNet background mask (255=bg, 0=fg).

    Checks:
    1. Not all-zero (empty mask)
    2. Not all-255 (segmentation failure — nothing detected as foreground)
    3. Background fraction is reasonable (10–90% of pixels)
    4. Mask has spatial structure (not pure noise — measured by connected components)

    Returns (score 0..1, verdict string).
    """
    if mask is None:
        return 0.0, "mask file missing"
    total = mask.size
    bg_frac = float((mask > 127).sum()) / total
    if bg_frac < 0.05:
        return 0.0, f"mask appears inverted or empty (bg_frac={bg_frac:.2f})"
    if bg_frac > 0.97:
        return 0.2, f"mask has almost no foreground detected (bg_frac={bg_frac:.2f})"
    # Check spatial structure using connected components
    fg = ((mask < 128) * 255).astype(np.uint8)
    n_comp, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=8)
    # A good fg mask has 1-20 sizable connected regions (character body parts)
    sizable = sum(1 for i in range(1, n_comp) if stats[i, cv2.CC_STAT_AREA] > 500)
    if sizable == 0:
        return 0.3, f"fg mask has no sizable connected regions (n_comp={n_comp})"
    if sizable > 50:
        return 0.5, f"fg mask is fragmented ({sizable} sizable blobs — likely noise)"
    score = min(1.0, sizable / 5.0) * 0.5 + 0.5  # 0.5..1.0 based on structure
    return score, f"bg_frac={bg_frac:.2f}, fg_blobs={sizable}"


# ---------------------------------------------------------------------------
# Affine / alignment analysis helpers
# ---------------------------------------------------------------------------

def _parse_affines(canvas_info: dict) -> Optional[List[Tuple[int, float, float]]]:
    """
    Parse stage08_canvas_info.json.

    Expected schema (either flat list or dict with 'affines' key):
      {"affines": [[a, b, tx, c, d, ty], ...], "canvas_h": ..., "canvas_w": ...}
    OR
      {"frames": [{"frame": N, "tx": ..., "ty": ...}, ...]}

    Returns list of (frame_idx, tx, ty) sorted by ty.
    """
    if canvas_info is None:
        return None
    # Schema variant 1: flat affine matrices
    if "affines" in canvas_info:
        raw = canvas_info["affines"]
        result = []
        for i, m in enumerate(raw):
            # m is either [a,b,tx,c,d,ty] (6 values) or [[a,b,tx],[c,d,ty]] (3x2)
            if isinstance(m[0], list):
                tx, ty = float(m[0][2]), float(m[1][2])
            else:
                tx, ty = float(m[2]), float(m[5])
            result.append((i, tx, ty))
        return result
    # Schema variant 2: per-frame dict
    if "frames" in canvas_info:
        return [
            (f["frame"], float(f.get("tx", 0.0)), float(f["ty"]))
            for f in canvas_info["frames"]
        ]
    return None


def _alignment_ratio(affines: List[Tuple[int, float, float]]) -> Tuple[float, float, float]:
    """
    Compute max_gap / median_gap ratio for ty values.

    Returns (ratio, max_gap, median_gap).
    """
    tys = sorted(a[2] for a in affines)
    gaps = np.diff(tys)
    if len(gaps) == 0:
        return 0.0, 0.0, 0.0
    med = float(np.median(gaps))
    if med < 1.0:
        return float("inf"), float(gaps.max()), med
    ratio = float(gaps.max() / med)
    return ratio, float(gaps.max()), med


def _clustering_score(affines: List[Tuple[int, float, float]]) -> Tuple[float, int]:
    """
    Count frame pairs with ty separation < 30px (pathological clustering).

    Returns (score 1.0=clean .. 0.0=all clustered, n_clustered_pairs).
    """
    tys = sorted(a[2] for a in affines)
    gaps = np.diff(tys)
    clustered = int((gaps < 30).sum())
    n = max(len(gaps), 1)
    score = float(np.clip(1.0 - clustered / n, 0.0, 1.0))
    return score, clustered


def _monotonicity_score(affines: List[Tuple[int, float, float]]) -> Tuple[float, int]:
    """
    Check whether frame ordering (by original index) is monotonically
    increasing in ty (expected for a top-to-bottom scroll).

    Returns (score, n_inversions).
    """
    by_idx = sorted(affines, key=lambda x: x[0])
    tys = [a[2] for a in by_idx]
    inversions = sum(1 for i in range(len(tys) - 1) if tys[i] > tys[i + 1] + 50.0)
    score = float(np.clip(1.0 - inversions / max(len(tys) - 1, 1), 0.0, 1.0))
    return score, inversions


def _tx_drift_score(affines: List[Tuple[int, float, float]]) -> Tuple[float, float]:
    """
    Measure horizontal drift (tx spread).  Pipeline only handles vertical pans;
    significant tx drift indicates an unsupported diagonal scroll.

    Returns (score 1.0=no drift .. 0.0=severe drift, tx_range_px).
    """
    txs = [a[1] for a in affines]
    tx_range = float(max(txs) - min(txs))
    # Threshold: if tx drift exceeds 5% of a typical 4K frame width (3840px) → 192px
    score = float(np.clip(1.0 - tx_range / 500.0, 0.0, 1.0))
    return score, tx_range


# ---------------------------------------------------------------------------
# Canvas / crop tests
# ---------------------------------------------------------------------------

def _height_ratio(pipeline_img: np.ndarray, reference_img: np.ndarray) -> float:
    """pipeline_h / reference_h  (should be close to 1.0)."""
    return pipeline_img.shape[0] / max(reference_img.shape[0], 1)


# ---------------------------------------------------------------------------
# Category A — Seam / brightness band tests
# ---------------------------------------------------------------------------

def test_A1_brightness_bands(ds_dir: Path, dataset: str) -> TestResult:
    """
    Measure horizontal brightness banding in the final panorama output.
    A clean stitch has a smooth row-brightness profile; bands produce
    high-frequency steps in that profile.
    """
    panorama_path = ds_dir / "output" / "panorama.png"
    img = _load_bgr(panorama_path)
    if img is None:
        return TestResult("A1_brightness_bands", "A", dataset, False, -1.0,
                          "panorama.png not found")
    score, max_step = _brightness_band_score(img)
    passed = score >= 0.7
    verdict = (
        f"Banding score {score:.2f} (max_step={max_step:.1f}) — "
        + ("clean" if passed else "VISIBLE BANDS DETECTED")
    )
    return TestResult("A1_brightness_bands", "A", dataset, passed, score, verdict)


def test_A2_composite_vs_render(ds_dir: Path, dataset: str) -> TestResult:
    """
    Compare Stage 9 (temporal render) vs Stage 11 (composite) banding scores.
    If Stage 11 is significantly worse than Stage 9, the compositor introduced bands.
    """
    stages = ds_dir / "output" / "panorama_stages"
    render = _load_bgr(stages / "stage09_temporal_render.png")
    composite = _load_bgr(stages / "stage11_composite.png")
    if render is None or composite is None:
        return TestResult("A2_composite_vs_render", "A", dataset, False, -1.0,
                          "stage09 or stage11 image missing")
    r_score, r_step = _brightness_band_score(render)
    c_score, c_step = _brightness_band_score(composite)
    degradation = r_score - c_score
    passed = degradation <= 0.15   # allow up to 15% degradation
    verdict = (
        f"Render banding={r_score:.2f}  Composite banding={c_score:.2f}  "
        f"Δ={degradation:+.2f} — "
        + ("OK" if passed else "COMPOSITOR INTRODUCED BANDS")
    )
    return TestResult("A2_composite_vs_render", "A", dataset, passed,
                      max(0.0, 1.0 - degradation), verdict)


def test_A3_seam_count(ds_dir: Path, dataset: str) -> TestResult:
    """
    Detect hard horizontal seams in Stage 11 composite by looking for
    rows with unusually high local contrast in the brightness profile.
    Hard seams (e.g. test3) produce isolated brightness spikes.
    """
    stages = ds_dir / "output" / "panorama_stages"
    img = _load_bgr(stages / "stage11_composite.png")
    if img is None:
        return TestResult("A3_seam_count", "A", dataset, False, -1.0,
                          "stage11_composite.png missing")
    row_m = _row_mean(img)
    diffs = np.abs(np.diff(row_m))
    # A "hard seam" is a row-to-row jump exceeding 15 brightness units
    hard_seam_rows = int((diffs > 15.0).sum())
    score = float(np.clip(1.0 - hard_seam_rows / 20.0, 0.0, 1.0))
    passed = hard_seam_rows <= 5
    verdict = f"{hard_seam_rows} hard-seam rows (threshold=5) — " + ("OK" if passed else "HARD SEAMS PRESENT")
    return TestResult("A3_seam_count", "A", dataset, passed, score, verdict,
                      detail=f"Rows with brightness jump >15: {hard_seam_rows}")


# ---------------------------------------------------------------------------
# Category B — Stage 9 ghosting tests
# ---------------------------------------------------------------------------

def test_B1_temporal_render_ghosting(ds_dir: Path, dataset: str) -> TestResult:
    """
    Detect ghosting in Stage 9 temporal render.
    Ghosting creates periodically duplicated edge patterns in the vertical
    profile (autocorrelation at ghost offset lags).
    """
    stages = ds_dir / "output" / "panorama_stages"
    img = _load_bgr(stages / "stage09_temporal_render.png")
    if img is None:
        return TestResult("B1_temporal_render_ghosting", "B", dataset, False, -1.0,
                          "stage09_temporal_render.png missing")
    score, strength = _ghosting_score(img)
    passed = score >= 0.6
    verdict = (
        f"Ghost score {score:.2f} (autocorr_strength={strength:.3f}) — "
        + ("OK" if passed else "GHOSTING DETECTED")
    )
    return TestResult("B1_temporal_render_ghosting", "B", dataset, passed, score, verdict)


def test_B2_render_coverage(ds_dir: Path, dataset: str) -> TestResult:
    """
    Check that Stage 9 render has adequate non-black pixel coverage.
    Catastrophic alignment causes large black regions in the render.
    Threshold: at least 70% of pixels must be non-black.
    """
    stages = ds_dir / "output" / "panorama_stages"
    img = _load_bgr(stages / "stage09_temporal_render.png")
    if img is None:
        return TestResult("B2_render_coverage", "B", dataset, False, -1.0,
                          "stage09_temporal_render.png missing")
    coverage = float((img.max(axis=2) > 10).mean())
    passed = coverage >= 0.70
    verdict = f"Coverage={coverage:.2%} — " + ("OK" if passed else "LOW COVERAGE (bad affines?)")
    return TestResult("B2_render_coverage", "B", dataset, passed, coverage, verdict)


def test_B3_mask_quality(ds_dir: Path, dataset: str) -> TestResult:
    """
    Audit all stage04 BiRefNet background masks.
    Inverted, empty, or fragmented masks corrupt LS normalization and
    boundary search, which then cascades to ghosting in Stage 9.
    """
    stages = ds_dir / "output" / "panorama_stages"
    mask_paths = sorted(stages.glob("stage04_bgmask_frame*.png"))
    if not mask_paths:
        return TestResult("B3_mask_quality", "B", dataset, False, -1.0,
                          "No stage04_bgmask_frame*.png files found")
    scores = []
    bad_frames = []
    for p in mask_paths:
        mask = _load_gray(p)
        s, v = _mask_quality_score(mask)
        scores.append(s)
        if s < 0.6:
            bad_frames.append(f"{p.name}: {v}")
    mean_score = float(np.mean(scores))
    passed = mean_score >= 0.65 and len(bad_frames) == 0
    verdict = (
        f"Mean mask score={mean_score:.2f} ({len(mask_paths)} masks) — "
        + ("OK" if passed else f"{len(bad_frames)} BAD MASKS")
    )
    detail = "\n".join(bad_frames) if bad_frames else ""
    return TestResult("B3_mask_quality", "B", dataset, passed, mean_score, verdict, detail=detail)


# ---------------------------------------------------------------------------
# Category C — Alignment / bundle adjustment tests
# ---------------------------------------------------------------------------

def test_C1_alignment_ratio(ds_dir: Path, dataset: str) -> TestResult:
    """
    Compute max_gap / median_gap ratio from stage08_canvas_info.json.
    Ratio > 3× indicates broken bundle adjustment.
    (Good datasets: test1=1.1, test4=1.0, test6=1.4)
    (Bad datasets: test7=4.7, test8=5.9, test9=11.8)
    """
    info = _load_json(ds_dir / "output" / "panorama_stages" / "stage08_canvas_info.json")
    affines = _parse_affines(info)
    if affines is None:
        return TestResult("C1_alignment_ratio", "C", dataset, False, -1.0,
                          "stage08_canvas_info.json missing or unrecognised schema")
    ratio, max_gap, med_gap = _alignment_ratio(affines)
    passed = ratio <= 3.0
    score = float(np.clip(1.0 - (ratio - 1.0) / 10.0, 0.0, 1.0))
    verdict = (
        f"max/median gap ratio={ratio:.1f}× (max={max_gap:.0f}px, median={med_gap:.0f}px) — "
        + ("OK" if passed else "BROKEN BUNDLE ADJUST")
    )
    return TestResult("C1_alignment_ratio", "C", dataset, passed, score, verdict)


def test_C2_frame_clustering(ds_dir: Path, dataset: str) -> TestResult:
    """
    Count frame pairs with ty separation < 30px.
    Near-zero ty gaps mean LoFTR produced a wrong (near-zero) dy estimate,
    causing multiple frames to collapse onto the same canvas rows.
    """
    info = _load_json(ds_dir / "output" / "panorama_stages" / "stage08_canvas_info.json")
    affines = _parse_affines(info)
    if affines is None:
        return TestResult("C2_frame_clustering", "C", dataset, False, -1.0,
                          "stage08_canvas_info.json missing")
    score, n_clustered = _clustering_score(affines)
    passed = n_clustered == 0
    verdict = (
        f"{n_clustered} clustered frame pairs (<30px apart) — "
        + ("OK" if passed else f"FRAME CLUSTERING (root cause of ghosting in test8/test9)")
    )
    # Report the actual clusters
    tys = sorted(a[2] for a in affines)
    gaps = np.diff(tys)
    bad_gaps = [(float(tys[i]), float(tys[i+1]), float(gaps[i]))
                for i in range(len(gaps)) if gaps[i] < 30.0]
    detail = "\n".join(f"  ty={a:.1f} and ty={b:.1f} → gap={g:.1f}px" for a, b, g in bad_gaps)
    return TestResult("C2_frame_clustering", "C", dataset, passed, score, verdict, detail=detail)


def test_C3_frame_ordering(ds_dir: Path, dataset: str) -> TestResult:
    """
    Check that frames appear in monotonically increasing ty order.
    Non-monotonic ordering (test2, test7) indicates wrong-direction LoFTR matches.
    """
    info = _load_json(ds_dir / "output" / "panorama_stages" / "stage08_canvas_info.json")
    affines = _parse_affines(info)
    if affines is None:
        return TestResult("C3_frame_ordering", "C", dataset, False, -1.0,
                          "stage08_canvas_info.json missing")
    score, inversions = _monotonicity_score(affines)
    passed = inversions == 0
    verdict = (
        f"{inversions} ty-ordering inversions — "
        + ("OK" if passed else "NON-MONOTONIC ORDER (wrong-direction LoFTR matches)")
    )
    # Show the inversion positions
    by_idx = sorted(affines, key=lambda x: x[0])
    tys = [a[2] for a in by_idx]
    inv_detail = []
    for i in range(len(tys) - 1):
        if tys[i] > tys[i + 1] + 50.0:
            inv_detail.append(f"  frame{by_idx[i][0]} ty={tys[i]:.1f} > frame{by_idx[i+1][0]} ty={tys[i+1]:.1f}")
    return TestResult("C3_frame_ordering", "C", dataset, passed, score, verdict,
                      detail="\n".join(inv_detail))


def test_C4_affine_residuals(ds_dir: Path, dataset: str) -> TestResult:
    """
    If stage05_edges.json exists, compute post-BA per-edge residuals and
    check for outliers that indicate the bundle adjust was not robust.

    Residual = |predicted_dy - measured_dy|, where:
      predicted_dy = affines[j].ty - affines[i].ty
      measured_dy  = edge['M'][1,2]  (raw LoFTR estimate)

    Outliers (residual > 3× median) indicate edges that corrupted the solve.
    """
    stages = ds_dir / "output" / "panorama_stages"
    edges_path = stages / "stage05_edges.json"
    canvas_info = _load_json(stages / "stage08_canvas_info.json")
    if not edges_path.exists() or canvas_info is None:
        return TestResult("C4_affine_residuals", "C", dataset, False, -1.0,
                          "stage05_edges.json or stage08_canvas_info.json missing (optional test)")
    affines = _parse_affines(canvas_info)
    if affines is None:
        return TestResult("C4_affine_residuals", "C", dataset, False, -1.0,
                          "Cannot parse affines from stage08_canvas_info.json")
    ty_map = {idx: ty for idx, _, ty in affines}
    with open(edges_path) as f:
        edges = json.load(f)
    residuals = []
    for e in edges:
        i, j = int(e["i"]), int(e["j"])
        if i not in ty_map or j not in ty_map:
            continue
        measured_dy = float(e["M"][1][2]) if isinstance(e["M"][0], list) else float(e["M"][5])
        predicted_dy = ty_map[j] - ty_map[i]
        residuals.append(abs(predicted_dy - measured_dy))
    if not residuals:
        return TestResult("C4_affine_residuals", "C", dataset, False, -1.0,
                          "No matching edges found")
    med_res = float(np.median(residuals))
    max_res = float(np.max(residuals))
    outliers = int(sum(1 for r in residuals if r > 3.0 * med_res + 20.0))
    score = float(np.clip(1.0 - outliers / max(len(residuals), 1), 0.0, 1.0))
    passed = outliers == 0
    verdict = (
        f"BA residuals: median={med_res:.1f}px, max={max_res:.1f}px, "
        f"outliers={outliers}/{len(residuals)} — "
        + ("OK" if passed else "OUTLIER EDGES CORRUPTING BUNDLE ADJUST")
    )
    return TestResult("C4_affine_residuals", "C", dataset, passed, score, verdict)


# ---------------------------------------------------------------------------
# Category D — Diagonal scroll / tx drift
# ---------------------------------------------------------------------------

def test_D1_tx_drift(ds_dir: Path, dataset: str) -> TestResult:
    """
    Measure horizontal tx spread across affines.
    The pipeline's canvas model only uses ty; significant tx drift means
    the diagonal scroll is being silently discarded (test7).
    Threshold: tx range > 200px is a problem.
    """
    info = _load_json(ds_dir / "output" / "panorama_stages" / "stage08_canvas_info.json")
    affines = _parse_affines(info)
    if affines is None:
        return TestResult("D1_tx_drift", "D", dataset, False, -1.0,
                          "stage08_canvas_info.json missing")
    score, tx_range = _tx_drift_score(affines)
    passed = tx_range <= 200.0
    verdict = (
        f"tx range={tx_range:.1f}px — "
        + ("OK" if passed else "DIAGONAL SCROLL DETECTED (tx discarded by canvas model)")
    )
    return TestResult("D1_tx_drift", "D", dataset, passed, score, verdict)


def test_D2_output_width_vs_reference(ds_dir: Path, dataset: str) -> TestResult:
    """
    Compare pipeline output width vs simple_stitch width.
    For diagonal scrolls the simple stitch is significantly wider (test7: 5530 vs 4603px).
    Threshold: pipeline width should be >= 80% of simple_stitch width.
    """
    panorama = _load_bgr(ds_dir / "output" / "panorama.png")
    simple = _load_bgr(ds_dir / "output" / "simple_stitch.png")
    if panorama is None or simple is None:
        return TestResult("D2_output_width_vs_reference", "D", dataset, False, -1.0,
                          "panorama.png or simple_stitch.png missing")
    ratio = panorama.shape[1] / max(simple.shape[1], 1)
    passed = ratio >= 0.80
    verdict = (
        f"Width ratio pipeline/simple={ratio:.2f} "
        f"({panorama.shape[1]}px vs {simple.shape[1]}px) — "
        + ("OK" if passed else "PIPELINE OUTPUT TOO NARROW (tx drift discarded?)")
    )
    return TestResult("D2_output_width_vs_reference", "D", dataset, passed,
                      min(1.0, ratio), verdict)


# ---------------------------------------------------------------------------
# Category E — Canvas overcrop / height loss
# ---------------------------------------------------------------------------

def test_E1_height_vs_reference(ds_dir: Path, dataset: str) -> TestResult:
    """
    Compare pipeline panorama height vs simple_stitch height.
    The pipeline should produce >= 85% the height of the simple stitch.
    Large height losses indicate canvas compression from bad affines
    OR over-aggressive _crop_to_valid.
    """
    panorama = _load_bgr(ds_dir / "output" / "panorama.png")
    simple = _load_bgr(ds_dir / "output" / "simple_stitch.png")
    if panorama is None or simple is None:
        return TestResult("E1_height_vs_reference", "E", dataset, False, -1.0,
                          "panorama.png or simple_stitch.png missing")
    ratio = panorama.shape[0] / max(simple.shape[0], 1)
    delta_px = simple.shape[0] - panorama.shape[0]
    passed = ratio >= 0.85
    verdict = (
        f"Height ratio pipeline/simple={ratio:.2f} "
        f"({panorama.shape[0]}px vs {simple.shape[0]}px, Δ={delta_px:+d}px) — "
        + ("OK" if passed else "SIGNIFICANT HEIGHT LOSS")
    )
    return TestResult("E1_height_vs_reference", "E", dataset, passed,
                      min(1.0, ratio), verdict)


def test_E2_canvas_vs_panorama_height(ds_dir: Path, dataset: str) -> TestResult:
    """
    Compare the canvas_h from stage08_canvas_info.json vs the final panorama height.
    A large discrepancy (> 5% smaller) indicates _crop_to_valid is over-cropping.
    (test4: canvas=3201px, panorama=3141px → 393px lost by over-aggressive crop)
    """
    info = _load_json(ds_dir / "output" / "panorama_stages" / "stage08_canvas_info.json")
    panorama = _load_bgr(ds_dir / "output" / "panorama.png")
    if info is None or panorama is None:
        return TestResult("E2_canvas_vs_panorama_height", "E", dataset, False, -1.0,
                          "stage08_canvas_info.json or panorama.png missing")
    canvas_h = info.get("canvas_h", None)
    if canvas_h is None:
        return TestResult("E2_canvas_vs_panorama_height", "E", dataset, False, -1.0,
                          "canvas_h not found in stage08_canvas_info.json")
    pano_h = panorama.shape[0]
    crop_px = canvas_h - pano_h
    crop_frac = crop_px / max(canvas_h, 1)
    passed = crop_frac <= 0.10   # allow up to 10% (edge_crop + dark borders)
    score = float(np.clip(1.0 - crop_frac / 0.20, 0.0, 1.0))
    verdict = (
        f"Canvas_h={canvas_h}px → Panorama_h={pano_h}px, cropped={crop_px}px ({crop_frac:.1%}) — "
        + ("OK" if passed else "_crop_to_valid OVER-CROPPING")
    )
    return TestResult("E2_canvas_vs_panorama_height", "E", dataset, passed, score, verdict)


def test_E3_black_border_fraction(ds_dir: Path, dataset: str) -> TestResult:
    """
    Measure what fraction of the final panorama is black (uncovered) pixels.
    High black fraction indicates the canvas is not being filled correctly.
    Threshold: < 5% black pixels.
    """
    panorama = _load_bgr(ds_dir / "output" / "panorama.png")
    if panorama is None:
        return TestResult("E3_black_border_fraction", "E", dataset, False, -1.0,
                          "panorama.png missing")
    black_frac = float((panorama.max(axis=2) < 10).mean())
    passed = black_frac <= 0.05
    score = float(np.clip(1.0 - black_frac / 0.10, 0.0, 1.0))
    verdict = (
        f"Black pixel fraction={black_frac:.2%} — "
        + ("OK" if passed else "LARGE BLACK REGIONS (bad affines or overcrop)")
    )
    return TestResult("E3_black_border_fraction", "E", dataset, passed, score, verdict)


# ---------------------------------------------------------------------------
# Cross-category regression test
# ---------------------------------------------------------------------------

def test_X1_pipeline_vs_simple_ssim(ds_dir: Path, dataset: str) -> TestResult:
    """
    Compute a structural similarity proxy between the pipeline panorama
    and the simple_stitch reference.  Both are resized to the same height
    before comparison; a very low score indicates a catastrophically wrong output.

    Note: the pipeline SHOULD differ from simple_stitch (it is sharper /
    less ghosted), so a low score is expected for GOOD outputs when the pipeline
    is doing content-aware compositing.  The test flags only catastrophic failures
    (score < 0.25 indicates the output is structurally wrong, not just different).
    """
    panorama = _load_bgr(ds_dir / "output" / "panorama.png")
    simple = _load_bgr(ds_dir / "output" / "simple_stitch.png")
    if panorama is None or simple is None:
        return TestResult("X1_pipeline_vs_simple_ssim", "X", dataset, False, -1.0,
                          "panorama.png or simple_stitch.png missing")
    # Resize both to a small comparison size
    compare_h = 512
    def _resize_h(img, h):
        scale = h / img.shape[0]
        w = max(1, int(img.shape[1] * scale))
        return cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    p = _resize_h(panorama, compare_h)
    s = _resize_h(simple, compare_h)
    # Crop to common width
    common_w = min(p.shape[1], s.shape[1])
    p = p[:, :common_w]
    s = s[:, :common_w]
    # Simple normalised cross-correlation as SSIM proxy
    pf = p.astype(np.float64) / 255.0
    sf = s.astype(np.float64) / 255.0
    mu_p, mu_s = pf.mean(), sf.mean()
    cov = ((pf - mu_p) * (sf - mu_s)).mean()
    std_p = max(pf.std(), 1e-6)
    std_s = max(sf.std(), 1e-6)
    ncc = float(cov / (std_p * std_s))
    score = float(np.clip((ncc + 1.0) / 2.0, 0.0, 1.0))
    passed = score >= 0.25   # only flag catastrophic structural failures
    verdict = (
        f"NCC score={score:.3f} (pipeline vs simple_stitch) — "
        + ("structurally plausible" if passed else "CATASTROPHIC STRUCTURAL MISMATCH")
    )
    return TestResult("X1_pipeline_vs_simple_ssim", "X", dataset, passed, score, verdict)


# ---------------------------------------------------------------------------
# Test registry
# ---------------------------------------------------------------------------

ALL_TESTS = [
    # Category A
    test_A1_brightness_bands,
    test_A2_composite_vs_render,
    test_A3_seam_count,
    # Category B
    test_B1_temporal_render_ghosting,
    test_B2_render_coverage,
    test_B3_mask_quality,
    # Category C
    test_C1_alignment_ratio,
    test_C2_frame_clustering,
    test_C3_frame_ordering,
    test_C4_affine_residuals,
    # Category D
    test_D1_tx_drift,
    test_D2_output_width_vs_reference,
    # Category E
    test_E1_height_vs_reference,
    test_E2_canvas_vs_panorama_height,
    test_E3_black_border_fraction,
    # Cross-category
    test_X1_pipeline_vs_simple_ssim,
]

CATEGORY_NAMES = {
    "A": "Seam / brightness bands (Stage 11)",
    "B": "Stage 9 temporal render ghosting",
    "C": "Alignment failure (Stage 7 bundle adjust)",
    "D": "Diagonal scroll / tx drift",
    "E": "Canvas overcrop / height loss",
    "X": "Cross-category regression",
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def discover_datasets(data_root: Path) -> List[str]:
    return sorted(
        p.name for p in data_root.iterdir()
        if p.is_dir() and (p / "output").exists()
    )


def run_dataset(
    data_root: Path,
    dataset: str,
    categories: Optional[List[str]] = None,
) -> DatasetReport:
    ds_dir = data_root / dataset
    report = DatasetReport(dataset)
    for test_fn in ALL_TESTS:
        cat = test_fn.__name__.split("_")[1][0]   # e.g. "A" from "test_A1_..."
        if categories and cat not in categories and cat != "X":
            continue
        try:
            result = test_fn(ds_dir, dataset)
        except Exception as exc:
            result = TestResult(
                test_fn.__name__, cat, dataset, False, -1.0,
                f"EXCEPTION: {exc}",
                detail=f"{type(exc).__name__}: {exc}",
            )
        report.add(result)
    return report


def run_all(
    data_root: Path,
    datasets: Optional[List[str]] = None,
    categories: Optional[List[str]] = None,
) -> List[DatasetReport]:
    if datasets is None:
        datasets = discover_datasets(data_root)
    reports = []
    for ds in datasets:
        print(f"  Running diagnostics on {ds}...", flush=True)
        rpt = run_dataset(data_root, ds, categories=categories)
        reports.append(rpt)
    return reports


def print_summary(reports: List[DatasetReport]) -> None:
    print("\n" + "="*60)
    print("ANIME STITCH PIPELINE — DIAGNOSTIC SUMMARY")
    print("="*60)
    for rpt in reports:
        print(rpt.summary())

    # Cross-dataset category breakdown
    print("\n" + "="*60)
    print("FAILURE CATEGORY BREAKDOWN")
    print("="*60)
    all_results = [r for rpt in reports for r in rpt.results]
    for cat, name in CATEGORY_NAMES.items():
        cat_results = [r for r in all_results if r.category == cat and r.score >= 0]
        if not cat_results:
            continue
        n_fail = sum(1 for r in cat_results if not r.passed)
        n_total = len(cat_results)
        bar = "█" * n_fail + "░" * (n_total - n_fail)
        print(f"  [{cat}] {name}")
        print(f"       {n_fail}/{n_total} failing  {bar}")
        failing_ds = sorted(set(r.dataset for r in cat_results if not r.passed))
        if failing_ds:
            print(f"       Affected: {', '.join(failing_ds)}")


def save_json(reports: List[DatasetReport], out_path: Path) -> None:
    from dataclasses import asdict
    data = [
        {
            "dataset": rpt.dataset,
            "results": [asdict(r) for r in rpt.results],
            "passed": sum(1 for r in rpt.results if r.passed),
            "total": len(rpt.results),
        }
        for rpt in reports
    ]
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"\nJSON report saved to {out_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent("""
            Stage-isolated diagnostic tests for AnimeStitchPipeline.
            Reads pre-saved stage artefacts — no GPU re-runs required.
        """),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--data-root", required=True,
        help="Root directory containing test1/, test2/, ... dataset subdirectories.",
    )
    parser.add_argument(
        "--datasets", nargs="+", metavar="DATASET",
        help="Run only these dataset(s). Default: all discovered datasets.",
    )
    parser.add_argument(
        "--categories", nargs="+", metavar="CAT",
        choices=list(CATEGORY_NAMES.keys()),
        help="Run only tests in these failure categories (A-F).",
    )
    parser.add_argument(
        "--json", metavar="FILE",
        help="Save machine-readable results to FILE as JSON.",
    )
    parser.add_argument(
        "--fail-fast", action="store_true",
        help="Stop after the first failed test.",
    )
    args = parser.parse_args(argv)

    data_root = Path(args.data_root)
    if not data_root.exists():
        print(f"ERROR: data-root '{data_root}' does not exist.", file=sys.stderr)
        return 1

    print(f"Data root: {data_root}")
    reports = run_all(
        data_root,
        datasets=args.datasets,
        categories=args.categories,
    )
    print_summary(reports)
    if args.json:
        save_json(reports, Path(args.json))

    total_failed = sum(
        1 for rpt in reports for r in rpt.results if not r.passed and r.score >= 0
    )
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
