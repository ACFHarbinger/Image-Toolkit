"""Sidecar handlers for the Web Crawler capability (B-01 / #906)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.crawler.commands import (
    CrawlCommand,
    ListSupportedCommand,
)
from middleware.src.services.crawler.service import CrawlerService


def handle_crawl(service: CrawlerService | None, params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch crawler.crawl onto CrawlerService."""
    svc = service or CrawlerService()
    actions_val = params.get("actions")
    actions_tuple = tuple(actions_val) if actions_val is not None else None
    cmd = CrawlCommand(
        crawler_type=params["crawler_type"],
        download_dir=str(params["download_dir"]),
        url=params.get("url"),
        tags=params.get("tags"),
        limit=params.get("limit"),
        max_pages=params.get("max_pages"),
        actions=actions_tuple,
        login_config=params.get("login_config"),
        auth=params.get("auth"),
    )
    result = svc.crawl(cmd)
    return {
        "success": result.success,
        "crawler_type": result.crawler_type,
        "total_downloaded": result.total_downloaded,
        "download_dir": result.download_dir,
        "errors": list(result.errors),
        "elapsed_seconds": result.elapsed_seconds,
    }


def handle_list_supported(
    service: CrawlerService | None, _params: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Dispatch crawler.list_supported onto CrawlerService."""
    svc = service or CrawlerService()
    result = svc.list_supported(ListSupportedCommand())
    return {
        "types": list(result.types),
        "boards": list(result.boards),
        "action_templates": list(result.action_templates),
    }
