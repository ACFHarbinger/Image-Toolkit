"""Average-hash comparison of caller image paths (#904).

Nothing here opens library.db or deletes a file. Header size is checked
before the 8x8 grayscale hash is decoded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_MAX_PIXELS = 4_000_000
_MAX_PATHS = 32
_MAX_PAIRS = 64


def compare_paths(paths: list[str], threshold: int) -> dict[str, Any]:
    if len(paths) > _MAX_PATHS:
        raise ValueError("compare accepts at most 32 paths")
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0 or threshold > 64:
        raise ValueError("threshold must be from 0 to 64")
    items = [_hash_one(path) for path in paths]
    pairs: list[dict[str, Any]] = []
    hashed = [item for item in items if item["ahash"]]
    for index, left in enumerate(hashed):
        for right in hashed[index + 1 :]:
            distance = (int(left["ahash"], 16) ^ int(right["ahash"], 16)).bit_count()
            if distance <= threshold:
                pairs.append({"left": left["path"], "right": right["path"], "distance": distance})
            if len(pairs) >= _MAX_PAIRS:
                return {"items": items, "pairs": pairs}
    return {"items": items, "pairs": pairs}


def _hash_one(path: str) -> dict[str, Any]:
    from PIL import UnidentifiedImageError

    blank = {"path": path, "width": 0, "height": 0, "ahash": "", "error": "not a file"}
    if not Path(path).is_file():
        return blank
    try:
        width, height, digest = _ahash(path)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return {"path": path, "width": 0, "height": 0, "ahash": "", "error": str(exc)}
    return {"path": path, "width": width, "height": height, "ahash": digest, "error": ""}


def _ahash(path: str) -> tuple[int, int, str]:
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
        if width < 1 or height < 1 or width * height > _MAX_PIXELS:
            raise ValueError("image is too large")
        converted = image.convert("L")
        try:
            resized = converted.resize((8, 8), Image.Resampling.BOX)
            try:
                pixels = list(resized.tobytes())
            finally:
                if resized is not converted:
                    resized.close()
        finally:
            if converted is not image:
                converted.close()
    average = sum(pixels) / len(pixels)
    bits = 0
    for index, pixel in enumerate(pixels):
        if pixel >= average:
            bits |= 1 << index
    return int(width), int(height), f"{bits:016x}"
