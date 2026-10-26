"""Describe a caller file without editing it (#919).

Size comes from ``stat``. Bytes are not read, ``library.db`` is not
connected, and image pixels are not decoded.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def describe_file(path: str) -> dict[str, Any]:
    missing = {
        "found": False,
        "path": path,
        "name": "",
        "size": 0,
        "suffix": "",
        "reason": "file is missing",
    }
    target = Path(os.path.expanduser(path))
    try:
        if not target.is_file() or target.is_symlink():
            return missing
        size = target.stat().st_size
    except OSError:
        return missing
    if size < 0:
        return missing
    return {
        "found": True,
        "path": path,
        "name": target.name,
        "size": size,
        "suffix": target.suffix,
        "reason": "metadata is not edited",
    }
