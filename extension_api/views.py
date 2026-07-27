"""Browser-extension bridge endpoints (§7.5A / §7.6 / §7.8).

Token-authenticated, CORS-enabled endpoints consumed by the WebExtension:

- ``GET  /api/extension/ping``       — version + feature discovery
- ``POST /api/extension/dup-check``  — perceptual duplicate search of the
  configured directory tree (``DirPhashIndex``)
- ``POST /api/extension/ingest``     — save an image into the library
- ``POST /api/extension/similar``    — ranked visual-similarity search
  (§7.8). Degrades to pHash top-K ranking (``DirPhashIndex.query_topk``)
  because the Unified DB embedding index (roadmap DB.7) is not populated
  yet — see the module docstring on ``SimilarView`` below.
- ``GET  /api/extension/phash-snapshot`` — exports the configured
  directory's distinct pHash set (§7.16C) for client-side caching, so the
  extension can do an offline, no-round-trip approximate pre-check before
  falling back to the authoritative ``dup-check`` call.

The actual business logic lives in ``bridge_handlers.py`` (transport-
agnostic, shared with the §7.5B native-messaging host in ``native_host.py``)
— these views are thin wrappers adding the HTTP-specific concerns (bearer
token auth, CORS, DRF request/response plumbing, OpenAPI schema) on top.
"""

from __future__ import annotations

import hmac
import logging

from django.http import HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from . import bridge_handlers
from .bridge_config import get_token

logger = logging.getLogger(__name__)


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
        _status, body = bridge_handlers.handle_ping()
        return Response(body, status=_status)


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
        _status, body = bridge_handlers.handle_ingest(request.data)
        return Response(body, status=_status)


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
        _status, body = bridge_handlers.handle_dup_check(request.data)
        return Response(body, status=_status)


class SimilarView(CorsAPIView):
    """§7.8 — ranked visual-similarity search ("Find similar in my library").

    The roadmap's ideal path embeds the query image (BGE-M3/CLIP) and does
    a cosine-kNN lookup against the app's embedding index. As of this
    implementation that index does not exist in a queryable state: the
    Unified DB roadmap's DB.7 ("Semantic Search & CBIR") — the phase that
    populates ``embeddings`` with real image vectors and wires up a
    "find similar" action — has no shipped marker (unlike DB.1-DB.4) and
    nothing in the codebase calls ``base.database``'s ``knn`` primitive
    outside its own unit test. The standalone ``Recommendation-Engine``
    submodule's BGE-M3/SQLite store is a different domain (media
    listings/entities, not this library's images) and isn't wired to it
    either.

    Per §7.8's own explicit fallback clause ("degrade to pHash-only §7.6
    when no embedding index exists"), this view ranks the configured
    directory tree by perceptual-hash Hamming distance
    (``DirPhashIndex.query_topk``) instead — same response shape as a
    future embedding-based implementation would use, so swapping the
    ranking method later is a body-only change.
    """

    permission_classes = [BridgeTokenPermission]

    @extend_schema(
        tags=["Extension Bridge"],
        summary="Ranked visual-similarity search (pHash top-K; degrades "
        "from the embedding index described in §7.8 until it exists)",
        request=inline_serializer(
            name="ExtensionSimilarRequest",
            fields={
                "url": drf_serializers.URLField(required=False),
                "data_b64": drf_serializers.CharField(required=False),
                "top_k": drf_serializers.IntegerField(required=False),
            },
        ),
        responses={
            200: OpenApiResponse(description="results / scanned / cold_scan / method"),
            400: OpenApiResponse(description="bad request or undecodable image"),
            409: OpenApiResponse(description="dup_root not configured"),
        },
    )
    def post(self, request):  # noqa: ANN001
        _status, body = bridge_handlers.handle_similar(request.data)
        return Response(body, status=_status)


class PhashSnapshotView(CorsAPIView):
    """§7.16C — compact pHash export for the client-side pre-check.

    A GET (no image payload) that returns every distinct pHash currently
    indexed for the configured directory tree, so the extension can cache
    it in ``storage.local`` and do an offline, no-round-trip Hamming-distance
    sweep before deciding whether an image is "probably already in the
    library" — useful for turbo/bulk downloads and for when the bridge is
    momentarily unreachable at browse time. The authoritative check remains
    §7.6 dup-check (``DupCheckView``), which always re-verifies live.
    """

    permission_classes = [BridgeTokenPermission]

    @extend_schema(
        tags=["Extension Bridge"],
        summary="Export the configured directory's pHash set for client-side caching",
        responses={
            200: OpenApiResponse(description="hashes / count / scanned / cold_scan"),
            409: OpenApiResponse(description="dup_root not configured"),
        },
    )
    def get(self, request):  # noqa: ANN001
        _status, body = bridge_handlers.handle_phash_snapshot({})
        return Response(body, status=_status)
