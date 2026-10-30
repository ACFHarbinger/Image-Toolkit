"""TSD-SR 4x inference shell: one-step residual on a bicubic reference, plus a fidelity guard.

The published network is a distilled diffusion UNet. This path does not train and does
not download weights. A miss blends toward the bicubic reference; it does not swap the
caller's algorithm for Lanczos.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.policy import cache_dir, weights_policy
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_ID = "tsd-sr"
_WEIGHT = "TSDSR_SRx4.pth"
_OWNER = "gif-upscale-tsd-sr"
_VRAM_MB = 5500
_SCALE = 4
_NESTED = ("state_dict", "params_ema", "params", "model", "model_state_dict")


class _ResidualConv(nn.Module):
    def __init__(self, width: int) -> None:
        super().__init__()
        self.conv1 = nn.Conv2d(width, width, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(width, width, kernel_size=3, padding=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.conv2(F.relu(self.conv1(x)))
        return x + residual


class OneStepResidualSR(nn.Module):
    """Shallow conv encoder, residual conv blocks, pixel-shuffle 4x residual on bicubic."""

    def __init__(self, width: int = 64, n_blocks: int = 4) -> None:
        super().__init__()
        if int(width) < 1 or int(n_blocks) < 1:
            raise ValueError("width and n_blocks must be positive")
        self.encoder = nn.Conv2d(3, int(width), kernel_size=3, padding=1)
        self.blocks = nn.ModuleList(_ResidualConv(int(width)) for _ in range(int(n_blocks)))
        self.tail = nn.Conv2d(int(width), 3 * _SCALE * _SCALE, kernel_size=3, padding=1)
        self.shuffle = nn.PixelShuffle(_SCALE)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        reference = F.interpolate(x, scale_factor=_SCALE, mode="bicubic", align_corners=False)
        hidden = F.relu(self.encoder(x))
        for block in self.blocks:
            hidden = block(hidden)
        return reference + self.shuffle(self.tail(hidden))


def _local_weight() -> Path | None:
    cached = cache_dir() / _WEIGHT
    if cached.is_file():
        return cached
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    if not hub.is_dir():
        return None
    matches = sorted(path for path in hub.glob(f"**/{_WEIGHT}") if path.is_file())
    if not matches:
        return None
    return matches[0]


def _missing_reason() -> str:
    try:
        policy = weights_policy()
    except ValueError as exc:
        return str(exc)
    if policy == "offline":
        return f"{_ID} weights are not cached and gif_upscale.weights_policy is offline."
    return f"{_ID} weights are not cached."


def available() -> tuple[bool, str]:
    if _local_weight() is not None:
        return True, ""
    return False, _missing_reason()


def _mean_absolute_error(predicted: np.ndarray, reference: np.ndarray) -> float:
    return float(np.mean(np.abs(predicted.astype(np.float32) - reference.astype(np.float32))))


def apply_fidelity_guard(predicted: np.ndarray, reference: np.ndarray, opts: dict | None) -> np.ndarray:
    """Blend toward bicubic when the distance exceeds the limit. Never calls Lanczos."""
    options = opts or {}
    distance_fn = options.get("fidelity_distance") or _mean_absolute_error
    distance = float(distance_fn(predicted, reference))
    if distance > float(options.get("fidelity_limit", 0.25)):
        blend = float(options.get("fidelity_blend", 0.5))
        mixed = (1.0 - blend) * predicted + blend * reference
        return np.asarray(mixed, dtype=np.float32)
    return np.asarray(predicted, dtype=np.float32)


def _frames(frames: list[np.ndarray] | None) -> list[np.ndarray]:
    if not frames:
        raise AlgorithmError(f"{_ID} frames are required")
    prepared: list[np.ndarray] = []
    for frame in frames:
        array = np.array(frame, dtype=np.float32, copy=True)
        if array.ndim != 3 or array.shape[2] != 4:
            raise AlgorithmError(f"{_ID} expected HxWx4 frames, got {getattr(frame, 'shape', None)}")
        if array.shape[0] < 1 or array.shape[1] < 1:
            raise AlgorithmError(f"{_ID} source size must be positive")
        prepared.append(array)
    return prepared


def _tensor_dict(blob: dict) -> bool:
    return bool(blob) and all(torch.is_tensor(value) for value in blob.values())


def _unwrap(blob: object) -> dict[str, torch.Tensor]:
    if not isinstance(blob, dict):
        raise AlgorithmError(f"{_ID} checkpoint must be a state dict.")
    for key in _NESTED:
        nested = blob.get(key)
        if isinstance(nested, dict) and _tensor_dict(nested):
            return nested
    if _tensor_dict(blob):
        return blob
    raise AlgorithmError(f"{_ID} checkpoint must be a state dict.")


def _architecture(state: dict[str, torch.Tensor]) -> tuple[int, int]:
    weight = state.get("encoder.weight")
    if not torch.is_tensor(weight) or weight.ndim != 4 or int(weight.shape[1]) != 3:
        raise AlgorithmError(f"{_ID} checkpoint is not the one-step residual shell.")
    indexes = [int(key.split(".")[1]) for key in state if key.startswith("blocks.")]
    n_blocks = max(indexes) + 1 if indexes else 0
    width = int(weight.shape[0])
    if width < 1 or n_blocks < 1:
        raise AlgorithmError(f"{_ID} checkpoint is not the one-step residual shell.")
    return width, n_blocks


def _load_network(path: Path) -> OneStepResidualSR:
    try:
        blob = torch.load(path, map_location="cpu", weights_only=True)
    except (OSError, RuntimeError, pickle.UnpicklingError, ValueError) as exc:
        raise AlgorithmError(f"{_ID} could not read {path.name}: {exc}") from exc
    state = _unwrap(blob)
    width, n_blocks = _architecture(state)
    network = OneStepResidualSR(width=width, n_blocks=n_blocks)
    try:
        network.load_state_dict(state, strict=True)
    except RuntimeError as exc:
        raise AlgorithmError(f"{_ID} checkpoint does not match the one-step shell: {exc}") from exc
    network.eval()
    return network


def _hwc(tensor: torch.Tensor) -> np.ndarray:
    array = tensor.detach().squeeze(0).permute(1, 2, 0).contiguous().numpy()
    return np.array(array, dtype=np.float32, copy=True)


def _nearest_alpha(alpha: np.ndarray) -> np.ndarray:
    return np.repeat(np.repeat(alpha, _SCALE, axis=0), _SCALE, axis=1)


def _run(frames: list[np.ndarray], opts: dict, path: Path) -> list[np.ndarray]:
    # The lease reserves the GPU. This conv shell stays on CPU: it is not the
    # distilled UNet, and the suite must not move the process onto CUDA.
    network = _load_network(path)
    output: list[np.ndarray] = []
    for frame in frames:
        rgb = np.ascontiguousarray(frame[:, :, :3])
        tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0)
        with torch.no_grad():
            predicted = network(tensor)
            reference = F.interpolate(tensor, scale_factor=_SCALE, mode="bicubic", align_corners=False)
        guarded = apply_fidelity_guard(_hwc(predicted), _hwc(reference), opts)
        color = np.clip(guarded, 0.0, 1.0).astype(np.float32, copy=False)
        output.append(np.dstack((color, _nearest_alpha(frame[:, :, 3]))))
    return output


def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    prepared = _frames(frames)
    if abs(float(scale) - float(_SCALE)) > 1e-3:
        raise AlgorithmError(f"{_ID} supports scale {_SCALE}, not {scale}.")
    path = _local_weight()
    if path is None:
        raise AlgorithmError(_missing_reason())
    from middleware.src.comfy_matrix import gpu_lease, try_admit

    refusal = try_admit(_OWNER, estimated_gb=_VRAM_MB / 1000, kind="generate")
    if refusal:
        raise AlgorithmError(refusal)
    try:
        return _run(prepared, opts or {}, path)
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
        available=available,
        containers=("gif", "still"),
    ),
    upscale,
)
