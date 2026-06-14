"""
§1.8A: TOML-based ASP pipeline configuration loader.

Loads ``asp_config.toml`` from the current working directory (or a path
supplied by the caller).  Any key present in the TOML file is exported as an
environment variable (via ``os.environ.setdefault``), so all downstream
``os.environ.get`` calls in pipeline modules pick up the value automatically.
Existing env-var values always win over the config file.

Usage::

    from backend.src.anim.config import load_asp_config
    load_asp_config()  # reads asp_config.toml if present in cwd

Example ``asp_config.toml``::

    [frame_selection]
    ASP_NEAR_DUP_LUMA = 5.0
    ASP_HOLD_THRESHOLD = 0.03

    [compositing]
    ASP_SP_SOFT_PX = 6
    ASP_GATE_GHOST_FLOOR = 40.0
    ASP_POISSON_SEAM = 0

    [pipeline]
    ASP_COV_MIN_MULTI_PCT = 0.30

All keys are optional; unrecognised keys are silently accepted (forwarded as
env vars).  Values must be numeric (int/float) or boolean — TOML strings are
forwarded as-is.
"""

from __future__ import annotations

import os
import tomllib
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__all__ = ["load_asp_config", "validate_asp_config"]

_DEFAULT_CONFIG_NAME = "asp_config.toml"

