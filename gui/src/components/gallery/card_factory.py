"""Shared gallery card construction and selection/preview highlight helper.

Widget galleries (single/two) build QWidget cards here; pagination stays
on each base. VirtualGallery paints cells in a delegate — it does not wrap
QWidget cards — but uses the same highlight colors/priority via
``highlight_border_spec``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gui.src.components.labels.clickable_label import ClickableLabel

GalleryCardVariant = Literal["single", "two"]

SELECTION_COLOR = "#5865f2"
IN_DB_COLOR = "#2ecc71"
PREVIEW_COLOR = "#f39c12"
VIDEO_COLOR = "#3498db"
DEFAULT_BORDER_COLOR = "#4f545c"
PREVIEW_WIDTH = 4

_PREVIEW_BORDER_QSS = f"border: {PREVIEW_WIDTH}px solid {PREVIEW_COLOR};"

CreateLabel = Callable[[str, int], QWidget]
UpdateStyle = Callable[[QWidget, bool], None]
ApplyPixmap = Callable[[QWidget, Optional[QPixmap], QLabel], None]


def highlight_border_spec(
    *,
    preview: bool = False,
    selected: bool = False,
    in_db: bool = False,
) -> tuple[Optional[str], int]:
    """Return ``(hex_color, pen_width)`` for a card's state border.

    Preview wins over selection, which wins over in-db. Used by the
    VirtualGallery delegate paint path and as the color source of truth
    for widget-gallery highlight QSS.
    """
    if preview:
        return PREVIEW_COLOR, PREVIEW_WIDTH
    if selected:
        return SELECTION_COLOR, 3
    if in_db:
        return IN_DB_COLOR, 3
    return None, 0


def apply_preview_highlight(
    card: Optional[QWidget],
    path: str,
    *,
    is_selected: bool,
    update_style: UpdateStyle,
) -> None:
    """Overlay the amber preview border on a widget card."""
    if not card or not path:
        return
    update_style(card, is_selected)
    if card.property("original_style") is None:
        card.setProperty("original_style", card.styleSheet())
    current = card.styleSheet().strip()
    sep = "" if not current or current.endswith(";") else ";"
    card.setStyleSheet(f"{current}{sep} {_PREVIEW_BORDER_QSS}")


def reset_preview_highlight(
    card: Optional[QWidget],
    path: str,
    *,
    is_selected: bool,
    update_style: UpdateStyle,
) -> None:
    """Restore a widget card after preview highlight, or re-apply selection."""
    if not card or not path:
        return
    orig = card.property("original_style")
    if orig is not None:
        card.setStyleSheet(orig)
        card.setProperty("original_style", None)
    else:
        update_style(card, is_selected)


def create_gallery_card(
    *,
    path: str,
    pixmap: Optional[QPixmap],
    thumb_size: int,
    selected: bool,
    variant: GalleryCardVariant,
    create_label: CreateLabel,
    update_style: UpdateStyle,
    approx_item_width: Optional[int] = None,
    failed: bool = False,
    is_video: bool = False,
    apply_pixmap: Optional[ApplyPixmap] = None,
) -> QWidget:
    """Build a single- or two-gallery card. Visuals stay variant-specific."""
    if variant == "single":
        return _create_single_card(
            path=path,
            pixmap=pixmap,
            thumb_size=thumb_size,
            selected=selected,
            create_label=create_label,
            update_style=update_style,
            approx_item_width=approx_item_width,
            failed=failed,
            is_video=is_video,
            apply_pixmap=apply_pixmap,
        )
    return _create_two_card(
        path=path,
        pixmap=pixmap,
        thumb_size=thumb_size,
        selected=selected,
        create_label=create_label,
        update_style=update_style,
        is_video=is_video,
    )


def _create_single_card(
    *,
    path: str,
    pixmap: Optional[QPixmap],
    thumb_size: int,
    selected: bool,
    create_label: CreateLabel,
    update_style: UpdateStyle,
    approx_item_width: Optional[int],
    failed: bool,
    is_video: bool,
    apply_pixmap: Optional[ApplyPixmap],
) -> QWidget:
    container = QWidget()
    width = approx_item_width if approx_item_width is not None else thumb_size
    container.setFixedSize(width, width)

    layout = QVBoxLayout(container)
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    label = create_label(path, thumb_size)
    if not isinstance(label, QLabel):
        raise TypeError("single-gallery create_label must return a QLabel")

    has_pixmap = pixmap is not None and not pixmap.isNull()
    if has_pixmap or failed:
        if apply_pixmap is not None:
            apply_pixmap(container, pixmap, label)
        elif has_pixmap:
            label.setPixmap(_scale_thumb(pixmap, thumb_size))
            label.setText("")
    else:
        label.clear()
        label.setText("Loading...")
        if is_video:
            label.setStyleSheet(
                f"border: 2px solid {VIDEO_COLOR}; color: {VIDEO_COLOR}; "
                "font-weight: bold; background-color: rgba(20, 24, 32, 0.35);"
            )
        else:
            label.setStyleSheet(
                "border: 1px dashed rgba(255, 255, 255, 0.20); color: #888; "
                "font-size: 10px; background-color: rgba(20, 24, 32, 0.35);"
            )

    layout.addWidget(label)
    container.setProperty("gallery_path", path)
    update_style(container, selected)
    return container


def _create_two_card(
    *,
    path: str,
    pixmap: Optional[QPixmap],
    thumb_size: int,
    selected: bool,
    create_label: CreateLabel,
    update_style: UpdateStyle,
    is_video: bool,
) -> QWidget:
    card_wrapper = create_label(path, thumb_size)

    if isinstance(card_wrapper, ClickableLabel):
        card_layout = QVBoxLayout(card_wrapper)
        card_layout.setContentsMargins(0, 0, 0, 0)

        img_label = QLabel()
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setFixedSize(thumb_size, thumb_size)

        card_wrapper.set_image_label(img_label)
        card_layout.addWidget(img_label)
        card_wrapper.setLayout(card_layout)
        target_label = img_label
    else:
        target_label = card_wrapper

    if hasattr(card_wrapper, "set_selected_style"):
        card_wrapper.style_callback = update_style

    if pixmap is not None and not pixmap.isNull():
        target_label.setPixmap(_scale_thumb(pixmap, thumb_size))
    else:
        target_label.setText("Loading...")
        if is_video:
            target_label.setStyleSheet(
                f"color: {VIDEO_COLOR}; border: 2px dashed {VIDEO_COLOR};"
            )
        else:
            target_label.setStyleSheet("color: #999; border: 1px dashed #666;")

    card_wrapper.setProperty("gallery_path", path)
    update_style(target_label, selected)
    return card_wrapper


def _scale_thumb(pixmap: QPixmap, thumb_size: int) -> QPixmap:
    if pixmap.width() > thumb_size or pixmap.height() > thumb_size:
        return pixmap.scaled(
            thumb_size,
            thumb_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    return pixmap


__all__ = [
    "DEFAULT_BORDER_COLOR",
    "IN_DB_COLOR",
    "PREVIEW_COLOR",
    "PREVIEW_WIDTH",
    "SELECTION_COLOR",
    "VIDEO_COLOR",
    "apply_preview_highlight",
    "create_gallery_card",
    "highlight_border_spec",
    "reset_preview_highlight",
]
