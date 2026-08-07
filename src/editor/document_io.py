"""Standalone editor: canvas document persistence (roadmap: standalone
editor, gate-5 exception, slice 8; see
``docs/moon/roadmaps/engine_architecture.md``).

Every earlier slice built an in-memory-only ``LayerStack``/
``CorrespondenceSet`` -- closing the app discarded all work. This module
saves/loads a ``LayerStack`` to/from a plain directory: one ``.npy`` file
per layer's pixel buffer (and mask, when present) plus one
``manifest.json`` describing layer order, identity, and flags. Deliberately
``.npy`` rather than PNG -- this package's existing "pure numpy, no Qt"
boundary (``layer_stack.py``, ``brush.py``) has no image-codec dependency,
and adding one (Pillow, Qt) just to persist RGBA arrays this module already
owns as numpy arrays would be new surface for no real benefit. A
correspondence set has no counterpart here because
``colorization.correspondence.save_correspondence_set``/
``load_correspondence_set`` already do that job; callers save/load it
alongside a document's directory directly rather than through this module.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .layer_stack import LayerStack

DOCUMENT_SCHEMA_VERSION = 1
_MANIFEST_NAME = "manifest.json"

__all__ = ["DOCUMENT_SCHEMA_VERSION", "save_document", "load_document"]


def save_document(directory: str | Path, layer_stack: LayerStack) -> Path:
    """Save ``layer_stack`` into ``directory``, creating it if needed.

    Overwrites any prior document in ``directory``: existing ``*.npy``
    files are removed first so a save with fewer/renamed layers than a
    previous save doesn't leave stale, unreferenced array files behind.
    """
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    for stale in destination.glob("*.npy"):
        stale.unlink()
    layers_manifest = []
    for layer in layer_stack.layers():
        pixels_file = f"{layer.meta.id}.pixels.npy"
        np.save(destination / pixels_file, layer.pixels)
        mask_file = None
        if layer.mask is not None:
            mask_file = f"{layer.meta.id}.mask.npy"
            np.save(destination / mask_file, layer.mask)
        layers_manifest.append(
            {
                "id": layer.meta.id,
                "name": layer.meta.name,
                "visible": layer.meta.visible,
                "opacity": layer.meta.opacity,
                "blend_mode": layer.meta.blend_mode,
                "pixels_file": pixels_file,
                "mask_file": mask_file,
            }
        )
    manifest = {
        "schema_version": DOCUMENT_SCHEMA_VERSION,
        "width": layer_stack.width,
        "height": layer_stack.height,
        "layers": layers_manifest,
    }
    (destination / _MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return destination


def load_document(directory: str | Path) -> LayerStack:
    """Load a ``LayerStack`` previously written by :func:`save_document`."""
    source = Path(directory)
    manifest_path = source / _MANIFEST_NAME
    if not manifest_path.exists():
        raise ValueError(f"no document manifest found in {source}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != DOCUMENT_SCHEMA_VERSION:
        raise ValueError(f"unsupported document schema version: {manifest.get('schema_version')}")
    layer_stack = LayerStack(manifest["width"], manifest["height"])
    for entry in manifest["layers"]:
        layer = layer_stack.add_layer(entry["id"], entry["name"])
        pixels = np.load(source / entry["pixels_file"])
        if pixels.shape != layer.pixels.shape or pixels.dtype != layer.pixels.dtype:
            raise ValueError(f"layer '{entry['id']}' pixel data does not match the document size")
        layer.pixels = pixels
        layer.meta.visible = entry["visible"]
        layer.meta.opacity = entry["opacity"]
        layer.meta.blend_mode = entry["blend_mode"]
        if entry["mask_file"] is not None:
            mask = np.load(source / entry["mask_file"])
            if mask.shape != (layer_stack.height, layer_stack.width):
                raise ValueError(
                    f"layer '{entry['id']}' mask data does not match the document size"
                )
            layer.mask = mask
    return layer_stack
