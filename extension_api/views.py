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

BRIDGE_VERSION = "1.0"
FEATURES = ["ping", "dup-check"]

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
