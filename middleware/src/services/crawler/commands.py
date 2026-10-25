"""Commands and results for the Web Crawler service (B-01 / #906)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from middleware.src.services.base import Command, Result

CrawlerType = Literal["general", "danbooru", "gelbooru", "sankaku", "safebooru"]


@dataclass(frozen=True)
class CrawlCommand(Command):
    """Command to execute a web scraping or image board crawl operation."""

    crawler_type: CrawlerType
    download_dir: str
    url: str | None = None
    tags: str | None = None
    limit: int | None = 20
    max_pages: int | None = 5
    actions: tuple[str, ...] | None = None
    login_config: dict[str, str | None] | None = None
    auth: dict[str, str | None] | None = None


@dataclass(frozen=True)
class CrawlResult(Result):
    """Result of executing a crawl operation."""

    success: bool
    crawler_type: str
    total_downloaded: int
    download_dir: str
    errors: tuple[str, ...] = ()
    elapsed_seconds: float = 0.0


@dataclass(frozen=True)
class ListSupportedCommand(Command):
    """Command to query supported crawler types and configurations."""


@dataclass(frozen=True)
class ListSupportedResult(Result):
    """Result of querying supported crawler capabilities."""

    types: tuple[str, ...] = field(default_factory=tuple)
    boards: tuple[str, ...] = field(default_factory=tuple)
    action_templates: tuple[str, ...] = field(default_factory=tuple)
