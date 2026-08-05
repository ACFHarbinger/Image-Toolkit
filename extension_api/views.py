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

import base64
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


# ── §7.14A/B — App-powered CV operations (bg-remove / upscale) ──────────────
#
# Unlike ping/dup-check/ingest/similar/phash-snapshot (fast, synchronous),
# BiRefNet/Real-ESRGAN inference is genuinely long-running, so these two
# endpoints follow the "job-id + polling" pattern the roadmap calls for,
# reusing this project's existing Celery task queue (the same one
# `tasks/views.py`'s `CoreTaskView` already uses for other async work)
# rather than inventing a second async mechanism. The image payload is
# still resolved synchronously here (via the shared
# `bridge_handlers._resolve_image_payload` helper) so a bad/unreachable
# URL fails fast with 400 instead of silently after being queued.
#
# These two are HTTP-only for now — they don't go through
# `bridge_handlers.HANDLERS`/`native_host.py`'s synchronous
# action-dispatch model, since a job-id-and-poll flow doesn't map onto a
# single-request/single-response native-messaging call without a second
# design pass (the native host would need its own polling loop or a
# push-style follow-up message). Not attempted here to keep this change
# bounded to what issues #93/#94 actually ask for; native-messaging parity
# for §7.14A/B is a reasonable, separate follow-on.


def _cv_job_response(task) -> Response:  # noqa: ANN001
    return Response({"job_id": task.id, "status": "processing"}, status=202)


def _decode_check(data: bytes):
    """Cheap synchronous decode probe so a bad image 400s immediately instead
    of only failing inside the queued job (§7.14A/B fail-fast, mirroring
    dup-check/similar's own ``"Image could not be decoded."`` behavior)."""
    import cv2
    import numpy as np

    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


class CvBgRemoveView(CorsAPIView):
    """§7.14A — "Remove background" (BiRefNet) — queues a Celery job."""

    permission_classes = [BridgeTokenPermission]

    @extend_schema(
        tags=["Extension Bridge"],
        summary="Queue a background-removal job (BiRefNet)",
        request=inline_serializer(
            name="ExtensionCvBgRemoveRequest",
            fields={
                "url": drf_serializers.URLField(required=False),
                "data_b64": drf_serializers.CharField(required=False),
            },
        ),
        responses={
            202: OpenApiResponse(description="job_id / status"),
            400: OpenApiResponse(description="bad request or undecodable image"),
        },
    )
    def post(self, request):  # noqa: ANN001
        data, url, err = bridge_handlers._resolve_image_payload(request.data)
        if err is not None:
            _status, body = err
            return Response(body, status=_status)
        if _decode_check(data) is None:
            return Response({"error": "Image could not be decoded."}, status=400)

        from .tasks import cv_bg_remove_task

        name_hint = _filename_hint(url)
        task = cv_bg_remove_task.delay(
            base64.b64encode(data).decode("ascii"), name_hint
        )
        return _cv_job_response(task)


class CvUpscaleView(CorsAPIView):
    """§7.14B — "Upscale & save" (Real-ESRGAN anime_6B) — queues a Celery job."""

    permission_classes = [BridgeTokenPermission]

    @extend_schema(
        tags=["Extension Bridge"],
        summary="Queue an upscale job (Real-ESRGAN anime_6B)",
        request=inline_serializer(
            name="ExtensionCvUpscaleRequest",
            fields={
                "url": drf_serializers.URLField(required=False),
                "data_b64": drf_serializers.CharField(required=False),
                "scale": drf_serializers.IntegerField(required=False),
            },
        ),
        responses={
            202: OpenApiResponse(description="job_id / status"),
            400: OpenApiResponse(description="bad request or undecodable image"),
        },
    )
    def post(self, request):  # noqa: ANN001
        data, url, err = bridge_handlers._resolve_image_payload(request.data)
        if err is not None:
            _status, body = err
            return Response(body, status=_status)
        if _decode_check(data) is None:
            return Response({"error": "Image could not be decoded."}, status=400)

        try:
            scale = int(request.data.get("scale", 4))
        except (TypeError, ValueError):
            scale = 4
        if scale not in (2, 4):
            scale = 4

        from .tasks import cv_upscale_task

        name_hint = _filename_hint(url)
        task = cv_upscale_task.delay(
            base64.b64encode(data).decode("ascii"), name_hint, scale
        )
        return _cv_job_response(task)


class CvJobStatusView(CorsAPIView):
    """§7.14A/B — poll a queued CV job's Celery status/result."""

    permission_classes = [BridgeTokenPermission]

    @extend_schema(
        tags=["Extension Bridge"],
        summary="Poll a queued CV job (bg-remove/upscale) by job_id",
        responses={
            200: OpenApiResponse(
                description="state (PENDING/STARTED/SUCCESS/FAILURE/...), "
                "result (once SUCCESS), error (once FAILURE)"
            ),
        },
    )
    def get(self, request, job_id):  # noqa: ANN001
        from celery.result import AsyncResult

        result = AsyncResult(job_id)
        body = {"job_id": job_id, "state": result.state}
        if result.state == "SUCCESS":
            body["result"] = result.result
        elif result.state == "FAILURE":
            body["error"] = str(result.result)
        return Response(body, status=200)


def _filename_hint(url) -> str:  # noqa: ANN001
    """Best-effort basename for suggesting `<name>_nobg.png`-style output names."""
    if not url:
        return "image.png"
    try:
        from urllib.parse import unquote, urlparse

        name = unquote(urlparse(url).path.split("/")[-1])
        return name or "image.png"
    except Exception:
        return "image.png"
