"""Protocol definitions for the Web Crawler service (B-01 / #906)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from middleware.src.services.crawler.commands import (
    CrawlCommand,
    CrawlResult,
    ListSupportedCommand,
    ListSupportedResult,
)


@runtime_checkable
class CrawlerServiceProtocol(Protocol):
    """Protocol declaring the public surface of the Crawler service."""

    def crawl(self, command: CrawlCommand) -> CrawlResult:
        """Execute a crawl operation according to command parameters."""
        ...

    def list_supported(self, command: ListSupportedCommand | None = None) -> ListSupportedResult:
        """Query supported crawler types, image boards, and action templates."""
        ...
