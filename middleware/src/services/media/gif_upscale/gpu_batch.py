"""GPU batch Lanczos3-dering scale + on-device Bayer dither and nearest-palette indexing (#1155).

Acquires a per-device lease from ``GpuLeaseArbiter`` (using live ``cuda_device_table``
free VRAM when no arbiter is injected), computes a safe frame batch size from free
VRAM, keeps scaled frames on the GPU through ordered Bayer dithering and palette
lookup (exact BLAS ``addmm`` for ``quality="exact"``, 7-bit ``128^3`` LUT for
``"balanced"``/``"fast"``), and downloads only ``uint8`` palette indices (16x less
Device-to-Host PCIe traffic than ``float32`` RGBA). Falls back cleanly to CPU with
an explicit reason when no usable GPU or lease is available (D12, D13, D16).
"""

from __future__ import annotations

import contextlib
import time
import uuid
from collections.abc import Sequence
from typing import Any

import numpy as np

from middleware.src.core.gpu_lease_arbiter import (
    GpuLeaseArbiter,
    cuda_device_table,
    profile_from_env,
)
from middleware.src.services.media.gif_upscale.classical._resize import (
    _LANCZOS_DERING,
    _OPAQUE_ALPHA,
    _clip_plan,
    _dering_strength,
    _ensure_sgemm,
    _lanczos_quality,
    lanczos_kernel,
)
from middleware.src.services.media.gif_upscale.encode import (
    _bayer_grid,
    _normalize_quality,
    build_palette_lut,
)

_FIXED_OVERHEAD_GB = 0.35
_SAFETY_FACTOR = 2.0
_VRAM_UTILIZATION = 0.70
_EXACT_INDEX_CHUNK = 262144


