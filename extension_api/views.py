"""Browser-extension bridge endpoints (§7.5A / §7.6).

Token-authenticated, CORS-enabled endpoints consumed by the WebExtension:

- ``GET  /api/extension/ping``       — version + feature discovery
- ``POST /api/extension/dup-check``  — perceptual duplicate search of the
  configured directory tree (``DirPhashIndex``)
"""

from __future__ import annotations

import base64
import hmac
import io
import logging
import urllib.request
from typing import Any, Dict, Optional

from django.http import HttpResponse
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiResponse

from .bridge_config import get_token, load_config

logger = logging.getLogger(__name__)

BRIDGE_VERSION = "1.1"
FEATURES = ["ping", "dup-check", "ingest"]

_MAX_FETCH_BYTES = 64 * 1024 * 1024  # 64 MB
_FETCH_TIMEOUT_S = 20
_THUMB_MAX_PX = 128


# ── Auth + CORS ──────────────────────────────────────────────────────────────


class BridgeTokenPermission(BasePermission):
    """Require ``Authorization: Bearer <token>`` matching the pairing token."""

    message = "Missing or invalid bridge token."

    def has_permission(self, request, view) -> bool:  # noqa: ANN001
        # CORS preflight requests never carry credentials — let them through
        # so the browser can learn the allowed headers; real requests are
        # still token-gated.
        if request.method == "OPTIONS":
            return True
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return False
        supplied = header[len("Bearer "):].strip()
        return hmac.compare_digest(supplied, get_token())


