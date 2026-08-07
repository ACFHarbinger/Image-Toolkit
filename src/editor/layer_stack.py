"""Deterministic layer-stack data model and compositing (standalone-editor
first slice; see ``docs/moon/roadmaps/engine_architecture.md``'s gate-5
exception for why this is being built now rather than after a documented
Krita limitation).

This is the substrate every later editor feature (masks, segmentation
review, palette preview, region-correspondence assignment) will sit on top
of, mirroring how Krita's own layer model underpins every existing Docker in
this same project. Pure numpy, no Qt/PySide -- the standalone GUI package
(``cel_shaded_generator_gui``) owns turning a ``LayerStack`` into pixels on
screen; this module owns what a layer stack *is* and how it composites.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

__all__ = ["VALID_BLEND_MODES", "LayerMeta", "Layer", "LayerStack"]

VALID_BLEND_MODES = ("normal", "multiply")


@dataclass
class LayerMeta:
    """A layer's non-pixel state: identity, ordering-independent flags."""

    id: str
    name: str
    visible: bool = True
    opacity: float = 1.0
    blend_mode: str = "normal"

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("layer id must not be empty")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("layer name must not be empty")
        if not isinstance(self.opacity, (int, float)) or not 0.0 <= self.opacity <= 1.0:
            raise ValueError("layer opacity must be between zero and one")
        if self.blend_mode not in VALID_BLEND_MODES:
            raise ValueError(f"unsupported blend mode: {self.blend_mode}")


@dataclass
class Layer:
    """One layer: its metadata, an HxWx4 uint8 straight-alpha RGBA buffer,
    and an optional HxW uint8 grayscale mask (``None`` when the layer has
    no mask). Where present, the mask non-destructively attenuates the
    layer's effective alpha during compositing -- 255 leaves a pixel fully
    as painted, 0 hides it, matching the standard non-destructive
    layer-mask convention every mainstream raster/paint editor uses."""

    meta: LayerMeta
    pixels: np.ndarray = field(repr=False)
    mask: np.ndarray | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.pixels, np.ndarray)
            or self.pixels.ndim != 3
            or self.pixels.shape[2] != 4
            or self.pixels.dtype != np.uint8
        ):
            raise ValueError("layer pixels must be an HxWx4 uint8 RGBA array")
        if self.mask is not None and (
            not isinstance(self.mask, np.ndarray)
            or self.mask.ndim != 2
            or self.mask.dtype != np.uint8
            or self.mask.shape != self.pixels.shape[:2]
        ):
            raise ValueError("layer mask must be an HxW uint8 array matching the layer's size")


def _blend_normal(base: np.ndarray, top: np.ndarray, opacity: float) -> np.ndarray:
    """Straight-alpha "over" compositing of ``top`` onto ``base``."""
    top_alpha = (top[:, :, 3:4].astype(np.float64) / 255.0) * opacity
    base_alpha = base[:, :, 3:4].astype(np.float64) / 255.0
    out_alpha = top_alpha + base_alpha * (1.0 - top_alpha)
    out_rgb = np.zeros_like(base[:, :, :3], dtype=np.float64)
    safe = out_alpha > 0
    top_rgb = top[:, :, :3].astype(np.float64)
    base_rgb = base[:, :, :3].astype(np.float64)
    blended = top_rgb * top_alpha + base_rgb * base_alpha * (1.0 - top_alpha)
    out_rgb[safe[:, :, 0]] = (blended[safe[:, :, 0]]) / out_alpha[safe[:, :, 0]]
    result = np.empty_like(base)
    result[:, :, :3] = np.clip(out_rgb, 0, 255).astype(np.uint8)
    result[:, :, 3] = np.clip(out_alpha[:, :, 0] * 255.0, 0, 255).astype(np.uint8)
    return result


def _blend_multiply(base: np.ndarray, top: np.ndarray, opacity: float) -> np.ndarray:
    """Multiply ``top``'s RGB into ``base`` wherever ``top`` is opaque, then
    composite the darkened result over ``base`` with straight alpha -- matches
    ``canvas_editor.py``'s ``_MultiplyPixmapItem`` line-art convention (white
    leaves the layer beneath unchanged, black stays black)."""
    darkened = base.copy()
    darkened[:, :, :3] = (
        base[:, :, :3].astype(np.float64) * top[:, :, :3].astype(np.float64) / 255.0
    ).astype(np.uint8)
    return _blend_normal(darkened, np.dstack([darkened[:, :, :3], top[:, :, 3]]), opacity)


