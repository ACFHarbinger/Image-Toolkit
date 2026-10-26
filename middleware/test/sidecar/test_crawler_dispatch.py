"""crawler.* methods reach CrawlerService through the sidecar dispatcher."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.services.crawler.service import CrawlerService
from middleware.src.sidecar.server import SidecarServer


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def _ready(service: CrawlerService | None = None) -> SidecarServer:
    server = SidecarServer(stdout=io.StringIO(), crawler_service=service)
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "crawler" in handshake["result"]["capabilities"]
    return server


def test_crawler_crawl_board_dispatch(tmp_path: Path) -> None:
    server = _ready()
    response = _request(
        server,
        "crawler.crawl",
        {
            "crawler_type": "danbooru",
            "download_dir": str(tmp_path),
            "tags": "cat",
            "limit": 5,
        },
        "crawl-1",
    )
    result = response["result"]
    assert result["success"] is True
    assert result["crawler_type"] == "danbooru"
    assert result["download_dir"] == str(tmp_path)


def test_crawler_crawl_general_dispatch(tmp_path: Path) -> None:
    server = _ready()
    response = _request(
        server,
        "crawler.crawl",
        {
            "crawler_type": "general",
            "download_dir": str(tmp_path),
            "url": "https://example.com/gallery",
            "actions": ["Download Image from Element"],
        },
        "crawl-2",
    )
    result = response["result"]
    assert result["success"] is True
    assert result["crawler_type"] == "general"


def test_crawler_list_supported_dispatch() -> None:
    server = _ready()
    response = _request(
        server,
        "crawler.list_supported",
        {},
        "supported-1",
    )
    result = response["result"]
    assert "general" in result["types"]
    assert "danbooru" in result["types"]
    assert "Danbooru API" in result["boards"]
