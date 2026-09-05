"""Regression test for #529: dispatch_web's crawl path must use the
Observable ``.subscribe()`` API, not the old Qt Signal ``.connect()``.

``ImageCrawler.on_status``/``on_finished`` were migrated from
``Signal(str)`` to ``Observable[str]`` (#529). ``.connect()`` doesn't
exist on ``Observable``, so the CLI crawl path raised ``AttributeError``
before the crawler could even start (caught by the broad ``except
Exception`` and printed as a generic failure) until this was caught.
"""

from __future__ import annotations

from unittest.mock import patch

from backend.controllers.backend_dispatch import dispatch_web
from backend.src.events import Observable


class _FakeCrawler:
    """Stand-in for ImageCrawler exposing the real Observable-based API."""

    def __init__(self, config):
        self.config = config
        self.on_status: Observable[str] = Observable()
        self.on_finished: Observable[str] = Observable()
        self.ran = False

    def run(self):
        self.ran = True
        self.on_status.publish("done")
        self.on_finished.publish("finished")


def test_dispatch_web_crawl_subscribes_without_raising(capsys):
    """dispatch_web's crawl path must not call the removed .connect()."""
    with patch(
        "backend.controllers.backend_dispatch.ImageCrawler", _FakeCrawler
    ):
        dispatch_web(
            {
                "web_command": "crawl",
                "query": "https://example.invalid",
                "output": "/tmp",
                "limit": 1,
            }
        )

    captured = capsys.readouterr()
    assert "❌" not in captured.err
    assert "[*] done" in captured.out
    assert "[+] finished" in captured.out