# §1.8B — Schema for known ASP env-var keys.
# Tuple: (expected_type, min_val, max_val, description)
# min_val / max_val are None when the bound is open.
_CONFIG_SCHEMA: Dict[str, Tuple] = {
    "ASP_HOLD_THRESHOLD": (float, 0.0, 1.0, "MAD hold-detection threshold [0, 1]"),
    "ASP_NEAR_DUP_LUMA": (float, 0.0, 255.0, "Near-dup luma floor (luma units 0–255)"),
    "ASP_COV_MIN_MULTI_PCT": (
        float,
        0.0,
        1.0,
        "Min multi-frame canvas coverage [0, 1]",
    ),
    "ASP_SP_SOFT_PX": (int, 0, None, "Single-pose feather half-width (px, 0=off)"),
    "ASP_GATE_GHOST_FLOOR": (
        float,
        0.0,
        None,
        "Ghost gate absolute floor (luma units)",
    ),
    "ASP_POISSON_SEAM": (int, 0, 1, "Enable Poisson seam blend (0 or 1)"),
    "ASP_TOONCRAFTER_SEAM": (int, 0, 1, "Enable ToonCrafter seam fill (0 or 1)"),
    "ASP_SCANS_RELOAD": (int, 0, 1, "Reload SCANS frames on demand (0 or 1)"),
    "ASP_TEMPORAL_VAR_THRESH": (
        float,
        0.0,
        None,
        "Temporal variance pre-filter threshold",
    ),
    "ASP_HIGH_HOLD_RESPONSE": (
        float,
        0.0,
        1.0,
        "Phase-corr response floor for hold merge",
    ),
    "ASP_BA_F_SCALE": (float, 0.01, None, "GNC Cauchy f_scale for bundle adjustment"),
    "ASP_POSE_WINDOW_PX": (int, 0, None, "DINOv2 pose-selection window (px, 0=off)"),
    "ASP_SGM_PROXY": (int, 0, 1, "Enable SLIC SGM flow proxy (0 or 1)"),
    "ASP_TWO_CHANNEL_SELECT": (
        int,
        0,
        1,
        "Enable BiRefNet two-channel selection (0/1)",
    ),
    "ASP_HOLD_DHASH_THRESH": (
        int,
        0,
        64,
        "dHash Hamming threshold for hold detection (0=off)",
    ),
    "ASP_MULTISCALE_GAIN": (int, 0, 1, "Enable multi-scale spatial gain map (0 or 1)"),
    "ASP_SIMILARITY_MODE": (
        int,
        0,
        1,
        "Use similarity (scale+rot+tx) instead of translation-only matching (0 or 1)",
    ),
    "ASP_HISTOGRAM_MATCH": (
        int,
        0,
        1,
        "Enable CDF histogram matching for bg normalisation (0 or 1)",
    ),
    "ASP_EXPOSURE_OUTLIER_THRESH": (
        float,
        0.0,
        255.0,
        "Max bg-lum deviation from median before norm skip (0=off)",
    ),
    "ASP_SCENE_CHANGE_LUMA_THRESH": (
        float,
        0.0,
        255.0,
        "Max mean-luma diff between frames before edge rejection (0=off)",
    ),
    "ASP_SCENE_CHANGE_BGR_THRESH": (
        float,
        0.0,
        255.0,
        "Max per-channel (BGR) mean diff between frames before edge rejection (0=off)",
    ),
    "ASP_SEAM_COLOR_GATE": (
        float,
        0.0,
        1.0,
        "Min Bhattacharyya colour similarity across seam to pass composite gate (0=off)",
    ),
    "ASP_SEAM_COLOR_GATE_BGR": (
        int,
        0,
        1,
        "Use per-channel BGR Bhattacharyya instead of greyscale in seam colour gate (0 or 1)",
    ),
    "ASP_MST_MIN_WEIGHT": (
        float,
        0.0,
        1.0,
        "Min mean MST edge weight before pre-BA SCANS fallback (0=off)",
    ),
    "ASP_CANVAS_SPAN_MIN_UTIL": (
        float,
        0.0,
        1.0,
        "Min canvas-span/expected-span utilisation ratio after BA (0=off)",
    ),
    "ASP_ADAPTIVE_SP_THRESH": (
        int,
        0,
        1,
        "Enable adaptive single-pose escalation threshold scaled by feather width (0 or 1)",
    ),
    "ASP_FG_FEATHER_CAP": (
        int,
        0,
        300,
        "Cap feather (px) in fg-dominated seam zones (0=off)",
    ),
    "ASP_FG_FEATHER_THRESH": (
        float,
        0.0,
        1.0,
        "Fg fraction threshold above which feather cap fires (default 0.60)",
    ),
    "ASP_TIGHT_STEP_PX": (
        int,
        0,
        500,
        "Dominant-axis step (px) below which seam is preemptively single-posed (0=off)",
    ),
    "ASP_SEAM_LUM_EQ": (
        int,
        0,
        1,
        "Enable post-composite seam luminance equalisation pass (0 or 1)",
    ),
    "ASP_ADAPTIVE_SP_SOFT": (
        int,
        0,
        1,
        "Enable adaptive single-pose soft-edge width scaled by feather (0 or 1)",
    ),
    "ASP_SEAM_HARD_BARRIER": (
        int,
        0,
        1,
        "Upgrade fg-column barrier from soft (2.0) to hard (1e6) when corridor exists (0 or 1)",
    ),
    "ASP_SEAM_HARD_BARRIER_COST": (
        float,
        0.0,
        None,
        "Hard barrier cost for fg-dominated seam columns (default 1e6)",
    ),
    "ASP_SEAM_STEP_GATE": (
        float,
        0.0,
        255.0,
        "Max luma step at seam boundary before SCANS fallback (0=off, recommend 25.0)",
    ),
    "ASP_SEAM_SMOOTH_WINDOW": (
        int,
        0,
        51,
        "Median-filter window for seam path jitter removal (0 or 1 = off, recommend 5)",
    ),
    "ASP_SEAM_MARGIN": (
        int,
        0,
        50,
        "Min rows between seam path and zone top/bottom edge (0 = off, recommend 3)",
    ),
    "ASP_BG_NORM_MIN_PX": (
        int,
        0,
        10000,
        "Min background pixels for gain normalisation (0 = use built-in 200-px floor)",
    ),
    "ASP_SEAM_INSTABILITY_THRESH": (
        float,
        0.0,
        500.0,
        "Max seam path std (rows) before single-pose escalation (0=off, recommend 20.0)",
    ),
    "ASP_STATIC_INPUT_MAX_MAD": (
        float,
        0.0,
        255.0,
        "MAD ceiling for static-input detection (0=off, recommend 2.0; exits early with frame-0 copy)",
    ),
    "ASP_ZONE_MIN_HEIGHT": (
        int,
        0,
        500,
        "Min blend-zone rows before single-pose escalation without DP (0=off, recommend 20)",
    ),
    "ASP_SEAM_FG_PENETRATION_MAX": (
        float,
        0.0,
        1.0,
        "Max fraction of seam columns through fg before single-pose escalation (0=off, recommend 0.7)",
    ),
    "ASP_GNC_OUTER": (
        int,
        0,
        20,
        "GNC-TLS outer iterations (0=Cauchy only, default 8)",
    ),
    "ASP_USE_SAM2": (
        int,
        0,
        1,
        "Use SAM-2 video predictor for temporally consistent fg masking (0=off, 1=on)",
    ),
    "ASP_OTSU_BG_CORR": (
        int,
        0,
        1,
        "Per-pair Otsu bg mask for phase correlation §1A (0=off, 1=on; no new deps)",
    ),
    "ASP_BG_COMPLETE": (
        int,
        0,
        1,
        "Background zero-coverage fill after temporal median §5A (0=off, 1=NN fill, 2=ProPainter)",
    ),
    "ASP_BG_COMPLETE_MIN_ROWS": (
        int,
        0,
        10000,
        "Minimum empty-pixel rows before bg completion runs (0=always, default 20)",
    ),
    "ASP_TRI_CONSISTENCY": (
        float,
        0.0,
        10000.0,
        "§2.14: Triangular consistency residual threshold (px); penalises weakest edge in bad triangles (0=off, recommended 80.0)",
    ),
    "ASP_SEAM_OVERLAY": (
        int,
        0,
        1,
        "§2.4B: Draw coloured seam-quality diagnostic lines on composite output (0=off, 1=on)",
    ),
    "ASP_BLUR_REJECT_THRESH": (
        float,
        0.0,
        None,
        "§1.2E: Laplacian variance floor (uint8 scale) for blur pre-rejection (0=off, suggest 50.0)",
    ),
    "ASP_SEAM_LOW_TEXTURE_THRESH": (
        float,
        0.0,
        None,
        "§1.34: Laplacian variance floor (uint8 scale) for flat-zone seam pre-escalation (0=off, suggest 5.0)",
    ),
    "ASP_LINE_GRAD_WEIGHT": (
        float,
        0.0,
        None,
        "§1.35: Additive cost weight [0, weight] for fg-interior gradient penalty in seam DP (0=off, suggest 1.0)",
    ),
    "ASP_MATCH_SPREAD_CEIL": (
        float,
        0.0,
        None,
        "§1.36: Max allowed MAD of LoFTR per-match dx/dy displacements (px) before rejecting edge (0=off, suggest 30.0)",
    ),
    "ASP_MIN_BG_FRACTION": (
        float,
        0.0,
        1.0,
        "§1.37: Minimum mean bg-pixel fraction across frames after Stage 4; below → SCANS fallback (0=off, suggest 0.05)",
    ),
    "ASP_LOFTR_BG_RATIO_MIN": (
        float,
        0.0,
        1.0,
        "§1.38: Minimum fraction of LoFTR matches on background pixels before rejecting LoFTR edge (0=off, suggest 0.15)",
    ),
    "ASP_RENDER_MIN_COVERAGE": (
        float,
        0.0,
        1.0,
        "§1.39: Minimum fraction of canvas pixels covered by ≥1 warped frame after Stage 10; below → SCANS fallback (0=off, suggest 0.30)",
    ),
    "ASP_ADAPTIVE_RENDER_GAIN": (
        int,
        0,
        1,
        "§1.40: Enable luminance-adaptive gain clamp in sequential colour correction (0=off fixed ±12%, 1=adaptive ±14–26%)",
    ),
    "ASP_GAIN_DRIFT_MAX": (
        float,
        0.0,
        None,
        "§1.41: Maximum cumulative gain fold-change across all frames before resetting sequential gains to identity (0=off, suggest 2.0)",
    ),
    "ASP_INTERP_BG_FILL": (
        int,
        0,
        1,
        "§1.42: Use linear interpolation instead of nearest-neighbour copy for zero-coverage bg fill (0=off, 1=linear interp)",
    ),
    "ASP_ADJ_COVERAGE_MIN": (
        float,
        0.0,
        1.0,
        "§1.43: Minimum fraction of adjacent frame pairs (|i-j|=1) that must have ≥1 matching edge before BA; below threshold → SCANS fallback (0=off, suggest 0.60)",
    ),
    "ASP_MAX_ADJACENT_GAP_PX": (
        float,
        0.0,
        None,
        "§1.44: Maximum pixel gap between adjacent frames in the dominant scroll axis after Stage 9; BA 'stretch' artefact — gap > threshold → SCANS fallback (0=off, suggest 100.0)",
    ),
    "ASP_MAX_CANVAS_WIDTH_RATIO": (
        float,
        0.0,
        None,
        "§1.45: Maximum canvas_w / median_frame_w ratio after Stage 9; catches BA tx-drift that widens the canvas far beyond frame width in a nominally vertical-scroll sequence — ratio > threshold → SCANS fallback (0=off, suggest 1.5)",
    ),
    "ASP_CONTRAST_THRESH": (
        float,
        0.0,
        None,
        "§1.46: Pixel std floor (0–255 scale) for low-contrast frame pre-rejection; interior frames with std below threshold dropped before hold detection — catches flash/whiteout frames that offer no LoFTR/PC texture (0=off, suggest 15.0)",
    ),
    "ASP_SIGN_INCONSISTENCY_MAX": (
        float,
        0.0,
        0.5,
        "§1.47: Maximum minority-sign fraction of adjacent-edge dominant-axis displacements before BA; high rate means some edges report opposite scroll direction to the majority — sign of matching confusion → SCANS fallback (0=off, suggest 0.20)",
    ),
    "ASP_ADJ_DISP_CV_MAX": (
        float,
        0.0,
        None,
        "§1.48: Maximum coefficient of variation (std/mean) of adjacent-edge dominant-axis displacement magnitudes before BA; high CV means one or more adjacent edges report wildly different step sizes (wrong-harmonic PC peak, non-adjacent TM match) → SCANS fallback (0=off, suggest 0.50)",
    ),
    "ASP_ADJ_MIN_WEIGHT": (
        float,
        0.0,
        1.0,
        "§1.49: Minimum allowed match-confidence weight for any single adjacent edge (|i-j|=1) before BA; a near-zero weight means that pair has no reliable displacement, making its compositing seam ill-placed even if BA solves cleanly → SCANS fallback (0=off, suggest 0.20)",
    ),
    "ASP_BA_RESIDUAL_MAX": (
        float,
        0.0,
        None,
        "§1.50: Maximum per-edge BA residual (L2, pixels) after Stage 7 bundle adjustment; residual = |observed_disp − (affine[j].t − affine[i].t)|; outlier edges that survive GNC/Cauchy weighting still produce large residuals in the solved frame placement (Category B failure) → SCANS fallback (0=off, suggest 200.0)",
    ),
    "ASP_MIN_ADJACENT_OVERLAP_PX": (
        float,
        0.0,
        None,
        "§1.51: Minimum canvas-space overlap (pixels) between each consecutive frame pair after BA; overlap < floor means the blend zone is too narrow for reliable DP seam cutting or FEATHER_MIN=80 feathering — complementary to §1.44 (gap gate) which fires for negative overlap → SCANS fallback (0=off, suggest 20.0)",
    ),
    "ASP_BA_WMEAN_RESIDUAL_MAX": (
        float,
        0.0,
        None,
        "§1.52: Maximum confidence-weighted mean per-edge BA residual (L2, pixels); Σ(w_i×r_i)/Σ(w_i) where r_i=‖observed−predicted‖; catches systematic BA drift where all edges are moderately wrong (40–60px), passing §1.50 max-residual gate but indicating unreliable global frame placement → SCANS fallback (0=off, suggest 30.0)",
    ),
    "ASP_CANVAS_MAX_MEMORY_MB": (
        float,
        0.0,
        None,
        "§1.53: Maximum estimated float32 RGB canvas array footprint (canvas_h × canvas_w × 3 × 4 / 1024²) in megabytes; CANVAS_MAX_DIM=32768 prevents individual extreme dimensions but not extreme products (e.g. 32768×1920≈720 MB); fires before OOM-prone allocation → SCANS fallback (0=off, suggest 2048.0)",
    ),
    "ASP_RENDER_LUMA_STD_MIN": (
        float,
        0.0,
        None,
        "§1.54: Minimum luminance std (0–255 scale, simple BGR mean per pixel) across valid canvas pixels after Stage 10 temporal render; std near zero indicates degenerate output — BaSiC over-correction fusing all frames to same mean luma, silent warp failure, or hold-block leakage; distinct from §1.39 (coverage quantity) → SCANS fallback (0=off, suggest 5.0)",
    ),
}


