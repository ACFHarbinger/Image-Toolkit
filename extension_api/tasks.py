"""Celery tasks backing §7.14A/B (background removal, upscale) over the bridge.

Named ``tasks.py`` (rather than e.g. ``cv_tasks.py``) so Celery's
``app.autodiscover_tasks()`` (``api/celery.py``) picks these up automatically
for every installed Django app, matching the existing ``tasks/tasks.py``
convention used by the rest of the project's async endpoints.

These two operations are genuinely long-running (BiRefNet / Real-ESRGAN
inference), so — per the roadmap's "job-id + polling using the app's
existing task queue" — they're wired through the same Celery queue
``tasks/views.py``'s ``CoreTaskView`` already uses (``.delay()`` -> a
``task_id`` the client polls), rather than inventing a second async
mechanism. ``CvJobStatusView`` (``views.py``) polls results via Celery's
own ``AsyncResult``.

Each task takes already-fetched, base64-encoded image bytes (the calling
view resolves ``{url|data_b64}`` synchronously via
``bridge_handlers._resolve_image_payload`` first, so a bad/unreachable URL
fails fast with 400 instead of silently after being queued) and returns a
plain JSON-serializable dict — Celery's default JSON serializer can't carry
raw bytes, so results/inputs are base64 text end to end.
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict

from celery import shared_task

logger = logging.getLogger(__name__)


def _decode_image(data: bytes):
    """Decode arbitrary image bytes into a BGR ``np.ndarray`` (cv2 convention)."""
    import cv2
    import numpy as np

    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _with_suffix(name_hint: str, suffix: str, ext: str) -> str:
    """``photo.jpg`` + ``_nobg`` + ``.png`` -> ``photo_nobg.png``."""
    import os

    stem = os.path.splitext(name_hint or "image")[0] or "image"
    return f"{stem}{suffix}{ext}"


@shared_task(bind=True, name="extension_api.cv_bg_remove")
def cv_bg_remove_task(
    self, data_b64: str, filename_hint: str = "image.png"
) -> Dict[str, Any]:
    """§7.14A — BiRefNet background removal; returns a base64 transparent PNG."""
    try:
        data = base64.b64decode(data_b64)
        img = _decode_image(data)
        if img is None:
            return {"status": "error", "message": "Could not decode image."}

        import cv2
        from backend.src.models.wrappers.birefnet_wrapper import BiRefNetWrapper
        from PIL import Image

        wrapper = BiRefNetWrapper()
        mask = wrapper.get_mask(img)  # (H, W) uint8, 255 = foreground

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        rgba = Image.fromarray(rgb, mode="RGB").convert("RGBA")
        rgba.putalpha(Image.fromarray(mask, mode="L"))

        import io

        buf = io.BytesIO()
        rgba.save(buf, format="PNG")
        out_bytes = buf.getvalue()

        return {
            "status": "success",
            "data_b64": base64.b64encode(out_bytes).decode("ascii"),
            "filename": _with_suffix(filename_hint, "_nobg", ".png"),
            "content_type": "image/png",
        }
    except Exception as exc:  # noqa: BLE001 - reported to the polling client
        logger.exception("cv_bg_remove_task failed")
        return {"status": "error", "message": str(exc)}


@shared_task(bind=True, name="extension_api.cv_upscale")
def cv_upscale_task(
    self,
    data_b64: str,
    filename_hint: str = "image.png",
    scale: int = 4,
) -> Dict[str, Any]:
    """§7.14B — Real-ESRGAN anime_6B upscale; returns a base64 PNG.

    The anime_6B checkpoint's architecture is fixed at a native 4x scale
    (two hardcoded 2x nearest-upsample stages in ``RRDBNet`` — see
    ``esrgan_wrapper.py``); constructing ``ESRGANWrapper(scale=2)`` would
    just mislabel the *same* 4x forward pass and corrupt the wrapper's own
    tile-stitching math (it slices output tiles assuming ``self.scale``
    matches what the network actually produces). So ``scale=2`` is honored
    by always running the real 4x pass, then a single Lanczos downsample
    to the requested net 2x — not a second, cheaper model path.
    """
    try:
        data = base64.b64decode(data_b64)
        img = _decode_image(data)
        if img is None:
            return {"status": "error", "message": "Could not decode image."}

        scale = 4 if scale not in (2, 4) else scale

        import cv2
        from backend.src.models.wrappers.esrgan_wrapper import ESRGANWrapper

        wrapper = ESRGANWrapper()  # native 4x anime_6B
        out = wrapper.upscale(img)

        if scale == 2:
            h, w = out.shape[:2]
            out = cv2.resize(
                out, (w // 2, h // 2), interpolation=cv2.INTER_LANCZOS4
            )

        ok, buf = cv2.imencode(".png", out)
        if not ok:
            return {"status": "error", "message": "Could not encode result PNG."}

        return {
            "status": "success",
            "data_b64": base64.b64encode(buf.tobytes()).decode("ascii"),
            "filename": _with_suffix(filename_hint, "_upscaled", ".png"),
            "content_type": "image/png",
            "scale": scale,
        }
    except Exception as exc:  # noqa: BLE001 - reported to the polling client
        logger.exception("cv_upscale_task failed")
        return {"status": "error", "message": str(exc)}
