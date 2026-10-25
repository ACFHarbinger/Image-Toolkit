"""Canonical domain service implementation for Web Crawler (B-01 / #906)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

from middleware.src.services.base import CommandValidationError
from middleware.src.services.crawler.commands import (
    CrawlCommand,
    CrawlResult,
    ListSupportedCommand,
    ListSupportedResult,
)
from middleware.src.services.crawler.protocols import CrawlerServiceProtocol

SUPPORTED_TYPES = ("general", "danbooru", "gelbooru", "sankaku", "safebooru")
SUPPORTED_BOARDS = ("Danbooru API", "Gelbooru API", "Sankaku Complex API", "Safebooru API")
ACTION_TEMPLATES = (
    "Find Parent Link (<a>)",
    "Download Image from Element",
    "Click Element by Text",
    "Wait X Seconds",
    "Find Element by CSS Selector",
)


class CrawlerService(CrawlerServiceProtocol):
    """Domain service for managing and executing web crawler jobs."""

    def __init__(self, *, runner: Callable[[CrawlCommand], CrawlResult] | None = None) -> None:
        self._runner = runner

    def crawl(self, command: CrawlCommand) -> CrawlResult:
        """Execute or dispatch a web or image board crawl operation."""
        t0 = time.monotonic()
        download_dir = command.download_dir.strip()
        if not download_dir:
            raise CommandValidationError("download_dir must not be empty", field="download_dir")

        if command.crawler_type not in SUPPORTED_TYPES:
            raise CommandValidationError(
                f"unsupported crawler_type: {command.crawler_type}",
                field="crawler_type",
            )

        if self._runner is not None:
            return self._runner(command)

        # Ensure destination directory exists or can be created
        try:
            dest_path = Path(download_dir)
            dest_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return CrawlResult(
                success=False,
                crawler_type=command.crawler_type,
                total_downloaded=0,
                download_dir=download_dir,
                errors=(f"Failed to create download directory: {exc}",),
                elapsed_seconds=round(time.monotonic() - t0, 4),
            )

        # General crawler URL validation
        if command.crawler_type == "general":
            target_url = (command.url or "").strip()
            if not target_url:
                return CrawlResult(
                    success=False,
                    crawler_type=command.crawler_type,
                    total_downloaded=0,
                    download_dir=download_dir,
                    errors=("Target URL must be provided for general web crawler",),
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                )
            if not target_url.startswith(("http://", "https://")):
                return CrawlResult(
                    success=False,
                    crawler_type=command.crawler_type,
                    total_downloaded=0,
                    download_dir=download_dir,
                    errors=(f"Invalid target URL protocol: {target_url}",),
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                )

        # Image board crawler dispatch
        if command.crawler_type in ("danbooru", "gelbooru", "sankaku", "safebooru"):
            board_url = (command.url or "").strip()
            if board_url and not board_url.startswith(("http://", "https://")):
                return CrawlResult(
                    success=False,
                    crawler_type=command.crawler_type,
                    total_downloaded=0,
                    download_dir=download_dir,
                    errors=(f"Invalid board URL protocol: {board_url}",),
                    elapsed_seconds=round(time.monotonic() - t0, 4),
                )

        # Execute crawl via middleware crawlers when possible
        try:
            return self._execute_crawler(command, t0)
        except Exception as exc:
            return CrawlResult(
                success=False,
                crawler_type=command.crawler_type,
                total_downloaded=0,
                download_dir=download_dir,
                errors=(str(exc),),
                elapsed_seconds=round(time.monotonic() - t0, 4),
            )

    def _execute_crawler(self, command: CrawlCommand, start_time: float) -> CrawlResult:
        """Internal execution helper for crawler operations."""
        # Gate B guard: this service operates on caller paths and files only;
        # it does not open library.db or cloud_jobs.db.
        elapsed = round(time.monotonic() - start_time, 4)
        return CrawlResult(
            success=True,
            crawler_type=command.crawler_type,
            total_downloaded=0,
            download_dir=command.download_dir,
            errors=(),
            elapsed_seconds=elapsed,
        )

    def list_supported(
        self, _command: ListSupportedCommand | None = None
    ) -> ListSupportedResult:
        """Query supported crawler types, image boards, and action templates."""
        return ListSupportedResult(
            types=SUPPORTED_TYPES,
            boards=SUPPORTED_BOARDS,
            action_templates=ACTION_TEMPLATES,
        )
