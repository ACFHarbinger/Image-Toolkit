"""Inspector controls for runs, subsets, and the case the user actually opened."""

from __future__ import annotations

import numpy as np
import pytest

from middleware.benchmark.asp.evaluation.other.run_library import snapshot_outputs
from middleware.benchmark.asp.evaluation.other.session import EvaluationSession
from middleware.benchmark.asp.evaluation.ui.coherence_v2_tab import CoherenceV2Tab
from middleware.benchmark.asp.evaluation.ui.queue_panel import QueuePanel
from middleware.benchmark.asp.evaluation.ui.run_library_panel import RunLibraryPanel
from middleware.benchmark.asp.evaluation.ui.viz_tab import VisualizationTab


def _session(tmp_path) -> EvaluationSession:
    return EvaluationSession(
        ["alpha_case", "beta_case", "gamma_case"],
        str(tmp_path / "eval.json"),
    )


@pytest.mark.inspector_ui
def test_queue_search_hides_non_matching_name(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("ASP_EVAL_LIBRARY", str(tmp_path / "library.json"))
    panel = QueuePanel()
    panel.set_session(_session(tmp_path))
    assert "beta_case" in panel.active_names()
    panel._search.setText("BETA")
    assert panel.active_names() == ["beta_case"]


@pytest.mark.inspector_ui
def test_queue_subset_filters_to_chosen_ids(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("ASP_EVAL_LIBRARY", str(tmp_path / "library.json"))
    panel = QueuePanel()
    panel.set_session(_session(tmp_path))
    panel._subset.addItem(
        "picked (user)",
        {"name": "picked", "case_ids": ["gamma_case", "missing"], "description": ""},
    )
    panel._subset.setCurrentIndex(panel._subset.count() - 1)
    assert panel.active_names() == ["gamma_case"]


@pytest.mark.inspector_ui
def test_coherence_set_context_outside_json_list(qapp):
    tab = CoherenceV2Tab()
    images = {
        "asp": np.zeros((8, 8, 3), dtype=np.uint8),
        "simple": np.full((8, 8, 3), 40, dtype=np.uint8),
    }
    tab.set_context(images, {}, "clip_new")
    assert "clip_new" in tab.lbl_status.text()


@pytest.mark.inspector_ui
def test_run_library_panel_lists_snapshot(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("ASP_EVAL_LIBRARY", str(tmp_path / "library.json"))
    root = tmp_path / "runs"
    base = tmp_path / "bench"
    base.mkdir()
    snapshot_outputs(
        str(base),
        ["alpha"],
        description="kept",
        tags=["seam"],
        label="first",
        root=root,
    )
    panel = RunLibraryPanel(root=root)
    panel.reload()
    assert panel._runs.rowCount() == 1


@pytest.mark.inspector_ui
def test_visualization_tab_lists_stitch_tools(qapp):
    tab = VisualizationTab()
    names = [name for name, _handler in tab._tools]
    assert "Local SSIM" in names
    assert "Seam energy" in names
