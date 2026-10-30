"""Dense residual-connected transformer for 4x realistic super-resolution.

Each group runs window self-attention, concatenates those block outputs, and
compresses the concatenation with a 1x1 convolution plus a residual. The tail
is a 4x pixel shuffle. Plain PyTorch only: no basicsr and no weight download.
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

_ID = "drct"
_OWNER = "gif-upscale-drct"
_FILENAME = "DRCT_SRx4.pth"
_VRAM_MB = 4500
_VRAM_GB = _VRAM_MB / 1000
# Published DRCT width: 6 groups, 180 channels, 6 heads, window 16. Tests pass a tiny net.
_DEFAULTS = {
    "embed_dim": 180,
    "depths": (6, 6, 6, 6, 6, 6),
    "num_heads": 6,
    "window_size": 16,
    "upscale": 4,
}


def _window_partition(image: torch.Tensor, window_size: int) -> torch.Tensor:
    batch, height, width, channels = image.shape
    windows = image.view(batch, height // window_size, window_size, width // window_size, window_size, channels)
    windows = windows.permute(0, 1, 3, 2, 4, 5).contiguous()
    return windows.view(-1, window_size * window_size, channels)


def _window_reverse(windows: torch.Tensor, window_size: int, height: int, width: int) -> torch.Tensor:
    channels = windows.shape[-1]
    count = (height // window_size) * (width // window_size)
    batch = windows.shape[0] // count
    image = windows.view(batch, height // window_size, width // window_size, window_size, window_size, channels)
    image = image.permute(0, 1, 3, 2, 4, 5).contiguous()
    return image.view(batch, height, width, channels)


def _attention_mask(
    height: int,
    width: int,
    window_size: int,
    shift: int,
    device: torch.device,
) -> torch.Tensor | None:
    """Keep a cyclic shift from attending across window borders."""
    if shift <= 0:
        return None
    canvas = torch.zeros((1, height, width, 1), device=device)
    sections = (slice(0, -window_size), slice(-window_size, -shift), slice(-shift, None))
    region = 0
    for row in sections:
        for col in sections:
            canvas[:, row, col, :] = region
            region += 1
    windows = _window_partition(canvas, window_size).squeeze(-1)
    difference = windows.unsqueeze(2) - windows.unsqueeze(1)
    return difference.masked_fill(difference != 0, -100.0)


def _pad_to_window(image: torch.Tensor, window_size: int) -> torch.Tensor:
    height, width = image.shape[-2:]
    pad_h = (window_size - height % window_size) % window_size
    pad_w = (window_size - width % window_size) % window_size
    if pad_h == 0 and pad_w == 0:
        return image
    return F.pad(image, (0, pad_w, 0, pad_h))


def _to_tokens(image: torch.Tensor) -> torch.Tensor:
    return image.flatten(2).transpose(1, 2).contiguous()


def _to_image(tokens: torch.Tensor, height: int, width: int) -> torch.Tensor:
    batch, _length, channels = tokens.shape
    return tokens.transpose(1, 2).reshape(batch, channels, height, width)


class WindowAttention(nn.Module):
    """Multi-head self-attention inside one window, with a relative position bias."""

    def __init__(self, dim: int, num_heads: int, window_size: int) -> None:
        super().__init__()
        if dim % num_heads != 0:
            raise ValueError(f"embed_dim {dim} must be divisible by num_heads {num_heads}")
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim**-0.5
        self.window_size = window_size
        self.qkv = nn.Linear(dim, dim * 3)
        self.proj = nn.Linear(dim, dim)
        bias_len = (2 * window_size - 1) ** 2
        self.relative_position_bias_table = nn.Parameter(torch.zeros(bias_len, num_heads))
        coords = torch.arange(window_size)
        grid = torch.stack(torch.meshgrid(coords, coords, indexing="ij"))
        flat = grid.reshape(2, -1)
        relative = (flat[:, :, None] - flat[:, None, :]).permute(1, 2, 0).contiguous()
        relative[:, :, 0] += window_size - 1
        relative[:, :, 1] += window_size - 1
        relative[:, :, 0] *= 2 * window_size - 1
        index = relative.sum(-1).long()
        self.register_buffer("relative_position_index", index, persistent=False)

    def forward(self, windows: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        count, length, channels = windows.shape
        qkv = self.qkv(windows).reshape(count, length, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)
        query, key, value = qkv.unbind(0)
        scores = (query * self.scale) @ key.transpose(-2, -1)
        bias = self.relative_position_bias_table[self.relative_position_index.reshape(-1)]
        bias = bias.view(length, length, self.num_heads).permute(2, 0, 1).contiguous()
        scores = scores + bias.unsqueeze(0)
        if mask is not None:
            n_windows = mask.shape[0]
            scores = scores.view(-1, n_windows, self.num_heads, length, length)
            scores = scores + mask.unsqueeze(1).unsqueeze(0)
            scores = scores.view(count, self.num_heads, length, length)
        mixed = scores.softmax(dim=-1) @ value
        mixed = mixed.transpose(1, 2).reshape(count, length, channels)
        return self.proj(mixed)


class WindowAttentionBlock(nn.Module):
    """Pre-norm window attention and an MLP. Odd blocks use a shifted window."""

    def __init__(self, dim: int, num_heads: int, window_size: int, *, shift: bool) -> None:
        super().__init__()
        self.window_size = window_size
        self.shift_size = window_size // 2 if shift else 0
        self.norm1 = nn.LayerNorm(dim)
        self.attn = WindowAttention(dim, num_heads, window_size)
        self.norm2 = nn.LayerNorm(dim)
        hidden = dim * 2
        self.mlp = nn.Sequential(nn.Linear(dim, hidden), nn.GELU(), nn.Linear(hidden, dim))

    def forward(self, tokens: torch.Tensor, height: int, width: int) -> torch.Tensor:
        batch, _length, channels = tokens.shape
        shortcut = tokens
        features = self.norm1(tokens).view(batch, height, width, channels)
        if self.shift_size:
            features = torch.roll(features, shifts=(-self.shift_size, -self.shift_size), dims=(1, 2))
        windows = _window_partition(features, self.window_size)
        mask = _attention_mask(height, width, self.window_size, self.shift_size, features.device)
        windows = self.attn(windows, mask)
        merged = _window_reverse(windows, self.window_size, height, width)
        if self.shift_size:
            merged = torch.roll(merged, shifts=(self.shift_size, self.shift_size), dims=(1, 2))
        attended = shortcut + merged.view(batch, height * width, channels)
        return attended + self.mlp(self.norm2(attended))


class DenseResidualGroup(nn.Module):
    """Concatenate every block output, compress with a 1x1 conv, and add the input."""

    def __init__(self, dim: int, depth: int, num_heads: int, window_size: int) -> None:
        super().__init__()
        self.blocks = nn.ModuleList(
            WindowAttentionBlock(dim, num_heads, window_size, shift=bool(index % 2)) for index in range(depth)
        )
        self.compress = nn.Conv2d(dim * depth, dim, kernel_size=1)

    def forward(self, tokens: torch.Tensor, height: int, width: int) -> torch.Tensor:
        batch, _length, channels = tokens.shape
        outputs: list[torch.Tensor] = []
        current = tokens
        for block in self.blocks:
            current = block(current, height, width)
            outputs.append(current)
        packed = torch.cat(outputs, dim=-1)
        image = packed.transpose(1, 2).reshape(batch, channels * len(outputs), height, width)
        fused = self.compress(image)
        residual = tokens.transpose(1, 2).reshape(batch, channels, height, width)
        return (fused + residual).flatten(2).transpose(1, 2)


class DRCT(nn.Module):
    """4x dense residual transformer. ``depths`` is the block count of each group."""

    def __init__(
        self,
        embed_dim: int = _DEFAULTS["embed_dim"],
        depths: tuple[int, ...] = _DEFAULTS["depths"],
        num_heads: int = _DEFAULTS["num_heads"],
        window_size: int = _DEFAULTS["window_size"],
        upscale: int = _DEFAULTS["upscale"],
    ) -> None:
        super().__init__()
        if embed_dim % num_heads != 0:
            raise ValueError(f"embed_dim {embed_dim} must be divisible by num_heads {num_heads}")
        if window_size < 2 or int(upscale) < 1 or not depths or any(int(depth) < 1 for depth in depths):
            raise ValueError("window_size, upscale, and depths must be positive")
        self.window_size = int(window_size)
        self.upscale = int(upscale)
        self.conv_first = nn.Conv2d(3, embed_dim, kernel_size=3, padding=1)
        self.groups = nn.ModuleList(
            DenseResidualGroup(embed_dim, int(depth), num_heads, self.window_size) for depth in depths
        )
        self.conv_body = nn.Conv2d(embed_dim, embed_dim, kernel_size=3, padding=1)
        self.tail = nn.Sequential(
            nn.Conv2d(embed_dim, 3 * self.upscale * self.upscale, kernel_size=3, padding=1),
            nn.PixelShuffle(self.upscale),
        )

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        _batch, _channels, height, width = image.shape
        padded = _pad_to_window(image, self.window_size)
        shallow = self.conv_first(padded)
        tokens = _to_tokens(shallow)
        padded_h, padded_w = shallow.shape[-2:]
        for group in self.groups:
            tokens = group(tokens, padded_h, padded_w)
        deep = self.conv_body(_to_image(tokens, padded_h, padded_w)) + shallow
        restored = self.tail(deep)
        return restored[:, :, : height * self.upscale, : width * self.upscale]


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


def _load_model(path: Path) -> DRCT:
    model = DRCT()
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
