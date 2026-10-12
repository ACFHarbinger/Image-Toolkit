"""What Changed overlay + Review compare-canvas host (#754)."""
from unittest.mock import MagicMock

import pytest
from backend.src.core.guidance_trajectory import (
    STRUCTURAL_HINT,
    AppliedChange,
    GuidanceTrajectory,
    TrajectoryStep,
    append_step,
    record_verdict,
)
from gui.src.components.guidance.what_changed_overlay import WhatChangedOverlay
from gui.src.windows.image_compare_window import ImageCompareWindow
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

pytestmark = pytest.mark.gui


def _traj(n=1, verdicts=(), variant="v1"):
    traj = GuidanceTrajectory(root_prompt_id="p0")
    for i in range(1, n + 1):
        step = TrajectoryStep(
            parent_prompt_id="p0" if i == 1 else f"v{i - 1}",
            variant_prompt_id=variant if i == n else f"v{i}",
            feedback="text artifacts" if i == 1 else "",
            expected="reduced oversaturation and text artifacts",
            applied=(
                AppliedChange("3", "cfg", 8.5, 6.0, "reduced oversaturation and text artifacts"),
            ),
        )
        traj = append_step(traj, step)
    for i, verdict in enumerate(verdicts, start=1):
        traj = record_verdict(traj, verdict, variant_prompt_id=f"v{i}")
    return traj


def _png(tmp_path, name="a.png"):
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage

    img = QImage(8, 6, QImage.Format.Format_RGB888)
    img.fill(QColor(16, 32, 64))
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    assert img.save(buf, "PNG")
    path = tmp_path / name
    path.write_bytes(bytes(buf.data()))
    return path


def test_overlay_lists_changes_and_emits_verdict(q_app):
    overlay = WhatChangedOverlay()
    try:
        overlay.set_trajectory(_traj())
        overlay.set_voting_enabled(True)
        assert overlay.isVisible()
        assert "cfg: 8.5 → 6.0 (node #3)" in overlay.findChild(QLabel, "dl_what_changed_changes").text()
        assert "Expected:" in overlay.findChild(QLabel, "dl_what_changed_expected").text()
        assert "p0" in overlay.findChild(QLabel, "dl_what_changed_baseline").text()
        assert "v1" in overlay.findChild(QLabel, "dl_what_changed_variant").text()
        seen = []
        overlay.verdict_chosen.connect(seen.append)
        overlay.findChild(QPushButton, "dl_what_changed_verdict_better").click()
        assert seen == ["better"]
        assert overlay.trajectory().latest.verdict == "better"
    finally:
        overlay.deleteLater()


def test_overlay_shows_structural_hint_after_three_unresolved(q_app):
    overlay = WhatChangedOverlay()
    try:
        overlay.set_trajectory(_traj(n=3, verdicts=("same", "worse", "unsure"), variant="v3"))
        hint = overlay.findChild(QLabel, "dl_what_changed_hint")
        assert hint.isVisible()
        assert STRUCTURAL_HINT in hint.text()
    finally:
        overlay.deleteLater()


def test_overlay_hidden_without_trajectory(q_app):
    overlay = WhatChangedOverlay()
    try:
        assert not overlay.isVisible()
        overlay.set_trajectory(_traj())
        overlay.clear()
        assert not overlay.isVisible()
        assert overlay.trajectory() is None
    finally:
        overlay.deleteLater()


def test_feedback_line_emits(q_app):
    overlay = WhatChangedOverlay()
    try:
        heard = []
        overlay.feedback_changed.connect(heard.append)
        overlay.findChild(QLineEdit, "dl_what_changed_feedback").setText("halos")
        assert heard[-1] == "halos"
        assert overlay.feedback() == "halos"
    finally:
        overlay.deleteLater()


