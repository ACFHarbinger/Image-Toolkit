"""Standalone editor: canvas document persistence (roadmap: standalone
editor, gate-5 exception, slice 8; recovery-revision rotation added in
slice 9; see ``docs/moon/roadmaps/engine_architecture.md``).

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

``save_document`` rotates bounded ``.recovery/`` snapshots of the prior
document state before overwriting, the same "accidental Save Document is
recoverable, but only a bounded amount" contract
``colorization.correspondence``/``colorization.style_bible`` already give
their own JSON assets via their own ``_rotate_recovery`` helpers -- this
one snapshots a whole directory of files (manifest + every layer array)
per revision instead of one JSON file, since a document is multiple files.
Like those two, this module only rotates; there is no restore API here
either, matching their existing scope -- recovering a snapshot is a manual
file-copy out of ``.recovery/<n>/`` for now.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np

from .layer_stack import LayerStack

DOCUMENT_SCHEMA_VERSION = 1
_MANIFEST_NAME = "manifest.json"
_RECOVERY_DIR_NAME = ".recovery"

__all__ = ["DOCUMENT_SCHEMA_VERSION", "save_document", "load_document"]


def save_document(
    directory: str | Path, layer_stack: LayerStack, *, recovery_revisions: int = 10
) -> Path:
    """Save ``layer_stack`` into ``directory``, creating it if needed.

    Overwrites any prior document in ``directory``: existing ``*.npy``
    files are removed first so a save with fewer/renamed layers than a
    previous save doesn't leave stale, unreferenced array files behind.
    If a document already exists in ``directory``, its prior state is
    rotated into ``.recovery/`` first, bounded by ``recovery_revisions``.
    """
    if not isinstance(recovery_revisions, int) or not 1 <= recovery_revisions <= 100:
        raise ValueError("document recovery revisions must be between 1 and 100")
    destination = Path(directory)
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / _MANIFEST_NAME).exists():
        _rotate_recovery(destination, recovery_revisions)
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


def _rotate_recovery(destination: Path, revisions: int) -> None:
    """Shift ``.recovery/1..revisions-1`` up to ``2..revisions`` (discarding
    anything beyond ``revisions``), then snapshot the document's current
    on-disk state -- before this save overwrites it -- into slot ``1``."""
    recovery = destination / _RECOVERY_DIR_NAME
    recovery.mkdir(exist_ok=True)
    for number in range(revisions, 1, -1):
        older = recovery / str(number - 1)
        newer = recovery / str(number)
        if older.exists():
            if newer.exists():
                shutil.rmtree(newer)
            older.rename(newer)
    slot_one = recovery / "1"
    if slot_one.exists():
        shutil.rmtree(slot_one)
    slot_one.mkdir()
    for item in destination.iterdir():
        if item.name == _RECOVERY_DIR_NAME:
            continue
        shutil.copy2(item, slot_one / item.name)
