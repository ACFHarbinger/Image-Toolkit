"""Deterministic background-image palette extraction (#439).

This module intentionally has no Qt dependency. Theme Studio can run it in a
worker and pass the resulting schema tokens to the existing theme resolver.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image

from .resolve import base_defaults
from .schema import ColorTokens

ImageSource = Union[str, Path, np.ndarray]


@dataclass(frozen=True)
class PaletteExtractionResult:
    """Extracted colors and the semantic tokens derived from them."""

    colors: tuple[str, ...]
    tokens: ColorTokens
    used_fallback: bool

    @property
    def overrides(self) -> dict[str, str]:
        """Return values ready for ``ThemePack.color_overrides``."""
        return self.tokens.as_dict()


def _load_rgb(source: ImageSource, max_side: int) -> np.ndarray:
    if isinstance(source, (str, Path)):
        with Image.open(source) as image:
            image = image.convert("RGB")
            image.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
            return np.asarray(image, dtype=np.float32).reshape(-1, 3)

    pixels = np.asarray(source)
    if pixels.ndim != 3 or pixels.shape[2] != 3:
        raise ValueError("image array must have shape (height, width, 3)")
    if pixels.shape[0] > max_side or pixels.shape[1] > max_side:
        image = Image.fromarray(pixels.astype(np.uint8), mode="RGB")
        image.thumbnail((max_side, max_side), Image.Resampling.BILINEAR)
        pixels = np.asarray(image)
    return pixels.astype(np.float32, copy=False).reshape(-1, 3)


def _hex(color: np.ndarray) -> str:
    rgb = np.clip(np.rint(color), 0, 255).astype(np.uint8)
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _luminance(colors: np.ndarray) -> np.ndarray:
    return colors @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)


def _kmeans(pixels: np.ndarray, n_colors: int, max_iter: int) -> np.ndarray:
    unique = np.unique(pixels.astype(np.uint8), axis=0).astype(np.float32)
    if len(unique) <= n_colors:
        return unique

    # Quantile initialization is deterministic and spreads seeds across the
    # image's luminance range without depending on global random state.
    luminance = _luminance(unique)
    order = np.argsort(luminance)
    indexes = np.linspace(0, len(order) - 1, n_colors, dtype=int)
    centers = unique[order[indexes]].copy()
    for _ in range(max_iter):
        distances = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = np.argmin(distances, axis=1)
        updated = centers.copy()
        for index in range(n_colors):
            members = pixels[labels == index]
            if len(members):
                updated[index] = members.mean(axis=0)
        if np.allclose(updated, centers, atol=0.5):
            centers = updated
            break
        centers = updated
    return centers


def _blend(first: np.ndarray, second: np.ndarray, amount: float) -> np.ndarray:
    return first * (1.0 - amount) + second * amount


def _semantic_tokens(colors: np.ndarray, base: str) -> ColorTokens:
    luminances = _luminance(colors)
    chroma = colors.max(axis=1) - colors.min(axis=1)
    accent = colors[int(np.argmax(chroma * (0.5 + luminances / 255.0)))]
    if base == "dark":
        window_bg = colors[int(np.argmin(luminances))]
        surface = _blend(window_bg, np.array([255.0, 255.0, 255.0]), 0.16)
        text = np.array([242.0, 242.0, 242.0])
        muted_text = np.array([170.0, 170.0, 170.0])
        border = _blend(surface, accent, 0.22)
    else:
        window_bg = colors[int(np.argmax(luminances))]
        surface = _blend(window_bg, np.array([255.0, 255.0, 255.0]), 0.35)
        text = np.array([30.0, 30.0, 30.0])
        muted_text = np.array([85.0, 85.0, 85.0])
        border = _blend(surface, accent, 0.16)
    return ColorTokens(
        accent=_hex(accent),
        surface=_hex(surface),
        window_bg=_hex(window_bg),
        text=_hex(text),
        muted_text=_hex(muted_text),
        border=_hex(border),
    )


def extract_palette(
    source: ImageSource,
    *,
    base: str = "dark",
    n_colors: int = 5,
    max_side: int = 128,
    max_iter: int = 20,
) -> PaletteExtractionResult:
    """Extract a semantic palette from an RGB image or image path.

    Extraction is deliberately opt-in at the caller. Images with insufficient
    chroma or luminance variation return the selected base theme unchanged so
    a dark/monochrome wallpaper cannot produce unreadable UI tokens.
    """
    if base not in ("dark", "light"):
        raise ValueError("base must be 'dark' or 'light'")
    if not 2 <= n_colors <= 12:
        raise ValueError("n_colors must be between 2 and 12")
    if max_side < 8:
        raise ValueError("max_side must be at least 8")

    pixels = _load_rgb(source, max_side)
    if len(pixels) == 0:
        raise ValueError("image contains no pixels")
    colors = _kmeans(pixels, n_colors, max_iter)
    luminance = _luminance(pixels)
    chroma = pixels.max(axis=1) - pixels.min(axis=1)
    low_variance = float(np.std(luminance)) < 8.0 or float(np.percentile(chroma, 90)) < 12.0
    if low_variance:
        fallback = base_defaults(base)
        return PaletteExtractionResult(tuple(_hex(color) for color in colors), fallback, True)
    return PaletteExtractionResult(
        tuple(_hex(color) for color in colors),
        _semantic_tokens(colors, base),
        False,
    )


__all__ = ["PaletteExtractionResult", "extract_palette"]
