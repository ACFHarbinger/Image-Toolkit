"""#744: dataset advisor wiring in LoRATrainTab — panel presence, hydra
availability, exclusion restaging round-trip, and override forwarding into
the LyCORIS dispatcher command."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtTest import QTest as qt_test
from PySide6.QtWidgets import QTabWidget

from gui.src.tabs.models.delta.lora_train_tab import (
    LoRATrainTab,
    resolve_imported_dataset,
)

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _no_modal_dialogs():
    with patch("gui.src.tabs.models.delta.lora_train_tab.QMessageBox"):
        yield


@pytest.fixture
def tab(q_app):
    widget = LoRATrainTab()
    yield widget
    widget.close()


def _img(path: Path, color=(40, 60, 80)) -> Path:
    from PIL import Image

    Image.new("RGB", (24, 24), color).save(path)
    return path


def _caption(path: Path, text: str) -> None:
    path.with_suffix(".txt").write_text(text, encoding="utf-8")


def _wait_for(predicate, timeout_ms=8000):
    qt_test.qWait(0)
    elapsed = 0
    while not predicate() and elapsed < timeout_ms:
        qt_test.qWait(25)
        elapsed += 25
    return predicate()


# ---------------------------------------------------------------------------
# resolve_imported_dataset exclusions (pure)
# ---------------------------------------------------------------------------


def test_exclusions_force_staging_and_hide_excluded_files(tmp_path):
    a = _img(tmp_path / "a.png", color=(1, 1, 1))
    b = _img(tmp_path / "b.png", color=(2, 2, 2))
    c = _img(tmp_path / "c.png", color=(3, 3, 3))
    excluded = frozenset({str(b.resolve())})

    imported = resolve_imported_dataset((str(tmp_path),), exclusions=excluded)

    assert imported.staged, "folder scope would let training see excluded files"
    assert set(imported.source_paths) == {str(a), str(c)}
    staged_names = {p.name for p in Path(imported.train_dir).iterdir()}
    assert "b.png" not in staged_names


def test_all_excluded_yields_empty_dataset(tmp_path):
    a = _img(tmp_path / "a.png")
    excluded = frozenset({str(a.resolve())})
    imported = resolve_imported_dataset((str(tmp_path),), exclusions=excluded)
    assert imported.train_dir is None
    assert imported.source_paths == ()


def test_no_exclusions_keeps_folder_scope(tmp_path):
    _img(tmp_path / "a.png")
    imported = resolve_imported_dataset((str(tmp_path),))
    assert not imported.staged
    assert imported.scope == "folder"


# ---------------------------------------------------------------------------
# Tab wiring
# ---------------------------------------------------------------------------


def test_tab_hosts_advisor_gallery_and_review_tab(tab):
    assert tab._right_tabs.count() == 2
    assert tab._right_tabs.tabText(0) == "Advisor"
    assert tab._right_tabs.tabText(1) == "Review Tags"
    assert isinstance(tab._right_tabs, QTabWidget)
    assert tab._advisor_panel is not None
    assert tab._gallery is not None


def test_hydra_availability_tracks_engine_choice(tab):
    assert tab.engine_combo.currentData() == "standard"
    assert not tab._advisor_panel._hydra_available
    tab.engine_combo.setCurrentIndex(1)  # locon
    assert tab._advisor_panel._hydra_available
    tab.engine_combo.setCurrentIndex(0)
    assert not tab._advisor_panel._hydra_available


def test_queued_override_reaches_lycoris_command(tab):
    tab._advisor_panel._queue_override("pipeline.run_captioning=true")
    fake_proc = MagicMock()
    fake_proc.stdout = iter([])
    fake_proc.wait.return_value = 0
    with patch(
        "gui.src.tabs.models.delta.lora_train_tab.subprocess.Popen",
        return_value=fake_proc,
    ) as mock_popen:
        tab._run_lycoris_training("/d", "m", "p", "o", "loha")
    cmd = mock_popen.call_args.args[0]
    assert "pipeline.run_captioning=true" in cmd


def test_effective_config_summary_mentions_pending_overrides(tab):
    assert "Advisor overrides" not in tab.get_effective_config_summary()
    tab._advisor_panel._queue_override("pipeline.run_captioning=true")
    assert "Advisor overrides: pipeline.run_captioning=true" in tab.get_effective_config_summary()


# ---------------------------------------------------------------------------
# Exclude → restage → restore round-trip
# ---------------------------------------------------------------------------


def test_exclude_restage_and_restore_roundtrip(tab, tmp_path):
    a = _img(tmp_path / "a.png", color=(1, 1, 1))
    _img(tmp_path / "b.png", color=(2, 2, 2))
    _img(tmp_path / "c.png", color=(9, 9, 9))
    _img(tmp_path / "copy.png", color=(1, 1, 1))  # duplicate of a

    tab.apply_imported_paths((str(tmp_path),))
    assert _wait_for(lambda: len(tab._dataset_paths) == 4)
    assert not tab._staging_dir

    tab._on_advisor_exclude([str(a.resolve())])
    assert _wait_for(lambda: tab._staging_dir is not None)
    assert len(tab._dataset_paths) == 3
    assert str(a.resolve()) not in {str(Path(p).resolve()) for p in tab._dataset_paths}
    assert len(tab._advisor_exclusions) == 1

    tab._on_advisor_restore()
    assert _wait_for(lambda: tab._staging_dir is None and len(tab._dataset_paths) == 4)
    assert not tab._advisor_exclusions


def test_explicit_selection_restore_never_switches_to_previous_folder(tab, tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    _img(old / "old.png")
    tab.apply_imported_paths((str(old),))
    assert _wait_for(lambda: tab._dataset_worker is None)
    selected = tmp_path / "selection"
    selected.mkdir()
    a = _img(selected / "a.png")
    b = _img(selected / "b.png", color=(1, 2, 3))
    _img(selected / "unselected.png")
    tab.apply_imported_paths((str(a), str(b)))
    assert _wait_for(lambda: tab._dataset_worker is None)
    tab._on_advisor_exclude([str(b)])
    assert _wait_for(lambda: tab._dataset_worker is None)
    assert tab._dataset_paths == (str(a),)
    tab._on_advisor_restore()
    assert _wait_for(lambda: tab._dataset_worker is None)
    assert set(tab._dataset_paths) == {str(a), str(b)}


def test_excluding_all_images_clears_training_input(tab, tmp_path):
    a = _img(tmp_path / "only.png")
    tab.apply_imported_paths((str(a),))
    assert _wait_for(lambda: tab._dataset_worker is None)
    tab._on_advisor_exclude([str(a)])
    assert _wait_for(lambda: tab._dataset_worker is None)
    assert not tab.data_dir_edit.text()
    assert not tab._dataset_paths
