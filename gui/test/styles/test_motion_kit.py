"""Tests for the shared motion/easing kit (§2.42, #519)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from gui.src.styles.motion_kit import (
    BASE_MS,
    FAST_MS,
    SLOW_MS,
    _in_out_cubic,
    _in_out_quad,
    _out_cubic,
    _out_quad,
    animate_fade,
    animate_slide,
    animate_width,
    reduce_motion,
)


class TestDurationConstants:
    def test_fast_is_shortest(self):
        assert FAST_MS < BASE_MS < SLOW_MS

    def test_values_match_spec(self):
        assert FAST_MS == 120
        assert BASE_MS == 200
        assert SLOW_MS == 320


class TestEasingCurves:
    def test_out_cubic_type(self):
        from PySide6.QtCore import QEasingCurve

        curve = _out_cubic()
        assert curve.type() == QEasingCurve.Type.OutCubic

    def test_in_out_cubic_type(self):
        from PySide6.QtCore import QEasingCurve

        curve = _in_out_cubic()
        assert curve.type() == QEasingCurve.Type.InOutCubic

    def test_out_quad_type(self):
        from PySide6.QtCore import QEasingCurve

        curve = _out_quad()
        assert curve.type() == QEasingCurve.Type.OutQuad

    def test_in_out_quad_type(self):
        from PySide6.QtCore import QEasingCurve

        curve = _in_out_quad()
        assert curve.type() == QEasingCurve.Type.InOutQuad


class TestReduceMotion:
    def setup_method(self):
        reduce_motion.cache_clear()

    def teardown_method(self):
        reduce_motion.cache_clear()

    def test_env_var_true(self):
        with patch.dict(os.environ, {"IMAGE_TOOLKIT_REDUCE_MOTION": "1"}):
            reduce_motion.cache_clear()
            assert reduce_motion() is True

    def test_env_var_false(self):
        with patch.dict(os.environ, {"IMAGE_TOOLKIT_REDUCE_MOTION": "0"}, clear=False):
            os.environ.pop("REDUCE_MOTION", None)
            reduce_motion.cache_clear()
            assert reduce_motion() is False

    def test_env_var_true_text(self):
        with patch.dict(os.environ, {"IMAGE_TOOLKIT_REDUCE_MOTION": "true"}):
            reduce_motion.cache_clear()
            assert reduce_motion() is True

    def test_reduce_motion_env_var(self):
        with patch.dict(os.environ, {"REDUCE_MOTION": "yes"}, clear=False):
            os.environ.pop("IMAGE_TOOLKIT_REDUCE_MOTION", None)
            reduce_motion.cache_clear()
            assert reduce_motion() is True

    def test_default_is_false(self):
        env = {k: v for k, v in os.environ.items() if "REDUCE" not in k.upper() and "MOTION" not in k.upper()}
        with patch.dict(os.environ, env, clear=True):
            reduce_motion.cache_clear()
            assert reduce_motion() is False

    def test_result_is_cached(self):
        reduce_motion.cache_clear()
        result1 = reduce_motion()
        result2 = reduce_motion()
        assert result1 == result2
        assert reduce_motion.cache_info().hits >= 1


@pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="No display available",
)
class TestAnimateFade:
    def test_returns_animation_when_motion_enabled(self, q_app):
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        with patch("gui.src.styles.motion_kit.reduce_motion", return_value=False):
            anim = animate_fade(widget, from_opacity=0.0, to_opacity=1.0)
            assert anim is not None

    def test_returns_none_when_reduce_motion(self, q_app):
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        with patch("gui.src.styles.motion_kit.reduce_motion", return_value=True):
            anim = animate_fade(widget, from_opacity=0.0, to_opacity=1.0)
            assert anim is None


@pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="No display available",
)
class TestAnimateSlide:
    def test_returns_animation_when_motion_enabled(self, q_app):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        with patch("gui.src.styles.motion_kit.reduce_motion", return_value=False):
            anim = animate_slide(
                widget,
                prop=b"pos",
                start_value=QPoint(0, 0),
                end_value=QPoint(100, 100),
            )
            assert anim is not None

    def test_returns_none_when_reduce_motion(self, q_app):
        from PySide6.QtCore import QPoint
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        with patch("gui.src.styles.motion_kit.reduce_motion", return_value=True):
            anim = animate_slide(
                widget,
                prop=b"pos",
                start_value=QPoint(0, 0),
                end_value=QPoint(100, 100),
            )
            assert anim is None


@pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="No display available",
)
class TestAnimateWidth:
    def test_returns_animation_when_motion_enabled(self, q_app):
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        with patch("gui.src.styles.motion_kit.reduce_motion", return_value=False):
            anim = animate_width(widget, from_width=0, to_width=200)
            assert anim is not None

    def test_returns_none_when_reduce_motion(self, q_app):
        from PySide6.QtWidgets import QWidget

        widget = QWidget()
        with patch("gui.src.styles.motion_kit.reduce_motion", return_value=True):
            anim = animate_width(widget, from_width=0, to_width=200)
            assert anim is None
