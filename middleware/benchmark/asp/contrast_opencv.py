"""Stage-by-stage contrast of ASP against OpenCV's SCANS stitcher, one dataset.

OpenCV's SCANS pipeline is ORB features -> all-pairs affine-partial matching
-> biggest confident component -> affine estimator -> partial-affine BA ->
graph-cut seams -> 5-band multiband blend. This harness records each of those
stages, runs ASP on the same frames, and lines the two up:

* frames each side kept, pair graphs (OpenCV's all-pairs confidence vs ASP's
  proposed / matched / filtered edges), and per-frame pose disagreement;
* a 2x2 factorial on geometry x compositing, scored by the bench's GT SSIM:
  ``cv_geom+cv_comp`` (OpenCV), ``asp_geom+cv_comp`` (ASP poses through an
  OpenCV composer replica), ``asp_geom+asp_comp`` (raw ASP);
* ``--inject-opencv-edges``: a second ASP run whose pairwise matcher is
  replaced by OpenCV's, isolating matching from ASP's filter/BA/render.

The composer replica reproduces OpenCV's frame placement exactly; its own
``cv_geom+cv_comp (replica)`` row is the baseline the ASP-pose row compares
against, since graph-cut seams can land slightly differently. Outputs go to ``--out`` (keep it under ~/Downloads/Data/Tests/).

Usage::

    python middleware/benchmark/asp/contrast_opencv.py ~/Downloads/Data/Dump/asp_test03 \
        --out ~/Downloads/Data/Tests/asp-contrast/asp_test03 [--opencv-only] \
        [--inject-opencv-edges] [--inject-masked]

One dataset per call. Corpus sweeps are benchmark runs: request them via
Codex on the bus (AGENTS.md resource rule).
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
import time
import types
from pathlib import Path
from typing import Any

import cv2
import numpy as np

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from middleware.src.stitching.alignment.canvas import (  # noqa: E402
    _largest_valid_rect,
    _load_frames,
    _normalise_widths,
    _scan_stitch_attempts,
)
from middleware.src.stitching.ingestion.frame_selection.selector import (  # noqa: E402
    smart_select_frames,
)

# Stitcher::create(SCANS) defaults (OpenCV 4.x stitcher.cpp).
_SEAM_MEGAPIX = 0.1
_CONF_THRESH = 1.0
_BLEND_BANDS = 5


# ── frames ──────────────────────────────────────────────────────────────────


def bench_frame_paths(dataset_dir: str) -> list[str]:
    """The bench's frame list: same glob, filters and smart selection."""
    all_imgs = sorted(
        glob.glob(os.path.join(dataset_dir, "*.png"))
        + glob.glob(os.path.join(dataset_dir, "*.jpg"))
    )
    paths = [
        p
        for p in all_imgs
        if not any(t in os.path.basename(p) for t in ("panorama", "test_", "stage"))
    ]
    return smart_select_frames(paths, min_step_px=50.0)


def load_frames(paths: list[str]) -> list[np.ndarray]:
    return _normalise_widths([cv2.imread(p) for p in paths])


# ── OpenCV stages ────────────────────────────────────────────────────────────


def _work_scale(img: np.ndarray, megapix: float) -> float:
    return min(1.0, math.sqrt(megapix * 1e6 / (img.shape[0] * img.shape[1])))


