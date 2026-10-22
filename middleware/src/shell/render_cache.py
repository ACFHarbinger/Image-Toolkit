"""Bounded gallery stills for the Tauri render cache (S-01, #887).

The C++ writer returns cache paths. This module does not forward pixel
buffers, and it drops any path that is not inside the requested cache
directory. Animated preview is a separate cancellable request and does
not write a still.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import backend

DEFAULT_MAX_EDGE = 256


def default_render_cache() -> Path:
    """Directory the Tauri asset scope already allows."""
    return Path.home() / ".image-toolkit" / "cache" / "render"


@dataclass(frozen=True, slots=True)
class RenderStill:
    source: str
    cache_path: str
    error: str
    kind: str
    frame_index: int


class PreviewCancelled(Exception):
    """The animated-preview request was cancelled before a decode."""


def _inside(root: Path, candidate: str) -> bool:
    if not candidate:
        return False
    try:
        Path(candidate).resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def write_render_stills(
    sources: Sequence[str],
    cache_dir: Path | None = None,
    max_edge: int = DEFAULT_MAX_EDGE,
) -> list[RenderStill]:
    """Write one bounded JPEG per source into ``cache_dir``.

    The default directory is the asset-scoped render cache. Tests pass
    their own directory and must not fall through to the home cache.
    """
    root = Path(cache_dir) if cache_dir is not None else default_render_cache()
    root.mkdir(parents=True, exist_ok=True)
    rows = backend.write_render_stills([str(source) for source in sources], str(root), int(max_edge))
    stills: list[RenderStill] = []
    for source, cache_path, error, kind, frame_index in rows:
        path = str(cache_path)
        failure = str(error)
        if path and not _inside(root, path):
            path = ""
            failure = failure or "cache path escaped the render directory"
        stills.append(
            RenderStill(
                source=str(source),
                cache_path=path,
                error=failure,
                kind=str(kind),
                frame_index=int(frame_index),
            )
        )
    return stills


def request_animated_preview(source: str, cancel: threading.Event) -> None:
    """Boundary for a cancellable animated preview.

    This spike does not decode ``source``. A set cancel event aborts
    before any read, and nothing is written to the render cache.
    """
    del source
    if cancel.is_set():
        raise PreviewCancelled("animated preview cancelled")
    if cancel.is_set():
        raise PreviewCancelled("animated preview cancelled")


def iter_cache_paths(stills: Iterable[RenderStill]) -> list[str]:
    return [still.cache_path for still in stills if still.cache_path and not still.error]
