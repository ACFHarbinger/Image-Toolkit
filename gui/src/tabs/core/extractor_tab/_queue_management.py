"""Extraction queue management (add/remove/reorder-by-load, sequential vs
parallel processing) and the "5. Results Gallery Section" build (output
gallery, queue box, search input, pagination).

Split (§5.17 Option B, #629) into :mod:`_queue_panel` (results-section
build, queue CRUD, In Process list UI) and :mod:`_queue_processing`
(run/cancel, progress, completion, close deferral) — pure code motion, no
logic change. This module keeps the public surface: the composed
controller plus the row-label helper and status constants (the latter
imported by ``test_inprocess_queue_labels``).
"""

from __future__ import annotations

from ._queue_panel import (
    _ST_DONE,
    _ST_ERROR,
    _ST_PENDING,
    _ST_PROCESSING,
    ExtractorQueuePanelController,
    _inprocess_row_label,
)
from ._queue_processing import ExtractorQueueProcessingController


class ExtractorQueueManagementController(
    ExtractorQueuePanelController, ExtractorQueueProcessingController
):
    """Extraction queue management and the Results Gallery / Queue section."""


__all__ = [
    "ExtractorQueueManagementController",
    "_ST_DONE",
    "_ST_ERROR",
    "_ST_PENDING",
    "_ST_PROCESSING",
    "_inprocess_row_label",
]