class CorsAPIView(APIView):
    """APIView that answers CORS preflight and stamps CORS response headers.

    Extension origins (``chrome-extension://…``, ``moz-extension://…``) are
    unpredictable across installs, so the origin is echoed back; the bearer
    token is what actually gates access.
    """

    def options(self, request, *args, **kwargs):  # noqa: ANN001
        return self._with_cors(HttpResponse(status=204), request)

    @staticmethod
    def _with_cors(response, request):  # noqa: ANN001
        response["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
        response["Access-Control-Max-Age"] = "86400"
        return response

    def finalize_response(self, request, response, *args, **kwargs):  # noqa: ANN001
        response = super().finalize_response(request, response, *args, **kwargs)
        return self._with_cors(response, request)


# ── Helpers ──────────────────────────────────────────────────────────────────


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


# ── Endpoints ────────────────────────────────────────────────────────────────


class PingView(CorsAPIView):
    permission_classes = [BridgeTokenPermission]

    @extend_schema(
        tags=["Extension Bridge"],
        summary="Bridge liveness + feature discovery",
        responses={
            200: inline_serializer(
                name="ExtensionPingResponse",
                fields={
                    "version": drf_serializers.CharField(),
                    "features": drf_serializers.ListField(
                        child=drf_serializers.CharField()
                    ),
                    "dup_root_configured": drf_serializers.BooleanField(),
                },
            )
        },
    )
    def get(self, request):  # noqa: ANN001
        cfg = load_config()
        return Response(
            {
                "version": BRIDGE_VERSION,
                "features": FEATURES,
                "dup_root_configured": bool(cfg.get("dup_root")),
            }
        )


def _resolve_image_payload(request) -> tuple:  # noqa: ANN001
    """Common `{url|data_b64}` handling → (bytes, source_url, error_response)."""
    url = request.data.get("url")
    data_b64 = request.data.get("data_b64")
    if not url and not data_b64:
        return None, None, Response(
            {"error": "Provide 'url' or 'data_b64'."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        data = base64.b64decode(data_b64) if data_b64 else _fetch_image_bytes(url)
    except Exception as exc:
        return None, None, Response(
            {"error": f"Could not fetch image: {exc}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if len(data) > _MAX_FETCH_BYTES:
        return None, None, Response(
            {"error": "Image too large."}, status=status.HTTP_400_BAD_REQUEST
        )
    return data, url, None


class IngestView(CorsAPIView):
    """§7.7 — save an image into the app's library with provenance metadata."""

    permission_classes = [BridgeTokenPermission]

    @extend_schema(
        tags=["Extension Bridge"],
        summary="Ingest an image into the library (with provenance sidecar)",
        request=inline_serializer(
            name="ExtensionIngestRequest",
            fields={
                "url": drf_serializers.URLField(required=False),
                "data_b64": drf_serializers.CharField(required=False),
                "source_page_url": drf_serializers.CharField(required=False),
                "page_title": drf_serializers.CharField(required=False),
                "force": drf_serializers.BooleanField(required=False),
            },
        ),
        responses={
            201: OpenApiResponse(description="saved: path"),
            400: OpenApiResponse(description="bad request"),
            409: OpenApiResponse(
                description="duplicate already in library (existing paths) or no ingest dir configured"
            ),
        },
    )
    def post(self, request):  # noqa: ANN001
        import re
        import time as _time
        from pathlib import Path

        cfg = load_config()
        ingest_dir = cfg.get("ingest_dir") or ""
        if not ingest_dir:
            dup_root = cfg.get("dup_root") or ""
            if dup_root:
                ingest_dir = str(Path(dup_root) / "inbox")
        if not ingest_dir:
            return Response(
                {"error": "No ingest directory configured in the app."},
                status=status.HTTP_409_CONFLICT,
            )

        data, url, err = _resolve_image_payload(request)
        if err is not None:
            return err

        # Implicit dup-check before ingest (§7.7) unless force=true
        from backend.src.core.dir_phash_index import DirPhashIndex

        force = bool(request.data.get("force", False))
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
                return Response(
                    {
                        "error": "Image already in library.",
                        "existing": [m["path"] for m in matches],
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        # Derive a safe, unique filename from the source URL
        name = ""
        if url:
            try:
                from urllib.parse import urlparse, unquote

                name = unquote(urlparse(url).path.split("/")[-1])
            except Exception:
                name = ""
        name = re.sub(r'[<>:"\\|?*/]', "_", name).strip() or f"image_{int(_time.time())}.jpg"
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
        from datetime import datetime, timezone

        sidecar = {
            "source_url": url,
            "page_url": request.data.get("source_page_url"),
            "page_title": request.data.get("page_title"),
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "via": "image-toolkit-extension",
        }
        (dest_dir / (dest.name + ".json")).write_text(
            _json.dumps(sidecar, indent=2), encoding="utf-8"
        )

        return Response({"path": str(dest)}, status=status.HTTP_201_CREATED)


class DupCheckView(CorsAPIView):
    permission_classes = [BridgeTokenPermission]

    @extend_schema(
        tags=["Extension Bridge"],
        summary="Perceptual duplicate search of the configured directory tree",
        request=inline_serializer(
            name="ExtensionDupCheckRequest",
            fields={
                "url": drf_serializers.URLField(required=False),
                "data_b64": drf_serializers.CharField(required=False),
                "threshold": drf_serializers.IntegerField(required=False),
            },
        ),
        responses={
            200: OpenApiResponse(description="matches / scanned / cold_scan"),
            400: OpenApiResponse(description="bad request or undecodable image"),
            409: OpenApiResponse(description="dup_root not configured"),
        },
    )
    def post(self, request):  # noqa: ANN001
        cfg = load_config()
        dup_root = cfg.get("dup_root") or ""
        if not dup_root:
            return Response(
                {"error": "No duplicate-search directory configured in the app."},
                status=status.HTTP_409_CONFLICT,
            )

        url = request.data.get("url")
        data_b64 = request.data.get("data_b64")
        if not url and not data_b64:
            return Response(
                {"error": "Provide 'url' or 'data_b64'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if data_b64:
                data = base64.b64decode(data_b64)
            else:
                data = _fetch_image_bytes(url)
        except Exception as exc:
            return Response(
                {"error": f"Could not fetch image: {exc}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(data) > _MAX_FETCH_BYTES:
            return Response(
                {"error": "Image too large."}, status=status.HTTP_400_BAD_REQUEST
            )

        from backend.src.core.dir_phash_index import DirPhashIndex

        try:
            threshold = int(request.data.get("threshold", cfg.get("threshold", 10)))
        except (TypeError, ValueError):
            threshold = 10

        index = DirPhashIndex(dup_root, recursive=bool(cfg.get("recursive", True)))
        try:
            stats = index.refresh()
            matches = index.query_bytes(data, threshold=threshold, limit=20)
            if matches is None:
                return Response(
                    {"error": "Image could not be decoded."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            enriched: list[Dict[str, Any]] = []
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
            return Response(
                {
                    "matches": enriched,
                    "scanned": stats["total"],
                    "cold_scan": stats["cold_scan"],
                    "threshold": threshold,
                }
            )
        finally:
            index.close()
