"""Synchronous JSON-RPC/stdio sidecar server.

All stdout writes go through ``bridge.framing``: responses and validated event
frames only. Diagnostics stay on stderr and never include tracebacks.
"""

from __future__ import annotations

import sys
import threading
from typing import Any, TextIO

from middleware.src.bridge import (
    COMPATIBILITY_MAX,
    COMPATIBILITY_MIN,
    PROTOCOL_NAME,
    BridgeAppError,
    Catalog,
    FrameValidationError,
    build_handshake_result,
    build_ping_result,
    build_response,
    catalog,
    decode_request,
    from_exception,
    in_compatibility_range,
    iter_frames,
    write_frame,
)
from middleware.src.services.cloud_jobs.projection import CloudProjection
from middleware.src.sidecar.handlers.cloud_jobs import (
    BadgeSource,
    JobsSource,
    handle_detail,
    handle_list,
    handle_resources,
    handle_spend,
    handle_summary,
    handle_terminate,
)
from middleware.src.sidecar.handlers.cloud_offer import handle_prefill
from middleware.src.sidecar.handlers.convert import handle_convert, start_convert_batch
from middleware.src.sidecar.handlers.library import (
    handle_list_groups,
    handle_list_images,
    handle_list_tags,
)
from middleware.src.sidecar.handlers.library_preview import (
    handle_describe,
    handle_difference,
    handle_frame,
)
from middleware.src.sidecar.handlers.library_admin import (
    handle_browse,
    handle_catalog,
    handle_mutate,
)
from middleware.src.sidecar.handlers.settings import (
    handle_settings_get,
    handle_settings_get_many,
    handle_settings_set,
    handle_settings_set_many,
)
from middleware.src.sidecar.jobs import JobRegistry

# Distinct from a handler result: cloud and settings routes may return None.
_UNHANDLED = object()


