"""Transport-agnostic bridge handler logic (§7.5).

Pure functions with no HTTP/DRF or native-messaging framing dependencies, so
both the token-authenticated Django HTTP views (§7.5A, ``views.py``) and the
native-messaging host (§7.5B, ``native_host.py``) share one implementation
rather than two copies of the same business logic. Each handler takes a
plain ``dict`` payload and returns ``(status_code, body_dict)`` — status
codes follow HTTP conventions (200/201/400/409) even though the
native-messaging transport has no HTTP status line; each transport maps
these into its own response envelope (DRF ``Response`` for HTTP, a JSON
envelope for native messaging).

Auth is deliberately NOT handled here: HTTP requires the bearer-token check
(``BridgeTokenPermission`` in ``views.py``) since a local port is otherwise
reachable by anything on the machine; native messaging's security boundary
is the browser itself (only extension IDs listed in the host manifest's
``allowed_origins``/``allowed_extensions`` may ever launch the host process
at all), so no additional token is needed there — this matches the
roadmap's Phase B rationale ("no open port, no token UX, browser-mediated
authentication").
"""

from __future__ import annotations

import base64
import io
import logging
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .bridge_config import load_config

logger = logging.getLogger(__name__)

BRIDGE_VERSION = "1.2"
FEATURES = ["ping", "dup-check", "ingest", "similar"]

_MAX_FETCH_BYTES = 64 * 1024 * 1024  # 64 MB
_FETCH_TIMEOUT_S = 20
_THUMB_MAX_PX = 128


# ── Shared helpers ───────────────────────────────────────────────────────────


