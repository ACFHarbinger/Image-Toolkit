"""Reusable UI components — lazily re-exported (issues #530, #573, R3.6)."""

from __future__ import annotations

import importlib

_LAZY_EXPORTS = {
    # .containers
    "CanvasBase": ".containers",
    "DraggableMonitorContainer": ".containers",
    "MarqueeScrollArea": ".containers",
    "MergeCanvas": ".containers",
    "canvas_base": ".containers",
    "draggable_monitor_container": ".containers",
    "marquee_scroll_area": ".containers",
    "merge_canvas": ".containers",
    # .dialogs
    "AddTagDialog": ".dialogs",
    "AspAdvancedConfigDialog": ".dialogs",
    "BatchStitchDialog": ".dialogs",
    "DeduplicationPruningDialog": ".dialogs",
    "DuplicateConfigDialog": ".dialogs",
    "ExtractionCloseProgressDialog": ".dialogs",
    "FrameSelectionDialog": ".dialogs",
    "ManualSelectionDialog": ".dialogs",
    "ProcessCloseProgressDialog": ".dialogs",
    "PropertyComparisonDialog": ".dialogs",
    "SafetensorsInspectorDialog": ".dialogs",
    "ScrollVideoExportDialog": ".dialogs",
    "TagReviewDialog": ".dialogs",
    "TaskCloseProgressDialog": ".dialogs",
    "ThumbnailFilePicker": ".dialogs",
    "extract_video_frame_via_ffmpeg": ".dialogs",
    "run_duplicate_scan": ".dialogs",
    # .elements
    "MergeCanvasItem": ".elements",
    "OptionalField": ".elements",
    "ScrubPreviewPopup": ".elements",
    "merge_canvas_item": ".elements",
    "optional_field": ".elements",
    "scrub_preview_popup": ".elements",
    # .forms
    "FormSection": ".forms",
    "SectionedFormBuilder": ".forms",
    # .labels
    "ClickableLabel": ".labels",
    "DoubleClickableLabel": ".labels",
    "DraggableLabel": ".labels",
    "clickable_label": ".labels",
    "double_clickable_label": ".labels",
    "draggable_label": ".labels",
    "metadata_overlay": ".labels",
    # .views
    "MonitorDropView": ".views",
    "OpaqueViewport": ".views",
    "QueueItemView": ".views",
    "display": ".views",
    "monitor_drop_view": ".views",
    "opaque_viewport": ".views",
    "queue_item_view": ".views",
    # .virtual_gallery
    "VirtualDualGallery": ".virtual_gallery",
    "VirtualGallery": ".virtual_gallery",
    "VirtualGalleryDelegate": ".virtual_gallery",
    "VirtualGalleryModel": ".virtual_gallery",
    "VirtualGalleryView": ".virtual_gallery",
}

__all__ = [
    "CanvasBase",
    "DraggableMonitorContainer",
    "MarqueeScrollArea",
    "MergeCanvas",
    "canvas_base",
    "draggable_monitor_container",
    "marquee_scroll_area",
    "merge_canvas",
    "AddTagDialog",
    "AspAdvancedConfigDialog",
    "BatchStitchDialog",
    "DeduplicationPruningDialog",
    "DuplicateConfigDialog",
    "ExtractionCloseProgressDialog",
    "FrameSelectionDialog",
    "ManualSelectionDialog",
    "ProcessCloseProgressDialog",
    "PropertyComparisonDialog",
    "SafetensorsInspectorDialog",
    "ScrollVideoExportDialog",
    "TagReviewDialog",
    "TaskCloseProgressDialog",
    "ThumbnailFilePicker",
    "extract_video_frame_via_ffmpeg",
    "run_duplicate_scan",
    "MergeCanvasItem",
    "OptionalField",
    "ScrubPreviewPopup",
    "merge_canvas_item",
    "optional_field",
    "scrub_preview_popup",
    "ClickableLabel",
    "DoubleClickableLabel",
    "DraggableLabel",
    "clickable_label",
    "double_clickable_label",
    "draggable_label",
    "metadata_overlay",
    "MonitorDropView",
    "OpaqueViewport",
    "QueueItemView",
    "display",
    "monitor_drop_view",
    "opaque_viewport",
    "queue_item_view",
    "FormSection",
    "SectionedFormBuilder",
    "VirtualDualGallery",
    "VirtualGallery",
    "VirtualGalleryDelegate",
    "VirtualGalleryModel",
    "VirtualGalleryView",
]


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(_LAZY_EXPORTS[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
