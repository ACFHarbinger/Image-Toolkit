"""Realistic Real-ESRGAN checkpoints: x4plus, x2plus, and general-x4v3.

Weights are read from the GIF cache or the local Hugging Face hub cache.
Nothing is downloaded: ``weights_sha256`` is unset, so a missing file stays missing.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from middleware.src.models.wrappers.esrgan_wrapper import RRDB, RRDBNet
from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.neural.realesrgan import _nearest_alpha
from middleware.src.services.media.gif_upscale.policy import cache_dir, weights_policy
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_TILE = 400
_TILE_PAD = 10


class RRDBNetX2(nn.Module):
    """Official Real-ESRGAN x2plus RRDBNet (BasicSR scale=2).

    PixelUnshuffle(2) makes conv_first a 12-channel conv. Two nearest 2x
    stages then bring the half-resolution map back to 2x. Odd H or W is
    reflect-padded so the unshuffle is legal, and the output is cropped
    to twice the original size.
    """

    def __init__(
        self,
        num_in_ch: int = 3,
        num_out_ch: int = 3,
        num_feat: int = 64,
        num_block: int = 23,
        num_grow_ch: int = 32,
    ):
        super().__init__()
        # scale=2 unshuffles first, so RGB (3) arrives as 12 channels.
        self.conv_first = nn.Conv2d(num_in_ch * 4, num_feat, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)
        self.unshuffle = nn.PixelUnshuffle(2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, _, height, width = x.shape
        pad_h = height % 2
        pad_w = width % 2
        if pad_h or pad_w:
            x = F.pad(x, (0, pad_w, 0, pad_h), mode="reflect")
        feat = self.unshuffle(x)
        feat = self.conv_first(feat)
        feat = feat + self.conv_body(self.body(feat))
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        out = self.conv_last(self.lrelu(self.conv_hr(feat)))
        return out[:, :, : height * 2, : width * 2]


class SRVGGNetCompact(nn.Module):
    """Published realesr-general-x4v3.

    The checkpoint is a conv/PReLU ``body`` plus a parameter-free PixelShuffle.
    There is no HR convolution; the nearest-upsampled input is added back.
    """

    def __init__(
        self,
        num_in_ch: int = 3,
        num_out_ch: int = 3,
        num_feat: int = 64,
        num_conv: int = 32,
        upscale: int = 4,
    ):
        super().__init__()
        self.upscale = upscale
        layers: list[nn.Module] = [
            nn.Conv2d(num_in_ch, num_feat, 3, 1, 1),
            nn.PReLU(num_parameters=num_feat),
        ]
        for _ in range(num_conv):
            layers.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            layers.append(nn.PReLU(num_parameters=num_feat))
        layers.append(nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1))
        self.body = nn.ModuleList(layers)
        self.upsampler = nn.PixelShuffle(upscale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = x
        for layer in self.body:
            out = layer(out)
        out = self.upsampler(out)
        return out + F.interpolate(x, scale_factor=self.upscale, mode="nearest")


@dataclass(frozen=True)
class _Model:
    algorithm_id: str
    filename: str
    scale: float
    vram_mb: int
    detail: str
    build: Callable[[], nn.Module]


def _local_weight(filename: str) -> Path | None:
    """A weight file already on disk. The GIF cache wins over the Hugging Face cache."""
    cached = cache_dir() / filename
    if cached.is_file():
        return cached
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.is_dir():
        return None
    matches = sorted(hub.glob(f"**/{filename}"))
    if not matches:
        return None
    return matches[0]


def _missing_reason(spec: _Model, policy: str) -> str:
    if policy == "offline":
        return (
            f"{spec.algorithm_id} weights are not cached ({spec.filename}, {spec.detail}) "
            "and gif_upscale.weights_policy is offline."
        )
    return f"{spec.algorithm_id} weights are not cached ({spec.filename})."


def _availability(spec: _Model) -> tuple[bool, str]:
    try:
        policy = weights_policy()
    except ValueError as exc:
        return False, str(exc)
    if _local_weight(spec.filename) is not None:
        return True, ""
    return False, _missing_reason(spec, policy)


def _unwrap_state(blob: object, spec: _Model) -> dict:
    if isinstance(blob, dict) and ("params_ema" in blob or "params" in blob):
        blob = blob.get("params_ema", blob.get("params"))
    if not isinstance(blob, dict):
        raise AlgorithmError(f"{spec.algorithm_id} weights in {spec.filename} are not a state dict.")
    return blob


def _load_state(path: Path, spec: _Model) -> dict:
    try:
        blob = torch.load(path, map_location="cpu")
    except Exception as exc:
        raise AlgorithmError(f"{spec.algorithm_id} could not read {spec.filename}: {exc}") from exc
    return _unwrap_state(blob, spec)


def _check_scale(spec: _Model, scale: float) -> None:
    try:
        factor = float(scale)
    except (TypeError, ValueError) as exc:
        raise AlgorithmError(f"{spec.algorithm_id} supports scales {spec.scale}, not {scale!r}.") from exc
    if factor != factor or abs(factor - spec.scale) > 1e-3:
        raise AlgorithmError(f"{spec.algorithm_id} supports scales {spec.scale}, not {scale}.")


def _prepare(frame: np.ndarray, algorithm_id: str) -> np.ndarray:
    array = np.asarray(frame)
    if array.ndim != 3 or array.shape[2] != 4:
        raise AlgorithmError(f"{algorithm_id} expected HxWx4 frames, got {getattr(frame, 'shape', None)}")
    if array.shape[0] < 1 or array.shape[1] < 1:
        raise AlgorithmError(f"{algorithm_id} source size must be positive")
    return array


def _forward_tiled(model: nn.Module, tensor: torch.Tensor, scale: int) -> torch.Tensor:
    _, _, height, width = tensor.shape
    if max(height, width) <= _TILE:
        return model(tensor).float().cpu()
    out_h, out_w = height * scale, width * scale
    output = torch.zeros((1, 3, out_h, out_w), dtype=torch.float32)
    tile = _TILE
    pad = _TILE_PAD
    tiles_x = (width + tile - 1) // tile
    tiles_y = (height + tile - 1) // tile
    for ty in range(tiles_y):
        for tx in range(tiles_x):
            x0, y0 = tx * tile, ty * tile
            x1, y1 = min(x0 + tile, width), min(y0 + tile, height)
            px0, py0 = max(0, x0 - pad), max(0, y0 - pad)
            px1, py1 = min(width, x1 + pad), min(height, y1 + pad)
            tile_out = model(tensor[:, :, py0:py1, px0:px1]).float().cpu()
            keep_x0 = (x0 - px0) * scale
            keep_y0 = (y0 - py0) * scale
            keep_x1 = keep_x0 + (x1 - x0) * scale
            keep_y1 = keep_y0 + (y1 - y0) * scale
            output[:, :, y0 * scale : y1 * scale, x0 * scale : x1 * scale] = tile_out[
                :, :, keep_y0:keep_y1, keep_x0:keep_x1
            ]
    return output


def _infer(model: nn.Module, frames: list[np.ndarray], spec: _Model) -> list[np.ndarray]:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.eval()
    model.to(device)
    scale = int(spec.scale)
    output: list[np.ndarray] = []
    try:
        with torch.no_grad():
            for frame in frames:
                array = _prepare(frame, spec.algorithm_id)
                rgb = np.asarray(array[:, :, :3], dtype=np.float32)
                tensor = torch.from_numpy(np.ascontiguousarray(rgb.transpose(2, 0, 1))).unsqueeze(0).to(device)
                pred = _forward_tiled(model, tensor, scale).squeeze(0).clamp(0, 1).numpy()
                color = np.transpose(pred, (1, 2, 0)).astype(np.float32, copy=False)
                alpha = _nearest_alpha(array[:, :, 3], color.shape[0], color.shape[1])
                output.append(np.dstack([color, alpha]).astype(np.float32, copy=False))
    finally:
        model.to("cpu")
    return output


def _upscale_photo(spec: _Model, frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    del opts
    ok, reason = _availability(spec)
    if not ok:
        raise AlgorithmError(reason)
    _check_scale(spec, scale)
    if not frames:
        return []
    path = _local_weight(spec.filename)
    if path is None:
        raise AlgorithmError(_missing_reason(spec, weights_policy()))
    from middleware.src.comfy_matrix import gpu_lease, try_admit

    owner = f"gif-upscale-{spec.algorithm_id}"
    refusal = try_admit(owner, estimated_gb=spec.vram_mb / 1024, kind="generate")
    if refusal:
        raise AlgorithmError(refusal)
    try:
        model = spec.build()
        try:
            model.load_state_dict(_load_state(path, spec), strict=True)
        except AlgorithmError:
            raise
        except (RuntimeError, ValueError) as exc:
            raise AlgorithmError(
                f"{spec.algorithm_id} weights in {spec.filename} do not match the network: {exc}"
            ) from exc
        return _infer(model, frames, spec)
    finally:
        gpu_lease.release(owner)


def _bind(spec: _Model) -> None:
    def available() -> tuple[bool, str]:
        return _availability(spec)

    def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
        return _upscale_photo(spec, frames, scale, opts)

    register_algorithm(
        AlgorithmSpec(
            id=spec.algorithm_id,
            family="realesrgan",
            content="realistic",
            kind="neural",
            supports_scale=frozenset({spec.scale}),
            supports_downscale=False,
            needs_gpu=True,
            vram_mb_estimate=spec.vram_mb,
            license="BSD-3-Clause",
            weights_sha256=None,
            containers=("gif", "still"),
            available=available,
        ),
        upscale,
    )


_MODELS = (
    _Model(
        algorithm_id="realesrgan-x4plus",
        filename="RealESRGAN_x4plus.pth",
        scale=4.0,
        vram_mb=2500,
        detail="23-block RRDBNet",
        build=lambda: RRDBNet(num_feat=64, num_block=23, num_grow_ch=32),
    ),
    _Model(
        algorithm_id="realesrgan-x2plus",
        filename="RealESRGAN_x2plus.pth",
        scale=2.0,
        vram_mb=2500,
        detail="2x RRDBNet",
        build=lambda: RRDBNetX2(num_feat=64, num_block=23, num_grow_ch=32),
    ),
    _Model(
        algorithm_id="realesrgan-general-x4v3",
        filename="realesr-general-x4v3.pth",
        scale=4.0,
        vram_mb=800,
        detail="SRVGGNetCompact",
        build=lambda: SRVGGNetCompact(num_feat=64, num_conv=32, upscale=4),
    ),
)

for _model in _MODELS:
    _bind(_model)
