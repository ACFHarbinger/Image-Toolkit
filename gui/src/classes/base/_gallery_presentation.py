"""Presentation mode and thumbnail overlay management for gallery base (§2.40 / #508).

Extracted from :mod:`gallery_base` (§5.17 Option B, #629) to keep
``AbstractGalleryBase`` under the 500-code-line gate. Provides presentation
modes (Uniform Grid, Masonry, Compact List), card geometry adaptation, badge
strips, and empty-space viewport context menus.
"""

from __future__ import annotations

from dataclasses import fields as _dc_fields
from typing import Optional

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QScrollArea,
    QWidget,
)

from gui.src.components.gallery.presentation_mode import (
    GalleryOverlayConfig,
    GalleryPresentationMode,
)
from gui.src.constants.ui import RATING_COLORS
from gui.src.theming.theme_api import color, qss


class _GalleryPresentationMixin:
    """Presentation modes and overlay badges for ``AbstractGalleryBase``.

    Manages:
    * Active presentation mode (Uniform Grid, Masonry, Compact List).
    * Mode-aware card placement and per-mode card geometry.
    * Thumbnail overlay badges (ratings, resolution, format, stars, tags).
    * Viewport right-click presentation context menu.
    """

    _OVERLAY_FIELDS = tuple(f.name for f in _dc_fields(GalleryOverlayConfig))
    _COMPACT_THUMB = 48

    def _init_presentation_mode(self) -> None:
        """Initialize presentation mode state and debounce timer."""
        self._presentation_mode: GalleryPresentationMode = (
            GalleryPresentationMode.UNIFORM_GRID
        )
        self._overlay_config: GalleryOverlayConfig = GalleryOverlayConfig()
        self._card_overlay_metadata: dict[str, dict] = {}
        self._presentation_menu_viewports: set[QWidget] = set()
        self._masonry_state: dict[QGridLayout, dict] = {}
        self._masonry_reflow_timer = QTimer(self)  # type: ignore[arg-type]
        self._masonry_reflow_timer.setSingleShot(True)
        self._masonry_reflow_timer.setInterval(120)
        self._masonry_reflow_timer.timeout.connect(self._on_layout_change)  # type: ignore[attr-defined]
        self._load_presentation_prefs()

    # ---------------------------------------------------------------------------
    # Presentation mode property & setter
    # ---------------------------------------------------------------------------

    @property
    def presentation_mode(self) -> GalleryPresentationMode:
        return self._presentation_mode

    @presentation_mode.setter
    def presentation_mode(self, mode: GalleryPresentationMode) -> None:
        self.set_presentation_mode(mode)

    def set_presentation_mode(self, mode: GalleryPresentationMode) -> None:
        mode = GalleryPresentationMode(mode)
        if mode == self._presentation_mode:
            return
        self._presentation_mode = mode
        self._save_presentation_prefs()
        for card in self._iter_gallery_cards():
            if mode == GalleryPresentationMode.COMPACT_LIST:
                self._apply_compact_geometry(card)
            elif mode == GalleryPresentationMode.MASONRY:
                self._apply_masonry_geometry(card)
            else:
                self._restore_uniform_geometry(card)
        self._masonry_state.clear()
        self._on_layout_change()  # type: ignore[attr-defined]
        self._reflow_presentation_layouts()

    def _reflow_presentation_layouts(self) -> None:
        """Reflow existing cards when a mode changes without a resize."""
        for layout_attr, columns_attr in (
            ("gallery_layout", "_current_cols"),
            ("found_gallery_layout", "_current_found_cols"),
            ("selected_gallery_layout", "_current_selected_cols"),
        ):
            layout = getattr(self, layout_attr, None)
            if layout is not None:
                self.common_reflow_layout(  # type: ignore[attr-defined]
                    layout, max(1, getattr(self, columns_attr, 1))
                )

    # ---------------------------------------------------------------------------
    # Overlay configuration & metadata
    # ---------------------------------------------------------------------------

    @property
    def overlay_config(self) -> GalleryOverlayConfig:
        return self._overlay_config

    def set_overlay_config(self, config: GalleryOverlayConfig) -> None:
        self._overlay_config = config
        self._save_presentation_prefs()
        for card in self._iter_gallery_cards():
            path = (
                card.property("gallery_path")
                or getattr(card, "path", "")
                or getattr(card, "file_path", "")
                or ""
            )
            self._apply_card_overlays(card, path)

    def set_overlay_metadata(self, path: str, **fields) -> None:
        """Record overlay metadata for one card."""
        self._card_overlay_metadata[path] = dict(fields)
        card = self._card_for_path(path)
        if card is not None:
            self._apply_card_overlays(card, path)

    def clear_overlay_metadata(self) -> None:
        self._card_overlay_metadata.clear()
        for card in self._iter_gallery_cards():
            self._remove_badge_strip(card)

    def _card_for_path(self, path: str) -> Optional[QWidget]:
        for attr in ("path_to_card_widget", "path_to_label_map", "selected_card_map"):
            mapping = getattr(self, attr, None)
            if mapping and path in mapping:
                try:
                    return mapping[path]
                except RuntimeError:
                    return None
        return None

    def _iter_gallery_cards(self):
        seen: set = set()
        for attr in ("path_to_card_widget", "path_to_label_map", "selected_card_map"):
            mapping = getattr(self, attr, None)
            if not mapping:
                continue
            for card in list(mapping.values()):
                try:
                    if id(card) in seen:
                        continue
                    seen.add(id(card))
                    yield card
                except RuntimeError:
                    continue

    # ---------------------------------------------------------------------------
    # Settings persistence
    # ---------------------------------------------------------------------------

    def _load_presentation_prefs(self) -> None:
        try:
            from gui.src.windows.settings.app_settings import AppSettings

            cn = self.__class__.__name__
            mode = AppSettings.session(cn, "presentation_mode", "") or ""
            if mode:
                self._presentation_mode = GalleryPresentationMode(mode)
            stored = AppSettings.session(cn, "gallery_overlay_config", {}) or {}
            if isinstance(stored, dict):
                self._overlay_config = GalleryOverlayConfig(
                    **{k: bool(v) for k, v in stored.items() if k in self._OVERLAY_FIELDS}
                )
        except Exception:
            self._presentation_mode = GalleryPresentationMode.UNIFORM_GRID
            self._overlay_config = GalleryOverlayConfig()

    def _save_presentation_prefs(self) -> None:
        try:
            from gui.src.windows.settings.app_settings import AppSettings

            cn = self.__class__.__name__
            AppSettings.set_session(cn, "presentation_mode", self._presentation_mode.value)
            AppSettings.set_session(
                cn,
                "gallery_overlay_config",
                {f: bool(getattr(self._overlay_config, f)) for f in self._OVERLAY_FIELDS},
            )
        except Exception:
            pass

    # ---------------------------------------------------------------------------
    # Overlay badges
    # ---------------------------------------------------------------------------

    def _apply_card_overlays(self, card: QWidget, path: str) -> None:
        """(Re)build the badge strip on one card from recorded metadata."""
        self._remove_badge_strip(card)
        if not path:
            return
        cfg = self._overlay_config
        md = self._card_overlay_metadata.get(path) or {}
        chips: list[tuple[str, str]] = []
        if cfg.show_rating and md.get("rating"):
            letter = str(md["rating"]).upper()[:1]
            chips.append(
                (letter, RATING_COLORS.get(str(md["rating"]).lower()[:1], color("accent")))
            )
        if cfg.show_resolution:
            res = md.get("resolution")
            if isinstance(res, (tuple, list)) and len(res) == 2:
                chips.append((f"{res[0]}×{res[1]}", ""))
        if cfg.show_format and md.get("file_format"):
            chips.append((str(md["file_format"]).upper(), ""))
        if cfg.show_star_rating and md.get("star_rating"):
            chips.append((f"★ {float(md['star_rating']):.1f}", ""))
        if cfg.show_tag_count and md.get("tag_count"):
            chips.append((f"🏷 {md['tag_count']}", ""))
        if not chips:
            return
        strip = QWidget(card)
        strip.setObjectName("gallery_card_badge_strip")
        row = QHBoxLayout(strip)
        row.setContentsMargins(2, 1, 2, 1)
        row.setSpacing(3)
        for text, bg in chips:
            badge = QLabel(text, strip)
            badge.setObjectName("gallery_card_badge")
            if bg:
                badge.setStyleSheet(
                    qss("gallery_card_badge", BADGE_BG=bg, BADGE_TEXT=color("text"))
                )
            else:
                badge.setStyleSheet(qss("gallery_card_badge"))
            row.addWidget(badge)
        row.addStretch(1)
        layout = card.layout()
        if layout is not None:
            layout.addWidget(strip)

    @staticmethod
    def _remove_badge_strip(card: QWidget) -> None:
        try:
            strip = card.findChild(QWidget, "gallery_card_badge_strip")
        except RuntimeError:
            return
        if strip is not None:
            strip.setParent(None)
            strip.deleteLater()

    # ---------------------------------------------------------------------------
    # Per-mode card geometry
    # ---------------------------------------------------------------------------

    @staticmethod
    def _card_image_label(card: QWidget) -> Optional[QLabel]:
        if isinstance(card, QLabel):
            return card
        try:
            for label in card.findChildren(QLabel):
                if label.objectName() in ("thumb_filename_lbl", "gallery_card_badge"):
                    continue
                return label
        except RuntimeError:
            return None
        return None

    def _remember_uniform_geometry(self, card: QWidget, label: QLabel) -> None:
        if card.property("gallery_base_orig_geometry") is None:
            card_h = card.minimumHeight()
            if card_h <= 0:
                card_h = card.sizeHint().height()
            card.setProperty(
                "gallery_base_orig_geometry",
                (max(1, card_h), label.width(), label.height()),
            )

    def _mutate_card_geometry(
        self,
        card: QWidget,
        *,
        thumb: Optional[int] = None,
        label_height: Optional[int] = None,
    ) -> None:
        label = self._card_image_label(card)
        if label is None:
            return
        self._remember_uniform_geometry(card, label)
        w = thumb if thumb is not None else label.width()
        h = (
            label_height
            if label_height is not None
            else (thumb if thumb is not None else label.height())
        )
        label.setFixedSize(w, h)
        orig_card_h, orig_label_w, orig_label_h = card.property(
            "gallery_base_orig_geometry"
        )
        card.setMinimumHeight(0)
        card.setMaximumHeight(orig_card_h - orig_label_h + h)

    def _apply_compact_geometry(self, card: QWidget) -> None:
        self._mutate_card_geometry(card, thumb=self._COMPACT_THUMB)

    def _apply_masonry_geometry(self, card: QWidget) -> None:
        label = self._card_image_label(card)
        if label is None or not label.width():
            return
        pm = label.pixmap()
        if pm is None or pm.isNull() or pm.width() <= 0 or pm.height() <= 0:
            return
        thumb = self.thumbnail_size  # type: ignore[attr-defined]
        lo, hi = max(40, thumb // 2), thumb * 2
        target = int(label.width() * pm.height() / pm.width())
        self._mutate_card_geometry(card, label_height=int(min(max(target, lo), hi)))

    def _restore_uniform_geometry(self, card: QWidget) -> None:
        orig = card.property("gallery_base_orig_geometry")
        label = self._card_image_label(card)
        if orig is not None and label is not None:
            orig_card_h, orig_label_w, orig_label_h = orig
            label.setFixedSize(orig_label_w, orig_label_h)
            card.setMinimumHeight(orig_card_h)
            card.setMaximumHeight(orig_card_h)
        card.setProperty("gallery_base_orig_geometry", None)

    def notify_card_pixmap_loaded(self, widget: QWidget, pixmap) -> None:
        """Hook for subclass update_card_pixmap to keep masonry card heights in sync."""
        if self._presentation_mode != GalleryPresentationMode.MASONRY:
            return
        if (
            pixmap is None
            or pixmap.isNull()
            or pixmap.width() <= 0
            or pixmap.height() <= 0
        ):
            return
        label = self._card_image_label(widget)
        if label is None or not label.width():
            return
        thumb = self.thumbnail_size  # type: ignore[attr-defined]
        lo, hi = max(40, thumb // 2), thumb * 2
        target = int(label.width() * pixmap.height() / pixmap.width())
        self._mutate_card_geometry(widget, label_height=int(min(max(target, lo), hi)))
        self._masonry_reflow_timer.start()

    # ---------------------------------------------------------------------------
    # Card placement & masonry packing
    # ---------------------------------------------------------------------------

    @staticmethod
    def _card_height_hint(widget: QWidget) -> int:
        h = widget.minimumHeight()
        if h <= 0:
            h = widget.sizeHint().height()
        return max(1, h)

    def common_place_card(
        self, layout: Optional[QGridLayout], card: QWidget, index: int, columns: int
    ) -> None:
        """Place one freshly-created card according to the active presentation mode."""
        if not layout:
            return
        self._ensure_presentation_menu(layout)
        mode = self._presentation_mode
        if mode == GalleryPresentationMode.MASONRY:
            state = self._masonry_state.setdefault(
                layout, {"heights": [0] * max(1, columns), "next_row": 0}
            )
            if len(state["heights"]) != max(1, columns):
                state["heights"] = [0] * max(1, columns)
                state["next_row"] = layout.count()
            heights = state["heights"]
            col = heights.index(min(heights))
            row = state["next_row"]
            layout.addWidget(
                card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            heights[col] += self._card_height_hint(card)
            state["next_row"] = row + 1
        elif mode == GalleryPresentationMode.COMPACT_LIST:
            layout.addWidget(
                card, index, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
        else:
            layout.addWidget(
                card,
                index // columns,
                index % columns,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
            )

    def _reflow_masonry(self, layout: QGridLayout, items: list, columns: int) -> None:
        columns = max(1, columns)
        heights = [0] * columns
        for widget in items:
            col = heights.index(min(heights))
            row = layout.count()
            layout.addWidget(
                widget, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            heights[col] += self._card_height_hint(widget)
        self._masonry_state[layout] = {"heights": heights, "next_row": layout.count()}

    # ---------------------------------------------------------------------------
    # Presentation context menu
    # ---------------------------------------------------------------------------

    def _ensure_presentation_menu(self, layout: QGridLayout) -> None:
        """Install empty-space presentation menu on layout's owning scroll area."""
        content = layout.parentWidget()
        ancestor = content.parentWidget() if content is not None else None
        scroll = None
        while ancestor is not None:
            if isinstance(ancestor, QScrollArea):
                scroll = ancestor
                break
            ancestor = ancestor.parentWidget()
        if scroll is None:
            return
        viewport = scroll.viewport()
        if viewport in self._presentation_menu_viewports:
            return
        viewport.installEventFilter(self)  # type: ignore[arg-type]
        self._presentation_menu_viewports.add(viewport)

    def eventFilter(self, obj, event) -> bool:  # noqa: C901
        if (
            obj in self._presentation_menu_viewports
            and event.type() == QEvent.Type.ContextMenu
        ):
            child = obj.childAt(event.pos())
            ancestor = child
            while ancestor is not None and ancestor is not obj:
                if ancestor.property("gallery_path"):
                    return False
                ancestor = ancestor.parentWidget()
            self._build_presentation_menu().exec(obj.mapToGlobal(event.pos()))
            return True
        return False

    def _build_presentation_menu(self) -> QMenu:
        """Build mode/overlay menu matching VirtualGalleryView surface."""
        menu = QMenu(self)  # type: ignore[arg-type]

        mode_menu = menu.addMenu("Presentation Mode")
        mode_group = QActionGroup(mode_menu)
        mode_group.setExclusive(True)
        for mode, label in (
            (GalleryPresentationMode.UNIFORM_GRID, "Uniform Grid"),
            (GalleryPresentationMode.MASONRY, "Masonry"),
            (GalleryPresentationMode.COMPACT_LIST, "Compact List"),
        ):
            action = QAction(label, mode_menu, checkable=True)
            action.setChecked(mode == self._presentation_mode)
            action.triggered.connect(
                lambda _checked=False, m=mode: self.set_presentation_mode(m)
            )
            mode_group.addAction(action)
            mode_menu.addAction(action)

        overlay_menu = menu.addMenu("Thumbnail Overlays")
        cfg = self._overlay_config
        for attr, label in (
            ("show_rating", "Rating Badge"),
            ("show_resolution", "Resolution"),
            ("show_format", "Format"),
            ("show_star_rating", "Star Rating"),
            ("show_tag_count", "Tag Count"),
        ):
            action = QAction(label, overlay_menu, checkable=True)
            action.setChecked(bool(getattr(cfg, attr)))
            action.toggled.connect(
                lambda checked, a=attr, c=cfg: (
                    setattr(c, a, checked),
                    self.set_overlay_config(c),
                )
            )
            overlay_menu.addAction(action)
        return menu


__all__ = ["_GalleryPresentationMixin"]