class SidecarServer:
    """Dispatch contract methods after the readiness/version handshake."""

    def __init__(
        self,
        *,
        table: Catalog | None = None,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
        stderr: TextIO | None = None,
        cloud_projection: CloudProjection | None = None,
        badge_source: BadgeSource | None = None,
        jobs_source: JobsSource | None = None,
        library_store: Any | None = None,
        library_admin_store: Any | None = None,
    ) -> None:
        self.table = table or catalog()
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.cloud_projection = cloud_projection
        self.badge_source = badge_source
        self.jobs_source = jobs_source
        self.library_store = library_store
        self.library_admin_store = library_admin_store
        self.jobs = JobRegistry(table=self.table, event_sink=self._write_event)
        self.cloud_service = None
        self._handshaken = False
        self._write_mu = threading.Lock()

    @property
    def handshaken(self) -> bool:
        return self._handshaken

    def serve(self) -> None:
        """Read frames until EOF; a bad line gets an error response, not a crash."""
        while True:
            try:
                for frame in iter_frames(self.stdin):
                    response = self.handle_frame(frame)
                    if response is not None:
                        self._write_protocol(response)
                return
            except BridgeAppError as exc:
                self._write_protocol(build_response(None, error=exc, table=self.table))
            except Exception as exc:  # keep the supervisor's child alive past bad input
                self._write_protocol(build_response(None, error=from_exception(exc), table=self.table))

    def handle_frame(self, frame: Any) -> dict[str, Any] | None:
        request_id = self._frame_id(frame)
        try:
            request = decode_request(frame, table=self.table)
            request_id = request["id"]
            method = str(request["method"])
            params = request.get("params", {})
            if method not in self.table.methods:
                raise BridgeAppError("bridge.method_not_found", details={"method": method})
            if method != "system.handshake" and not self._handshaken:
                raise BridgeAppError(
                    "bridge.invalid_request",
                    retryable=True,
                    details={"reason": "system.handshake required before command dispatch"},
                )
            errors = self.table.validate_params(method, params)
            if errors:
                raise BridgeAppError(
                    "bridge.invalid_params",
                    retryable=True,
                    details={"errors": [str(error) for error in errors]},
                )
            result = self._dispatch(method, params)
            errors = self.table.validate_result(method, result)
            if errors:
                raise BridgeAppError(
                    "app.internal",
                    details={"errors": [str(error) for error in errors]},
                )
            return build_response(request_id, result=result, table=self.table)
        except (BridgeAppError, FrameValidationError, ValueError, TypeError) as exc:
            return build_response(request_id, error=from_exception(exc), table=self.table)
        except Exception as exc:
            return build_response(request_id, error=from_exception(exc), table=self.table)

    def _dispatch(self, method: str, params: dict[str, Any]) -> Any:
        if method == "system.handshake":
            return self._handshake(params)
        if method == "system.ping":
            return build_ping_result(table=self.table)
        if method == "jobs.submit":
            return self.jobs.submit(params)
        if method == "jobs.status":
            return self.jobs.status(params)
        if method == "jobs.list":
            return self.jobs.list(params)
        if method == "jobs.cancel":
            return self.jobs.cancel(params)
        if method == "convert.convert":
            return handle_convert(params)
        if method == "convert.convert_batch":
            return start_convert_batch(self.jobs, params)
        cloud = self._dispatch_cloud(method, params)
        if cloud is not _UNHANDLED:
            return cloud
        settings = self._dispatch_settings(method, params)
        if settings is not _UNHANDLED:
            return settings
        library = self._dispatch_library(method, params)
        if library is not _UNHANDLED:
            return library
        admin = self._dispatch_admin(method, params)
        if admin is not _UNHANDLED:
            return admin
        raise BridgeAppError("bridge.method_not_found", details={"method": method})

    def _dispatch_cloud(self, method: str, params: dict[str, Any]) -> Any:
        if method == "cloud_jobs.summary":
            return handle_summary(self.badge_source)
        if method == "cloud_jobs.list":
            return handle_list(self.jobs_source, params)
        if method == "cloud_jobs.detail":
            return handle_detail(self.jobs_source, params)
        if method == "cloud_jobs.resources":
            return handle_resources(self.cloud_projection)
        if method == "cloud_jobs.spend":
            return handle_spend(self.cloud_projection)
        if method == "cloud_jobs.terminate":
            return handle_terminate(self.cloud_projection, params)
        if method == "cloud_jobs.preview":
            from middleware.src.sidecar.handlers.cloud_submit import handle_preview

            return handle_preview(self.cloud_service, params)
        if method == "cloud_jobs.submit":
            from middleware.src.sidecar.handlers.cloud_submit import handle_submit

            return handle_submit(self.cloud_service, params)
        if method == "cloud_offer.prefill":
            return handle_prefill(params)
        return _UNHANDLED

    def _dispatch_settings(self, method: str, params: dict[str, Any]) -> Any:
        if method == "settings.get":
            return handle_settings_get(params)
        if method == "settings.set":
            return handle_settings_set(params)
        if method == "settings.get_many":
            return handle_settings_get_many(params)
        if method == "settings.set_many":
            return handle_settings_set_many(params)
        return _UNHANDLED

    def _dispatch_library(self, method: str, params: dict[str, Any]) -> Any:
        if method == "library.list_images":
            return handle_list_images(self.library_store, params)
        if method == "library.list_tags":
            return handle_list_tags(self.library_store)
        if method == "library.list_groups":
            return handle_list_groups(self.library_store)
        if method == "library_preview.describe":
            return handle_describe(params)
        if method == "library_preview.frame":
            return handle_frame(params)
        if method == "library_preview.difference":
            return handle_difference(params)
        return _UNHANDLED

    def _dispatch_admin(self, method: str, params: dict[str, Any]) -> Any:
        store = self.library_admin_store
        if method == "library_admin.catalog":
            return handle_catalog(store)
        if method == "library_admin.mutate":
            return handle_mutate(store, params)
        if method == "library_admin.browse":
            return handle_browse(store, params)
        return _UNHANDLED

    def _handshake(self, params: dict[str, Any]) -> dict[str, Any]:
        protocol = params["protocol"]
        if protocol != PROTOCOL_NAME:
            raise BridgeAppError(
                "bridge.protocol_mismatch",
                details={"expected": PROTOCOL_NAME, "got": protocol},
            )
        client_version = params["client"]["version"]
        if not in_compatibility_range(
            client_version,
            minimum=COMPATIBILITY_MIN,
            maximum=COMPATIBILITY_MAX,
        ):
            raise BridgeAppError(
                "bridge.version_mismatch",
                details={
                    "client": client_version,
                    "min": COMPATIBILITY_MIN,
                    "max": COMPATIBILITY_MAX,
                },
            )
        result = build_handshake_result(table=self.table)
        self._handshaken = True
        return result

    def _write_event(self, frame: dict[str, Any]) -> None:
        self._write_protocol(frame)

    def _write_protocol(self, frame: dict[str, Any]) -> None:
        with self._write_mu:
            write_frame(self.stdout, frame)

    @staticmethod
    def _frame_id(frame: Any) -> str | int | None:
        if not isinstance(frame, dict):
            return None
        request_id = frame.get("id")
        return request_id if isinstance(request_id, (str, int)) and not isinstance(request_id, bool) else None
