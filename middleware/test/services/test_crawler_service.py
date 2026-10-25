"""Unit tests for the Crawler service (B-01 / #906)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from middleware.src.services.base import CommandValidationError
from middleware.src.services.crawler import (
    CrawlCommand,
    CrawlerService,
    CrawlerServiceProtocol,
    CrawlResult,
    ListSupportedCommand,
    ListSupportedResult,
)


def test_crawler_service_protocol_conformance() -> None:
    service = CrawlerService()
    assert isinstance(service, CrawlerServiceProtocol)


def test_crawl_command_immutability() -> None:
    cmd = CrawlCommand(crawler_type="danbooru", download_dir="/tmp/test")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cmd.download_dir = "/tmp/other"  # type: ignore[misc]


def test_crawl_validation_missing_download_dir() -> None:
    service = CrawlerService()
    with pytest.raises(CommandValidationError):
        service.crawl(CrawlCommand(crawler_type="general", download_dir=""))


def test_crawl_validation_unsupported_type() -> None:
    service = CrawlerService()
    with pytest.raises(CommandValidationError):
        service.crawl(CrawlCommand(crawler_type="invalid_type", download_dir="/tmp/test"))  # type: ignore[arg-type]


def test_crawl_general_missing_url(tmp_path: Path) -> None:
    service = CrawlerService()
    result = service.crawl(CrawlCommand(crawler_type="general", download_dir=str(tmp_path)))
    assert result.success is False
    assert any("Target URL must be provided" in err for err in result.errors)


def test_crawl_general_invalid_url_protocol(tmp_path: Path) -> None:
    service = CrawlerService()
    result = service.crawl(
        CrawlCommand(
            crawler_type="general",
            download_dir=str(tmp_path),
            url="ftp://invalid.url",
        )
    )
    assert result.success is False
    assert any("Invalid target URL protocol" in err for err in result.errors)


def test_crawl_board_execution(tmp_path: Path) -> None:
    service = CrawlerService()
    result = service.crawl(
        CrawlCommand(
            crawler_type="danbooru",
            download_dir=str(tmp_path),
            tags="scenic",
            limit=10,
        )
    )
    assert result.success is True
    assert result.crawler_type == "danbooru"
    assert result.download_dir == str(tmp_path)
    assert result.elapsed_seconds >= 0.0


def test_crawl_with_custom_runner(tmp_path: Path) -> None:
    def fake_runner(cmd: CrawlCommand) -> CrawlResult:
        return CrawlResult(
            success=True,
            crawler_type=cmd.crawler_type,
            total_downloaded=42,
            download_dir=cmd.download_dir,
            errors=(),
            elapsed_seconds=0.123,
        )

    service = CrawlerService(runner=fake_runner)
    result = service.crawl(
        CrawlCommand(
            crawler_type="gelbooru",
            download_dir=str(tmp_path),
        )
    )
    assert result.success is True
    assert result.total_downloaded == 42


def test_list_supported() -> None:
    service = CrawlerService()
    result = service.list_supported(ListSupportedCommand())
    assert isinstance(result, ListSupportedResult)
    assert "general" in result.types
    assert "danbooru" in result.types
    assert "Danbooru API" in result.boards
    assert "Find Parent Link (<a>)" in result.action_templates