def _fetch_image_bytes(url: str) -> bytes:
    """Fetch image bytes server-side (avoids extension CORS restrictions)."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "ImageToolkit-Bridge/1.0"}
    )
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_S) as resp:
        return resp.read(_MAX_FETCH_BYTES + 1)


def _thumb_b64(path: str) -> Optional[str]:
    """Small JPEG preview of a matched file, base64-encoded."""
    try:
        from PIL import Image

        with Image.open(path) as img:
            img.thumbnail((_THUMB_MAX_PX, _THUMB_MAX_PX))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, "JPEG", quality=80)
            return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def _image_dims(path: str) -> Optional[tuple]:
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except Exception:
        return None


def _resolve_image_payload(
    payload: Dict[str, Any],
) -> Tuple[Optional[bytes], Optional[str], Optional[Tuple[int, Dict[str, Any]]]]:
    """Common ``{url|data_b64}`` handling → ``(bytes, source_url, error)``."""
    url = payload.get("url")
    data_b64 = payload.get("data_b64")
    if not url and not data_b64:
        return None, None, (400, {"error": "Provide 'url' or 'data_b64'."})
    try:
        data = base64.b64decode(data_b64) if data_b64 else _fetch_image_bytes(url)
    except Exception as exc:
        return None, None, (400, {"error": f"Could not fetch image: {exc}"})
    if len(data) > _MAX_FETCH_BYTES:
        return None, None, (400, {"error": "Image too large."})
    return data, url, None


# ── Handlers ─────────────────────────────────────────────────────────────────


def handle_ping() -> Tuple[int, Dict[str, Any]]:
    cfg = load_config()
    return 200, {
        "version": BRIDGE_VERSION,
        "features": FEATURES,
        "dup_root_configured": bool(cfg.get("dup_root")),
    }


def handle_dup_check(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    cfg = load_config()
    dup_root = cfg.get("dup_root") or ""
    if not dup_root:
        return 409, {"error": "No duplicate-search directory configured in the app."}

    data, _url, err = _resolve_image_payload(payload)
    if err is not None:
        return err

    from backend.src.core.dir_phash_index import DirPhashIndex

    try:
        threshold = int(payload.get("threshold", cfg.get("threshold", 10)))
    except (TypeError, ValueError):
        threshold = 10

    index = DirPhashIndex(dup_root, recursive=bool(cfg.get("recursive", True)))
    try:
        stats = index.refresh()
        matches = index.query_bytes(data, threshold=threshold, limit=20)
        if matches is None:
            return 400, {"error": "Image could not be decoded."}

        enriched = []
        for m in matches:
            dims = _image_dims(m["path"])
            enriched.append(
                {
                    **m,
                    "width": dims[0] if dims else None,
                    "height": dims[1] if dims else None,
                    "thumb_b64": _thumb_b64(m["path"]),
                }
            )
        return 200, {
            "matches": enriched,
            "scanned": stats["total"],
            "cold_scan": stats["cold_scan"],
            "threshold": threshold,
        }
    finally:
        index.close()


def handle_ingest(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    cfg = load_config()
    ingest_dir = cfg.get("ingest_dir") or ""
    if not ingest_dir:
        dup_root = cfg.get("dup_root") or ""
        if dup_root:
            ingest_dir = str(Path(dup_root) / "inbox")
    if not ingest_dir:
        return 409, {"error": "No ingest directory configured in the app."}

    data, url, err = _resolve_image_payload(payload)
    if err is not None:
        return err

    from backend.src.core.dir_phash_index import DirPhashIndex

    force = bool(payload.get("force", False))
    dup_root = cfg.get("dup_root") or ""
    if dup_root and not force:
        index = DirPhashIndex(dup_root, recursive=bool(cfg.get("recursive", True)))
        try:
            index.refresh()
            matches = index.query_bytes(
                data, threshold=int(cfg.get("threshold", 10)), limit=5
            )
        finally:
            index.close()
        if matches:
            return 409, {
                "error": "Image already in library.",
                "existing": [m["path"] for m in matches],
            }

    name = ""
    if url:
        try:
            from urllib.parse import unquote, urlparse

            name = unquote(urlparse(url).path.split("/")[-1])
        except Exception:
            name = ""
    name = re.sub(r'[<>:"\\|?*/]', "_", name).strip() or f"image_{int(time.time())}.jpg"
    if "." not in name:
        name += ".jpg"

    dest_dir = Path(ingest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / name
    stem, suffix = dest.stem, dest.suffix
    counter = 1
    while dest.exists():
        dest = dest_dir / f"{stem} ({counter}){suffix}"
        counter += 1

    dest.write_bytes(data)

    import json as _json

    sidecar = {
        "source_url": url,
        "page_url": payload.get("source_page_url"),
        "page_title": payload.get("page_title"),
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "via": "image-toolkit-extension",
    }
    (dest_dir / (dest.name + ".json")).write_text(
        _json.dumps(sidecar, indent=2), encoding="utf-8"
    )

    return 201, {"path": str(dest)}


def handle_similar(payload: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    cfg = load_config()
    dup_root = cfg.get("dup_root") or ""
    if not dup_root:
        return 409, {"error": "No duplicate-search directory configured in the app."}

    data, _url, err = _resolve_image_payload(payload)
    if err is not None:
        return err

    try:
        top_k = int(payload.get("top_k", 12))
    except (TypeError, ValueError):
        top_k = 12
    top_k = max(1, min(top_k, 100))

    from backend.src.core.dir_phash_index import DirPhashIndex

    index = DirPhashIndex(dup_root, recursive=bool(cfg.get("recursive", True)))
    try:
        stats = index.refresh()
        matches = index.query_topk_bytes(data, k=top_k)
        if matches is None:
            return 400, {"error": "Image could not be decoded."}

        results = []
        for m in matches:
            dims = _image_dims(m["path"])
            results.append(
                {
                    "path": m["path"],
                    "score": round(1.0 - (m["hamming"] / 64.0), 4),
                    "hamming": m["hamming"],
                    "width": dims[0] if dims else None,
                    "height": dims[1] if dims else None,
                    "thumb_b64": _thumb_b64(m["path"]),
                }
            )
        return 200, {
            "results": results,
            "scanned": stats["total"],
            "cold_scan": stats["cold_scan"],
            "method": "phash",
        }
    finally:
        index.close()


HANDLERS = {
    "ping": lambda payload: handle_ping(),
    "dup_check": handle_dup_check,
    "ingest": handle_ingest,
    "similar": handle_similar,
}
