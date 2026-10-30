"""MambaIRv2 stand-in for 4x realistic super-resolution.

The scan is the pure-torch prompt block, not the CUDA kernel: a depthwise
local scan, a gated linear unit, and a residual. This module does not import
mamba_ssm or causal-conv1d. The tail is a 4x pixel shuffle.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.policy import cache_dir, weights_policy
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_ID = "mambairv2"
_OWNER = "gif-upscale-mambairv2"
_FILENAME = "MambaIRv2_SRx4.pth"
_VRAM_MB = 5000
_VRAM_GB = _VRAM_MB / 1000
# Classic MambaIRv2 width. Tests pass the same tiny constructor DRCT uses.
_DEFAULTS = {
    "embed_dim": 174,
    "depths": (6, 6, 6, 6, 6, 6, 6, 6),
    "num_heads": 6,
    "window_size": 16,
    "upscale": 4,
}


def _to_tokens(image: torch.Tensor) -> torch.Tensor:
    return image.flatten(2).transpose(1, 2).contiguous()


def _to_image(tokens: torch.Tensor, height: int, width: int) -> torch.Tensor:
    batch, _length, channels = tokens.shape
    return tokens.transpose(1, 2).reshape(batch, channels, height, width)


class PromptLocalScan(nn.Module):
    """Pure-torch prompt block: depthwise local scan, GLU, and a residual.

    This is not the mamba_ssm selective-scan kernel and not causal-conv1d.
    ``window_size`` is the depthwise kernel. ``num_heads`` splits the learned prompt.
    """

    def __init__(self, dim: int, num_heads: int, window_size: int) -> None:
        super().__init__()
        if dim % num_heads != 0:
            raise ValueError(f"embed_dim {dim} must be divisible by num_heads {num_heads}")
        if window_size < 1:
            raise ValueError("window_size must be positive")
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.norm = nn.LayerNorm(dim)
        self.in_proj = nn.Linear(dim, dim * 2)
        self.local_scan = nn.Conv2d(dim, dim, kernel_size=window_size, padding=0, groups=dim)
        self.prompt = nn.Parameter(torch.zeros(1, 1, num_heads, self.head_dim))
        self.out_proj = nn.Linear(dim, dim)

    def forward(self, tokens: torch.Tensor, height: int, width: int) -> torch.Tensor:
        batch, length, channels = tokens.shape
        value, gate = self.in_proj(self.norm(tokens)).chunk(2, dim=-1)
        image = value.transpose(1, 2).reshape(batch, channels, height, width)
        kernel = int(self.local_scan.kernel_size[0])
        total = kernel - 1
        before = total // 2
        after = total - before
        scanned = self.local_scan(F.pad(image, (before, after, before, after)))
        headed = scanned.flatten(2).transpose(1, 2).reshape(batch, length, self.num_heads, self.head_dim)
        mixed = (headed + self.prompt).reshape(batch, length, channels) * torch.sigmoid(gate)
        return tokens + self.out_proj(mixed)


class ScanGroup(nn.Module):
    """A residual group of prompt local-scan blocks."""

    def __init__(self, dim: int, depth: int, num_heads: int, window_size: int) -> None:
        super().__init__()
        self.blocks = nn.ModuleList(PromptLocalScan(dim, num_heads, window_size) for _ in range(depth))
        self.fuse = nn.Conv2d(dim, dim, kernel_size=3, padding=1)

    def forward(self, tokens: torch.Tensor, height: int, width: int) -> torch.Tensor:
        shortcut = tokens
        for block in self.blocks:
            tokens = block(tokens, height, width)
        fused = self.fuse(_to_image(tokens, height, width)) + _to_image(shortcut, height, width)
        return _to_tokens(fused)


class MambaIRv2(nn.Module):
    """4x MambaIRv2 stand-in. The scan is the pure-torch prompt block, not CUDA."""

    def __init__(
        self,
        embed_dim: int = _DEFAULTS["embed_dim"],
        depths: tuple[int, ...] = _DEFAULTS["depths"],
        num_heads: int = _DEFAULTS["num_heads"],
        window_size: int = _DEFAULTS["window_size"],
        upscale: int = _DEFAULTS["upscale"],
    ) -> None:
        super().__init__()
        if embed_dim % int(num_heads) != 0:
            raise ValueError(f"embed_dim {embed_dim} must be divisible by num_heads {num_heads}")
        if window_size < 1 or int(upscale) < 1 or not depths or any(int(depth) < 1 for depth in depths):
            raise ValueError("window_size, upscale, and depths must be positive")
        self.upscale = int(upscale)
        self.conv_first = nn.Conv2d(3, embed_dim, kernel_size=3, padding=1)
        self.groups = nn.ModuleList(
            ScanGroup(embed_dim, int(depth), int(num_heads), int(window_size)) for depth in depths
        )
        self.conv_body = nn.Conv2d(embed_dim, embed_dim, kernel_size=3, padding=1)
        self.tail = nn.Sequential(
            nn.Conv2d(embed_dim, 3 * self.upscale * self.upscale, kernel_size=3, padding=1),
            nn.PixelShuffle(self.upscale),
        )

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        _batch, _channels, height, width = image.shape
        shallow = self.conv_first(image)
        tokens = _to_tokens(shallow)
        for group in self.groups:
            tokens = group(tokens, height, width)
        deep = self.conv_body(_to_image(tokens, height, width)) + shallow
        return self.tail(deep)


def _checkpoint() -> Path | None:
    """Local weight file. The GIF cache wins over a Hub snapshot already on disk."""
    cached = cache_dir() / _FILENAME
    if cached.is_file():
        return cached
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.is_dir():
        return None
    matches = sorted(path for path in hub.glob(f"**/{_FILENAME}") if path.is_file())
    if not matches:
        return None
    return matches[0]


def _available() -> tuple[bool, str]:
    try:
        policy = weights_policy()
    except ValueError as exc:
        return False, str(exc)
    if _checkpoint() is not None:
        return True, ""
    if policy == "offline":
        return False, f"{_ID} weights are not cached and gif_upscale.weights_policy is offline."
    return False, f"{_ID} weights are not cached."


def _tensor_dict(blob: dict) -> bool:
    return bool(blob) and all(torch.is_tensor(value) for value in blob.values())


def _unwrap_state(blob: object) -> dict:
    if not isinstance(blob, dict):
        raise AlgorithmError(f"{_ID} state dict mismatch: weights are not a state dict.")
    for key in ("params_ema", "params", "state_dict", "model"):
        inner = blob.get(key)
        if isinstance(inner, dict) and _tensor_dict(inner):
            return inner
    if _tensor_dict(blob):
        return blob
    raise AlgorithmError(f"{_ID} state dict mismatch: weights are not a tensor state dict.")


def _read_state(path: Path) -> dict:
    try:
        blob = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as exc:
        raise AlgorithmError(f"{_ID} could not read weights {path.name}: {exc}") from exc
    return _unwrap_state(blob)


def _apply_state(model: nn.Module, state: dict) -> None:
    try:
        model.load_state_dict(state, strict=True)
    except (RuntimeError, ValueError) as exc:
        raise AlgorithmError(f"{_ID} state dict mismatch: {exc}") from exc


def _load_model(path: Path) -> MambaIRv2:
    model = MambaIRv2()
    _apply_state(model, _read_state(path))
    model.eval()
    return model


def _require_scale(scale: float) -> None:
    try:
        value = float(scale)
    except (TypeError, ValueError) as exc:
        raise AlgorithmError(f"{_ID} supports scale 4, not {scale!r}.") from exc
    if not np.isfinite(value) or abs(value - 4.0) > 1e-3:
        raise AlgorithmError(f"{_ID} supports scale 4, not {scale!r}.")


def _require_frames(frames: list[np.ndarray] | None) -> list[np.ndarray]:
    if not frames:
        raise AlgorithmError(f"{_ID} needs frames.")
    prepared: list[np.ndarray] = []
    for frame in frames:
        array = np.asarray(frame)
        if array.ndim != 3 or array.shape[2] != 4 or array.shape[0] < 1 or array.shape[1] < 1:
            raise AlgorithmError(f"{_ID} expected HxWx4 frames, got {getattr(array, 'shape', None)}.")
        array = np.ascontiguousarray(array, dtype=np.float32)
        if not np.isfinite(array).all():
            raise AlgorithmError(f"{_ID} refused a frame with non-finite values.")
        prepared.append(array)
    return prepared


def _nearest_alpha(alpha: np.ndarray, height: int, width: int) -> np.ndarray:
    if alpha.shape == (height, width):
        return np.ascontiguousarray(alpha, dtype=np.float32)
    from PIL import Image

    image = Image.fromarray(np.clip(np.rint(alpha * 255.0), 0, 255).astype(np.uint8), "L")
    try:
        resized = image.resize((width, height), Image.Resampling.NEAREST)
        try:
            return np.asarray(resized).astype(np.float32) / 255.0
        finally:
            resized.close()
    finally:
        image.close()


def _run_model(model: nn.Module, frames: list[np.ndarray], device: torch.device) -> list[np.ndarray]:
    model.eval()
    model.to(device)
    output: list[np.ndarray] = []
    for frame in frames:
        rgb = np.ascontiguousarray(frame[:, :, :3])
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(device)
        with torch.inference_mode():
            predicted = model(tensor)
        color = predicted.squeeze(0).permute(1, 2, 0).contiguous().detach().to("cpu").numpy()
        expected = (frame.shape[0] * 4, frame.shape[1] * 4)
        if color.shape[:2] != expected or color.shape[2] != 3 or not np.isfinite(color).all():
            raise AlgorithmError(f"{_ID} produced non-finite pixels or the wrong 4x shape.")
        color = np.clip(color, 0.0, 1.0).astype(np.float32, copy=False)
        alpha = _nearest_alpha(frame[:, :, 3], color.shape[0], color.shape[1])
        output.append(np.dstack((color, alpha)).astype(np.float32, copy=False))
    return output


def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    """Upscale HxWx4 float frames in 0..1. RGB uses the network; alpha is nearest."""
    del opts
    _require_scale(scale)
    prepared = _require_frames(frames)
    ready, reason = _available()
    if not ready:
        raise AlgorithmError(reason)
    path = _checkpoint()
    if path is None:
        raise AlgorithmError(reason or f"{_ID} weights are not cached.")
    from middleware.src.comfy_matrix import gpu_lease, try_admit

    refusal = try_admit(_OWNER, estimated_gb=_VRAM_GB, kind="generate")
    if refusal:
        raise AlgorithmError(refusal)
    try:
        model = _load_model(path)
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return _run_model(model, prepared, device)
    finally:
        gpu_lease.release(_OWNER)


register_algorithm(
    AlgorithmSpec(
        id=_ID,
        family=_ID,
        content="realistic",
        kind="neural",
        supports_scale=frozenset({4.0}),
        supports_downscale=False,
        needs_gpu=True,
        vram_mb_estimate=_VRAM_MB,
        license="Apache-2.0",
        weights_sha256=None,
        available=_available,
        containers=("gif", "still"),
    ),
    upscale,
)