def opencv_features_and_matches(
    frames: list[np.ndarray],
    registration_resol: float,
    masks: list[np.ndarray | None] | None = None,
) -> tuple[list, list, float]:
    """Stitcher's registration front half: ORB at the registration scale,
    then AffineBestOf2NearestMatcher(full_affine=False) over all pairs."""
    ws = _work_scale(frames[0], registration_resol)
    finder = cv2.ORB_create()
    feats = []
    for idx, img in enumerate(frames):
        small = cv2.resize(img, None, fx=ws, fy=ws, interpolation=cv2.INTER_LINEAR_EXACT)
        mask = None
        if masks is not None and masks[idx] is not None:
            mask = cv2.resize(
                (masks[idx] > 0).astype(np.uint8) * 255,
                (small.shape[1], small.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            )
        feat = cv2.detail.computeImageFeatures2(finder, small, mask)
        feat.img_idx = idx
        feats.append(feat)
    matcher = cv2.detail_AffineBestOf2NearestMatcher(False, False)
    pairwise = matcher.apply2(feats)
    matcher.collectGarbage()
    return feats, pairwise, ws


def pair_matrix(pairwise: list, n: int, ws: float) -> list[dict]:
    """Every i<j pair OpenCV scored, with its full-resolution translation."""
    rows = []
    for i in range(n):
        for j in range(i + 1, n):
            mi = pairwise[i * n + j]
            H = mi.H
            t = None
            if H is not None and np.size(H) == 9:
                t = [float(H[0, 2]) / ws, float(H[1, 2]) / ws]
            rows.append(
                {
                    "i": i,
                    "j": j,
                    "confidence": round(float(mi.confidence), 4),
                    "matches": len(mi.matches),
                    "inliers": int(mi.num_inliers),
                    "t": t,
                }
            )
    return rows


def _camera_forward(R, work_scale: float) -> np.ndarray:
    """Frame->pano affine of a SCANS camera at full resolution.

    AffineWarper::getRTfromHomogeneous turns camera ``[A|t]`` into plane
    warper ``R = A^T``, ``T = -A^T t`` (a transpose, not an inverse), and
    composePanorama scales T by 1/workScale (focal 1). So the forward map is
    ``p -> A^T p - A^T t / workScale``.
    """
    H = np.asarray(R, np.float64)
    At = H[:2, :2].T
    return np.hstack([At, (-At @ H[:2, 2] / work_scale)[:, None]])


def run_opencv(frames: list[np.ndarray], paths: list[str]) -> dict[str, Any]:
    """The bench's SCANS ladder, keeping cameras from the attempt that wins."""
    cv2.ocl.setUseOpenCL(False)
    out: dict[str, Any] = {"attempts": []}
    for name, idx, mode, resol in _scan_stitch_attempts(len(frames)):
        sub = [frames[i] for i in idx]
        stitcher = cv2.Stitcher_create(mode)
        stitcher.setRegistrationResol(resol)
        t0 = time.perf_counter()
        status = int(stitcher.estimateTransform(sub))
        pano = None
        if status == cv2.Stitcher_OK:
            status, pano = stitcher.composePanorama()
            status = int(status)
        out["attempts"].append(
            {"name": name, "n": len(sub), "status": status, "sec": round(time.perf_counter() - t0, 2)}
        )
        if status != cv2.Stitcher_OK or pano is None:
            continue
        comp = [idx[int(c)] for c in stitcher.component()]
        fwd = [_camera_forward(c.R, stitcher.workScale()) for c in stitcher.cameras()]
        out.update(
            attempt=name,
            mode=mode,
            registration_resol=resol,
            component=comp,
            component_paths=[os.path.basename(paths[i]) for i in comp],
            dropped_by_component=[os.path.basename(paths[i]) for i in idx if i not in comp],
            forward=fwd,
            pano=pano,
        )
        if mode == 1:
            feats, pairwise, ws = opencv_features_and_matches(sub, resol)
            replica = [idx[int(c)] for c in cv2.detail.leaveBiggestComponent(feats, pairwise, _CONF_THRESH)]
            out["n_keypoints"] = {
                os.path.basename(paths[idx[k]]): len(f.getKeypoints()) for k, f in enumerate(feats)
            }
            out["pairs"] = [
                {**row, "i": idx[row["i"]], "j": idx[row["j"]]}
                for row in pair_matrix(pairwise, len(sub), ws)
            ]
            out["replica_component_matches"] = sorted(replica) == sorted(comp)
        return out
    out["attempt"] = None
    return out


# ── composer replica ─────────────────────────────────────────────────────────


def _warp(img: np.ndarray, fwd: np.ndarray, scale: float, interp: int, border: int):
    """Warp ``img`` by frame->pano ``fwd`` at ``scale``; return (warped, corner)."""
    # At scale s the source is resized by s, so only the translation scales.
    A = np.asarray(fwd, np.float64).copy()
    A[:, 2] *= scale
    src = img if scale == 1.0 else cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR_EXACT)
    h, w = src.shape[:2]
    c = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float64)
    pts = c @ A[:, :2].T + A[:, 2]
    x0, y0 = np.floor(pts.min(axis=0)).astype(int)
    x1, y1 = np.ceil(pts.max(axis=0)).astype(int)
    A[:, 2] -= (x0, y0)
    warped = cv2.warpAffine(src, A, (int(x1 - x0), int(y1 - y0)), flags=interp, borderMode=border)
    return warped, (int(x0), int(y0))


