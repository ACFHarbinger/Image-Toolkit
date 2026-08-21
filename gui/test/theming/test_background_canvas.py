"""Unit tests for full-window background canvas and glassmorphic layering (#440)."""

from __future__ import annotations

from pathlib import Path
import tempfile
import pytest

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from gui.src.styles.background_canvas import (
    BackgroundCanvasController,
    BackgroundConfig,
    _apply_simple_box_blur,
    generate_glassmorphism_qss,
)
from gui.src.theming.schema import BackgroundAssetRef, BackgroundTokens

pytestmark = pytest.mark.gui


@pytest.fixture
def sample_bg_image(tmp_path: Path) -> Path:
    img_path = tmp_path / "test_bg.png"
    img = QImage(200, 200, QImage.Format.Format_RGB32)
    img.fill(QColor(100, 150, 200))
    img.save(str(img_path))
    return img_path


@pytest.fixture
def sample_bg_playlist(tmp_path: Path) -> list[Path]:
    paths = []
    for i in range(3):
        p = tmp_path / f"test_bg_{i}.png"
        img = QImage(100, 100, QImage.Format.Format_RGB32)
        img.fill(QColor(50 * (i + 1), 70 * (i + 1), 90))
        img.save(str(p))
        paths.append(p)
    return paths


class TestBackgroundConfig:
    def test_default_config(self):
        cfg = BackgroundConfig()
        assert cfg.image_path == ""
        assert cfg.opacity == 0.50
        assert cfg.fit_mode == "cover"
        assert cfg.blur_radius == 0
        assert cfg.playlist_paths == []

    def test_from_dict_and_to_dict_roundtrip(self):
        data = {
            "image_path": "/tmp/wallpaper.png",
            "playlist_paths": ["/tmp/1.png", "/tmp/2.png"],
            "playlist_interval_sec": 60,
            "opacity": 0.75,
            "blur_radius": 12,
            "fit_mode": "contain",
            "glassmorphism_enabled": True,
            "tab_overrides": {"GalleryTab": "/tmp/tab.png"},
        }
        cfg = BackgroundConfig.from_dict(data)
        assert cfg.image_path == "/tmp/wallpaper.png"
        assert cfg.playlist_interval_sec == 60
        assert cfg.opacity == 0.75
        assert cfg.blur_radius == 12
        assert cfg.fit_mode == "contain"
        assert cfg.glassmorphism_enabled is True
        assert cfg.tab_overrides == {"GalleryTab": "/tmp/tab.png"}

        exported = cfg.to_dict()
        assert exported == data


class TestBackgroundCanvasController:
    def test_controller_singleton(self, q_app):
        c1 = BackgroundCanvasController.instance()
        c2 = BackgroundCanvasController.instance()
        assert c1 is c2

    def test_render_background_with_cover_mode(self, q_app, sample_bg_image: Path):
        controller = BackgroundCanvasController()
        controller.set_config(
            BackgroundConfig(
                image_path=str(sample_bg_image),
                opacity=0.8,
                fit_mode="cover",
                blur_radius=0,
            )
        )

        target_surface = QPixmap(400, 300)
        target_surface.fill(Qt.GlobalColor.black)
        painter = QPainter(target_surface)
        rendered = controller.render_background(painter, QRect(0, 0, 400, 300))
        painter.end()

        assert rendered is True

    def test_render_background_with_tab_override(self, q_app, sample_bg_image: Path, tmp_path: Path):
        override_img = tmp_path / "override.png"
        img = QImage(50, 50, QImage.Format.Format_RGB32)
        img.fill(QColor(255, 0, 0))
        img.save(str(override_img))

        controller = BackgroundCanvasController()
        controller.set_config(
            BackgroundConfig(
                image_path=str(sample_bg_image),
                tab_overrides={"StitchTab": str(override_img)},
            )
        )

        assert controller.get_effective_image_path("StitchTab") == str(override_img)
        assert controller.get_effective_image_path("OtherTab") == str(sample_bg_image)

    def test_playlist_advancement(self, q_app, sample_bg_playlist: list[Path]):
        controller = BackgroundCanvasController()
        controller.set_config(
            BackgroundConfig(
                playlist_paths=[str(p) for p in sample_bg_playlist],
                playlist_interval_sec=10,
            )
        )

        assert controller.get_effective_image_path() == str(sample_bg_playlist[0])
        controller.advance_playlist()
        assert controller.get_effective_image_path() == str(sample_bg_playlist[1])
        controller.advance_playlist()
        assert controller.get_effective_image_path() == str(sample_bg_playlist[2])
        controller.advance_playlist()
        assert controller.get_effective_image_path() == str(sample_bg_playlist[0])

    def test_set_background_tokens_integration(self, q_app, sample_bg_image: Path):
        controller = BackgroundCanvasController()
        ref = BackgroundAssetRef(kind="linked", path=str(sample_bg_image))
        tokens = BackgroundTokens(
            images=(ref,),
            opacity=0.65,
            blur_px=8,
            fit_mode="contain",
            rotation_interval_sec=300,
        )

        controller.set_background_tokens(tokens)

        assert controller.config.image_path == str(sample_bg_image)
        assert controller.config.opacity == 0.65
        assert controller.config.blur_radius == 8
        assert controller.config.fit_mode == "contain"
        assert controller.config.glassmorphism_enabled is True


class TestGlassmorphismQSS:
    def test_glassmorphism_disabled_returns_empty(self):
        cfg = BackgroundConfig(glassmorphism_enabled=False)
        assert generate_glassmorphism_qss(cfg, is_dark=True) == ""

    def test_glassmorphism_dark_mode_qss(self):
        cfg = BackgroundConfig(image_path="/tmp/bg.png", glassmorphism_enabled=True)
        qss = generate_glassmorphism_qss(cfg, is_dark=True)
        assert "QMainWindow" in qss
        assert "QTabWidget::pane" in qss
        assert "QGroupBox" in qss
        assert "rgba(" in qss

    def test_glassmorphism_light_mode_qss(self):
        cfg = BackgroundConfig(image_path="/tmp/bg.png", glassmorphism_enabled=True)
        qss = generate_glassmorphism_qss(cfg, is_dark=False)
        assert "rgba(255, 255, 255" in qss


class TestBoxBlurProxy:
    def test_blur_returns_same_size(self):
        img = QImage(120, 80, QImage.Format.Format_RGB32)
        img.fill(QColor(200, 100, 50))
        blurred = _apply_simple_box_blur(img, radius=10)
        assert blurred.size() == img.size()
