"""DOVE clip upscaler.

This is the pure-torch temporal shell (SeedVR2 DiT, FlashVSR block-sparse
attention, and DOVE's CogVideoX backbone are not bundled). A strict weight
load fails closed if an official checkpoint does not match, which is correct.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.policy import cache_dir, weights_policy
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_ID = "dove"
_FILENAME = "DOVE_SRx4.pth"
_OWNER = "gif-upscale-dove"
_VRAM_MB = 11000


class _ResidualBlock(nn.Module):
    def __init__(self, channels: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.act = nn.LeakyReLU(0.2, inplace=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.conv2(self.act(self.conv1(x)))


class TemporalShell(nn.Module):
    """Pure-torch temporal shell.

    SeedVR2 DiT, FlashVSR block-sparse attention, and DOVE's CogVideoX backbone
    are not bundled. ``load_state_dict(..., strict=True)`` fails closed when an
    official checkpoint does not match this shell.
    """

    def __init__(self, channels: int = 8, n_blocks: int = 1) -> None:
        super().__init__()
        if channels < 1 or n_blocks < 1:
            raise ValueError("channels and n_blocks must be positive")
        self.temporal = nn.Conv3d(3, channels, kernel_size=(3, 1, 1), padding=(1, 0, 0))
        self.blocks = nn.Sequential(*(_ResidualBlock(channels) for _ in range(n_blocks)))
        self.tail = nn.Conv2d(channels, 3 * 16, kernel_size=3, padding=1)
        self.shuffle = nn.PixelShuffle(4)

    def forward(self, clip: torch.Tensor) -> torch.Tensor:
        added_batch = clip.ndim == 4
        if added_batch:
            clip = clip.unsqueeze(0)
        if clip.ndim != 5 or clip.shape[2] != 3:
            raise ValueError("clip must be (T, 3, H, W) or (1, T, 3, H, W)")
        mixed = self.temporal(clip.permute(0, 2, 1, 3, 4))
        batch, channels, time, height, width = mixed.shape
        spatial = mixed.permute(0, 2, 1, 3, 4).reshape(batch * time, channels, height, width)
        spatial = self.blocks(spatial)
        restored = self.shuffle(self.tail(spatial))
        restored = restored.reshape(batch, time, 3, height * 4, width * 4)
        if added_batch:
            return restored[0]
        return restored


def _local_checkpoint() -> str | None:
    cached = cache_dir() / _FILENAME
    if cached.is_file():
        return str(cached)
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.is_dir():
        return None
    matches = sorted(path for path in hub.glob(f"**/{_FILENAME}") if path.is_file())
    if not matches:
        return None
    return str(matches[0])


def _available() -> tuple[bool, str]:
    if _local_checkpoint() is not None:
        return True, ""
    try:
        policy = weights_policy()
    except ValueError as exc:
        return False, f"{_ID}: {exc}"
    if policy == "offline":
        return False, f"{_ID} weights are not cached and gif_upscale.weights_policy is offline."
    return False, f"{_ID} weights are not cached."


def _nearest_alpha(alpha: np.ndarray, height: int, width: int) -> np.ndarray:
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


def _cuda_ready() -> bool:
    is_available = getattr(torch.cuda, "is_available", None)
    return bool(callable(is_available) and is_available())


def _load_shell(path: str) -> TemporalShell:
    model = TemporalShell()
    try:
        blob = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(blob, dict):
            raise AlgorithmError(f"{_ID} checkpoint is not a state dict.")
        model.load_state_dict(blob, strict=True)
    except AlgorithmError:
        raise
    except Exception as exc:
        raise AlgorithmError(f"{_ID} weights do not match the temporal shell: {exc}") from exc
    model.eval()
    return model


def _same_shape(frames: list[np.ndarray]) -> None:
    first = np.asarray(frames[0])
    if first.ndim != 3 or first.shape[2] != 4:
        raise AlgorithmError(f"{_ID} expects HxWx4 frames.")
    for frame in frames[1:]:
        if np.asarray(frame).shape != first.shape:
            raise AlgorithmError(f"{_ID} expects every frame to share a shape.")


def _infer(model: TemporalShell, frames: list[np.ndarray]) -> list[np.ndarray]:
    rgb = np.stack([np.asarray(frame, dtype=np.float32)[:, :, :3] for frame in frames], axis=0)
    clip = torch.from_numpy(np.ascontiguousarray(rgb)).permute(0, 3, 1, 2)
    device = torch.device("cuda" if _cuda_ready() else "cpu")
    model = model.to(device)
    with torch.no_grad():
        output = model(clip.to(device))
    planes = output.detach().float().clamp(0, 1).permute(0, 2, 3, 1).cpu().numpy()
    scaled: list[np.ndarray] = []
    for index, frame in enumerate(frames):
        color = np.asarray(planes[index], dtype=np.float32)
        alpha = _nearest_alpha(np.asarray(frame, dtype=np.float32)[:, :, 3], color.shape[0], color.shape[1])
        scaled.append(np.dstack([color, alpha]).astype(np.float32))
    return scaled


def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    del opts
    if abs(float(scale) - 4.0) > 1e-3:
        raise AlgorithmError(f"{_ID} supports scale 4, not {scale}.")
    if not frames:
        return []
    _same_shape(frames)
    path = _local_checkpoint()
    if path is None:
        _ok, reason = _available()
        raise AlgorithmError(reason or f"{_ID} weights are not cached.")
    from middleware.src.comfy_matrix import gpu_lease, try_admit

    refusal = try_admit(_OWNER, estimated_gb=_VRAM_MB / 1024.0, kind="generate")
    if refusal:
        raise AlgorithmError(refusal)
    try:
        return _infer(_load_shell(path), frames)
    finally:
        gpu_lease.release(_OWNER)


register_algorithm(
    AlgorithmSpec(
        id=_ID,
        family="video",
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
