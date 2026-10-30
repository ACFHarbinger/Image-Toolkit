"""SwinIR realistic 4x super-resolution in plain PyTorch.

Residual Swin layers are window attention plus an MLP. A convolution closes
the residual around each stage, and a pixel-shuffle tail expands to 4x.
Checkpoints are read from disk only.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

from middleware.src.services.media.gif_upscale.base import AlgorithmError, AlgorithmSpec
from middleware.src.services.media.gif_upscale.policy import cache_dir, weights_policy
from middleware.src.services.media.gif_upscale.registry import register_algorithm

_ID = "swinir"
_OWNER = "gif-upscale-swinir"
_FILENAME = "SwinIR_SRx4.pth"
_VRAM_MB = 3000
_UPSCALE = 4


def _window_partition(image: torch.Tensor, window_size: int) -> torch.Tensor:
    """(B, H, W, C) -> (B*nW, window*window, C)."""
    batch, height, width, channels = image.shape
    image = image.contiguous().view(
        batch,
        height // window_size,
        window_size,
        width // window_size,
        window_size,
        channels,
    )
    windows = image.permute(0, 1, 3, 2, 4, 5).contiguous()
    return windows.view(-1, window_size * window_size, channels)


def _window_reverse(windows: torch.Tensor, window_size: int, height: int, width: int) -> torch.Tensor:
    """(B*nW, window*window, C) -> (B, H, W, C)."""
    channels = windows.shape[-1]
    window_count = (height // window_size) * (width // window_size)
    batch = windows.shape[0] // window_count
    merged = windows.contiguous().view(
        batch,
        height // window_size,
        width // window_size,
        window_size,
        window_size,
        channels,
    )
    merged = merged.permute(0, 1, 3, 2, 4, 5).contiguous()
    return merged.view(batch, height, width, channels)


def _relative_position_index(window_size: int) -> torch.Tensor:
    coords = torch.stack(torch.meshgrid(torch.arange(window_size), torch.arange(window_size), indexing="ij"))
    flat = coords.flatten(1)
    relative = (flat[:, :, None] - flat[:, None, :]).permute(1, 2, 0).contiguous()
    relative[:, :, 0] += window_size - 1
    relative[:, :, 1] += window_size - 1
    relative[:, :, 0] *= 2 * window_size - 1
    return relative.sum(-1)


def _shift_attention_mask(
    height: int,
    width: int,
    window_size: int,
    shift: int,
    device: torch.device,
) -> torch.Tensor:
    """Block attention from crossing the cyclic-shift boundary. Shape (nW, N, N)."""
    image = torch.zeros((1, height, width, 1), device=device)
    slices = (slice(0, -window_size), slice(-window_size, -shift), slice(-shift, None))
    region = 0
    for height_slice in slices:
        for width_slice in slices:
            image[:, height_slice, width_slice, :] = region
            region += 1
    windows = _window_partition(image, window_size).squeeze(-1)
    mask = windows.unsqueeze(1) - windows.unsqueeze(2)
    return mask.masked_fill(mask != 0, -100.0).masked_fill(mask == 0, 0.0)


def _pad_to_window(image: torch.Tensor, window_size: int) -> tuple[torch.Tensor, int, int]:
    _, _, height, width = image.shape
    pad_h = (window_size - height % window_size) % window_size
    pad_w = (window_size - width % window_size) % window_size
    if pad_h == 0 and pad_w == 0:
        return image, height, width
    reflect = height > 1 and width > 1 and pad_h < height and pad_w < width
    mode = "reflect" if reflect else "replicate"
    return F.pad(image, (0, pad_w, 0, pad_h), mode=mode), height, width


def _stage_heads(depths: tuple[int, ...], num_heads: int | tuple[int, ...]) -> tuple[int, ...]:
    if isinstance(num_heads, int):
        return tuple(num_heads for _ in depths)
    heads = tuple(int(item) for item in num_heads)
    if len(heads) != len(depths):
        raise ValueError(f"num_heads has {len(heads)} stages but depths has {len(depths)}")
    return heads


class WindowAttention(nn.Module):
    """Multi-head self-attention inside one window, with a relative position bias."""

    def __init__(self, dim: int, num_heads: int, window_size: int) -> None:
        super().__init__()
        if num_heads < 1 or dim % num_heads != 0:
            raise ValueError(f"embed dim {dim} must be divisible by num_heads {num_heads}")
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim**-0.5
        self.qkv = nn.Linear(dim, dim * 3)
        self.proj = nn.Linear(dim, dim)
        table = (2 * window_size - 1) ** 2
        self.relative_position_bias_table = nn.Parameter(torch.zeros(table, num_heads))
        nn.init.trunc_normal_(self.relative_position_bias_table, std=0.02)
        index = _relative_position_index(window_size)
        self.register_buffer("relative_position_index", index, persistent=False)

    def forward(self, tokens: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        batch, length, channels = tokens.shape
        qkv = self.qkv(tokens).reshape(batch, length, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)
        query, key, value = qkv[0], qkv[1], qkv[2]
        attn = (query * self.scale) @ key.transpose(-2, -1)
        bias = self.relative_position_bias_table[self.relative_position_index.reshape(-1)]
        bias = bias.view(length, length, self.num_heads).permute(2, 0, 1).contiguous()
        attn = attn + bias.unsqueeze(0)
        if mask is not None:
            windows = mask.shape[0]
            attn = attn.view(batch // windows, windows, self.num_heads, length, length)
            attn = attn + mask.unsqueeze(1).unsqueeze(0)
            attn = attn.view(-1, self.num_heads, length, length)
        attn = attn.softmax(dim=-1)
        out = (attn @ value).transpose(1, 2).reshape(batch, length, channels)
        return self.proj(out)


class Mlp(nn.Module):
    def __init__(self, dim: int, ratio: float = 2.0) -> None:
        super().__init__()
        hidden = max(1, int(dim * ratio))
        self.fc1 = nn.Linear(dim, hidden)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(hidden, dim)

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        return self.fc2(self.act(self.fc1(tokens)))


class SwinTransformerLayer(nn.Module):
    """Pre-norm window attention and MLP, each with a residual."""

    def __init__(self, dim: int, num_heads: int, window_size: int, shift: int) -> None:
        super().__init__()
        self.window_size = window_size
        self.shift = shift if 0 < shift < window_size else 0
        self.norm1 = nn.LayerNorm(dim)
        self.attn = WindowAttention(dim, num_heads, window_size)
        self.norm2 = nn.LayerNorm(dim)
        self.mlp = Mlp(dim)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        tokens = self.norm1(image.permute(0, 2, 3, 1))
        if self.shift:
            tokens = torch.roll(tokens, shifts=(-self.shift, -self.shift), dims=(1, 2))
            mask = _shift_attention_mask(
                tokens.shape[1],
                tokens.shape[2],
                self.window_size,
                self.shift,
                tokens.device,
            )
        else:
            mask = None
        windows = _window_partition(tokens, self.window_size)
        windows = self.attn(windows, mask)
        merged = _window_reverse(windows, self.window_size, tokens.shape[1], tokens.shape[2])
        if self.shift:
            merged = torch.roll(merged, shifts=(self.shift, self.shift), dims=(1, 2))
        attended = image + merged.permute(0, 3, 1, 2).contiguous()
        tokens = attended.permute(0, 2, 3, 1)
        tokens = tokens + self.mlp(self.norm2(tokens))
        return tokens.permute(0, 3, 1, 2).contiguous()


class ResidualSwinGroup(nn.Module):
    """A stack of Swin layers plus the convolution that closes the group residual."""

    def __init__(self, dim: int, depth: int, num_heads: int, window_size: int) -> None:
        super().__init__()
        self.layers = nn.ModuleList(
            [
                SwinTransformerLayer(
                    dim,
                    num_heads,
                    window_size,
                    shift=(window_size // 2 if index % 2 else 0),
                )
                for index in range(depth)
            ]
        )
        self.conv = nn.Conv2d(dim, dim, kernel_size=3, padding=1)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        shortcut = image
        for layer in self.layers:
            image = layer(image)
        return shortcut + self.conv(image)


class PixelShuffleTail(nn.Module):
    """4x tail: one convolution into 16 sub-pixels, then PixelShuffle."""

    def __init__(self, channels: int, out_channels: int = 3) -> None:
        super().__init__()
        self.expand = nn.Conv2d(channels, out_channels * (_UPSCALE**2), kernel_size=3, padding=1)
        self.shuffle = nn.PixelShuffle(_UPSCALE)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        return self.shuffle(self.expand(image))


class SwinIR(nn.Module):
    """Residual Swin transformer. ``depths`` is layers per residual group.

    The tiny test net is ``SwinIR(embed_dim=16, depths=(1,), num_heads=2, window_size=4)``.
    Defaults match classical SwinIR-M (180 channels, six groups of six, window 8).
    """

    def __init__(
        self,
        embed_dim: int = 180,
        depths: tuple[int, ...] = (6, 6, 6, 6, 6, 6),
        num_heads: int | tuple[int, ...] = 6,
        window_size: int = 8,
        upscale: int = 4,
    ) -> None:
        super().__init__()
        if upscale != _UPSCALE:
            raise ValueError(f"SwinIR upscale must be {_UPSCALE}, got {upscale}")
        if window_size < 1:
            raise ValueError("window_size must be positive")
        depth_tuple = tuple(int(item) for item in depths)
        if not depth_tuple:
            raise ValueError("depths must contain at least one residual group")
        self.window_size = window_size
        self.upscale = upscale
        heads = _stage_heads(depth_tuple, num_heads)
        self.conv_first = nn.Conv2d(3, embed_dim, kernel_size=3, padding=1)
        self.groups = nn.ModuleList(
            [
                ResidualSwinGroup(embed_dim, depth, head, window_size)
                for depth, head in zip(depth_tuple, heads, strict=True)
            ]
        )
        self.conv_after = nn.Conv2d(embed_dim, embed_dim, kernel_size=3, padding=1)
        self.tail = PixelShuffleTail(embed_dim)

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        padded, height, width = _pad_to_window(image, self.window_size)
        shallow = self.conv_first(padded)
        deep = shallow
        for group in self.groups:
            deep = group(deep)
        deep = self.conv_after(deep) + shallow
        out = self.tail(deep)
        return out[:, :, : height * self.upscale, : width * self.upscale]


def _local_checkpoint() -> str | None:
    """GIF cache wins. Otherwise the first matching file under the Hugging Face hub cache."""
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


def _missing_message(policy: str) -> str:
    if policy == "offline":
        return f"{_ID} weights are not cached and gif_upscale.weights_policy is offline."
    return f"{_ID} weights are not cached."


def _available() -> tuple[bool, str]:
    # Never downloads. A missing file is unavailable for every policy, including on_demand.
    try:
        policy = weights_policy()
    except ValueError as exc:
        return False, f"{_ID} {exc}"
    if _local_checkpoint() is not None:
        return True, ""
    return False, _missing_message(policy)


def _reject_scale(scale: float) -> None:
    try:
        value = float(scale)
    except (TypeError, ValueError) as exc:
        raise AlgorithmError(f"{_ID} supports scale 4, not {scale!r}.") from exc
    if abs(value - 4.0) > 1e-3:
        raise AlgorithmError(f"{_ID} supports scale 4, not {value}.")


def _reject_frames(frames: list[np.ndarray]) -> None:
    for frame in frames:
        shape = getattr(frame, "shape", None)
        if shape is None or len(shape) != 3 or int(shape[2]) != 4 or int(shape[0]) < 1 or int(shape[1]) < 1:
            raise AlgorithmError(f"{_ID} expected HxWx4 frames, got {shape}.")


def _require_checkpoint() -> str:
    path = _local_checkpoint()
    if path is None:
        try:
            policy = weights_policy()
        except ValueError as exc:
            raise AlgorithmError(f"{_ID} {exc}") from exc
        raise AlgorithmError(_missing_message(policy))
    return path


def _tensor_dict(payload: object) -> dict[str, torch.Tensor] | None:
    if not isinstance(payload, dict) or not payload:
        return None
    if all(torch.is_tensor(value) for value in payload.values()):
        return payload
    return None


def _read_state_dict(path: str) -> dict[str, torch.Tensor]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        payload = torch.load(path, map_location="cpu")
    except (OSError, RuntimeError, ValueError, pickle.UnpicklingError, EOFError) as exc:
        raise AlgorithmError(f"{_ID} could not read weights: {exc}") from exc
    direct = _tensor_dict(payload)
    if direct is not None:
        return direct
    if isinstance(payload, dict):
        for key in ("params_ema", "params", "state_dict", "model"):
            nested = _tensor_dict(payload.get(key))
            if nested is not None:
                return nested
    raise AlgorithmError(f"{_ID} checkpoint is not a state dict.")


def _load_weights(model: nn.Module, path: str) -> None:
    try:
        model.load_state_dict(_read_state_dict(path), strict=True)
    except RuntimeError as exc:
        raise AlgorithmError(f"{_ID} weight key mismatch: {exc}") from exc


def _device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def _nearest_alpha(alpha: np.ndarray, height: int, width: int) -> np.ndarray:
    flat = np.ascontiguousarray(alpha, dtype=np.float32)
    tensor = torch.from_numpy(flat).view(1, 1, flat.shape[0], flat.shape[1])
    resized = F.interpolate(tensor, size=(height, width), mode="nearest")
    return resized.reshape(height, width).numpy()


def _color(model: nn.Module, frame: np.ndarray, device: torch.device) -> np.ndarray:
    rgb = np.ascontiguousarray(frame[:, :, :3], dtype=np.float32)
    tensor = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(device)
    try:
        predicted = model(tensor)
    except RuntimeError as exc:
        raise AlgorithmError(f"{_ID} failed on a frame: {exc}") from exc
    color = predicted.squeeze(0).permute(1, 2, 0).detach().float().cpu().numpy()
    if not np.isfinite(color).all():
        raise AlgorithmError(f"{_ID} produced non-finite pixels.")
    return np.clip(color, 0.0, 1.0).astype(np.float32, copy=False)


def _infer(frames: list[np.ndarray], path: str) -> list[np.ndarray]:
    device = _device()
    model = SwinIR().to(device)
    model.eval()
    _load_weights(model, path)
    output: list[np.ndarray] = []
    with torch.inference_mode():
        for frame in frames:
            color = _color(model, frame, device)
            alpha = _nearest_alpha(np.asarray(frame[:, :, 3]), color.shape[0], color.shape[1])
            output.append(np.dstack((color, alpha)).astype(np.float32, copy=False))
    return output


def upscale(frames: list[np.ndarray], scale: float, opts: dict) -> list[np.ndarray]:
    del opts
    _reject_scale(scale)
    _reject_frames(frames)
    path = _require_checkpoint()
    from middleware.src.comfy_matrix import gpu_lease, try_admit

    refusal = try_admit(_OWNER, estimated_gb=_VRAM_MB / 1000, kind="generate")
    if refusal:
        raise AlgorithmError(refusal)
    try:
        return _infer(frames, path)
    finally:
        gpu_lease.release(_OWNER)


register_algorithm(
    AlgorithmSpec(
        id=_ID,
        family="swinir",
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
