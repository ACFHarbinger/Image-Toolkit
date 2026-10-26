"""Check a download plan without fetching the URL (#909)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


def plan_download(url: str, destination: str) -> dict[str, Any]:
    result = {
        "accepted": False,
        "downloaded": False,
        "url": url,
        "destination": destination,
        "reason": "",
    }
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        result["reason"] = "url must be http or https"
        return result
    if parts.username or parts.password:
        result["reason"] = "url must not carry credentials"
        return result
    if not Path(destination).is_dir():
        result["reason"] = "destination directory is missing"
        return result
    result["accepted"] = True
    result["reason"] = "download is not performed"
    return result
