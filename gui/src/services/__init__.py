"""gui/src/services/__init__.py
============================
Shared application services for GUI components (ui-arch-40 / #562).
"""

from __future__ import annotations

from .directory_scan_service import (
    ScanRequest,
    ScanSession,
    collect_files,
    normalize_extensions,
)
from .preview_service import (
    PreviewContext,
    PreviewService,
    get_preview_service,
    launch_external_player,
    open_preview,
)

__all__ = [
    "PreviewContext",
    "PreviewService",
    "ScanRequest",
    "ScanSession",
    "collect_files",
    "get_preview_service",
    "launch_external_player",
    "normalize_extensions",
    "open_preview",
]
