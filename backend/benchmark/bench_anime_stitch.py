#!/usr/bin/env python3
"""
Anime Stitch Pipeline Benchmark
================================
Runs both the Anime Stitch Pipeline (ASP) and OpenCV SCANS Simple Stitch on
every asp_testX dataset in data/, then generates a comprehensive markdown
report with side-by-side comparisons, CV metrics, intermediate-output
analysis (2-D and 3-D visualizations), and structured feedback blocks for
human review and LLM-assisted iteration.
"""

import gc
import glob
import json
import math
import os
import platform
import shutil
import sys
import time
import datetime
from typing import Dict, List, Optional

import cv2
import numpy as np
import torch

sys.path.insert(0, "/home/pkhunter/Repositories/Image-Toolkit")
os.environ.setdefault("PYTORCH_ALLOC_CONF", "expandable_segments:True")

# ---------------------------------------------------------------------------
# Lazy-import heavy plotting deps so the benchmark still runs without them
# ---------------------------------------------------------------------------
try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 (registers 3-D projection)

    _MPL_OK = True
except ImportError:
    _MPL_OK = False

try:
    from skimage.metrics import structural_similarity as ssim

    _SSIM_OK = True
except ImportError:
    _SSIM_OK = False

from backend.src.anim.pipeline import AnimeStitchPipeline
from backend.src.anim.canvas import (
    _load_frames,
    _normalise_widths,
    _compute_canvas,
    _crop_to_valid,
    _scan_stitch_fallback,
)
from backend.src.anim.validation import _validate_affines
from backend.src.anim.masking import _compute_fg_masks
from backend.src.anim.matching import _pairwise_match
from backend.src.anim.bundle_adjust import _bundle_adjust_affine
from backend.src.anim.ecc import _ecc_refine
from backend.src.anim.rendering import _render_median
from backend.src.anim.compositing import _composite_foreground


# ============================================================================
# SYSTEM INFO
# ============================================================================


def _system_info() -> Dict:
    info: Dict = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu": platform.processor(),
        "cpu_count": os.cpu_count() or 0,
        "cpu_threads": 0,
        "ram_gb": 0.0,
        "gpu": "N/A",
        "cuda_version": "N/A",
        "vram_gb": 0.0,
    }
    try:
        import psutil as ps

        info["cpu_threads"] = ps.cpu_count(logical=True) or 0
        info["ram_gb"] = round(ps.virtual_memory().total / 1024**3, 1)
    except Exception:
        pass
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["cuda_version"] = torch.version.cuda or "N/A"
        props = torch.cuda.get_device_properties(0)
        info["vram_gb"] = round(props.total_memory / 1024**3, 1)
    return info


# ============================================================================
# CV METRIC HELPERS
# ============================================================================


def _sharpness(img: np.ndarray) -> float:
    """Laplacian-variance sharpness (higher = sharper)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    lap = cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F)
    return float(lap.var())


def _coverage(img: np.ndarray) -> float:
    """Fraction of non-black pixels (proxy for crop completeness)."""
    mask = img.max(axis=2) > 8 if img.ndim == 3 else img > 8
    return float(mask.sum()) / max(mask.size, 1)


def _mean_seam_gradient(
    img: np.ndarray, affines: Optional[List[np.ndarray]] = None
) -> float:
    """
    Average gradient magnitude along horizontal seam boundaries.
    Without affines, samples the whole image and returns mean gradient.
    With affines, evaluates only the seam transition rows.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gy = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    if affines is None:
        return float(np.abs(gy).mean())
    H, W = gray.shape
    seam_rows = set()
    for a in affines:
        row = round(float(a[1, 2]))
        for dr in range(-5, 6):
            r = row + dr
            if 0 <= r < H:
                seam_rows.add(r)
    if not seam_rows:
        return float(np.abs(gy).mean())
    rows = np.array(sorted(seam_rows))
    return float(np.abs(gy[rows]).mean())


def _color_entropy(img: np.ndarray) -> float:
    """Shannon entropy of luma histogram (higher = more diverse colours)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    hist = hist / max(hist.sum(), 1.0)
    hist = hist[hist > 0]
    return float(-np.sum(hist * np.log2(hist)))


def _ssim_score(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """SSIM between two images (resized to min dims if needed)."""
    if not _SSIM_OK:
        return float("nan")
    h = min(img_a.shape[0], img_b.shape[0])
    w = min(img_a.shape[1], img_b.shape[1])
    a = cv2.resize(img_a, (w, h))
    b = cv2.resize(img_b, (w, h))
    ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    score, _ = ssim(ga, gb, full=True, data_range=255)
    return float(score)


def _psnr(img_a: np.ndarray, img_b: np.ndarray) -> float:
    """PSNR (dB) between two images after resizing to common dims."""
    h = min(img_a.shape[0], img_b.shape[0])
    w = min(img_a.shape[1], img_b.shape[1])
    a = cv2.resize(img_a, (w, h)).astype(np.float32)
    b = cv2.resize(img_b, (w, h)).astype(np.float32)
    mse = float(np.mean((a - b) ** 2))
    if mse < 1e-8:
        return float("inf")
    return 20 * math.log10(255.0 / math.sqrt(mse))


def _ghosting_score(img: np.ndarray) -> float:
    """
    Proxy for ghosting: detect double-edge bands.
    High-frequency energy in a narrow band around seam transitions.
    Returns mean absolute value of second-order vertical derivative.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    g = gray.astype(np.float32)
    gy2 = cv2.Sobel(cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3), cv2.CV_32F, 0, 1, ksize=3)
    return float(np.abs(gy2).mean())


def _compute_all_metrics(img: np.ndarray, affines: Optional[List] = None) -> Dict:
    return {
        "sharpness": round(_sharpness(img), 2),
        "coverage": round(_coverage(img), 4),
        "seam_gradient": round(_mean_seam_gradient(img, affines), 3),
        "color_entropy": round(_color_entropy(img), 4),
        "ghosting_score": round(_ghosting_score(img), 4),
        "width": img.shape[1],
        "height": img.shape[0],
    }


# ============================================================================
# VISUALIZATION HELPERS
# ============================================================================


