"""Sidecar handlers for the entity_recon capability (B-06 / #911).

The engine is injected (``SidecarServer(recon_engine=...)``); with none
attached every result stays ``available: false``. The handler loads the
cutout image (cv2, like the Qt worker); a missing file is a failed
resolve. Tests inject a fake engine and never touch the network.
"""

from __future__ import annotations

from typing import Any

from middleware.src.services.web.entity_recon import (
    describe_result,
    resolve_result,
)


def handle_entity_recon_describe(engine: Any | None) -> dict[str, Any]:
    return describe_result(engine)


def handle_entity_recon_resolve(engine: Any | None, params: dict[str, Any]) -> dict[str, Any]:
    cutout_rgb = None
    cutout_png = b""
    if engine is not None:
        # cv2 stays out of the sidecar's import graph (test_sidecar's
        # heavy-import guard); it loads only when a resolve actually runs.
        import cv2
        import numpy

        # imread is BGR. The PNG cutout stays BGR so imencode writes the
        # same pixels. Resolution matches DatasetIndexer.build, which
        # converts to RGB before embedding.
        bgr = cv2.imread(str(params["image_path"]))
        frame = bgr if bgr is not None else numpy.zeros((1, 1, 3), dtype="uint8")
        ok, buffer = cv2.imencode(".png", frame)
        cutout_png = buffer.tobytes() if ok else b""
        cutout_rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB) if bgr is not None else None
    return resolve_result(engine, cutout_rgb, cutout_png, params)


__all__ = [
    "handle_entity_recon_describe",
    "handle_entity_recon_resolve",
]
