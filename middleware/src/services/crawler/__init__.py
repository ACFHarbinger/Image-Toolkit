"""Web Crawler service package (B-01 / #906)."""

from middleware.src.services.crawler.commands import (
    CrawlCommand,
    CrawlResult,
    ListSupportedCommand,
    ListSupportedResult,
)
from middleware.src.services.crawler.protocols import CrawlerServiceProtocol
from middleware.src.services.crawler.service import CrawlerService

__all__ = [
    "CrawlerService",
    "CrawlerServiceProtocol",
    "CrawlCommand",
    "CrawlResult",
    "ListSupportedCommand",
    "ListSupportedResult",
]
