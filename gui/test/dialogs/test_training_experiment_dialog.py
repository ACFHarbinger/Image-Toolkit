from pathlib import Path
from unittest.mock import patch

import pytest
from middleware.src.comfy_matrix import gpu_lease

from gui.src.components.dialogs.training_experiment_dialog import OWNER, ExperimentWorker, TrainingExperimentDialog

pytestmark = pytest.mark.gui


def test_worker_releases_lease_on_preparation_error(tmp_path):
    worker = ExperimentWorker(str(tmp_path), "rank", [2, 4])
    assert gpu_lease.try_acquire(OWNER)
    try:
        with (patch("gui.src.components.dialogs.training_experiment_dialog.experiments.prepare_experiment", side_effect=ValueError("bad")),
              pytest.raises(ValueError)):
            worker._execute()
        assert gpu_lease.owner is None
    finally:
        gpu_lease.release(OWNER)


def test_dialog_previews_cost_and_rejects_duplicates(q_app):
    with patch.object(ExperimentWorker, "start"):
        dialog = TrainingExperimentDialog("unused")
    try:
        dialog._loaded({"record": {"config": {"epochs": 2, "batch_size": 1}}, "paths": [Path("one.png")], "bytes": 10})
        assert dialog.launch.isEnabled()
        assert "2 sequential runs" in dialog.estimate.text()
        dialog.values.setText("1e-4, 1e-4")
        assert not dialog.launch.isEnabled()
    finally:
        dialog.close()


def test_chart_uses_shared_step_axes_and_close_cancels(q_app):
    with patch.object(ExperimentWorker, "start"):
        dialog = TrainingExperimentDialog("unused")
    worker = ExperimentWorker("unused", "rank", [2, 4])
    dialog._worker = worker
    dialog._changed(("/experiment", [
        {"value": 2, "status": "success", "points": [(1, .8), (5, .2)]},
        {"value": 4, "status": "success", "points": [(1, .7), (3, .3)]},
    ]))
    a, b = dialog.figure.axes
    assert a.get_xlim() == b.get_xlim()
    assert a.get_ylim() == b.get_ylim()
    dialog.close()
    assert worker.cancelled.is_set()