def validate_asp_config(
    config: Dict[str, Any],
    *,
    strict: bool = False,
) -> List[str]:
    """§1.8B: Validate a flat ASP config dict against ``_CONFIG_SCHEMA``.

    Parameters
    ----------
    config:
        Flat mapping of ASP key → value (as returned by :func:`load_asp_config`).
    strict:
        When *True*, raises :exc:`ValueError` listing all violations instead of
        returning them.  Use in CI/scripting contexts where a misconfigured
        experiment should abort immediately.

    Returns
    -------
    list[str]
        Violation messages.  Empty list means the config is valid.

    Notes
    -----
    *Unknown* keys (not in ``_CONFIG_SCHEMA``) emit a :class:`UserWarning` but
    are not counted as violations — forward-compatibility is preserved so that
    configs written for a newer pipeline version still load on an older one.

    TOML integers are accepted where *float* is expected (TOML does not
    distinguish ``0`` from ``0.0`` at the application level).
    """
    violations: List[str] = []

    for key, val in config.items():
        if key not in _CONFIG_SCHEMA:
            warnings.warn(
                f"[ASP config] Unknown key {key!r} — not in schema; forwarded as-is.",
                UserWarning,
                stacklevel=2,
            )
            continue

        expected_type, lo, hi, desc = _CONFIG_SCHEMA[key]

        # Allow int where float is expected (TOML integers → Python int)
        is_type_ok = isinstance(val, expected_type) or (
            expected_type is float and isinstance(val, int)
        )
        if not is_type_ok:
            violations.append(
                f"{key}: expected {expected_type.__name__}, "
                f"got {type(val).__name__} ({val!r}). Hint: {desc}"
            )
            continue

        numeric_val = float(val) if expected_type is float else int(val)
        if lo is not None and numeric_val < lo:
            violations.append(f"{key}={val!r} is below minimum {lo}. Hint: {desc}")
        if hi is not None and numeric_val > hi:
            violations.append(f"{key}={val!r} exceeds maximum {hi}. Hint: {desc}")

    if strict and violations:
        raise ValueError(
            "ASP config validation failed:\n"
            + "\n".join(f"  • {v}" for v in violations)
        )

    return violations


