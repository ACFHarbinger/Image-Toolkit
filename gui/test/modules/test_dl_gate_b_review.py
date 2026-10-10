"""Cross-PR regressions found while reviewing Gate B (#763–#766)."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QFormLayout

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def no_model_loads(monkeypatch):
    from gui.src.components.prompt_edit import SdxlTokenCounter
    monkeypatch.setattr(SdxlTokenCounter, "_tokenizers", lambda *args: None)


def test_vocabulary_uses_real_repository(monkeypatch):
    from backend.src.database.unified import session
    from gui.src.components.prompt_vocabulary import _default_tag_rows
    db = Mock()
    db.query.return_value = [("cat", "general", 3)]
    monkeypatch.setattr(session, "get_session", lambda: db)
    assert _default_tag_rows() == [("cat", "general", 3)]


def test_completion_keeps_usage_out_of_prompt(q_app):
    from gui.src.components.prompt_edit import PromptEdit
    from gui.src.components.prompt_vocabulary import TagSuggestion
    edit = PromptEdit("ca")
    edit._popup.fill([TagSuggestion("cat", uses=42)])
    edit._popup._on_click(edit._popup.item(0))
    assert edit.text() == "cat,"


def test_clearing_model_invalidates_pending_count(q_app):
    from gui.src.components.prompt_edit import PromptEdit
    edit = PromptEdit("cat")
    edit._count_seq = 2
    edit.set_meter_model_id("")
    edit._on_counts(2, "cat", (19, 20))
    assert edit._meter.text() == "—"


def test_uncreated_output_does_not_invalidate_pin(tmp_path):
    from gui.src.tabs.models.dl_comparison_spine import PinnedRun, artifact_from_config, classify_pin
    config = {"output_filename": str(tmp_path / "future.png")}
    assert classify_pin(PinnedRun("run", "form", config=config)).available
    assert artifact_from_config(config) == ""


def test_pin_owns_snapshot(q_app):
    from gui.src.tabs.models.dl_comparison_spine import ComparisonSpine, PinnedRun
    spine = ComparisonSpine()
    config = {"sub_config": {"steps": 10}}
    spine.note_run(PinnedRun("run", "form", config=config))
    spine.pin("run")
    config["sub_config"]["steps"] = 20
    assert spine.pinned_runs()[0].config["sub_config"]["steps"] == 10


def test_pinning_wrapped_train_keeps_settings(q_app):
    from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost
    host = DeepLearningWorkspaceHost()
    run = host.pin_current_form()
    assert run.config["selected_model"] == "anything"
    assert "sub_config" in run.config
    host.deleteLater()


def test_cloning_pin_updates_wrapped_train(q_app):
    from gui.src.tabs.models.dl_comparison_spine import PinnedRun
    from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost
    host = DeepLearningWorkspaceHost()
    host._clone_pin(PinnedRun("run", "form", config={"selected_model": "anything", "sub_config": {"epochs": 9}}))
    assert host._train_tab.anything_tab.widgets["epochs"].value() == 9
    host.deleteLater()


def test_disclosure_preserves_model_visibility_and_labels(q_app):
    from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab
    tab = LoRAGenerateTab()
    tab.model_selector.setCurrentIndex(0)
    tab.update_ui_visibility()
    tab.apply_disclosure_tier("simple")
    assert tab.gan_group.isHidden()
    assert tab.neg_prompt_edit.isHidden()
    layout = tab.diffusion_group.layout()
    assert isinstance(layout, QFormLayout)
    assert layout.labelForField(tab.neg_prompt_edit).isHidden()
    tab.apply_disclosure_tier("advanced")
    assert tab.gan_group.isHidden()
    assert not tab.neg_prompt_edit.isHidden()
    tab.deleteLater()


def test_summary_tracks_negative_and_batch(q_app):
    from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab
    tab = LoRAGenerateTab()
    tab.neg_prompt_edit.setText("review-negative")
    tab.batch_size_box.setValue(3)
    summary = tab.get_effective_config_summary()
    assert "review-negative" in summary
    assert "Batch: 3" in summary
    tab.deleteLater()


def test_review_reentry_does_not_replace_running_worker(q_app):
    from gui.src.components.dialogs.tag_review_panel import TagReviewPanel
    panel = TagReviewPanel()
    worker = Mock()
    worker.isRunning.return_value = True
    panel._worker = worker
    panel.start_review([])
    assert panel._worker is worker


def test_staging_separates_caption_names(tmp_path):
    from pathlib import Path

    from gui.src.tabs.models.delta.lora_train_tab import resolve_imported_dataset

    images = []
    for directory, suffix, caption in (("one", ".png", "first"), ("two", ".jpg", "second")):
        folder = tmp_path / directory
        folder.mkdir()
        image = folder / ("same" + suffix)
        image.write_bytes(b"x")
        image.with_suffix(".txt").write_text(caption)
        images.append(str(image))
    result = resolve_imported_dataset(tuple(images), staging_root=tmp_path)
    captions = sorted(p.read_text() for p in Path(result.train_dir).glob("*.txt"))
    assert captions == ["first", "second"]


def test_unpin_refreshes_review_canvas(q_app, tmp_path):
    from gui.src.tabs.models.dl_comparison_spine import PinnedRun
    from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost
    from gui.src.windows.image_compare_window import ImageCompareWindow
    from PySide6.QtGui import QImage

    path = tmp_path / "sample.png"
    image = QImage(4, 4, QImage.Format.Format_RGB32)
    image.fill(0)
    assert image.save(str(path))
    host = DeepLearningWorkspaceHost()
    host.note_run(PinnedRun("image", "image", str(path)))
    host.pin_run("image")
    host.activate_route("review")
    assert host.findChild(ImageCompareWindow, "dl_compare_view") is not None
    host.unpin_run("image")
    assert host.findChild(ImageCompareWindow, "dl_compare_view") is None
    host.deleteLater()


def test_model_change_preserves_simple_disclosure(q_app):
    from gui.src.tabs.models.delta.lora_train_tab import LoRATrainTab

    tab = LoRATrainTab()
    tab.apply_disclosure_tier("simple")
    tab.update_ui_visibility()
    assert tab.lora_group.isHidden()
    tab.deleteLater()
