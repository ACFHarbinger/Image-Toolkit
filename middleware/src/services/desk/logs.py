"""Read a caller log without following it (#919).

One snapshot from the end of a regular file, capped at 1 MiB. Symlinks are
not followed and ``~/.image-toolkit`` is never opened.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any

_READ_CAP = 1024 * 1024
_ERROR_WORD = re.compile(r"\bERROR\b")
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)


def read_log(path: str, limit: int) -> dict[str, Any]:
    missing = {
        "found": False,
        "path": path,
        "lines": [],
        "error_count": 0,
        "reason": "log file is missing",
    }
    target = Path(os.path.expanduser(path))
    if _in_image_toolkit(target):
        return missing
    fd = _open_regular(target)
    if fd is None:
        return missing
    try:
        data = _tail(fd, _READ_CAP)
    except OSError:
        return missing
    finally:
        os.close(fd)
    lines = [line for line in data.decode("utf-8", errors="replace").splitlines() if line]
    chosen = lines[-limit:] if limit > 0 else []
    return {
        "found": True,
        "path": path,
        "lines": chosen,
        "error_count": sum(1 for line in chosen if _counts_as_error(line)),
        "reason": "log is not followed",
    }


def _counts_as_error(line: str) -> bool:
    return " ERROR " in line or _ERROR_WORD.search(line) is not None


def _in_image_toolkit(path: Path) -> bool:
    root = (Path.home() / ".image-toolkit").resolve()
    for candidate in (path, path.absolute()):
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate.absolute()
        if resolved == root or root in resolved.parents:
            return True
    return False


def _open_regular(path: Path) -> int | None:
    try:
        info = path.lstat()
    except OSError:
        return None
    if not stat.S_ISREG(info.st_mode):
        return None
    try:
        return os.open(path, os.O_RDONLY | _NOFOLLOW | _CLOEXEC)
    except OSError:
        return None


def _tail(fd: int, cap: int) -> bytes:
    size = os.lseek(fd, 0, os.SEEK_END)
    start = size - cap if size > cap else 0
    partial = False
    if start > 0:
        os.lseek(fd, start - 1, os.SEEK_SET)
        partial = os.read(fd, 1) != b"\n"
    os.lseek(fd, start, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = size - start
    while remaining > 0:
        block = os.read(fd, remaining)
        if not block:
            break
        chunks.append(block)
        remaining -= len(block)
    data = b"".join(chunks)
    if partial:
        newline = data.find(b"\n")
        if newline != -1:
            data = data[newline + 1 :]
    return data