def _save_affine_path_plot(
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
    frame_h: int,
    frame_w: int,
    out_path: str,
) -> None:
    """2-D plot of frame placement on the canvas."""
    if not _MPL_OK:
        return
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_xlim(-50, canvas_w + 50)
    ax.set_ylim(canvas_h + 50, -50)
    ax.set_aspect("equal")
    ax.set_title("Frame Placement on Canvas (2D)", fontsize=11)
    ax.set_xlabel("X (px)")
    ax.set_ylabel("Y (px)")
    colors = plt.cm.plasma(np.linspace(0, 1, len(affines)))
    for idx, (M, color) in enumerate(zip(affines, colors)):
        tx = float(M[0, 2])
        ty = float(M[1, 2])
        rect = plt.Rectangle(
            (tx, ty),
            frame_w,
            frame_h,
            linewidth=1.5,
            edgecolor=color,
            facecolor=(*color[:3], 0.08),
        )
        ax.add_patch(rect)
        ax.text(
            tx + frame_w / 2,
            ty + frame_h / 2,
            str(idx),
            ha="center",
            va="center",
            fontsize=7,
            color=color,
        )
    ax.set_facecolor("#1a1a2e")
    fig.patch.set_facecolor("#12121f")
    ax.title.set_color("white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    sm = plt.cm.ScalarMappable(cmap="plasma", norm=plt.Normalize(0, len(affines) - 1))
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax)
    cbar.set_label("Frame index", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_translation_plot(
    affines: List[np.ndarray],
    out_path: str,
    title: str = "Translation Vectors per Frame",
) -> None:
    """2-D plot of tx/ty translation per frame."""
    if not _MPL_OK:
        return
    N = len(affines)
    txs = [float(M[0, 2]) for M in affines]
    tys = [float(M[1, 2]) for M in affines]
    frames = list(range(N))
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for ax, vals, label, color in zip(
        axes, [txs, tys], ["tx (horizontal)", "ty (vertical)"], ["#4ecdc4", "#ff6b6b"]
    ):
        ax.plot(frames, vals, marker="o", color=color, linewidth=2, markersize=5)
        ax.set_xlabel("Frame index")
        ax.set_ylabel(f"{label} (px)")
        ax.set_title(label)
        ax.grid(True, alpha=0.3)
        ax.set_facecolor("#1a1a2e")
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
    fig.suptitle(title, color="white")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_gains_plot(
    frame_lums: List[Optional[float]],
    gains: List[float],
    out_path: str,
) -> None:
    """Bar chart of per-frame luminance gain corrections."""
    if not _MPL_OK:
        return
    N = len(gains)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    valid = [lum if lum is not None else 0.0 for lum in frame_lums]

    ax0, ax1 = axes
    ax0.bar(range(N), valid, color="#4ecdc4", alpha=0.8)
    ax0.axhline(
        float(np.median([v for v in valid if v > 0]))
        if any(v > 0 for v in valid)
        else 0,
        color="#ff6b6b",
        linestyle="--",
        label="median",
    )
    ax0.set_title("Background Luminance per Frame")
    ax0.set_xlabel("Frame index")
    ax0.set_ylabel("Mean luminance")
    ax0.legend(facecolor="#2a2a3e", labelcolor="white")

    ax1.bar(range(N), gains, color="#ff6b6b", alpha=0.8)
    ax1.axhline(1.0, color="#4ecdc4", linestyle="--", label="gain=1.0")
    ax1.set_title("Applied Luminance Gain per Frame")
    ax1.set_xlabel("Frame index")
    ax1.set_ylabel("Gain multiplier")
    ax1.legend(facecolor="#2a2a3e", labelcolor="white")

    for ax in axes:
        ax.set_facecolor("#1a1a2e")
        ax.title.set_color("white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.tick_params(colors="white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#444")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_seam_heatmap(img: np.ndarray, out_path: str, title: str = "") -> None:
    """2-D heatmap of gradient magnitude — highlights seam artefacts."""
    if not _MPL_OK:
        return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    # Compute magnitude of gradient
    gx = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx**2 + gy**2)
    # Downsample for plotting
    scale = max(1, max(mag.shape) // 512)
    if scale > 1:
        mag = cv2.resize(mag, (mag.shape[1] // scale, mag.shape[0] // scale))
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(mag, cmap="inferno", aspect="auto")
    ax.set_title(title or "Gradient Magnitude Heatmap", color="white")
    ax.axis("off")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03)
    cbar.set_label("Gradient magnitude", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_3d_surface(img: np.ndarray, out_path: str, title: str = "") -> None:
    """3-D surface plot of pixel luminance — reveals exposure ridges/valleys."""
    if not _MPL_OK:
        return
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    # Aggressively downsample to keep rendering fast
    target = 96
    h, w = gray.shape
    sh = max(1, h // target)
    sw = max(1, w // target)
    small = gray[::sh, ::sw].astype(np.float32)
    # Smooth to reduce noise
    small = cv2.GaussianBlur(small, (5, 5), 0)
    Y, X = np.mgrid[0 : small.shape[0], 0 : small.shape[1]]
    fig = plt.figure(figsize=(9, 5))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_surface(
        X,
        Y,
        small,
        cmap="viridis",
        linewidth=0,
        antialiased=False,
        rstride=1,
        cstride=1,
        alpha=0.9,
    )
    ax.set_title(title or "Luminance Surface (3D)", color="white", pad=8)
    ax.set_xlabel("X (px ÷ " + str(sw) + ")", color="white", fontsize=7)
    ax.set_ylabel("Y (px ÷ " + str(sh) + ")", color="white", fontsize=7)
    ax.set_zlabel("Luma", color="white", fontsize=7)
    ax.tick_params(colors="white", labelsize=6)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    fig.patch.set_facecolor("#12121f")
    ax.set_facecolor("#1a1a2e")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_overlap_map(
    affines: List[np.ndarray],
    canvas_h: int,
    canvas_w: int,
    frame_h: int,
    frame_w: int,
    out_path: str,
) -> None:
    """2-D heatmap counting how many frames contribute to each canvas pixel."""
    if not _MPL_OK:
        return
    scale = max(1, max(canvas_h, canvas_w) // 512)
    ch = max(1, canvas_h // scale)
    cw = max(1, canvas_w // scale)
    acc = np.zeros((ch, cw), dtype=np.float32)
    for M in affines:
        tx = int(float(M[0, 2]) / scale)
        ty = int(float(M[1, 2]) / scale)
        fh = max(1, frame_h // scale)
        fw = max(1, frame_w // scale)
        r0, r1 = max(0, ty), min(ch, ty + fh)
        c0, c1 = max(0, tx), min(cw, tx + fw)
        if r1 > r0 and c1 > c0:
            acc[r0:r1, c0:c1] += 1.0
    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(acc, cmap="hot", aspect="auto")
    ax.set_title("Frame Overlap Count Map (2D)", color="white")
    ax.axis("off")
    cbar = fig.colorbar(im, ax=ax, fraction=0.03)
    cbar.set_label("# overlapping frames", color="white")
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_mask_overlay(
    frame: np.ndarray,
    mask: Optional[np.ndarray],
    out_path: str,
    title: str = "",
) -> None:
    """Visualize a foreground mask overlaid on the source frame."""
    if not _MPL_OK:
        return
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    overlay = rgb.copy().astype(np.float32)
    if mask is not None:
        fg = mask < 128  # fg pixels (BiRefNet: 0=foreground)
        overlay[fg, 0] = np.clip(overlay[fg, 0] * 0.4 + 200, 0, 255)
        overlay[fg, 1] = np.clip(overlay[fg, 1] * 0.4, 0, 255)
        overlay[fg, 2] = np.clip(overlay[fg, 2] * 0.4, 0, 255)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(overlay.astype(np.uint8), aspect="auto")
    ax.set_title(title or "FG mask overlay (red=foreground)", color="white")
    ax.axis("off")
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _save_metrics_bar(metrics_asp: Dict, metrics_simple: Dict, out_path: str) -> None:
    """Side-by-side bar chart comparing key CV metrics for ASP vs simple."""
    if not _MPL_OK:
        return
    keys = ["sharpness", "coverage", "seam_gradient", "color_entropy", "ghosting_score"]
    labels = [
        "Sharpness",
        "Coverage",
        "Seam\nGradient",
        "Color\nEntropy",
        "Ghosting\nScore",
    ]
    asp_vals = [metrics_asp.get(k, 0) for k in keys]
    sim_vals = [metrics_simple.get(k, 0) for k in keys]
    # Normalize each metric to [0,1] for display
    maxes = [max(a, b, 1e-9) for a, b in zip(asp_vals, sim_vals)]
    asp_n = [v / m for v, m in zip(asp_vals, maxes)]
    sim_n = [v / m for v, m in zip(sim_vals, maxes)]
    x = np.arange(len(keys))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 4))
    b1 = ax.bar(x - width / 2, asp_n, width, label="ASP", color="#4ecdc4", alpha=0.85)
    b2 = ax.bar(
        x + width / 2, sim_n, width, label="Simple", color="#ff6b6b", alpha=0.85
    )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, color="white", fontsize=9)
    ax.set_ylabel("Normalised value", color="white")
    ax.set_title("CV Metrics: ASP vs Simple Stitch (normalised)", color="white")
    ax.legend(facecolor="#2a2a3e", labelcolor="white")
    ax.set_facecolor("#1a1a2e")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    # Raw value annotations
    for bar, val in zip(b1, asp_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{val:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#4ecdc4",
        )
    for bar, val in zip(b2, sim_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{val:.2f}",
            ha="center",
            va="bottom",
            fontsize=7,
            color="#ff6b6b",
        )
    fig.patch.set_facecolor("#12121f")
    plt.tight_layout()
    fig.savefig(out_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


# ============================================================================
# SIMPLE STITCH (OpenCV SCANS)
# ============================================================================


def _run_simple_stitch(frames_paths: List[str], out_path: str) -> bool:
    """Generate OpenCV SCANS simple stitch and save. Returns True on success."""
    raw = [cv2.imread(p) for p in frames_paths]
    raw = [f for f in raw if f is not None]
    if len(raw) < 2:
        return False
    raw = _normalise_widths(raw)
    try:
        _scan_stitch_fallback(raw, out_path)
        return True
    except Exception as exc:
        print(f"  [Simple stitch] FAILED: {exc}")
        return False


# ============================================================================
# MAIN DATASET PROCESSOR
# ============================================================================


def process_dataset(dataset_dir: str) -> Optional[Dict]:
    """
    Run both pipelines on a single dataset directory.

    Returns a dict of per-dataset results for the global report, or None if
    the dataset is skipped.
    """
    t_total_start = time.perf_counter()
    timings: Dict[str, float] = {}

    print(f"\n{'=' * 60}\nProcessing dataset: {dataset_dir}\n{'=' * 60}")

    dataset_name = os.path.basename(dataset_dir)
    stage_dir = os.path.join(dataset_dir, "output", "panorama_stages")
    out_path = os.path.join(dataset_dir, "output", "panorama.png")
    simple_stitch_path = os.path.join(dataset_dir, "output", "simple_stitch.png")
    plots_dir = os.path.join(dataset_dir, "output", "plots")

    # Central output
    central_out_dir = os.path.join(os.path.dirname(dataset_dir), "output")
    os.makedirs(central_out_dir, exist_ok=True)
    central_anime_path = os.path.join(
        central_out_dir, f"{dataset_name}_anime_stitch.png"
    )
    central_simple_path = os.path.join(
        central_out_dir, f"{dataset_name}_simple_stitch.png"
    )

    # Clean old outputs
    if os.path.exists(out_path):
        os.remove(out_path)
    if os.path.exists(stage_dir):
        shutil.rmtree(stage_dir)
    os.makedirs(stage_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)

    # Collect frames
    all_pngs = sorted(
        glob.glob(os.path.join(dataset_dir, "*.png"))
        + glob.glob(os.path.join(dataset_dir, "*.jpg"))
    )
    frames_paths = [
        p
        for p in all_pngs
        if "panorama" not in os.path.basename(p)
        and "test_" not in os.path.basename(p)
        and "stage" not in os.path.basename(p)
    ]
    if len(frames_paths) < 2:
        print(f"Skipping {dataset_dir}: not enough frames.")
        return None

    print(f"Source frames ({len(frames_paths)}):")
    for p in frames_paths:
        print(f"  {os.path.basename(p)}")

    # ------------------------------------------------------------------
    # STEP 0: Generate simple stitch (always regenerate for consistency)
    # ------------------------------------------------------------------
    print("\n[0] Running OpenCV SCANS simple stitch …")
    t0 = time.perf_counter()
    simple_ok = _run_simple_stitch(frames_paths, simple_stitch_path)
    timings["simple_stitch_sec"] = round(time.perf_counter() - t0, 3)
    if simple_ok:
        shutil.copy2(simple_stitch_path, central_simple_path)
        print(f"  Saved: {simple_stitch_path}")
    else:
        print(f"  Warning: simple stitch failed for {dataset_name}")

    # ------------------------------------------------------------------
    # STEP 1-2: Load & normalise
    # ------------------------------------------------------------------
    frames = _load_frames(frames_paths)
    N = len(frames)
    frames = _normalise_widths(frames)
    H, W = frames[0].shape[:2]
    scans_frames = list(frames)  # pre-ML snapshot for SCANS fallback
    for i, f in enumerate(frames):
        cv2.imwrite(os.path.join(stage_dir, f"stage02_normalised_frame{i:02d}.png"), f)

    # ------------------------------------------------------------------
    # STEP 3: BiRefNet foreground masks
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    birefnet_ok = False
    try:
        from backend.src.models.birefnet_wrapper import BiRefNetWrapper

        birefnet = BiRefNetWrapper()
        bg_masks = _compute_fg_masks(frames, birefnet)
        birefnet_ok = True
        if torch.cuda.is_available():
            try:
                birefnet.offload()
            except Exception:
                pass
        del birefnet
        gc.collect()
        torch.cuda.empty_cache()
    except Exception as e:
        print(f"  BiRefNet failed ({e}), using None masks")
        bg_masks = [None] * N
    timings["birefnet_sec"] = round(time.perf_counter() - t0, 3)

    for i, m in enumerate(bg_masks):
        img = m if m is not None else np.ones((H, W), dtype=np.uint8) * 255
        cv2.imwrite(os.path.join(stage_dir, f"stage04_bgmask_frame{i:02d}.png"), img)

    # Visualise mask overlays for first 3 frames
    for i in range(min(3, N)):
        _save_mask_overlay(
            frames[i],
            bg_masks[i],
            os.path.join(plots_dir, f"mask_overlay_frame{i:02d}.png"),
            title=f"FG Mask Overlay — Frame {i}",
        )

    # ------------------------------------------------------------------
    # STEP 4: Background photometric normalisation (luminance scalar gain)
    # ------------------------------------------------------------------
    _LUM_W = np.array([0.114, 0.587, 0.299], dtype=np.float32)
    bg_frame_lums: List[Optional[float]] = []
    for frame, mask in zip(frames, bg_masks):
        if mask is not None:
            bg_px = frame[mask > 127].astype(np.float32)
            if len(bg_px) >= 1000:
                bg_frame_lums.append(float(bg_px.dot(_LUM_W).mean()))
                continue
        bg_frame_lums.append(None)

    valid_lums = [l for l in bg_frame_lums if l is not None]
    applied_gains = [1.0] * N
    if len(valid_lums) >= 3:
        ref_lum = float(np.median(valid_lums))
        _gain_lo, _gain_hi = (0.80, 1.25) if ref_lum < 80.0 else (0.88, 1.14)
        for i in range(N):
            if bg_frame_lums[i] is None:
                continue
            gain = float(
                np.clip(ref_lum / max(bg_frame_lums[i], 1.0), _gain_lo, _gain_hi)
            )
            applied_gains[i] = gain
            if abs(gain - 1.0) > 0.01:
                frames[i] = np.clip(frames[i].astype(np.float32) * gain, 0, 255).astype(
                    np.uint8
                )

    # Save stage 3 corrected frames
    for i, f in enumerate(frames):
        cv2.imwrite(
            os.path.join(stage_dir, f"stage03_basic_corrected_frame{i:02d}.png"), f
        )

    # Gains plot
    _save_gains_plot(
        bg_frame_lums,
        applied_gains,
        os.path.join(plots_dir, "gains.png"),
    )

    # ------------------------------------------------------------------
    # STEP 5-7: Match → filter → bundle-adjust → ECC
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    loftr_ok = False
    try:
        from backend.src.models.loftr_wrapper import LoFTRWrapper

        loftr = LoFTRWrapper()
        loftr_ok = True
    except Exception:
        loftr = None

    edges = _pairwise_match(frames, bg_masks, loftr_wrapper=loftr)
    if loftr is not None:
        if torch.cuda.is_available():
            try:
                loftr.offload()
            except Exception:
                pass
        del loftr
        gc.collect()
        torch.cuda.empty_cache()
    timings["matching_sec"] = round(time.perf_counter() - t0, 3)

    # Collect edge metadata before filtering
    raw_edge_count = len(edges)
    edge_methods: Dict[str, int] = {}
    for e in edges:
        m = e.get("method", "unknown")
        edge_methods[m] = edge_methods.get(m, 0) + 1

    # ── Post-match: Spatial dedup of near-static consecutive frames ──────────
    _SPATIAL_DEDUP_PX = 25
    _spa_changed = True
    _total_spa_dropped = 0
    while _spa_changed:
        _spa_changed = False
        _adj_m = {e["j"]: e for e in edges if e["j"] == e["i"] + 1}
        if not _adj_m:
            break
        _adx = [abs(float(e["M"][0, 2])) for e in _adj_m.values()]
        _ady = [abs(float(e["M"][1, 2])) for e in _adj_m.values()]
        _spa_axis = 0 if float(np.median(_adx)) > float(np.median(_ady)) else 1
        _drop: set = set()
        for _jj in sorted(_adj_m):
            _ee = _adj_m[_jj]
            if _ee["i"] in _drop:
                continue
            if abs(float(_ee["M"][_spa_axis, 2])) < _SPATIAL_DEDUP_PX:
                _drop.add(_jj)
                _spa_changed = True
                print(
                    f"  Spatial dedup: frame {_jj} ≈ frame {_ee['i']} "
                    f"(d{'x' if _spa_axis == 0 else 'y'}="
                    f"{float(_ee['M'][_spa_axis, 2]):.1f}px) — dropped."
                )
        if _drop:
            _total_spa_dropped += len(_drop)
            _keep_idx = [i for i in range(N) if i not in _drop]
            frames = [frames[i] for i in _keep_idx]
            bg_masks = [bg_masks[i] for i in _keep_idx]
            frames_paths = [frames_paths[i] for i in _keep_idx]
            _o2n = {old: new for new, old in enumerate(_keep_idx)}
            edges = [
                {**e, "i": _o2n[e["i"]], "j": _o2n[e["j"]]}
                for e in edges
                if e["i"] not in _drop and e["j"] not in _drop
            ]
            N = len(frames)
            H, W = frames[0].shape[:2]
            if N < 2:
                print(
                    f"  Spatial dedup removed too many frames; skipping {dataset_dir}."
                )
                return None
    if _total_spa_dropped:
        print(
            f"  Spatial dedup complete: {_total_spa_dropped} frames removed, {N} remain."
        )

    t0 = time.perf_counter()
    pipe = AnimeStitchPipeline(
        use_basic=False, use_birefnet=False, use_loftr=False, use_ecc=False
    )
    edges = pipe._filter_edges(edges, frames_paths, H, W, frames, bg_masks)
    affines = _bundle_adjust_affine(edges, N)
    timings["bundle_adjust_sec"] = round(time.perf_counter() - t0, 3)

    filtered_edge_count = len(edges)
    edge_stats = [
        {
            "i": int(e["i"]),
            "j": int(e["j"]),
            "method": e.get("method", "unknown"),
            "weight": round(float(e.get("weight", 0.0)), 4),
            "n_pts": len(e.get("pts_i", [])),
            "tx": round(float(e["M"][0, 2]), 2),
            "ty": round(float(e["M"][1, 2]), 2),
        }
        for e in edges
    ]

    # Validate affines
    health = _validate_affines(affines)
    print(
        f"  Affine health: valid={health.valid}, reason={health.reason}, "
        f"ratio={health.ratio:.2f}, min_gap={health.min_gap:.1f}px"
    )

    if not health.valid:
        print(f"  Validation FAILED ({health.reason}); attempting recovery...")
        # Retry 1: consecutive-only bundle
        _adj_only = [e for e in edges if e["j"] == e["i"] + 1]
        if len(_adj_only) >= N - 1:
            affines_r1 = _bundle_adjust_affine(_adj_only, N)
            health_r1 = _validate_affines(affines_r1)
            if health_r1.valid:
                affines, health = affines_r1, health_r1
                print(f"  Recovery Retry 1 succeeded: {health.reason}")

        # Retry 2: smart sequential + fill
        if not health.valid:
            _adj_only_r2 = [e for e in edges if e["j"] == e["i"] + 1]
            _step_dx = (
                float(np.median([float(e["M"][0, 2]) for e in _adj_only_r2]))
                if _adj_only_r2
                else 0.0
            )
            _step_dy = (
                float(np.median([float(e["M"][1, 2]) for e in _adj_only_r2]))
                if _adj_only_r2
                else 0.0
            )
            _has_adj_src = {e["j"] for e in _adj_only_r2}
            _seq = [np.eye(2, 3, dtype=np.float32) for _ in range(N)]
            _anchored: set = {0}
            for _f in range(1, N):
                _best_e, _best_span = None, float("inf")
                for _e in edges:
                    if _e["j"] == _f and _e["i"] in _anchored:
                        if _f - _e["i"] < _best_span:
                            _best_span = _f - _e["i"]
                            _best_e = _e
                if _best_e is not None:
                    _seq[_f][0, 2] = _seq[_best_e["i"]][0, 2] - float(
                        _best_e["M"][0, 2]
                    )
                    _seq[_f][1, 2] = _seq[_best_e["i"]][1, 2] - float(
                        _best_e["M"][1, 2]
                    )
                    _anchored.add(_f)
            for _uf in sorted(i for i in range(N) if i not in _anchored):
                if _uf in _has_adj_src:
                    continue
                _lft = max((a for a in _anchored if a < _uf), default=None)
                _rgt = min((a for a in _anchored if a > _uf), default=None)
                if _lft is not None and _rgt is not None:
                    _t = (_uf - _lft) / (_rgt - _lft)
                    _seq[_uf][0, 2] = (
                        _seq[_lft][0, 2] * (1 - _t) + _seq[_rgt][0, 2] * _t
                    )
                    _seq[_uf][1, 2] = (
                        _seq[_lft][1, 2] * (1 - _t) + _seq[_rgt][1, 2] * _t
                    )
                elif _lft is not None:
                    _n = _uf - _lft
                    _seq[_uf][0, 2] = _seq[_lft][0, 2] - _n * _step_dx
                    _seq[_uf][1, 2] = _seq[_lft][1, 2] - _n * _step_dy
                _anchored.add(_uf)
            _chg = True
            while _chg:
                _chg = False
                for _f in range(1, N):
                    if _f in _anchored:
                        continue
                    _best_e, _best_span = None, float("inf")
                    for _e in edges:
                        if _e["j"] == _f and _e["i"] in _anchored:
                            if _f - _e["i"] < _best_span:
                                _best_span = _f - _e["i"]
                                _best_e = _e
                    if _best_e is not None:
                        _seq[_f][0, 2] = _seq[_best_e["i"]][0, 2] - float(
                            _best_e["M"][0, 2]
                        )
                        _seq[_f][1, 2] = _seq[_best_e["i"]][1, 2] - float(
                            _best_e["M"][1, 2]
                        )
                        _anchored.add(_f)
                        _chg = True
            health_r2 = _validate_affines(_seq)
            if health_r2.valid:
                affines, health = _seq, health_r2
                print(f"  Recovery Retry 2 succeeded: {health.reason}")
            else:
                health_r3 = _validate_affines(_seq, min_step=20.0)
                if health_r3.valid:
                    affines, health = _seq, health_r3
                    print(f"  Recovery Retry 3 (relaxed) succeeded: {health.reason}")

    if not health.valid:
        print("  Validation FAILED → SCANS fallback.")
        t0 = time.perf_counter()
        _scan_stitch_fallback(scans_frames, out_path)
        timings["scans_fallback_sec"] = round(time.perf_counter() - t0, 3)
        timings["total_sec"] = round(time.perf_counter() - t_total_start, 3)
        shutil.copy2(out_path, central_anime_path)
        print(f"\nFinished (SCANS): {dataset_dir} -> {out_path}")
        asp_img = cv2.imread(central_anime_path)
        sim_img = cv2.imread(central_simple_path) if simple_ok else None
        return _build_result(
            dataset_name,
            central_anime_path,
            central_simple_path,
            asp_img,
            sim_img,
            affines,
            bg_frame_lums,
            applied_gains,
            health,
            plots_dir,
            stage_dir,
            canvas_h=None,
            canvas_w=None,
            used_fallback=True,
            timings=timings,
            frame_count=N,
            frame_h=H,
            frame_w=W,
            raw_edge_count=raw_edge_count,
            filtered_edge_count=filtered_edge_count,
            edge_methods=edge_methods,
            edge_stats=edge_stats,
            birefnet_ok=birefnet_ok,
            loftr_ok=loftr_ok,
        )

    try:
        # ECC refinement
        t0 = time.perf_counter()
        affines = _ecc_refine(frames, affines, bg_masks)
        timings["ecc_sec"] = round(time.perf_counter() - t0, 3)

        # Canvas construction
        canvas_h, canvas_w, T_global = _compute_canvas(frames, affines)
        for i in range(N):
            affines[i][0, 2] += T_global[0]
            affines[i][1, 2] += T_global[1]

        canvas_info = {
            "canvas_h": canvas_h,
            "canvas_w": canvas_w,
            "affines_final": [a.tolist() for a in affines],
        }
        with open(os.path.join(stage_dir, "stage08_canvas_info.json"), "w") as fh:
            json.dump(canvas_info, fh)

        # Canvas visualisations
        _save_affine_path_plot(
            affines,
            canvas_h,
            canvas_w,
            H,
            W,
            os.path.join(plots_dir, "canvas_frame_placement.png"),
        )
        _save_translation_plot(
            affines,
            os.path.join(plots_dir, "translation_vectors.png"),
            title=f"{dataset_name} — Translation Vectors",
        )
        _save_overlap_map(
            affines,
            canvas_h,
            canvas_w,
            H,
            W,
            os.path.join(plots_dir, "overlap_map.png"),
        )

        # ------------------------------------------------------------------
        # STEP 8-10: Render → composite → crop
        # ------------------------------------------------------------------
        t0 = time.perf_counter()
        canvas, valid_mask, _, _ = _render_median(
            frames, affines, bg_masks, canvas_h, canvas_w
        )
        timings["render_sec"] = round(time.perf_counter() - t0, 3)
        cv2.imwrite(os.path.join(stage_dir, "stage09_temporal_render.png"), canvas)

        t0 = time.perf_counter()
        canvas = _composite_foreground(
            [], [], canvas, canvas_h, canvas_w, frames, affines, bg_masks
        )
        timings["composite_sec"] = round(time.perf_counter() - t0, 3)
        cv2.imwrite(os.path.join(stage_dir, "stage11_fg_composite.png"), canvas)

        canvas_out = _crop_to_valid(canvas, valid_mask)
        ec = 30
        if ec * 2 < canvas_out.shape[0] and ec * 2 < canvas_out.shape[1]:
            canvas_out = canvas_out[ec:-ec, ec:-ec]

        from PIL import Image

        rgb = cv2.cvtColor(canvas_out, cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save(out_path)
        shutil.copy2(out_path, central_anime_path)
        print(f"\nFinished: {dataset_dir} -> {out_path}")

    except Exception as _render_exc:
        gc.collect()
        print(f"  ASP render/ECC failed ({_render_exc}); falling back to SCANS.")
        t0 = time.perf_counter()
        _scan_stitch_fallback(scans_frames, out_path)
        timings["scans_fallback_sec"] = round(time.perf_counter() - t0, 3)
        timings["total_sec"] = round(time.perf_counter() - t_total_start, 3)
        shutil.copy2(out_path, central_anime_path)
        print(f"\nFinished (SCANS): {dataset_dir} -> {out_path}")
        asp_img = cv2.imread(central_anime_path)
        sim_img = cv2.imread(central_simple_path) if simple_ok else None
        return _build_result(
            dataset_name,
            central_anime_path,
            central_simple_path,
            asp_img,
            sim_img,
            affines,
            bg_frame_lums,
            applied_gains,
            health,
            plots_dir,
            stage_dir,
            canvas_h=None,
            canvas_w=None,
            used_fallback=True,
            timings=timings,
            frame_count=N,
            frame_h=H,
            frame_w=W,
            raw_edge_count=raw_edge_count,
            filtered_edge_count=filtered_edge_count,
            edge_methods=edge_methods,
            edge_stats=edge_stats,
            birefnet_ok=birefnet_ok,
            loftr_ok=loftr_ok,
        )

    # ------------------------------------------------------------------
    # Visualisations on final images
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    asp_img = cv2.imread(central_anime_path)
    sim_img = cv2.imread(central_simple_path) if simple_ok else None

    if asp_img is not None:
        _save_seam_heatmap(
            asp_img,
            os.path.join(plots_dir, "asp_seam_heatmap.png"),
            title="ASP — Gradient Magnitude Heatmap",
        )
        _save_3d_surface(
            asp_img,
            os.path.join(plots_dir, "asp_3d_surface.png"),
            title="ASP — Luminance Surface (3D)",
        )
    if sim_img is not None:
        _save_seam_heatmap(
            sim_img,
            os.path.join(plots_dir, "simple_seam_heatmap.png"),
            title="Simple Stitch — Gradient Magnitude Heatmap",
        )
        _save_3d_surface(
            sim_img,
            os.path.join(plots_dir, "simple_3d_surface.png"),
            title="Simple Stitch — Luminance Surface (3D)",
        )

    # Temporal render visualisation
    render_img = cv2.imread(os.path.join(stage_dir, "stage09_temporal_render.png"))
    if render_img is not None:
        _save_3d_surface(
            render_img,
            os.path.join(plots_dir, "temporal_render_3d.png"),
            title="Stage 9 — Temporal Render Luminance (3D)",
        )

    # Metrics comparison bar
    if asp_img is not None and sim_img is not None:
        _save_metrics_bar(
            _compute_all_metrics(asp_img, affines),
            _compute_all_metrics(sim_img),
            os.path.join(plots_dir, "metrics_comparison.png"),
        )

    timings["visualisations_sec"] = round(time.perf_counter() - t0, 3)
    timings["total_sec"] = round(time.perf_counter() - t_total_start, 3)

    return _build_result(
        dataset_name,
        central_anime_path,
        central_simple_path,
        asp_img,
        sim_img,
        affines,
        bg_frame_lums,
        applied_gains,
        health,
        plots_dir,
        stage_dir,
        canvas_h,
        canvas_w,
        used_fallback=False,
        timings=timings,
        frame_count=N,
        frame_h=H,
        frame_w=W,
        raw_edge_count=raw_edge_count,
        filtered_edge_count=filtered_edge_count,
        edge_methods=edge_methods,
        edge_stats=edge_stats,
        birefnet_ok=birefnet_ok,
        loftr_ok=loftr_ok,
    )


# ============================================================================
# RESULT BUILDER
# ============================================================================


def _build_result(
    dataset_name: str,
    anime_path: str,
    simple_path: str,
    asp_img: Optional[np.ndarray],
    sim_img: Optional[np.ndarray],
    affines: List[np.ndarray],
    bg_frame_lums: List[Optional[float]],
    applied_gains: List[float],
    health,
    plots_dir: str,
    stage_dir: str,
    canvas_h: Optional[int],
    canvas_w: Optional[int],
    used_fallback: bool,
    timings: Optional[Dict] = None,
    frame_count: int = 0,
    frame_h: int = 0,
    frame_w: int = 0,
    raw_edge_count: int = 0,
    filtered_edge_count: int = 0,
    edge_methods: Optional[Dict] = None,
    edge_stats: Optional[List] = None,
    birefnet_ok: bool = False,
    loftr_ok: bool = False,
) -> Dict:
    asp_metrics = _compute_all_metrics(asp_img, affines) if asp_img is not None else {}
    sim_metrics = _compute_all_metrics(sim_img) if sim_img is not None else {}

    ssim_val = float("nan")
    psnr_val = float("nan")
    if asp_img is not None and sim_img is not None:
        ssim_val = _ssim_score(asp_img, sim_img)
        psnr_val = _psnr(asp_img, sim_img)

    # Affine translation summary for JSON
    affine_translations = [
        {
            "frame": i,
            "tx": round(float(M[0, 2]), 2),
            "ty": round(float(M[1, 2]), 2),
            "a": round(float(M[0, 0]), 5),
            "b": round(float(M[0, 1]), 5),
        }
        for i, M in enumerate(affines)
    ]

    # Inter-frame deltas
    tys = [float(M[1, 2]) for M in affines]
    txs = [float(M[0, 2]) for M in affines]
    dy_steps = [round(tys[i + 1] - tys[i], 2) for i in range(len(tys) - 1)]
    dx_steps = [round(txs[i + 1] - txs[i], 2) for i in range(len(txs) - 1)]
    dy_cv = (
        float(np.std(dy_steps) / (abs(np.mean(dy_steps)) + 1e-6)) if dy_steps else 0.0
    )
    dx_cv = (
        float(np.std(dx_steps) / (abs(np.mean(dx_steps)) + 1e-6)) if dx_steps else 0.0
    )

    # Background luminance stats
    valid_lums = [l for l in bg_frame_lums if l is not None]
    ref_lum = round(float(np.median(valid_lums)), 2) if valid_lums else None
    non_trivial_gains = sum(1 for g in applied_gains if abs(g - 1.0) > 0.01)

    return {
        "name": dataset_name,
        "anime_path": anime_path,
        "simple_path": simple_path,
        # --- timing ---
        "time": timings or {},
        # --- frame / canvas geometry ---
        "frames": {
            "count": frame_count,
            "source_h": frame_h,
            "source_w": frame_w,
        },
        "canvas": {
            "width": canvas_w,
            "height": canvas_h,
        },
        # --- pipeline config ---
        "pipeline_config": {
            "use_birefnet": birefnet_ok,
            "use_loftr": loftr_ok,
            "use_basic": False,
            "use_ecc": True,
            "renderer": "median",
            "edge_erosion_px": 30,
        },
        # --- matching ---
        "matching": {
            "raw_edges": raw_edge_count,
            "filtered_edges": filtered_edge_count,
            "methods": edge_methods or {},
            "edges": edge_stats or [],
        },
        # --- alignment ---
        "alignment": {
            "affines": affine_translations,
            "dy_steps": dy_steps,
            "dx_steps": dx_steps,
            "dy_cv": round(dy_cv, 4),
            "dx_cv": round(dx_cv, 4),
        },
        "affine_health": {
            "valid": health.valid,
            "ratio": round(health.ratio, 3),
            "min_gap_px": round(health.min_gap, 1),
            "max_rotation": round(health.max_rotation, 4),
            "max_scale_dev": round(health.max_scale_dev, 4),
            "reason": health.reason,
        },
        # --- photometric correction ---
        "photometric": {
            "ref_lum": ref_lum,
            "bg_lums": [round(l, 2) if l is not None else None for l in bg_frame_lums],
            "applied_gains": [round(g, 4) for g in applied_gains],
            "frames_corrected": non_trivial_gains,
            "gain_range": [
                round(min(applied_gains), 4),
                round(max(applied_gains), 4),
            ],
        },
        # --- quality metrics ---
        "metrics_asp": asp_metrics,
        "metrics_simple": sim_metrics,
        "comparison": {
            "ssim": round(ssim_val, 4) if not math.isnan(ssim_val) else None,
            "psnr_db": round(psnr_val, 2) if not math.isnan(psnr_val) else None,
            "verdict": _auto_verdict(asp_metrics, sim_metrics),
        },
        # --- status ---
        "used_fallback": used_fallback,
        # --- paths (for the notebook to locate files) ---
        "paths": {
            "plots_dir": plots_dir,
            "stage_dir": stage_dir,
            "anime_stitch": anime_path,
            "simple_stitch": simple_path,
        },
    }


# ============================================================================
# JSON RESULTS FILE
# ============================================================================


def generate_json_results(results: List[Dict], suite_start_time: float) -> str:
    """
    Write a structured JSON results file to backend/benchmark/results/ and
    return the path.  Schema mirrors the existing benchmark JSON files.
    """
    total_sec = round(time.perf_counter() - suite_start_time, 3)
    ts = datetime.datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")
    ts_iso = ts.isoformat()

    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)
    out_path = os.path.join(results_dir, f"anime_stitch_{ts_str}.json")

    # Aggregate summary stats
    asp_sharpness = [
        r["metrics_asp"].get("sharpness", 0.0) for r in results if r["metrics_asp"]
    ]
    sim_sharpness = [
        r["metrics_simple"].get("sharpness", 0.0)
        for r in results
        if r["metrics_simple"]
    ]
    asp_ghosting = [
        r["metrics_asp"].get("ghosting_score", 0.0) for r in results if r["metrics_asp"]
    ]
    sim_ghosting = [
        r["metrics_simple"].get("ghosting_score", 0.0)
        for r in results
        if r["metrics_simple"]
    ]
    asp_coverage = [
        r["metrics_asp"].get("coverage", 0.0) for r in results if r["metrics_asp"]
    ]
    ssim_vals = [
        r["comparison"]["ssim"]
        for r in results
        if r["comparison"].get("ssim") is not None
    ]
    dataset_times = [r["time"].get("total_sec", 0.0) for r in results]
    fallback_count = sum(1 for r in results if r["used_fallback"])
    verdicts = [r["comparison"]["verdict"] for r in results]

    # Performance insights
    def _rank_by(key_fn, results_list, top=True):
        valid = [(r["name"], key_fn(r)) for r in results_list if key_fn(r) is not None]
        if not valid:
            return None
        ranked = sorted(valid, key=lambda x: x[1], reverse=top)
        return {"name": ranked[0][0], "value": round(ranked[0][1], 4)}

    best_asp = _rank_by(lambda r: r["metrics_asp"].get("sharpness"), results)
    worst_asp = _rank_by(
        lambda r: r["metrics_asp"].get("sharpness"), results, top=False
    )
    slowest = _rank_by(lambda r: r["time"].get("total_sec"), results)
    fastest = _rank_by(
        lambda r: r["time"].get("total_sec")
        if r["time"].get("total_sec", 0) > 0
        else None,
        results,
        top=False,
    )
    most_ghosting = _rank_by(lambda r: r["metrics_asp"].get("ghosting_score"), results)
    least_ghosting = _rank_by(
        lambda r: r["metrics_asp"].get("ghosting_score"), results, top=False
    )

    doc = {
        "metadata": {
            "suite_name": "Anime Stitch Pipeline",
            "timestamp": ts_iso,
            "total_datasets": len(results),
            "total_time_sec": total_sec,
            "format_version": "1.0",
        },
        "system": _system_info(),
        "summary": {
            "total_datasets": len(results),
            "datasets_passed": len(results) - fallback_count,
            "datasets_fallback": fallback_count,
            "total_time_sec": total_sec,
            "avg_time_per_dataset_sec": round(
                sum(dataset_times) / max(len(dataset_times), 1), 3
            ),
            "avg_sharpness_asp": round(float(np.mean(asp_sharpness)), 3)
            if asp_sharpness
            else None,
            "avg_sharpness_simple": round(float(np.mean(sim_sharpness)), 3)
            if sim_sharpness
            else None,
            "avg_ghosting_asp": round(float(np.mean(asp_ghosting)), 4)
            if asp_ghosting
            else None,
            "avg_ghosting_simple": round(float(np.mean(sim_ghosting)), 4)
            if sim_ghosting
            else None,
            "avg_coverage_asp": round(float(np.mean(asp_coverage)), 4)
            if asp_coverage
            else None,
            "avg_ssim": round(float(np.mean(ssim_vals)), 4) if ssim_vals else None,
            "verdict_counts": {
                "asp_better": verdicts.count("asp_better"),
                "simple_better": verdicts.count("simple_better"),
                "comparable": verdicts.count("comparable"),
                "insufficient_data": verdicts.count("insufficient_data"),
            },
        },
        "datasets": results,
        "performance_insights": {
            "slowest_dataset": slowest,
            "fastest_dataset": fastest,
            "best_asp_sharpness": best_asp,
            "worst_asp_sharpness": worst_asp,
            "most_asp_ghosting": most_ghosting,
            "least_asp_ghosting": least_ghosting,
            "datasets_asp_better_than_simple": [
                r["name"] for r in results if r["comparison"]["verdict"] == "asp_better"
            ],
            "datasets_simple_better_than_asp": [
                r["name"]
                for r in results
                if r["comparison"]["verdict"] == "simple_better"
            ],
            "datasets_alignment_failed": [
                r["name"] for r in results if not r["affine_health"]["valid"]
            ],
        },
    }

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2)

    print(f"\n[JSON] Results written to {out_path}")
    return out_path


# ============================================================================
# MARKDOWN REPORT GENERATOR
# ============================================================================

_REPORT_HEADER = """\
---
report_version: "1.0"
generated: "{date}"
pipeline: "AnimeStitchPipeline"
datasets: {num_datasets}
---

# Anime Stitch Pipeline — Benchmark Report

> **How to use this report**
>
> Each test section contains:
> - Side-by-side outputs (ASP vs Simple/OpenCV)
> - CV metric table
> - Intermediate output visualizations (2D & 3D)
> - A structured `<!-- FEEDBACK -->` block
>
> To review/correct feedback, edit the YAML inside each `<!-- FEEDBACK -->…<!-- /FEEDBACK -->`
> block. Valid `status` values: `pending`, `correct`, `incomplete`, `incorrect`.
> Add your corrections in the `human_notes` field.
> Machine-readable fields (`asp_issues`, `simple_issues`, `verdict`) are pre-filled
> and updated automatically on re-runs.

"""

_GLOBAL_SUMMARY_HEADER = """\
---

## Global Summary

"""

_GLOBAL_FEEDBACK_BLOCK = """\

---

## Global Feedback & Human Notes

<!-- GLOBAL_FEEDBACK
status: pending
overall_asp_rating: null
overall_simple_rating: null
most_common_asp_failure: null
most_common_simple_failure: null
priority_fixes:
  - null
human_notes: |
  (Your analysis here)
/GLOBAL_FEEDBACK -->

"""

_PER_TEST_HUMAN_SECTION = """\

### My Feedback

<!-- FEEDBACK
status: pending
asp_issues:
{asp_issues}
simple_issues:
{simple_issues}
verdict: "{verdict}"
human_notes: |
  (Edit this section — confirm, correct, or extend the CV analysis above)
/FEEDBACK -->

---
"""


def _auto_verdict(asp_m: Dict, sim_m: Dict) -> str:
    """Quick heuristic verdict from metrics."""
    if not asp_m or not sim_m:
        return "insufficient_data"
    asp_score = (
        asp_m.get("sharpness", 0) * 0.4
        + asp_m.get("coverage", 0) * 100 * 0.3
        - asp_m.get("ghosting_score", 0) * 0.2
        - asp_m.get("seam_gradient", 0) * 0.1
    )
    sim_score = (
        sim_m.get("sharpness", 0) * 0.4
        + sim_m.get("coverage", 0) * 100 * 0.3
        - sim_m.get("ghosting_score", 0) * 0.2
        - sim_m.get("seam_gradient", 0) * 0.1
    )
    if asp_score > sim_score * 1.1:
        return "asp_better"
    if sim_score > asp_score * 1.1:
        return "simple_better"
    return "comparable"


def _auto_issues(metrics: Dict, is_asp: bool) -> List[str]:
    """Generate a list of detected issues from metrics."""
    issues = []
    if not metrics:
        return ["- no_image"]
    cov = metrics.get("coverage", 1.0)
    if cov < 0.70:
        issues.append(
            f"  - low_coverage: {cov:.2%} (image heavily cropped or malformed)"
        )
    ghost = metrics.get("ghosting_score", 0)
    if ghost > 15:
        issues.append(f"  - high_ghosting: score={ghost:.2f} (double-edges detected)")
    seam = metrics.get("seam_gradient", 0)
    if seam > 20:
        issues.append(
            f"  - seam_discontinuity: gradient={seam:.2f} (abrupt transitions)"
        )
    sharp = metrics.get("sharpness", 0)
    if sharp < 30:
        issues.append(f"  - low_sharpness: {sharp:.2f} (blurry / smeared)")
    if not issues:
        issues.append("  - none_detected")
    return issues


def _rel_path(path: str, report_dir: str) -> str:
    """Return path relative to report_dir for markdown embedding."""
    try:
        return os.path.relpath(path, report_dir)
    except ValueError:
        return path


def _plot_exists(plots_dir: str, name: str) -> bool:
    return os.path.exists(os.path.join(plots_dir, name))


def generate_report(results: List[Dict], output_dir: str) -> str:
    """
    Write benchmark_report.md inside output_dir.
    Returns the path to the written file.
    """
    report_path = os.path.join(output_dir, "benchmark_report.md")
    rd = output_dir  # report dir = base for relative paths

    lines = []

    # Header
    lines.append(
        _REPORT_HEADER.format(
            date=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            num_datasets=len(results),
        )
    )

    # Global summary table
    lines.append(_GLOBAL_SUMMARY_HEADER)
    lines.append(
        "| Test | ASP Size | Simple Size | Coverage ASP | Coverage Simple | Ghosting ASP | Ghosting Simple | SSIM | Verdict | Fallback |\n"
    )
    lines.append(
        "|------|----------|-------------|-------------|----------------|-------------|----------------|------|---------|----------|\n"
    )
    for r in results:
        am, sm = r["metrics_asp"], r["metrics_simple"]
        asp_sz = f"{am.get('width', '?')}×{am.get('height', '?')}" if am else "—"
        sim_sz = f"{sm.get('width', '?')}×{sm.get('height', '?')}" if sm else "—"
        cov_a = f"{am.get('coverage', 0):.1%}" if am else "—"
        cov_s = f"{sm.get('coverage', 0):.1%}" if sm else "—"
        gh_a = f"{am.get('ghosting_score', 0):.2f}" if am else "—"
        gh_s = f"{sm.get('ghosting_score', 0):.2f}" if sm else "—"
        ssim_v = (
            f"{r['comparison']['ssim']:.3f}"
            if r["comparison"]["ssim"] is not None
            else "—"
        )
        verdict = _auto_verdict(am, sm)
        fallback = "✓" if r["used_fallback"] else ""
        lines.append(
            f"| [{r['name']}](#{r['name']}) | {asp_sz} | {sim_sz} | {cov_a} | {cov_s} | "
            f"{gh_a} | {gh_s} | {ssim_v} | {verdict} | {fallback} |\n"
        )
    lines.append("\n")

    # Global ASP failure breakdown
    lines.append("### Failure Mode Counts (ASP)\n\n")
    fail_counts: Dict[str, int] = {}
    for r in results:
        for issue in _auto_issues(r["metrics_asp"], is_asp=True):
            key = issue.strip().lstrip("- ").split(":")[0]
            fail_counts[key] = fail_counts.get(key, 0) + 1
    lines.append("| Issue | Count |\n|-------|-------|\n")
    for k, v in sorted(fail_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{k}` | {v} |\n")
    lines.append("\n")

    # Per-test sections
    for r in results:
        name = r["name"]
        anime_rel = _rel_path(r["anime_path"], rd)
        simple_rel = (
            _rel_path(r["simple_path"], rd)
            if os.path.exists(r["simple_path"])
            else None
        )
        pd = r["paths"]["plots_dir"]
        sd = r["paths"]["stage_dir"]
        am, sm = r["metrics_asp"], r["metrics_simple"]

        lines.append(f"---\n\n## {name}\n\n")

        # Side-by-side final outputs
        lines.append("### Final Outputs\n\n")
        lines.append("| Anime Stitch Pipeline | OpenCV Simple Stitch |\n")
        lines.append("|:---------------------:|:--------------------:|\n")
        asp_cell = (
            f"![ASP]({anime_rel})"
            if os.path.exists(r["anime_path"])
            else "_not generated_"
        )
        simple_cell = (
            f"![Simple]({simple_rel})"
            if simple_rel and os.path.exists(r["simple_path"])
            else "_not generated_"
        )
        lines.append(f"| {asp_cell} | {simple_cell} |\n\n")

        # CV Metrics table
        lines.append("### CV Metrics\n\n")
        lines.append("| Metric | ASP | Simple | Notes |\n")
        lines.append("|--------|-----|--------|-------|\n")
        metric_defs = [
            ("sharpness", "Laplacian variance — higher = sharper edges"),
            ("coverage", "Fraction of non-black pixels — lower = heavy crop"),
            (
                "seam_gradient",
                "Mean gradient magnitude at seam rows — higher = abrupt transitions",
            ),
            ("color_entropy", "Shannon entropy of luma histogram — lower = washed out"),
            ("ghosting_score", "2nd-order vertical gradient — higher = double-edges"),
            ("width", "Output width (px)"),
            ("height", "Output height (px)"),
        ]
        for key, note in metric_defs:
            a_val = f"{am.get(key, '—')}" if am else "—"
            s_val = f"{sm.get(key, '—')}" if sm else "—"
            lines.append(f"| `{key}` | {a_val} | {s_val} | {note} |\n")
        ssim_v = (
            f"{r['comparison']['ssim']:.3f}"
            if r["comparison"]["ssim"] is not None
            else "—"
        )
        psnr_v = (
            f"{r['comparison']['psnr_db']:.1f} dB"
            if r["comparison"]["psnr_db"] is not None
            else "—"
        )
        lines.append(
            f"| `ssim (asp vs simple)` | {ssim_v} | — | Structural similarity between the two outputs |\n"
        )
        lines.append(
            f"| `psnr (asp vs simple)` | {psnr_v} | — | Peak SNR between the two outputs |\n"
        )
        lines.append("\n")

        # Affine health
        ah = r["affine_health"]
        lines.append("### Alignment Health\n\n")
        lines.append("```yaml\n")
        lines.append(f"valid: {ah['valid']}\n")
        lines.append(f"reason: {ah['reason']}\n")
        lines.append(f"spacing_ratio: {ah['ratio']}\n")
        lines.append(f"min_gap_px: {ah['min_gap_px']}\n")
        lines.append(f"max_rotation: {ah['max_rotation']}\n")
        lines.append(f"max_scale_deviation: {ah['max_scale_dev']}\n")
        lines.append(f"used_scans_fallback: {r['used_fallback']}\n")
        if r["canvas"]["height"] is not None:
            lines.append(f"canvas: {r['canvas']['width']}×{r['canvas']['height']}\n")
        lines.append("```\n\n")

        # Gains summary
        gains = r["photometric"]["applied_gains"]
        # lums = r["photometric"]["bg_lums"]
        non_trivial = [g for g in gains if abs(g - 1.0) > 0.01]
        lines.append("### Photometric Correction\n\n")
        lines.append(f"- Frames: **{len(gains)}**  \n")
        lines.append(
            f"- Frames corrected (|gain − 1| > 0.01): **{len(non_trivial)}**  \n"
        )
        if non_trivial:
            lines.append(
                f"- Gain range: [{min(non_trivial):.4f}, {max(non_trivial):.4f}]  \n"
            )
        lines.append("\n")

        # Visualisation section
        lines.append("### Intermediate Output Visualizations\n\n")

        def _img_row(label, fname, alt=""):
            p = os.path.join(pd, fname)
            if os.path.exists(p):
                rel = _rel_path(p, rd)
                return f"**{label}**  \n![{alt or label}]({rel})\n\n"
            return ""

        # Metrics comparison bar
        bar_path = os.path.join(pd, "metrics_comparison.png")
        if os.path.exists(bar_path):
            lines.append(
                _img_row("CV Metrics Comparison (normalised)", "metrics_comparison.png")
            )

        # Gains
        gains_path = os.path.join(pd, "gains.png")
        if os.path.exists(gains_path):
            lines.append(_img_row("Per-Frame Luminance Gains", "gains.png"))

        # 2D canvas & overlap
        cp = os.path.join(pd, "canvas_frame_placement.png")
        if os.path.exists(cp):
            lines.append(
                _img_row("Canvas Frame Placement (2D)", "canvas_frame_placement.png")
            )

        tv = os.path.join(pd, "translation_vectors.png")
        if os.path.exists(tv):
            lines.append(
                _img_row("Translation Vectors (2D)", "translation_vectors.png")
            )

        om = os.path.join(pd, "overlap_map.png")
        if os.path.exists(om):
            lines.append(_img_row("Frame Overlap Count Map (2D)", "overlap_map.png"))

        # Seam heatmaps
        for img_type in ["asp", "simple"]:
            hm = os.path.join(pd, f"{img_type}_seam_heatmap.png")
            if os.path.exists(hm):
                label = "ASP" if img_type == "asp" else "Simple Stitch"
                lines.append(
                    _img_row(
                        f"{label} — Seam Gradient Heatmap (2D)",
                        f"{img_type}_seam_heatmap.png",
                    )
                )

        # 3D surface plots
        for fname, label in [
            ("asp_3d_surface.png", "ASP — Luminance Surface (3D)"),
            ("simple_3d_surface.png", "Simple Stitch — Luminance Surface (3D)"),
            (
                "temporal_render_3d.png",
                "Stage 9 Temporal Render — Luminance Surface (3D)",
            ),
        ]:
            p = os.path.join(pd, fname)
            if os.path.exists(p):
                lines.append(_img_row(label, fname))

        # Mask overlays
        mask_any = False
        for i in range(3):
            mp = os.path.join(pd, f"mask_overlay_frame{i:02d}.png")
            if os.path.exists(mp):
                if not mask_any:
                    lines.append(
                        "**BiRefNet Foreground Mask Overlays (first 3 frames)**\n\n"
                    )
                    lines.append(
                        "| Frame 0 | Frame 1 | Frame 2 |\n|:---:|:---:|:---:|\n| "
                    )
                    mask_any = True
        if mask_any:
            cells = []
            for i in range(3):
                mp = os.path.join(pd, f"mask_overlay_frame{i:02d}.png")
                if os.path.exists(mp):
                    cells.append(f"![mask f{i}]({_rel_path(mp, rd)})")
                else:
                    cells.append("—")
            lines.append(" | ".join(cells) + " |\n\n")

        # Stage images
        lines.append("#### Stage Intermediate Outputs\n\n")
        _n_frames = min(r.get("frames", {}).get("count", 4), 4)
        stage_imgs = {
            "Stage 2 Normalised Frames": [
                os.path.join(sd, f"stage02_normalised_frame{i:02d}.png")
                for i in range(_n_frames)
            ],
            "Stage 3 Corrected Frames": [
                os.path.join(sd, f"stage03_basic_corrected_frame{i:02d}.png")
                for i in range(_n_frames)
            ],
            "Stage 4 BG Masks": [
                os.path.join(sd, f"stage04_bgmask_frame{i:02d}.png")
                for i in range(_n_frames)
            ],
        }
        for stage_label, paths in stage_imgs.items():
            existing = [p for p in paths if os.path.exists(p)]
            if not existing:
                continue
            lines.append(f"**{stage_label}**\n\n")
            cols = min(4, len(existing))
            header = "| " + " | ".join([f"Frame {i}" for i in range(cols)]) + " |\n"
            sep = "|" + "---|" * cols + "\n"
            row = (
                "| "
                + " | ".join(
                    [
                        f"![f{i}]({_rel_path(p, rd)})"
                        for i, p in enumerate(existing[:cols])
                    ]
                )
                + " |\n\n"
            )
            lines.append(header + sep + row)

        # Temporal render and composite
        for fname, label in [
            ("stage09_temporal_render.png", "Stage 9 — Temporal Median Render"),
            ("stage11_fg_composite.png", "Stage 11 — FG Composite"),
        ]:
            sp = os.path.join(sd, fname)
            if os.path.exists(sp):
                rel = _rel_path(sp, rd)
                lines.append(f"**{label}**  \n![{label}]({rel})\n\n")

        # Auto-generated analysis
        lines.append("### Automated Analysis\n\n")
        verdict = _auto_verdict(am, sm)
        verdict_map = {
            "asp_better": "ASP produces a **higher-quality** output by CV metrics.",
            "simple_better": "Simple/OpenCV produces a **higher-quality** output by CV metrics.",
            "comparable": "Both pipelines produce **comparable** quality by CV metrics.",
            "insufficient_data": "Insufficient data to determine a verdict.",
        }
        lines.append(f"> **CV Verdict:** {verdict_map.get(verdict, verdict)}\n\n")

        lines.append("**Detected issues — ASP:**\n")
        for issue in _auto_issues(am, is_asp=True):
            lines.append(f"{issue}\n")
        lines.append("\n**Detected issues — Simple Stitch:**\n")
        for issue in _auto_issues(sm, is_asp=False):
            lines.append(f"{issue}\n")
        lines.append("\n")

        if r["used_fallback"]:
            lines.append(
                "> ⚠️ **SCANS Fallback used** — Alignment failed, ASP result is identical to Simple Stitch.\n\n"
            )

        # Human feedback block
        asp_issues_yaml = "\n".join(_auto_issues(am, True))
        simple_issues_yaml = "\n".join(_auto_issues(sm, False))
        lines.append(
            _PER_TEST_HUMAN_SECTION.format(
                asp_issues=asp_issues_yaml,
                simple_issues=simple_issues_yaml,
                verdict=verdict,
            )
        )

    # Global feedback section
    lines.append(_GLOBAL_FEEDBACK_BLOCK)

    # Appendix: raw metrics JSON
    lines.append("---\n\n## Appendix — Raw Metrics JSON\n\n")
    lines.append("```json\n")
    summary = {
        "generated": datetime.datetime.now().isoformat(),
        "datasets": [
            {
                "name": r["name"],
                "asp_metrics": r["metrics_asp"],
                "sim_metrics": r["metrics_simple"],
                "ssim": r["comparison"]["ssim"],
                "psnr": r["comparison"]["psnr_db"],
                "affine_health": r["affine_health"],
                "used_fallback": r["used_fallback"],
            }
            for r in results
        ],
    }
    lines.append(json.dumps(summary, indent=2))
    lines.append("\n```\n")

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)

    print(f"\n[Report] Written to {report_path}")
    return report_path


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    base_dir = "/home/pkhunter/Repositories/Image-Toolkit/data"
    datasets = sorted(glob.glob(os.path.join(base_dir, "asp_test*")))

    suite_start = time.perf_counter()
    results = []
    for ds in datasets:
        if os.path.isdir(ds):
            result = process_dataset(ds)
            if result is not None:
                results.append(result)
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    if results:
        output_dir = os.path.join(base_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        generate_report(results, output_dir)
        generate_json_results(results, suite_start)
        print(f"\nAll done. {len(results)} datasets processed.")
    else:
        print("No results to report.")
