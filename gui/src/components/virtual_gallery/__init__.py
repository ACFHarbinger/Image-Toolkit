"""Virtualized (QListView + QAbstractItemModel) gallery — GUI/UX §2.1 Option A.

Prototype of the Option A rewrite described in `docs/moon/roadmaps/gui_ux.md`
§2.1: replace the bounded-page QLabel-grid card surface with a model/view
gallery where Qt's viewport culling keeps the widget/paint cost constant
regardless of item count. Additive — the existing QLabel-gallery base classes
are untouched until a tab migrates to this widget.
"""

from .delegate import VirtualGalleryDelegate as VirtualGalleryDelegate
from .dual_widget import VirtualDualGallery as VirtualDualGallery
from .virtual_gallery_model import VirtualGalleryModel as VirtualGalleryModel
from .virtual_gallery_view import VirtualGalleryView as VirtualGalleryView
from .widget import VirtualGallery as VirtualGallery

__all__ = [
    "VirtualGalleryModel",
    "VirtualGalleryView",
    "VirtualGallery",
    "VirtualDualGallery",
    "VirtualGalleryDelegate",
]