def test_review_hosts_overlay_under_compare_canvas(q_app, tmp_path):
    from gui.src.tabs.models.dl_workspace_host import _ReviewToolsPage

    page = _ReviewToolsPage(host=MagicMock(), preference_store=None)
    try:
        overlay = page.findChild(WhatChangedOverlay, "dl_what_changed")
        assert overlay is not None
        src = _png(tmp_path)
        page.set_compare_paths([str(src)])
        assert page.findChild(ImageCompareWindow, "dl_compare_view") is not None
        assert page.findChild(WhatChangedOverlay, "dl_what_changed") is overlay
        page._on_trajectory_updated(_traj())
        assert not overlay.isHidden()
        overlay.findChild(QPushButton, "dl_what_changed_verdict_same").click()
        payload = page.advisor_trajectory()
        assert payload["steps"][0]["verdict"] is None
        assert not overlay.findChild(QPushButton, "dl_what_changed_verdict_same").isEnabled()
        page.set_compare_paths([])
        assert page.findChild(WhatChangedOverlay, "dl_what_changed") is overlay
        assert page.findChild(QLabel, "dl_compare_empty") is not None
    finally:
        page.deleteLater()


def test_bound_pair_loads_parent_and_variant_then_enables_voting(q_app, tmp_path):
    from types import SimpleNamespace

    from backend.src.core.guidance_pair import BoundPair
    from gui.src.tabs.models.dl_workspace_host import _ReviewToolsPage

    parent = _png(tmp_path, "parent.png")
    variant = _png(tmp_path, "variant.png")
    records = {
        "p0": SimpleNamespace(
            prompt_id="p0",
            parent_prompt_id=None,
            local_output_path=str(parent),
            outputs=(),
        ),
        "v1": SimpleNamespace(
            prompt_id="v1",
            parent_prompt_id="p0",
            local_output_path=str(variant),
            outputs=(),
        ),
    }
    manager = MagicMock()
    manager.get_run.side_effect = records.get
    page = _ReviewToolsPage(host=MagicMock(), preference_store=None)
    page._guidance._manager = manager
    page._pair_cache_dir = str(tmp_path / "cache")
    page._pair_loader.start = lambda *_args, **_kwargs: None
    overlay = page.findChild(WhatChangedOverlay, "dl_what_changed")
    try:
        page._on_trajectory_updated(_traj())
        assert not overlay.findChild(QPushButton, "dl_what_changed_verdict_better").isEnabled()
        page._pair_loader._load(
            manager.get_run, None, "p0", "v1", page._pair_generation, page._pair_cache_dir
        )
        assert overlay.findChild(QPushButton, "dl_what_changed_verdict_better").isEnabled()
        view = page.findChild(ImageCompareWindow, "dl_compare_view")
        assert view is not None
        assert page._compare_paths == [str(parent), str(variant)]
        stale = BoundPair("p0", "v1", str(parent), str(variant), generation=page._pair_generation - 1)
        page._what_changed.set_voting_enabled(False)
        page._on_pair_loaded(stale)
        assert not overlay.findChild(QPushButton, "dl_what_changed_verdict_better").isEnabled()
        page._on_pair_loaded(
            BoundPair("p0", "v1", str(parent), str(variant), generation=page._pair_generation)
        )
        overlay.findChild(QPushButton, "dl_what_changed_verdict_better").click()
        assert overlay.trajectory().latest.verdict == "better"
        page.set_compare_paths([str(parent)])
        assert overlay.trajectory() is None
        assert not overlay.findChild(QPushButton, "dl_what_changed_verdict_better").isEnabled()
    finally:
        page.deleteLater()


def test_pair_loader_persists_verdict_off_caller(q_app, tmp_path):
    from gui.src.components.guidance.pair_loader import ComparisonPairLoader

    written = []
    sidecars = []

    class Manager:
        def update_run_meta(self, prompt_id, meta):
            written.append((prompt_id, meta))

    loader = ComparisonPairLoader()
    done = []
    loader.persisted.connect(lambda: done.append(True))
    loader._persist(Manager(), _traj(), "v1", sidecars.append)
    assert written[0][0] == "v1"
    assert sidecars
    assert done == [True]
