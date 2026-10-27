"""Execute download of a media URL to destination directory or file (#909 / #1109)."""

from __future__ import annotations

import os
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from middleware.src.services.media_loader.plan import plan_download


def fetch_media(
    url: str,
    destination: str,
    timeout: float = 30.0,
    downloader: Any | None = None,
) -> dict[str, Any]:
    """Download media from url into destination folder or target path."""
    t0 = time.monotonic()

    # Run plan validation first
    plan = plan_download(url, destination)
    if not plan.get("accepted"):
        return {
            "success": False,
            "url": url,
            "destination_path": "",
            "bytes_downloaded": 0,
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "error": plan.get("reason") or "invalid download plan",
        }

    dest_dir = Path(destination)
    if not dest_dir.is_dir():
        return {
            "success": False,
            "url": url,
            "destination_path": "",
            "bytes_downloaded": 0,
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "error": "destination directory is missing",
        }

    # Extract target file name
    parsed = urllib.parse.urlsplit(url)
    filename = Path(urllib.parse.unquote(parsed.path)).name.strip()
    if not filename:
        filename = f"media_{int(time.time())}.bin"
    target_path = dest_dir / filename

    if downloader is not None:
        try:
            bytes_written = downloader(url, str(target_path))
            return {
                "success": True,
                "url": url,
                "destination_path": str(target_path),
                "bytes_downloaded": int(bytes_written),
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "url": url,
                "destination_path": str(target_path),
                "bytes_downloaded": 0,
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": str(exc),
            }

    # Sibling keeps the destination suffix so type sniffing still works, but
    # the real path is replaced only after the full body is on disk.
    temp_path: Path | None = None
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Image-Toolkit-MediaLoader/1.0"},
        )
        fd, tmp_name = tempfile.mkstemp(
            suffix=target_path.suffix,
            prefix=f".{target_path.name}.",
            dir=dest_dir,
        )
        temp_path = Path(tmp_name)
        total_bytes = 0
        with os.fdopen(fd, "wb") as handle, urllib.request.urlopen(req, timeout=timeout) as response:
            while chunk := response.read(64 * 1024):
                handle.write(chunk)
                total_bytes += len(chunk)
        os.replace(temp_path, target_path)
        temp_path = None

        return {
            "success": True,
            "url": url,
            "destination_path": str(target_path),
            "bytes_downloaded": total_bytes,
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "url": url,
            "destination_path": str(target_path),
            "bytes_downloaded": 0,
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "error": str(exc),
        }
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
