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
from middleware.src.services.crawler.service import CrawlerService
from middleware.src.services.hie.service import HieService
from middleware.src.services.stitch.status import stitch_status
from middleware.src.sidecar.handlers.auth import handle_status
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
from middleware.src.sidecar.handlers.cloud_setup import handle_cloud_setup_providers
from middleware.src.sidecar.handlers.convert import handle_convert, start_convert_batch
from middleware.src.sidecar.handlers.crawler import handle_crawl, handle_list_supported
from middleware.src.sidecar.handlers.desk import handle_logs_read, handle_metadata_describe
from middleware.src.sidecar.handlers.dl import handle_inspect
from middleware.src.sidecar.handlers.drive_sync import handle_drive_plan
from middleware.src.sidecar.handlers.entity_recon import (
    handle_entity_recon_describe,
    handle_entity_recon_resolve,
)
from middleware.src.sidecar.handlers.extractor import handle_probe
from middleware.src.sidecar.handlers.hie import (
    handle_execute_edit,
    handle_export_document,
    handle_list_capabilities,
    handle_open_document,
)
from middleware.src.sidecar.handlers.library import (
    handle_list_groups,
    handle_list_images,
    handle_list_tags,
)
from middleware.src.sidecar.handlers.library_admin import (
    handle_browse,
    handle_catalog,
    handle_mutate,
)
from middleware.src.sidecar.handlers.library_preview import (
    handle_describe,
    handle_difference,
    handle_frame,
)
from middleware.src.sidecar.handlers.media_loader import handle_media_plan
from middleware.src.sidecar.handlers.merge import handle_concatenate
from middleware.src.sidecar.handlers.prefs import handle_prefs_describe
from middleware.src.sidecar.handlers.reverse_search import (
    handle_reverse_search,
    handle_reverse_search_engines,
)
from middleware.src.sidecar.handlers.scan import (
    handle_save_metadata,
    handle_scan_directory,
    handle_suggest_tags,
)
from middleware.src.sidecar.handlers.settings import (
    handle_settings_get,
    handle_settings_get_many,
    handle_settings_set,
    handle_settings_set_many,
)
from middleware.src.sidecar.handlers.similarity import handle_compare
from middleware.src.sidecar.handlers.webreq import (
    handle_webreq_execute,
    handle_webreq_sequence,
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
        scan_service: Any | None = None,
        library_store: Any | None = None,
        library_admin_store: Any | None = None,
        crawler_service: Any | None = None,
        recon_engine: Any | None = None,
        webreq_service: Any | None = None,
        hie_service: Any | None = None,
    ) -> None:
        self.table = table or catalog()
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout
        self.stderr = stderr or sys.stderr
        self.cloud_projection = cloud_projection
        self.badge_source = badge_source
        self.jobs_source = jobs_source
        self.scan_service = scan_service
        self.library_store = library_store
        self.library_admin_store = library_admin_store
        self.crawler_service = crawler_service or CrawlerService()
        self.recon_engine = recon_engine
        self.webreq_service = webreq_service
        self.hie_service = hie_service or HieService()
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
        core = self._dispatch_core(method, params)
        if core is not _UNHANDLED:
            return core
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
        scan = self._dispatch_scan(method, params)
        if scan is not _UNHANDLED:
            return scan
        tail = self._dispatch_tail(method, params)
        if tail is not _UNHANDLED:
            return tail
        system_pages = self._dispatch_system_pages(method, params)
        if system_pages is not _UNHANDLED:
            return system_pages
        reverse = self._dispatch_reverse_search(method, params)
        if reverse is not _UNHANDLED:
            return reverse
        setup = self._dispatch_cloud_setup(method, params)
        if setup is not _UNHANDLED:
            return setup
        raise BridgeAppError("bridge.method_not_found", details={"method": method})

    def _dispatch_core(self, method: str, params: dict[str, Any]) -> Any:
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
        return _UNHANDLED

    def _dispatch_cloud_setup(self, method: str, params: dict[str, Any]) -> Any:
        if method == "cloud_setup.providers":
            return handle_cloud_setup_providers()
        return _UNHANDLED

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
        if method == "prefs.describe":
            return handle_prefs_describe(params)
        return _UNHANDLED

    def _dispatch_reverse_search(self, method: str, params: dict[str, Any]) -> Any:
        if method == "reverse_search.engines":
            return handle_reverse_search_engines()
        if method == "reverse_search.search":
            return handle_reverse_search(params)
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

    def _dispatch_scan(self, method: str, params: dict[str, Any]) -> Any:
        if method == "scan.directory":
            return handle_scan_directory(self.scan_service, params)
        if method == "scan.save_metadata":
            return handle_save_metadata(self.scan_service, params)
        if method == "scan.suggest_tags":
            return handle_suggest_tags(self.scan_service, params)
        return _UNHANDLED

    def _dispatch_tail(self, method: str, params: dict[str, Any]) -> Any:
        system_pages = self._dispatch_system_pages(method, params)
        if system_pages is not _UNHANDLED:
            return system_pages
        hie = self._dispatch_hie(method, params)
        if hie is not _UNHANDLED:
            return hie
        webreq = self._dispatch_webreq(method, params)
        if webreq is not _UNHANDLED:
            return webreq
        recon = self._dispatch_entity_recon(method, params)
        if recon is not _UNHANDLED:
            return recon
        crawler = self._dispatch_crawler(method, params)
        if crawler is not _UNHANDLED:
            return crawler
        return self._dispatch_web(method, params)

    def _dispatch_crawler(self, method: str, params: dict[str, Any]) -> Any:
        if method == "crawler.crawl":
            return handle_crawl(self.crawler_service, params)
        if method == "crawler.list_supported":
            return handle_list_supported(self.crawler_service, params)
        return _UNHANDLED

    def _dispatch_entity_recon(self, method: str, params: dict[str, Any]) -> Any:
        if method == "entity_recon.describe":
            return handle_entity_recon_describe(self.recon_engine)
        if method == "entity_recon.resolve":
            return handle_entity_recon_resolve(self.recon_engine, params)
        return _UNHANDLED

    def _dispatch_webreq(self, method: str, params: dict[str, Any]) -> Any:
        if method == "webreq.execute":
            return handle_webreq_execute(self.webreq_service, params)
        if method == "webreq.sequence":
            return handle_webreq_sequence(self.webreq_service, params)
        return _UNHANDLED

    def _dispatch_hie(self, method: str, params: dict[str, Any]) -> Any:
        if method == "hie.open_document":
            return handle_open_document(self.hie_service, params)
        if method == "hie.execute_edit":
            return handle_execute_edit(self.hie_service, params)
        if method == "hie.export_document":
            return handle_export_document(self.hie_service, params)
        if method == "hie.list_capabilities":
            return handle_list_capabilities(self.hie_service, params)
        return _UNHANDLED

    def _dispatch_system_pages(self, method: str, params: dict[str, Any]) -> Any:
        if method == "merge.concatenate":
            return handle_concatenate(params)
        if method == "similarity.compare":
            return handle_compare(params)
        if method == "extractor.probe":
            return handle_probe(params)
        if method == "stitch.status":
            return stitch_status(params["route"])
        if method == "logs.read":
            return handle_logs_read(params)
        if method == "metadata.describe":
            return handle_metadata_describe(params)
        if method == "dl.inspect":
            return handle_inspect(params)
        if method == "auth.status":
            return handle_status(params)
        return _UNHANDLED

    def _dispatch_web(self, method: str, params: dict[str, Any]) -> Any:
        if method == "drive_sync.plan":
            return handle_drive_plan(params)
        if method == "media_loader.plan":
            return handle_media_plan(params)
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