def compose_opencv_style(frames: list[np.ndarray], forward: list[np.ndarray]) -> np.ndarray:
    """Stitcher::composePanorama for SCANS on arbitrary frame->pano affines:
    graph-cut (COST_COLOR) seams at 0.1 MP, no exposure compensation,
    5-band multiband blend at full resolution."""
    ss = _work_scale(frames[0], _SEAM_MEGAPIX)
    ones = [np.full(f.shape[:2], 255, np.uint8) for f in frames]
    seam_imgs, seam_masks, seam_corners = [], [], []
    for f, m, A in zip(frames, ones, forward, strict=True):
        wi, c = _warp(f, A, ss, cv2.INTER_LINEAR, cv2.BORDER_REFLECT)
        wm, _ = _warp(m, A, ss, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT)
        seam_imgs.append(wi.astype(np.float32))
        seam_masks.append(wm)
        seam_corners.append(c)
    seams = cv2.detail_GraphCutSeamFinder("COST_COLOR").find(seam_imgs, seam_corners, seam_masks)

    blender = cv2.detail_MultiBandBlender(0, _BLEND_BANDS)
    warped, corners = [], []
    for k, (f, m, A) in enumerate(zip(frames, ones, forward, strict=True)):
        wi, c = _warp(f, A, 1.0, cv2.INTER_LINEAR, cv2.BORDER_REFLECT)
        wm, _ = _warp(m, A, 1.0, cv2.INTER_NEAREST, cv2.BORDER_CONSTANT)
        seam = seams[k].get() if hasattr(seams[k], "get") else seams[k]
        seam = cv2.resize(cv2.dilate(seam, None), (wm.shape[1], wm.shape[0]), interpolation=cv2.INTER_LINEAR_EXACT)
        warped.append((wi, cv2.bitwise_and(seam, wm)))
        corners.append(c)
    sizes = [(w.shape[1], w.shape[0]) for w, _ in warped]
    blender.prepare(cv2.detail.resultRoi(corners=corners, sizes=sizes))
    for (wi, wm), c in zip(warped, corners, strict=True):
        blender.feed(wi.astype(np.int16), wm, c)
    result, _ = blender.blend(None, None)
    return np.clip(result, 0, 255).astype(np.uint8)


def crop_valid(img: np.ndarray) -> np.ndarray:
    x0, y0, x1, y1 = _largest_valid_rect(img.max(axis=2) > 0)
    return img[y0:y1, x0:x1] if x1 > x0 and y1 > y0 else img


# ── ASP ──────────────────────────────────────────────────────────────────────


def _kept_paths(session) -> list[str]:
    return [row["path"] for row in session.frame_provenance if row.get("kept")]


def _edge_rows(edges: list[dict], paths: list[str]) -> list[dict]:
    rows = []
    for e in edges:
        M = np.asarray(e["M"], np.float64)
        rows.append(
            {
                "a": os.path.basename(paths[e["i"]]),
                "b": os.path.basename(paths[e["j"]]),
                "span": int(e["j"]) - int(e["i"]),
                "t": [float(M[0, 2]), float(M[1, 2])],
                "weight": round(float(e.get("weight", 0.0)), 4),
            }
        )
    return rows


def _opencv_edges(frames, bg_masks, motion_model: str, use_masks: bool) -> list[dict]:
    """OpenCV's pairwise matches on ASP's own frames, in ASP's edge format
    (M maps frame-i points to frame-j points; pts are inlier keypoints)."""
    from middleware.src.stitching.alignment.matching._pairwise import _ransac_metrics

    u8 = [f if f.dtype == np.uint8 else np.clip(f, 0, 255).astype(np.uint8) for f in frames]
    masks = bg_masks if use_masks else None
    feats, pairwise, ws = opencv_features_and_matches(u8, 0.8, masks)
    n = len(frames)
    edges = []
    for i in range(n):
        kp_i = feats[i].getKeypoints()
        for j in range(i + 1, n):
            mi = pairwise[i * n + j]
            if mi.confidence < _CONF_THRESH or mi.H is None or np.size(mi.H) != 9:
                continue
            M = np.asarray(mi.H, np.float64)[:2].astype(np.float32)
            M[:, 2] /= ws
            if motion_model == "translation":
                M[:, :2] = np.eye(2, dtype=np.float32)
            kp_j = feats[j].getKeypoints()
            keep = [m for m, ok in zip(mi.matches, np.ravel(mi.inliers_mask), strict=False) if ok]
            pts_i = np.float32([kp_i[m.queryIdx].pt for m in keep]) / ws
            pts_j = np.float32([kp_j[m.trainIdx].pt for m in keep]) / ws
            edges.append(
                {
                    "i": i,
                    "j": j,
                    "M": M,
                    "pts_i": pts_i,
                    "pts_j": pts_j,
                    "weight": float(min(1.0, mi.confidence)),
                    "registration_metrics": _ransac_metrics(pts_i, pts_j),
                }
            )
    return edges