def load_asp_config(
    path: Optional[str] = None,
    *,
    override_env: bool = True,
    validate: bool = False,
    strict: bool = False,
) -> Dict[str, Any]:
    """Load ASP pipeline configuration from a TOML file.

    Parameters
    ----------
    path:
        Path to the TOML file.  Defaults to ``asp_config.toml`` in the
        current working directory.  If the file does not exist the function
        returns an empty dict without error.
    override_env:
        When *True* (default), each loaded key is written to ``os.environ``
        via ``setdefault`` so downstream modules see it.  Set to *False* to
        load values for inspection only, without touching the environment.
    validate:
        When *True*, run :func:`validate_asp_config` on the loaded dict before
        writing env vars.  Invalid keys emit warnings (or raise, if *strict*).
    strict:
        Passed to :func:`validate_asp_config` when *validate* is *True*.
        Raises :exc:`ValueError` on the first batch of violations.

    Returns
    -------
    dict
        Flat mapping of all keys found in the TOML file (sections merged).
        Empty if the file is absent or contains no section data.
    """
    config_path = Path(path) if path is not None else Path(_DEFAULT_CONFIG_NAME)
    if not config_path.exists():
        return {}

    with open(config_path, "rb") as fh:
        raw: Dict[str, Any] = tomllib.load(fh)

    flat: Dict[str, Any] = {}
    for value in raw.values():
        if isinstance(value, dict):
            flat.update(value)

    if not flat:
        return {}

    if validate:
        validate_asp_config(flat, strict=strict)

    if override_env:
        for key, val in flat.items():
            if isinstance(val, bool):
                os.environ.setdefault(key, "1" if val else "0")
            else:
                os.environ.setdefault(key, str(val))

    return flat
