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
from gui.src.constants.gallery import GALLERY_PREVIEW_COLOR
from gui.src.theming.theme_api import color, qss

GalleryCardVariant = Literal["single", "two"]

# State colors come from theme tokens so the widget galleries and the
# virtual-gallery paint path cannot drift (#571 reconciled with #585).
SELECTION_COLOR = color("accent")
IN_DB_COLOR = color("success")
PREVIEW_COLOR = GALLERY_PREVIEW_COLOR
VIDEO_COLOR = color("accent")
DEFAULT_BORDER_COLOR = color("border")
PREVIEW_WIDTH = 4

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
    if not card.property("preview_highlighted"):
        card.setProperty("preview_highlighted", True)
        current = card.styleSheet().strip()
        card.setStyleSheet(qss("gallery_card_preview_overlay", BASE_STYLE=current))


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
    if card.property("preview_highlighted"):
        card.setProperty("preview_highlighted", False)
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
            label.setStyleSheet(qss("gallery_card_video_loading"))
        else:
            label.setStyleSheet(qss("gallery_card_loading_image"))

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
            target_label.setStyleSheet(qss("gallery_card_video_loading_dashed"))
        else:
            target_label.setStyleSheet(qss("gallery_card_no_thumbnail"))

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