def run_asp(
    paths: list[str], out_dir: str, *, inject_opencv: bool = False, inject_masked: bool = False
) -> dict[str, Any]:
    from middleware.src.stitching.core.pipeline.bench_adapter import (
        _affines_from_session,
        apply_ungated_gate_env,
    )
    from middleware.src.stitching.core.pipeline.manager import AnimeStitchPipeline
    from middleware.src.stitching.core.pipeline.session import (
        PipelineSession,
        snapshot_pipeline_config,
    )

    apply_ungated_gate_env()  # the bench does this before every canonical run
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "asp_output.png")
    pipe = AnimeStitchPipeline()  # product defaults (renderer: seam)
    session = PipelineSession.create(paths, work, config=snapshot_pipeline_config(pipe))
    spy: dict[str, Any] = {}

    real_match = pipe._pairwise_match_with
    real_filter = pipe._filter_edges

    def match(self, frames, bg_masks, active_loftr, proposal_telemetry=None):
        if inject_opencv:
            edges = _opencv_edges(frames, bg_masks, self.motion_model, inject_masked)
        else:
            edges = real_match(frames, bg_masks, active_loftr, proposal_telemetry=proposal_telemetry)
        spy.setdefault("matched", _edge_rows(edges, _kept_paths(session)))
        return edges

    def filt(self, edges, image_paths, *args, **kwargs):
        kept = real_filter(edges, image_paths, *args, **kwargs)
        spy.setdefault("filter_in", _edge_rows(edges, image_paths))
        spy.setdefault("filter_out", _edge_rows(kept, image_paths))
        return kept

    pipe._pairwise_match_with = types.MethodType(match, pipe)
    pipe._filter_edges = types.MethodType(filt, pipe)

    t0 = time.perf_counter()
    error = None
    try:
        pipe.run(paths, work, session=session)
    except Exception as exc:  # a failed run is a finding, not a harness crash
        error = f"{type(exc).__name__}: {exc}"
    session = pipe.last_session or session
    kept = _kept_paths(session)
    affines = _affines_from_session(session)
    art = session.artifacts
    return {
        "sec": round(time.perf_counter() - t0, 1),
        "error": error,
        "identity": str(session.identity) if session.identity else None,
        "fallbacks": [
            {"identity": str(f.get("identity")), "reason": f.get("reason")} for f in session.fallbacks
        ],
        "kept_paths": [os.path.basename(p) for p in kept],
        "dropped": [
            {"path": os.path.basename(r["path"]), "reason": r.get("drop_reason")}
            for r in session.frame_provenance
            if not r.get("kept")
        ],
        "edge_stage_counts": art.get("edge_stage_counts"),
        "edge_graph_connected": art.get("edge_graph_connected"),
        "affine_health": art.get("affine_health"),
        "edges": spy,
        "affines": affines if len(affines) == len(kept) else [],
        "output": work if os.path.isfile(work) else None,
    }


# ── contrast ─────────────────────────────────────────────────────────────────


def pose_disagreement(
    names_a: list[str], fwd_a: list, names_b: list[str], fwd_b: list
) -> dict[str, Any] | None:
    """Translation disagreement of each common frame relative to the first
    common frame: |inv(F_ref) F_k| compared across the two pose sets."""
    common = [n for n in names_a if n in names_b]
    if len(common) < 2:
        return None

    def rel(names, fwd):
        F = {n: np.vstack([np.asarray(f, np.float64), [0, 0, 1]]) for n, f in zip(names, fwd, strict=True)}
        ref = np.linalg.inv(F[common[0]])
        return {n: (ref @ F[n])[:2, 2] for n in common}

    ra, rb = rel(names_a, fwd_a), rel(names_b, fwd_b)
    err = {n: float(np.linalg.norm(ra[n] - rb[n])) for n in common}
    vals = list(err.values())
    return {
        "reference": common[0],
        "n_common": len(common),
        "median_px": round(float(np.median(vals)), 2),
        "max_px": round(float(np.max(vals)), 2),
        "per_frame_px": {n: round(v, 2) for n, v in err.items()},
    }