_BLEND_FUNCS = {"normal": _blend_normal, "multiply": _blend_multiply}


class LayerStack:
    """Ordered, mutable stack of same-sized layers, bottom to top."""

    def __init__(self, width: int, height: int):
        if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
            raise ValueError("canvas dimensions must be positive integers")
        self.width = width
        self.height = height
        self._layers: list[Layer] = []

    def add_layer(self, layer_id: str, name: str, *, index: int | None = None) -> Layer:
        if any(layer.meta.id == layer_id for layer in self._layers):
            raise ValueError(f"layer id already exists: {layer_id}")
        pixels = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        layer = Layer(LayerMeta(layer_id, name), pixels)
        if index is None or index >= len(self._layers):
            self._layers.append(layer)
        else:
            self._layers.insert(max(0, index), layer)
        return layer

    def remove_layer(self, layer_id: str) -> bool:
        for position, layer in enumerate(self._layers):
            if layer.meta.id == layer_id:
                del self._layers[position]
                return True
        return False

    def reorder_layer(self, layer_id: str, index: int) -> bool:
        for position, layer in enumerate(self._layers):
            if layer.meta.id == layer_id:
                del self._layers[position]
                self._layers.insert(max(0, min(index, len(self._layers))), layer)
                return True
        return False

    def set_visibility(self, layer_id: str, visible: bool) -> bool:
        layer = self.layer(layer_id)
        if layer is None:
            return False
        layer.meta.visible = bool(visible)
        return True

    def layer(self, layer_id: str) -> Layer | None:
        return next((layer for layer in self._layers if layer.meta.id == layer_id), None)

    def layers(self) -> list[Layer]:
        """Bottom-to-top ordered snapshot of the current layers."""
        return list(self._layers)

    def add_mask(self, layer_id: str) -> bool:
        """Attach a fully-opaque (255, i.e. "reveal everything") mask to
        ``layer_id``. Returns ``False`` if the layer doesn't exist or
        already has a mask -- never silently replaces an existing one."""
        layer = self.layer(layer_id)
        if layer is None or layer.mask is not None:
            return False
        layer.mask = np.full((self.height, self.width), 255, dtype=np.uint8)
        return True

    def remove_mask(self, layer_id: str) -> bool:
        layer = self.layer(layer_id)
        if layer is None or layer.mask is None:
            return False
        layer.mask = None
        return True

    def composite(self) -> np.ndarray:
        """Flatten every visible layer bottom-to-top into one HxWx4 uint8 RGBA array."""
        result = np.zeros((self.height, self.width, 4), dtype=np.uint8)
        for layer in self._layers:
            if not layer.meta.visible or layer.meta.opacity <= 0:
                continue
            pixels = layer.pixels
            if layer.mask is not None:
                pixels = pixels.copy()
                pixels[:, :, 3] = (
                    pixels[:, :, 3].astype(np.uint16) * layer.mask.astype(np.uint16) // 255
                ).astype(np.uint8)
            result = _BLEND_FUNCS[layer.meta.blend_mode](result, pixels, layer.meta.opacity)
        return result

    def save_state(
        self,
    ) -> list[tuple[str, str, bool, float, str, np.ndarray, np.ndarray | None]]:
        """A deep, order-preserving copy of every layer's full state, opaque
        to callers -- pass it back to :meth:`load_state` to restore it.
        Backs ``editor.history.EditHistory``'s undo/redo."""
        return [
            (
                layer.meta.id,
                layer.meta.name,
                layer.meta.visible,
                layer.meta.opacity,
                layer.meta.blend_mode,
                layer.pixels.copy(),
                None if layer.mask is None else layer.mask.copy(),
            )
            for layer in self._layers
        ]

    def load_state(
        self, state: list[tuple[str, str, bool, float, str, np.ndarray, np.ndarray | None]]
    ) -> None:
        """Replace every layer with a deep copy of ``state`` (from an earlier
        :meth:`save_state`), in place -- callers keep the same ``LayerStack``
        identity across an undo/redo, so nothing needs to rebind to a new
        object."""
        self._layers = [
            Layer(
                LayerMeta(layer_id, name, visible, opacity, blend_mode),
                pixels.copy(),
                None if mask is None else mask.copy(),
            )
            for layer_id, name, visible, opacity, blend_mode, pixels, mask in state
        ]