def compute_gpu_batch_size(
    free_gb: float,
    src_h: int,
    src_w: int,
    dst_h: int,
    dst_w: int,
    *,
    quality: str = "balanced",
    vram_cap_gb: float | None = None,
    min_batch: int = 1,
    max_batch: int = 64,
) -> int:
    """Compute a safe frame batch size from available VRAM at job start."""
    usable_gb = float(free_gb)
    if vram_cap_gb is not None and vram_cap_gb > 0:
        usable_gb = min(usable_gb, float(vram_cap_gb))
    budget_bytes = max(0.0, (usable_gb * _VRAM_UTILIZATION - _FIXED_OVERHEAD_GB)) * (1024**3)
    if budget_bytes <= 0:
        return max(1, int(min_batch))
    src_pixels = max(1, int(src_h) * int(src_w))
    dst_pixels = max(1, int(dst_h) * int(dst_w))
    mid_pixels = max(1, int(src_h) * int(dst_w))
    # Source uint8 + premul float32 + 6x6 pool bounds + horizontal intermediate + dst float32/int64/uint8
    per_frame_bytes = (
        src_pixels * (4 + 16 + 36)
        + mid_pixels * 16
        + dst_pixels * (16 + 16 + 16 + 8 + 1)
    ) * _SAFETY_FACTOR
    if _normalize_quality(quality) == "exact":
        per_frame_bytes += dst_pixels * 4
    batch = int(budget_bytes // max(1.0, per_frame_bytes))
    return max(int(min_batch), min(int(max_batch), batch))


class GpuResampleSession:
    """Holds one leased CUDA device and cached resample + palette tensors for a clip."""

    def __init__(
        self,
        *,
        arbiter: GpuLeaseArbiter,
        owner: str,
        device_index: int,
        free_gb: float,
        src_h: int,
        src_w: int,
        dst_h: int,
        dst_w: int,
        opts: dict[str, Any],
        algorithm_id: str = _LANCZOS_DERING,
        batch_size: int | None = None,
    ) -> None:
        import torch

        self._torch = torch
        self.arbiter = arbiter
        self.owner = owner
        self.device_index = int(device_index)
        self.device = torch.device(f"cuda:{self.device_index}")
        self.free_gb = float(free_gb)
        self.src_h = int(src_h)
        self.src_w = int(src_w)
        self.dst_h = int(dst_h)
        self.dst_w = int(dst_w)
        self.opts = opts
        self.algorithm_id = algorithm_id
        self._closed = False

        kernel = lanczos_kernel(3.0)
        self.plan = _clip_plan(opts, algorithm_id, self.src_h, self.src_w, self.dst_h, self.dst_w, 3.0, kernel)
        _ensure_sgemm(self.plan)
        self.quality = _lanczos_quality(opts, algorithm_id, self.src_h, self.src_w, self.dst_h, self.dst_w)
        self.window_ok = (
            bool(self.plan["window"])
            and self.dst_w >= self.src_w
            and self.dst_h >= self.src_h
            and self.quality != "exact"
        )
        self.strength: float | None = _dering_strength(opts) if self.quality == "fast" else None

        params = opts.get("params") if isinstance(opts.get("params"), dict) else {}
        vram_cap = params.get("vram_cap_gb")
        cap_val = float(vram_cap) if isinstance(vram_cap, (int, float)) and vram_cap > 0 else None
        self.batch_size = (
            int(batch_size)
            if batch_size is not None and batch_size >= 1
            else compute_gpu_batch_size(
                self.free_gb,
                self.src_h,
                self.src_w,
                self.dst_h,
                self.dst_w,
                quality=self.quality,
                vram_cap_gb=cap_val,
            )
        )

        # Upload separable weight matrices and coordinate maps once per clip
        self.wx_t = torch.from_numpy(np.ascontiguousarray(self.plan["wx"], dtype=np.float32)).to(self.device)
        self.wy_t = torch.from_numpy(np.ascontiguousarray(self.plan["wy"], dtype=np.float32)).to(self.device)
        src_x_np = (
            np.floor((np.arange(self.dst_w, dtype=np.float64) + 0.5) * (self.src_w / self.dst_w) - 0.5).astype(np.int64)
            + 1
        )
        src_y_np = (
            np.floor((np.arange(self.dst_h, dtype=np.float64) + 0.5) * (self.src_h / self.dst_h) - 0.5).astype(np.int64)
            + 1
        )
        self.src_x_t = torch.from_numpy(src_x_np).to(self.device)
        self.src_y_t = torch.from_numpy(src_y_np).to(self.device)

        x_index, x_weight, x_valid = self.plan["x"]
        y_index, y_weight, y_valid = self.plan["y"]
        self.x_index_t = torch.from_numpy(np.ascontiguousarray(x_index, dtype=np.int64)).to(self.device)
        self.x_weight_t = torch.from_numpy(np.ascontiguousarray(x_weight, dtype=np.float32)).to(self.device)
        self.x_valid_t = torch.from_numpy(np.ascontiguousarray(x_valid, dtype=bool)).to(self.device)
        self.y_index_t = torch.from_numpy(np.ascontiguousarray(y_index, dtype=np.int64)).to(self.device)
        self.y_weight_t = torch.from_numpy(np.ascontiguousarray(y_weight, dtype=np.float32)).to(self.device)
        self.y_valid_t = torch.from_numpy(np.ascontiguousarray(y_valid, dtype=bool)).to(self.device)

        # Palette & dither state (populated by prepare_palette)
        self._bayer_t = None
        self._pal_t = None
        self._half_t = None
        self._lut_t = None
        self._transparent = True
        self._dither = "ordered"
        self._index_quality = self.quality

        self._update_opts_metadata()

    @property
    def device_name(self) -> str:
        return f"cuda:{self.device_index}"

    @property
    def scale_path(self) -> str:
        idx_tag = "exact" if _normalize_quality(self._index_quality) == "exact" else "lut"
        if not self.window_ok:
            return f"gpu-taps-mask-{idx_tag}"
        if self.strength is not None:
            return f"gpu-sgemm-strength-{idx_tag}"
        return f"gpu-sgemm-{idx_tag}"

    def _update_opts_metadata(self) -> None:
        self.opts["_device"] = self.device_name
        self.opts["_scale_path"] = self.scale_path

    def prepare_palette(
        self,
        palette: np.ndarray,
        *,
        transparent: bool,
        dither: str = "ordered",
        quality: str | None = None,
    ) -> None:
        """Upload palette, Bayer dither grid, and 7-bit LUT (for balanced/fast) to the GPU."""
        torch = self._torch
        self._transparent = bool(transparent)
        self._dither = str(dither or "ordered").strip().lower()
        self._index_quality = _normalize_quality(quality if quality is not None else self.quality)
        active = np.ascontiguousarray(palette[1:] if self._transparent else palette, dtype=np.float32)
        if self._dither == "ordered":
            self._bayer_t = torch.from_numpy(_bayer_grid(self.dst_h, self.dst_w)).to(self.device)
        else:
            self._bayer_t = None
        if self._index_quality == "exact":
            self._pal_t = torch.from_numpy(active).to(self.device)
            self._half_t = np.float32(0.5) * (self._pal_t**2).sum(dim=1)
            self._lut_t = None
        else:
            lut_np = build_palette_lut(active)
            self._lut_t = torch.from_numpy(lut_np).to(self.device)
            self._pal_t = None
            self._half_t = None
        self._update_opts_metadata()

    def _scale_tensors(self, frames: Sequence[np.ndarray]):
        """Scale a batch of RGBA frames on GPU and return ``(rgb_f32_0_1, alpha_f32_0_1)`` of shape ``(B, H, W, 3)`` and ``(B, H, W)``."""
        torch = self._torch
        import torch.nn.functional as F

        stacked = np.ascontiguousarray(np.stack(frames, axis=0))
        if stacked.dtype == np.uint8:
            x = torch.from_numpy(stacked).to(self.device, non_blocking=True).to(torch.float32) * np.float32(1.0 / 255.0)
        else:
            x = torch.from_numpy(stacked.astype(np.float32, copy=False)).to(self.device, non_blocking=True)

        batch_len = x.shape[0]
        alpha_min = float(x[..., 3].min().item())
        all_opaque = alpha_min >= _OPAQUE_ALPHA

        if self.window_ok and all_opaque:
            src_rgb = x[..., :3].permute(0, 3, 1, 2).contiguous()
            out_rgb = torch.matmul(self.wy_t, torch.matmul(src_rgb, self.wx_t))
            if self.strength is None or self.strength > 0.0:
                padded = F.pad(src_rgb, (3, 3, 3, 3), mode="replicate")
                hi = F.max_pool2d(padded, kernel_size=6, stride=1)
                lo = -F.max_pool2d(-padded, kernel_size=6, stride=1)
                hi_dst = hi[:, :, self.src_y_t[:, None], self.src_x_t[None, :]]
                lo_dst = lo[:, :, self.src_y_t[:, None], self.src_x_t[None, :]]
                if self.strength is None or self.strength >= 1.0:
                    out_rgb = torch.clamp(out_rgb, lo_dst, hi_dst)
                else:
                    clamped = torch.clamp(out_rgb, lo_dst, hi_dst)
                    out_rgb = out_rgb + (clamped - out_rgb) * float(self.strength)
            rgb_hwc = torch.clamp(out_rgb.permute(0, 2, 3, 1), 0.0, 1.0)
            alpha_hw = torch.ones((batch_len, self.dst_h, self.dst_w), dtype=torch.float32, device=self.device)
            return rgb_hwc, alpha_hw

        # Premultiply alpha for translucent frames or masked-tap exact/downscale path
        alpha = x[..., 3:4]
        premul = torch.cat([x[..., :3] * alpha, alpha], dim=-1)  # (B, src_h, src_w, 4)
        premul_chw = premul.permute(0, 3, 1, 2).contiguous()  # (B, 4, src_h, src_w)
        filtered_chw = torch.matmul(self.wy_t, torch.matmul(premul_chw, self.wx_t))  # (B, 4, dst_h, dst_w)

        if self.window_ok:
            if self.strength is None or self.strength > 0.0:
                src_rgb = premul_chw[:, :3]
                padded = F.pad(src_rgb, (3, 3, 3, 3), mode="replicate")
                hi = F.max_pool2d(padded, kernel_size=6, stride=1)
                lo = -F.max_pool2d(-padded, kernel_size=6, stride=1)
                hi_dst = hi[:, :, self.src_y_t[:, None], self.src_x_t[None, :]]
                lo_dst = lo[:, :, self.src_y_t[:, None], self.src_x_t[None, :]]
                rgb_part = filtered_chw[:, :3]
                if self.strength is None or self.strength >= 1.0:
                    filtered_chw[:, :3] = torch.clamp(rgb_part, lo_dst, hi_dst)
                else:
                    clamped = torch.clamp(rgb_part, lo_dst, hi_dst)
                    filtered_chw[:, :3] = rgb_part + (clamped - rgb_part) * float(self.strength)
        else:
            # Exact / downscale / non-window masked 6-tap neighborhood range on GPU
            src_rgb = premul_chw[:, :3]  # (B, 3, src_h, src_w)
            vlo = torch.full((batch_len, 3, self.dst_h, self.src_w), float("inf"), dtype=torch.float32, device=self.device)
            vhi = torch.full((batch_len, 3, self.dst_h, self.src_w), float("-inf"), dtype=torch.float32, device=self.device)
            for tap in range(self.y_index_t.shape[0]):
                valid_y = self.y_valid_t[tap]
                if not bool(valid_y.any().item()):
                    continue
                rows = src_rgb[:, :, self.y_index_t[tap], :]
                mask_y = valid_y[None, None, :, None]
                vlo = torch.where(mask_y, torch.minimum(vlo, rows), vlo)
                vhi = torch.where(mask_y, torch.maximum(vhi, rows), vhi)
            lo_dst = torch.full((batch_len, 3, self.dst_h, self.dst_w), float("inf"), dtype=torch.float32, device=self.device)
            hi_dst = torch.full((batch_len, 3, self.dst_h, self.dst_w), float("-inf"), dtype=torch.float32, device=self.device)
            for tap in range(self.x_index_t.shape[0]):
                valid_x = self.x_valid_t[tap]
                if not bool(valid_x.any().item()):
                    continue
                cols_lo = vlo[:, :, :, self.x_index_t[tap]]
                cols_hi = vhi[:, :, :, self.x_index_t[tap]]
                mask_x = valid_x[None, None, None, :]
                lo_dst = torch.where(mask_x, torch.minimum(lo_dst, cols_lo), lo_dst)
                hi_dst = torch.where(mask_x, torch.maximum(hi_dst, cols_hi), hi_dst)
            filtered_chw[:, :3] = torch.clamp(filtered_chw[:, :3], lo_dst, hi_dst)

        filtered = filtered_chw.permute(0, 2, 3, 1)  # (B, dst_h, dst_w, 4)
        raw_a = filtered[..., 3]
        safe_a = torch.where(raw_a > 1e-6, raw_a, torch.ones_like(raw_a))
        out_rgb = torch.where(
            raw_a[..., None] > 1e-6,
            filtered[..., :3] / safe_a[..., None],
            torch.zeros_like(filtered[..., :3]),
        )
        out_rgb = torch.clamp(out_rgb, 0.0, 1.0)
        out_a = torch.clamp(raw_a, 0.0, 1.0)
        return out_rgb, out_a

    def scale_batch_float(self, frames: Sequence[np.ndarray]) -> list[np.ndarray]:
        """Scale a batch of frames on GPU and return float32 ``[0, 1]`` RGBA arrays."""
        if not frames:
            return []
        torch = self._torch
        with torch.no_grad():
            rgb, alpha = self._scale_tensors(frames)
            rgba = torch.cat([rgb, alpha[..., None]], dim=-1).cpu().numpy()
        return [rgba[i] for i in range(rgba.shape[0])]

    def scale_batch_uint8(self, frames: Sequence[np.ndarray]) -> list[np.ndarray]:
        """Scale a batch of frames on GPU and return ``uint8`` RGBA arrays (4x less DtoH PCIe traffic)."""
        if not frames:
            return []
        torch = self._torch
        with torch.no_grad():
            rgb, alpha = self._scale_tensors(frames)
            rgba_u8 = torch.clamp(torch.round(torch.cat([rgb, alpha[..., None]], dim=-1) * 255.0), 0.0, 255.0).to(torch.uint8)
            arr = rgba_u8.cpu().numpy()
        return [arr[i] for i in range(arr.shape[0])]

    def _index_tensors(self, rgb_u8_f32, alpha_u8_f32):
        """Run on-device Bayer dither and nearest-palette indexing, returning ``(B, dst_h, dst_w)`` uint8 tensor."""
        torch = self._torch
        batch_len = rgb_u8_f32.shape[0]
        adjusted = rgb_u8_f32 + self._bayer_t[None, :, :, None] if self._bayer_t is not None else rgb_u8_f32

        if self._index_quality == "exact":
            assert self._pal_t is not None and self._half_t is not None
            flat = adjusted.reshape(-1, 3)
            chosen = torch.empty(flat.shape[0], dtype=torch.uint8, device=self.device)
            for start in range(0, flat.shape[0], _EXACT_INDEX_CHUNK):
                chunk = flat[start : start + _EXACT_INDEX_CHUNK]
                scores = torch.addmm(self._half_t, chunk, self._pal_t.T, alpha=-1.0)
                # torch.argmin returns the lowest index on ties, matching NumPy argmin.
                chosen[start : start + _EXACT_INDEX_CHUNK] = scores.argmin(dim=1).to(torch.uint8)
            idx = chosen.reshape(batch_len, self.dst_h, self.dst_w)
        else:
            assert self._lut_t is not None
            clamped = torch.clamp(adjusted, 0.0, 255.0)
            q = torch.round(clamped * np.float32(127.0 / 255.0)).to(torch.int64)
            key = (q[..., 0] << 14) | (q[..., 1] << 7) | q[..., 2]
            idx = self._lut_t[key]

        if self._transparent:
            idx = idx + 1
            idx = torch.where(alpha_u8_f32 < 128.0, torch.zeros_like(idx), idx)
        return idx

    def scale_and_index_batch(self, frames: Sequence[np.ndarray]) -> tuple[np.ndarray, float, float]:
        """Scale + clamp + dither + palette-index a batch on GPU, returning ``(uint8_indices, scale_s, index_s)``."""
        torch = self._torch
        with torch.no_grad():
            t0 = time.perf_counter()
            rgb, alpha = self._scale_tensors(frames)
            rgb_u8_f32 = torch.clamp(torch.round(rgb * 255.0), 0.0, 255.0)
            alpha_u8_f32 = torch.clamp(torch.round(alpha * 255.0), 0.0, 255.0)
            torch.cuda.synchronize(self.device)
            scale_s = time.perf_counter() - t0

            t1 = time.perf_counter()
            idx_gpu = self._index_tensors(rgb_u8_f32, alpha_u8_f32)
            idx_cpu = idx_gpu.cpu().numpy()
            index_s = time.perf_counter() - t1
        return idx_cpu, scale_s, index_s

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.wx_t = None
        self.wy_t = None
        self._bayer_t = None
        self._pal_t = None
        self._half_t = None
        self._lut_t = None
        with contextlib.suppress(Exception):
            self.arbiter.release(self.owner, device=self.device_index)


def acquire_gpu_session(
    *,
    src_h: int,
    src_w: int,
    dst_h: int,
    dst_w: int,
    opts: dict[str, Any],
    algorithm_id: str = _LANCZOS_DERING,
    arbiter: GpuLeaseArbiter | None = None,
    owner: str | None = None,
) -> tuple[GpuResampleSession | None, str | None]:
    """Try to acquire a GPU lease and build a ``GpuResampleSession`` for ``lanczos3-dering``.

    Returns ``(session, None)`` on success, or ``(None, fallback_reason)`` when CPU
    must be used instead.
    """
    if algorithm_id != _LANCZOS_DERING:
        return None, None
    params = opts.get("params") if isinstance(opts.get("params"), dict) else {}
    requested_device = str(params.get("device") or "").strip().lower()
    if requested_device == "cpu":
        opts["_device"] = "cpu"
        return None, None

    try:
        import torch
    except ImportError:
        opts["_device"] = "cpu"
        reason = "PyTorch is not installed; fell back to CPU"
        opts["_gpu_fallback"] = reason
        return None, reason

    if not torch.cuda.is_available():
        opts["_device"] = "cpu"
        reason = "CUDA is unavailable; fell back to CPU"
        opts["_gpu_fallback"] = reason
        return None, reason

    target_device: int | None = None
    if requested_device.startswith("cuda:"):
        tail = requested_device.split(":", 1)[1].strip()
        if tail.isdigit():
            target_device = int(tail)
    elif requested_device.isdigit():
        target_device = int(requested_device)

    active_arbiter = arbiter if isinstance(arbiter, GpuLeaseArbiter) else params.get("gpu_arbiter")
    if not isinstance(active_arbiter, GpuLeaseArbiter):
        table = cuda_device_table()
        if not table:
            opts["_device"] = "cpu"
            reason = "No usable CUDA devices found; fell back to CPU"
            opts["_gpu_fallback"] = reason
            return None, reason
        allow = params.get("allow_devices")
        allow_tuple = tuple(int(x) for x in allow) if isinstance(allow, (list, tuple)) else None
        active_arbiter = GpuLeaseArbiter(
            profile=profile_from_env(),
            devices=table,
            allow_devices=allow_tuple,
        )

    job_owner = owner or f"gif_upscale_{uuid.uuid4().hex[:8]}"
    # Minimum single-frame estimate so conservative profile can check capacity
    min_est_gb = max(0.25, (src_h * src_w * 56 + dst_h * dst_w * 57) * _SAFETY_FACTOR / (1024**3) + _FIXED_OVERHEAD_GB)
    if not active_arbiter.try_acquire(job_owner, estimated_gb=min_est_gb, kind="generate", device=target_device):
        opts["_device"] = "cpu"
        reason = f"{active_arbiter.refusal_text()} Fell back to CPU"
        opts["_gpu_fallback"] = reason
        return None, reason

    leased_index = active_arbiter.device_for(job_owner)
    device_index = int(leased_index) if leased_index is not None else (int(target_device) if target_device is not None else 0)
    free_gb = active_arbiter.free_gb(device_index)
    if free_gb is None:
        try:
            free_bytes, _total_bytes = torch.cuda.mem_get_info(device_index)
            free_gb = float(free_bytes) / (1024**3)
        except Exception:
            free_gb = 4.0

    try:
        session = GpuResampleSession(
            arbiter=active_arbiter,
            owner=job_owner,
            device_index=device_index,
            free_gb=free_gb,
            src_h=src_h,
            src_w=src_w,
            dst_h=dst_h,
            dst_w=dst_w,
            opts=opts,
            algorithm_id=algorithm_id,
        )
    except Exception as exc:
        active_arbiter.release(job_owner, device=device_index)
        opts["_device"] = "cpu"
        reason = f"GPU init failed ({exc}); fell back to CPU"
        opts["_gpu_fallback"] = reason
        return None, reason

    return session, None