def pair_contrast(cv: dict, asp: dict, names: list[str]) -> dict[str, Any]:
    """Pairs OpenCV trusts (confidence >= 1) against what ASP proposed,
    matched, and kept after filtering."""
    if "pairs" not in cv:
        return {}
    keyed = lambda rows: {(r["a"], r["b"]): r for r in rows}  # noqa: E731
    matched = keyed(asp["edges"].get("matched", []))
    f_in = keyed(asp["edges"].get("filter_in", []))
    f_out = keyed(asp["edges"].get("filter_out", []))
    trusted, lost = [], []
    for row in cv["pairs"]:
        if row["confidence"] < _CONF_THRESH or row["t"] is None:
            continue
        key = (names[row["i"]], names[row["j"]])
        entry = {
            "pair": key,
            "span": row["j"] - row["i"],
            "cv_conf": row["confidence"],
            "cv_inliers": row["inliers"],
            "cv_t": [round(v, 1) for v in row["t"]],
            "asp_matched": key in matched,
            "asp_t": [round(v, 1) for v in matched[key]["t"]] if key in matched else None,
            "asp_filtered_in": key in f_in,
            "asp_kept": key in f_out,
        }
        trusted.append(entry)
        if not entry["asp_kept"]:
            lost.append(entry)
    return {
        "opencv_trusted_pairs": len(trusted),
        "asp_matched_of_trusted": sum(e["asp_matched"] for e in trusted),
        "asp_kept_of_trusted": sum(e["asp_kept"] for e in trusted),
        "trusted_spans": sorted({e["span"] for e in trusted}),
        "lost": lost,
    }


def _gt_ssim(img: np.ndarray | None, gt: np.ndarray | None) -> float | None:
    if img is None or gt is None:
        return None
    # Scored with the bench's own metric, loaded lazily (heavy import).
    import importlib.util

    name = "_contrast_bench"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name("bench_anime_stitch.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return round(float(sys.modules[name]._compute_aligned_ssim(img, gt)), 4)


def _load_gt(dataset_dir: str) -> np.ndarray | None:
    name = os.path.basename(os.path.normpath(dataset_dir))
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(os.path.dirname(os.path.normpath(dataset_dir)), "ground_truth", name + ext)
        if os.path.exists(p):
            return cv2.imread(p)
    return None


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k) if not isinstance(k, str) else k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.round(4).tolist()
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    return obj


def contrast(dataset_dir: str, out_dir: str, args) -> dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    paths = bench_frame_paths(dataset_dir)
    names = [os.path.basename(p) for p in paths]
    frames = load_frames(paths)
    gt = _load_gt(dataset_dir)
    report: dict[str, Any] = {
        "dataset": os.path.basename(os.path.normpath(dataset_dir)),
        "n_frames": len(paths),
        "frame_size": list(frames[0].shape[:2]),
        "has_gt": gt is not None,
        "outputs": {},
    }

    cv = run_opencv(frames, paths)
    pano_cv = cv.pop("pano", None)
    fwd_cv = cv.pop("forward", None)
    report["opencv"] = cv
    if pano_cv is not None:
        pano_cv = crop_valid(pano_cv)
        cv2.imwrite(os.path.join(out_dir, "cv_geom+cv_comp.png"), pano_cv)
        report["outputs"]["cv_geom+cv_comp"] = {"shape": list(pano_cv.shape[:2]), "gt_ssim": _gt_ssim(pano_cv, gt)}
        if cv.get("mode") == 1:
            # Placement matches the warper exactly; graph-cut seams can still
            # land differently, so asp_geom+cv_comp is compared against this
            # replica row, not against the Stitcher's own output.
            replica = crop_valid(compose_opencv_style([frames[i] for i in cv["component"]], fwd_cv))
            cv2.imwrite(os.path.join(out_dir, "cv_geom+cv_comp_replica.png"), replica)
            report["outputs"]["cv_geom+cv_comp (replica)"] = {
                "shape": list(replica.shape[:2]),
                "gt_ssim": _gt_ssim(replica, gt),
            }

    if args.opencv_only:
        return report

    asp = run_asp(paths, os.path.join(out_dir, "asp"))
    affines = asp.pop("affines")
    report["asp"] = asp
    report["pairs"] = pair_contrast(cv, asp, names)
    if asp["output"]:
        img = cv2.imread(asp["output"])
        key = "asp_geom+asp_comp" if asp["identity"] == "raw_asp" else f"asp published ({asp['identity']})"
        report["outputs"][key] = {"shape": list(img.shape[:2]), "gt_ssim": _gt_ssim(img, gt)}
    if affines:
        # ASP's poses were estimated on its own loaded frames (dark-border
        # trim applied), so compose those, not the untrimmed harness frames.
        # Load the full input set: ASP_DARK_TRIM=sequence picks its box from it.
        asp_frames = _normalise_widths(_load_frames(paths))
        kept = [asp_frames[names.index(n)] for n in asp["kept_paths"]]
        mixed = crop_valid(compose_opencv_style(kept, affines))
        cv2.imwrite(os.path.join(out_dir, "asp_geom+cv_comp.png"), mixed)
        report["outputs"]["asp_geom+cv_comp"] = {"shape": list(mixed.shape[:2]), "gt_ssim": _gt_ssim(mixed, gt)}
        if fwd_cv is not None and cv.get("mode") == 1:  # PANORAMA cameras are not affine
            report["pose_disagreement"] = pose_disagreement(
                cv["component_paths"], fwd_cv, asp["kept_paths"], affines
            )

    # Poses for offline experiments. OpenCV's are on the untrimmed harness
    # frames; ASP's are on its own loaded (dark-trimmed) frames.
    poses = {
        "cv": None if fwd_cv is None else {
            "mode": cv.get("mode"),
            "paths": cv.get("component_paths"),
            "forward": [np.asarray(f, float).tolist() for f in fwd_cv],
        },
        "asp": None if not affines else {
            "paths": asp["kept_paths"],
            "affines": [np.asarray(a, float).tolist() for a in affines],
        },
    }
    with open(os.path.join(out_dir, "poses.json"), "w") as fh:
        json.dump(poses, fh)

    if args.inject_opencv_edges:
        inj = run_asp(
            paths, os.path.join(out_dir, "asp_cv_edges"), inject_opencv=True, inject_masked=args.inject_masked
        )
        inj.pop("affines")
        report["asp_with_opencv_edges"] = inj
        if inj["output"]:
            img = cv2.imread(inj["output"])
            key = "cv_match+asp_rest" if inj["identity"] == "raw_asp" else f"cv_match+asp_rest ({inj['identity']})"
            report["outputs"][key] = {"shape": list(img.shape[:2]), "gt_ssim": _gt_ssim(img, gt)}
    return report



