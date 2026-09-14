"""Crawler selection dialogs (manual review + automated duplicate pruning).

Split (§5.17 Option B, #629) into :mod:`_manual_selection` (image cards +
manual selection dialog) and :mod:`_duplicate_pruning` (duplicate config +
pruning dialogs, duplicate-scan runner) — pure code motion, no logic
change. This module keeps the public surface.
"""

from __future__ import annotations

from ._duplicate_pruning import (
    DeduplicationPruningDialog,
    DuplicateConfigDialog,
    run_duplicate_scan,
)
from ._manual_selection import (
    ClickableImageCard,
    ManualSelectionDialog,
    get_file_sha256,
    get_file_size_str,
)

__all__ = [
    "ClickableImageCard",
    "DeduplicationPruningDialog",
    "DuplicateConfigDialog",
    "ManualSelectionDialog",
    "get_file_sha256",
    "get_file_size_str",
    "run_duplicate_scan",
]
