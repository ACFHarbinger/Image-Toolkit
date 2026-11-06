"""Stitch tab applies an ASP result inside Hybrid Stitch (issue #1088)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from asp_gui.elements._hybrid_panel import _HybridPanelMixin
from asp_gui.tabs.stencil import HybridStitchPanel
from middleware.src.services.asp.handoff import build_hybrid_handoff
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QTabWidget, QWidget


def _fake_imread(_path, *_args, **_kwargs):
    return np.full((16, 16, 3), 40, np.uint8)


def _fake_resize(img, size, *_args, **_kwargs):
    width, height = int(size[0]), int(size[1])
    if getattr(img, "ndim", 0) == 2:
        return np.zeros((height, width), np.uint8)
    channels = img.shape[2] if getattr(img, "ndim", 0) == 3 else 3
    return np.zeros((height, width, channels), np.uint8)


def _fake_cvt(img, _code):
    return np.ascontiguousarray(img)


def _fake_warp(img, _matrix, size):
    return _fake_resize(img, size)


def _fake_add(img_a, _wa, _img_b, _wb, _gamma):
    return np.ascontiguousarray(img_a)


def _settle(*widgets: QWidget) -> None:
    """Run queued fit/show events while the widgets still exist."""
    for widget in widgets:
        widget.close()
    QApplication.processEvents()


@pytest.fixture
def cv2_images(monkeypatch):
    """gui/test mocks cv2. Give the panel real arrays for thumbs and warps."""
    monkeypatch.setattr(cv2, "imread", _fake_imread)
    monkeypatch.setattr(cv2, "resize", _fake_resize)
    monkeypatch.setattr(cv2, "cvtColor", _fake_cvt)
    monkeypatch.setattr(cv2, "warpPerspective", _fake_warp)
    monkeypatch.setattr(cv2, "addWeighted", _fake_add)


def _handoff(path_a: str = "frame_a.png", path_b: str = "frame_b.png"):
    return build_hybrid_handoff(
        image_paths=(path_a, path_b),
        affines=(
            [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
            [[1.0, 0.0, 0.0], [0.0, 1.0, 40.0]],
        ),
        output_path="panorama.png",
        identity="raw_asp",
        fallback_reason="dy_cv_gate",
    )


def test_hybrid_panel_seeds_alignment_and_clears_local_edits(q_app, cv2_images):
    del cv2_images
    panel = HybridStitchPanel()
    panel._corrections["stale"] = {"brightness": 3}
    panel._seam_masks[(0, 1)] = np.zeros((2, 2), dtype=np.uint8)
    handoff = _handoff()

    parsed = panel.apply_asp_handoff(handoff.to_payload())

    assert parsed.image_paths == ("frame_a.png", "frame_b.png")
    assert panel._seq_list.count() == 2
    assert [panel._seq_list.item(row).text() for row in range(2)] == [
        "frame_a.png",
        "frame_b.png",
    ]
    assert panel._sequence == ["frame_a.png", "frame_b.png"]
    assert panel._corrections == {}
    assert panel._seam_masks == {}
    homography = panel._homographies[(0, 1)]
    assert np.allclose(homography @ [3.0, 10.0, 1.0], [3.0, -30.0, 1.0])
    assert "1 homographies" in panel._render_panel._status.text()

    panel._load_current_pair()
    seeded = panel._cp_editor.get_homography()
    assert seeded is not None
    assert np.allclose(seeded, homography)
    _settle(panel)


def test_stitch_tab_handoff_switches_to_hybrid_and_rejects_a_bad_payload(q_app, cv2_images, monkeypatch):
    del cv2_images
    messages: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kwargs: None)

    class Host(QWidget, _HybridPanelMixin):
        def __init__(self) -> None:
            super().__init__()
            self._log: list[str] = []
            self._asp_hybrid_handoff = None
            self._btn_refine_hybrid = QPushButton("Refine in Hybrid Stitch")
            self._btn_refine_hybrid.setEnabled(False)
            self._hybrid_panel = HybridStitchPanel()
            self.hybrid_stitch_panel = self._hybrid_panel
            self._tab_widget = QTabWidget()
            self._tab_widget.addTab(QWidget(), "Stitch")
            self._tab_widget.addTab(self.hybrid_stitch_panel, "Hybrid Stitch")

        def _log_append(self, msg: str) -> None:
            self._log.append(msg)

    host = Host()
    handoff = _handoff()
    host._on_asp_hybrid_handoff(handoff.to_payload())

    assert host._btn_refine_hybrid.isEnabled()
    assert host._asp_hybrid_handoff == handoff
    assert any("handoff ready" in line for line in host._log)

    host._handoff_asp_to_hybrid()

    assert host._tab_widget.currentWidget() is host.hybrid_stitch_panel
    assert host._hybrid_panel._sequence == ["frame_a.png", "frame_b.png"]
    assert (0, 1) in host._hybrid_panel._homographies
    messages.extend(host._log)
    assert any("Seeded 1 adjacent alignment" in line for line in messages)
    assert any("dy_cv_gate" in line for line in messages)

    host._on_asp_hybrid_handoff({"kind": "not-a-handoff"})
    assert host._asp_hybrid_handoff is None
    assert host._btn_refine_hybrid.isEnabled() is False
    assert any("unavailable" in line for line in host._log)

    host._on_asp_hybrid_handoff(handoff)
    host._clear_asp_hybrid_handoff()
    assert host._asp_hybrid_handoff is None
    assert host._btn_refine_hybrid.isEnabled() is False
    _settle(host)
