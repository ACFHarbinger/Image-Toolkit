"""Full-window background canvas and glassmorphic layering engine (#440).

Provides root-window background image rendering with:
- Configurable opacity (0.10 - 1.0) and optional cached Gaussian blur (0 - 30px).
- Fit/scaling modes: cover, contain, center, tile.
- Global single-clock playlist slideshow rotation with configurable interval.
- Per-tab background image overrides.
- Translucent glassmorphism QSS styling for layered content cards and panels.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from pathlib import Path
from typing import Any, Callable, Sequence

from PySide6.QtCore import QObject, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

log = logging.getLogger(__name__)


@dataclass
class BackgroundConfig:
    """Configuration model for full-window background canvas and glassmorphic layering."""

    image_path: str = ""
    playlist_paths: list[str] = field(default_factory=list)
    playlist_interval_sec: int = 300
    opacity: float = 0.50
    blur_radius: int = 0
    fit_mode: str = "cover"  # "cover" | "contain" | "center" | "tile"
    glassmorphism_enabled: bool = True
    tab_overrides: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BackgroundConfig:
        if not data or not isinstance(data, dict):
            return cls()
        return cls(
            image_path=str(data.get("image_path", "")),
            playlist_paths=[str(p) for p in data.get("playlist_paths", []) if p],
            playlist_interval_sec=max(5, int(data.get("playlist_interval_sec", 300))),
            opacity=max(0.05, min(1.0, float(data.get("opacity", 0.50)))),
            blur_radius=max(0, min(30, int(data.get("blur_radius", 0)))),
            fit_mode=str(data.get("fit_mode", "cover")).lower()
            if str(data.get("fit_mode", "cover")).lower() in {"cover", "contain", "center", "tile"}
            else "cover",
            glassmorphism_enabled=bool(data.get("glassmorphism_enabled", True)),
            tab_overrides={str(k): str(v) for k, v in data.get("tab_overrides", {}).items()},
        )


def _apply_simple_box_blur(image: QImage, radius: int) -> QImage:
    """Lightweight pure-Qt multi-pass box blur proxy for Gaussian blur caching."""
    if radius <= 0:
        return image

    # Fast downscale/upscale approximation for high-performance backdrop blur
    scale_factor = max(1, radius // 2)
    small_w = max(1, image.width() // scale_factor)
    small_h = max(1, image.height() // scale_factor)

    scaled_down = image.scaled(
        small_w,
        small_h,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    scaled_up = scaled_down.scaled(
        image.width(),
        image.height(),
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    return scaled_up


class BackgroundCanvasController(QObject):
    """Manages active background pixmap rendering, scaling, caching, and playlist rotation."""

    background_changed = Signal()

    _instance: BackgroundCanvasController | None = None

    @classmethod
    def instance(cls) -> BackgroundCanvasController:
        if cls._instance is None:
            cls._instance = BackgroundCanvasController()
        return cls._instance

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = BackgroundConfig()
        self._current_playlist_idx: int = 0
        self._cached_source_path: str | None = None
        self._cached_source_pixmap: QPixmap | None = None
        self._cached_rendered_pixmap: QPixmap | None = None
        self._cached_rendered_size: tuple[int, int, str, int] | None = None

        self._playlist_timer = QTimer(self)
        self._playlist_timer.timeout.connect(self.advance_playlist)

    @property
    def config(self) -> BackgroundConfig:
        return self._config

    def set_config(self, config: BackgroundConfig) -> None:
        """Update background configuration and adjust playlist timer accordingly."""
        self._config = config
        self.invalidate_cache()

        if self._config.playlist_paths and len(self._config.playlist_paths) > 1:
            interval_ms = self._config.playlist_interval_sec * 1000
            if not self._playlist_timer.isActive() or self._playlist_timer.interval() != interval_ms:
                self._playlist_timer.start(interval_ms)
        else:
            self._playlist_timer.stop()

        self.background_changed.emit()

    def set_background_tokens(self, tokens: Any, active_theme_backgrounds: Sequence[Any] | None = None) -> None:
        """Convert and load theme schema BackgroundTokens into the background controller."""
        # Local import to avoid circular dependencies
        try:
            from gui.src.theming.schema import BackgroundTokens
            from gui.src.theming.storage import resolve_asset_path
        except ImportError:
            BackgroundTokens = None  # type: ignore
            resolve_asset_path = None  # type: ignore

        if BackgroundTokens is not None and isinstance(tokens, BackgroundTokens):
            image_paths: list[str] = []
            for ref in tokens.images:
                if resolve_asset_path is not None:
                    p = resolve_asset_path(ref)
                    if p is not None and p.exists():
                        image_paths.append(str(p))
                elif getattr(ref, "path", None):
                    image_paths.append(str(ref.path))

            tab_overrides: dict[str, str] = {}
            if active_theme_backgrounds:
                for bg in active_theme_backgrounds:
                    if getattr(bg, "scope", "global") != "global" and bg.images:
                        if resolve_asset_path is not None:
                            resolved = resolve_asset_path(bg.images[0])
                            if resolved and resolved.exists():
                                tab_overrides[str(bg.scope)] = str(resolved)
                        elif getattr(bg.images[0], "path", None):
                            tab_overrides[str(bg.scope)] = str(bg.images[0].path)

            primary_image = image_paths[0] if image_paths else ""
            self.set_config(
                BackgroundConfig(
                    image_path=primary_image,
                    playlist_paths=image_paths,
                    playlist_interval_sec=max(5, int(tokens.rotation_interval_sec or 300)),
                    opacity=float(tokens.opacity),
                    blur_radius=int(tokens.blur_px),
                    fit_mode=str(tokens.fit_mode),
                    glassmorphism_enabled=bool(primary_image),
                    tab_overrides=tab_overrides,
                )
            )


    def invalidate_cache(self) -> None:
        """Clear cached scaled/blurred pixmaps."""
        self._cached_source_path = None
        self._cached_source_pixmap = None
        self._cached_rendered_pixmap = None
        self._cached_rendered_size = None

    def advance_playlist(self) -> None:
        """Step to the next image in the background playlist."""
        if not self._config.playlist_paths:
            return
        self._current_playlist_idx = (self._current_playlist_idx + 1) % len(self._config.playlist_paths)
        self.invalidate_cache()
        self.background_changed.emit()

    def get_effective_image_path(self, active_tab: str | None = None) -> str:
        """Resolve effective image path considering tab overrides and playlists."""
        if active_tab and active_tab in self._config.tab_overrides:
            override = self._config.tab_overrides[active_tab].strip()
            if override and Path(override).exists():
                return override

        if self._config.playlist_paths:
            idx = self._current_playlist_idx % len(self._config.playlist_paths)
            candidate = self._config.playlist_paths[idx].strip()
            if candidate and Path(candidate).exists():
                return candidate

        return self._config.image_path.strip()

    def _get_source_pixmap(self, path: str) -> QPixmap | None:
        if not path or not Path(path).exists():
            return None
        if self._cached_source_path == path and self._cached_source_pixmap is not None:
            return self._cached_source_pixmap

        pixmap = QPixmap(path)
        if pixmap.isNull():
            return None

        self._cached_source_path = path
        self._cached_source_pixmap = pixmap
        return pixmap

    def render_background(
        self,
        painter: QPainter,
        target_rect: QRect,
        active_tab: str | None = None,
    ) -> bool:
        """Draws the scaled/blurred background image onto painter covering target_rect."""
        path = self.get_effective_image_path(active_tab)
        if not path:
            return False

        src_pixmap = self._get_source_pixmap(path)
        if src_pixmap is None or src_pixmap.isNull():
            return False

        tw, th = target_rect.width(), target_rect.height()
        if tw <= 0 or th <= 0:
            return False

        cache_key = (tw, th, self._config.fit_mode, self._config.blur_radius)
        if self._cached_rendered_size != cache_key or self._cached_rendered_pixmap is None:
            self._cached_rendered_pixmap = self._build_rendered_pixmap(src_pixmap, tw, th)
            self._cached_rendered_size = cache_key

        if self._cached_rendered_pixmap is None or self._cached_rendered_pixmap.isNull():
            return False

        painter.save()
        painter.setOpacity(self._config.opacity)
        if self._config.fit_mode == "tile":
            painter.drawTiledPixmap(target_rect, self._cached_rendered_pixmap)
        else:
            painter.drawPixmap(target_rect.topLeft(), self._cached_rendered_pixmap)
        painter.restore()
        return True

    def _build_rendered_pixmap(self, src: QPixmap, tw: int, th: int) -> QPixmap:
        mode = self._config.fit_mode
        if mode == "cover":
            scaled = src.scaled(
                QSize(tw, th),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Crop to exact dimensions
            x = max(0, (scaled.width() - tw) // 2)
            y = max(0, (scaled.height() - th) // 2)
            cropped = scaled.copy(x, y, tw, th)
        elif mode == "contain":
            scaled = src.scaled(
                QSize(tw, th),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            cropped = QPixmap(tw, th)
            cropped.fill(Qt.GlobalColor.transparent)
            p = QPainter(cropped)
            px = max(0, (tw - scaled.width()) // 2)
            py = max(0, (th - scaled.height()) // 2)
            p.drawPixmap(px, py, scaled)
            p.end()
        elif mode == "center":
            cropped = QPixmap(tw, th)
            cropped.fill(Qt.GlobalColor.transparent)
            p = QPainter(cropped)
            px = (tw - src.width()) // 2
            py = (th - src.height()) // 2
            p.drawPixmap(px, py, src)
            p.end()
        elif mode == "tile":
            cropped = src
        else:
            cropped = src.scaled(QSize(tw, th), Qt.AspectRatioMode.IgnoreAspectRatio)

        if self._config.blur_radius > 0:
            img = cropped.toImage()
            blurred_img = _apply_simple_box_blur(img, self._config.blur_radius)
            return QPixmap.fromImage(blurred_img)

        return cropped


def generate_glassmorphism_qss(config: BackgroundConfig, is_dark: bool = True) -> str:
    """Build QSS snippet for translucent cards, panes, and widgets when background canvas is active."""
    if not config.glassmorphism_enabled or not config.image_path:
        return ""

    if is_dark:
        card_bg = "rgba(18, 22, 30, 0.35)"
        card_hover = "rgba(25, 32, 44, 0.48)"
        pane_bg = "rgba(14, 18, 25, 0.28)"
        tab_bg = "rgba(24, 28, 38, 0.45)"
        tab_selected = "rgba(10, 14, 20, 0.70)"
        list_bg = "rgba(14, 18, 25, 0.38)"
        input_bg = "rgba(12, 15, 22, 0.55)"
        header_bg = "rgba(14, 18, 24, 0.50)"
        dialog_bg = "rgba(20, 24, 32, 0.94)"
        menu_bg = "rgba(18, 22, 30, 0.94)"
        border_color = "rgba(255, 255, 255, 0.12)"
        border_subtle = "rgba(255, 255, 255, 0.06)"
        text_color = "#ffffff"
        scrollbar_bg = "rgba(20, 24, 32, 0.30)"
    else:
        card_bg = "rgba(255, 255, 255, 0.45)"
        card_hover = "rgba(255, 255, 255, 0.60)"
        pane_bg = "rgba(255, 255, 255, 0.30)"
        tab_bg = "rgba(240, 242, 248, 0.45)"
        tab_selected = "rgba(255, 255, 255, 0.75)"
        list_bg = "rgba(255, 255, 255, 0.40)"
        input_bg = "rgba(255, 255, 255, 0.65)"
        header_bg = "rgba(255, 255, 255, 0.50)"
        dialog_bg = "rgba(255, 255, 255, 0.95)"
        menu_bg = "rgba(255, 255, 255, 0.95)"
        border_color = "rgba(0, 0, 0, 0.10)"
        border_subtle = "rgba(0, 0, 0, 0.05)"
        text_color = "#1e1e1e"
        scrollbar_bg = "rgba(0, 0, 0, 0.10)"

    return f"""
    /* --- Full App Window Background & Glassmorphic Layering (#440) --- */
    QWidget {{
        background-color: transparent;
    }}

    MainWindow, QMainWindow, QWidget#central_widget,
    QStackedWidget, QTabWidget, QScrollArea, QAbstractScrollArea,
    QSplitter {{
        background: transparent !important;
        background-color: transparent !important;
    }}

    /* Tab bar & Panes */
    QTabWidget::pane {{
        background: {pane_bg} !important;
        background-color: {pane_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px;
    }}
    QTabBar::tab {{
        background: {tab_bg} !important;
        background-color: {tab_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_subtle} !important;
        border-bottom: none;
        padding: 8px 16px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background: {tab_selected} !important;
        background-color: {tab_selected} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-bottom: none;
        font-weight: bold;
    }}
    QTabBar::tab:hover:!selected {{
        background: {card_hover} !important;
        background-color: {card_hover} !important;
    }}

    /* Translucent Panels & Group Boxes */
    QGroupBox {{
        background-color: {card_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px;
        margin-top: 22px;
        padding-top: 14px;
    }}
    QGroupBox:hover {{
        background-color: {card_hover} !important;
        border-color: {border_color} !important;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 3px 10px;
        border-radius: 4px;
    }}

    /* Card widgets and preview frames */
    QFrame#card, QFrame#preview_frame, QFrame#details_frame,
    QFrame#gallery_card, QWidget#gallery_card, QWidget[is_card="true"],
    QFrame.card {{
        background-color: {card_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px;
    }}

    /* Lists, Tables, Trees */
    QListWidget, QTreeWidget, QTableView, QTableWidget, QListView {{
        background-color: {list_bg} !important;
        border: 1px solid {border_color} !important;
        border-radius: 6px;
        color: {text_color};
    }}
    QHeaderView::section {{
        background-color: {header_bg} !important;
        color: {text_color};
        border: 1px solid {border_subtle};
        padding: 4px;
    }}

    /* Inputs */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit {{
        background-color: {input_bg} !important;
        color: {text_color} !important;
        border: 1px solid {border_color} !important;
        border-radius: 4px;
        padding: 6px;
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
    QTextEdit:focus, QPlainTextEdit:focus {{
        background-color: {card_hover} !important;
    }}

    /* Drop-downs and Menus */
    QComboBox QAbstractItemView {{
        background-color: {menu_bg} !important;
        color: {text_color};
        border: 1px solid {border_color};
    }}
    QMenu {{
        background-color: {menu_bg} !important;
        color: {text_color};
        border: 1px solid {border_color};
        border-radius: 6px;
    }}

    /* Dialogs */
    QDialog {{
        background-color: {dialog_bg};
    }}

    /* Scrollbars */
    QScrollBar:vertical, QScrollBar:horizontal {{
        background: {scrollbar_bg};
    }}

    /* Generic labels and buttons in glassmorphism mode */
    QLabel {{
        background-color: transparent !important;
    }}
    QCheckBox, QRadioButton {{
        background-color: transparent !important;
    }}
    QStatusBar {{
        background: transparent !important;
    }}
    QWidget#header_widget {{
        background-color: {header_bg} !important;
    }}
    """