def summary_lines(r: dict[str, Any]) -> list[str]:
    cv, asp = r["opencv"], r.get("asp")
    lines = [f"# {r['dataset']} — ASP vs OpenCV SCANS", ""]
    lines.append(f"{r['n_frames']} frames after smart selection, {r['frame_size'][1]}x{r['frame_size'][0]}.")
    lines.append(
        f"OpenCV: attempt `{cv.get('attempt')}`, component {len(cv.get('component') or [])}/"
        f"{r['n_frames']}, dropped {cv.get('dropped_by_component') or []}."
    )
    if asp:
        fb = "; ".join(f"{f['identity']}:{f['reason']}" for f in asp["fallbacks"]) or "none"
        lines.append(
            f"ASP: identity `{asp['identity']}`, kept {len(asp['kept_paths'])}/{r['n_frames']}, "
            f"fallbacks {fb}, error {asp['error']}."
        )
        lines.append(f"ASP edge counts: {asp['edge_stage_counts']}.")
    p = r.get("pairs") or {}
    if p:
        lines.append(
            f"Pairs OpenCV trusts: {p['opencv_trusted_pairs']} (spans {p['trusted_spans']}); "
            f"ASP matched {p['asp_matched_of_trusted']}, kept after filter {p['asp_kept_of_trusted']}."
        )
    if r.get("pose_disagreement"):
        d = r["pose_disagreement"]
        lines.append(f"Pose disagreement (vs {d['reference']}): median {d['median_px']} px, max {d['max_px']} px.")
    lines += ["", "| output | size | GT SSIM |", "|---|---|---|"]
    for k, v in r["outputs"].items():
        lines.append(f"| {k} | {v['shape'][1]}x{v['shape'][0]} | {v['gt_ssim']} |")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--opencv-only", action="store_true")
    ap.add_argument("--inject-opencv-edges", action="store_true")
    ap.add_argument("--inject-masked", action="store_true", help="mask FG out of OpenCV features when injecting")
    args = ap.parse_args()
    out_dir = os.path.expanduser(args.out)
    report = contrast(os.path.expanduser(args.dataset_dir), out_dir, args)
    with open(os.path.join(out_dir, "contrast.json"), "w") as f:
        json.dump(_jsonable(report), f, indent=1)
    lines = summary_lines(report)
    with open(os.path.join(out_dir, "contrast.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
