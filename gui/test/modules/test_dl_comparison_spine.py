"""Comparison spine (#732): pins survive destination switches and stale files stay visible."""

from __future__ import annotations

import pytest
from gui.src.tabs.models.dl_comparison_spine import PinnedRun, classify_pin
from gui.src.tabs.models.dl_workspace_host import DeepLearningWorkspaceHost
from PySide6.QtWidgets import QLabel, QWidget

pytestmark = pytest.mark.gui


def test_deleted_artifact_stays_pinned_and_unavailable(tmp_path):
    missing = tmp_path / "gone.safetensors"
    run = classify_pin(
        PinnedRun(run_id="a", label="lora", artifact_path=str(missing), config={})
    )
    assert run.available is False
    assert run.unavailable_reason == "deleted run"


def test_deleted_local_model_is_unavailable_and_hub_id_is_not(tmp_path):
    missing = tmp_path / "base.safetensors"
    local = classify_pin(
        PinnedRun(
            run_id="a",
            label="local",
            config={"model_id": str(missing)},
        )
    )
    hub = classify_pin(
        PinnedRun(
            run_id="b",
            label="hub",
            config={"model_id": "stabilityai/stable-diffusion-xl-base-1.0"},
        )
    )
    assert local.available is False
    assert local.unavailable_reason == "deleted model"
    assert hub.available is True


def test_pins_persist_across_routes_and_cap_at_five(q_app, monkeypatch):
    def fake_build(self, route_key: str) -> QWidget:
        page = QLabel(route_key)
        page.apply_calls = []

        def apply_pinned_run(run: PinnedRun) -> None:
            page.apply_calls.append(run.run_id)

        page.apply_pinned_run = apply_pinned_run
        return page

    monkeypatch.setattr(DeepLearningWorkspaceHost, "_build_page", fake_build)
    host = DeepLearningWorkspaceHost()
    for index in range(6):
        host.note_run(PinnedRun(run_id=f"r{index}", label=f"run {index}"))
        host.pin_run(f"r{index}")

    assert [run.run_id for run in host._spine.pinned_runs()] == ["r0", "r1", "r2", "r3", "r4"]
    assert host.findChild(QLabel, "dl_pin_limit").isHidden() is False

    host.activate_route("generate")
    host.activate_route("review")
    assert [run.run_id for run in host._spine.pinned_runs()] == ["r0", "r1", "r2", "r3", "r4"]

    host.findChild(QWidget, "dl_pin_chip_r1").click()
    assert host._stack.currentWidget().apply_calls == ["r1"]


def test_stale_pin_is_not_removed_on_destination_switch(q_app, monkeypatch, tmp_path):
    artifact = tmp_path / "ckpt.safetensors"
    artifact.write_bytes(b"x")

    def fake_build(self, route_key: str) -> QWidget:
        return QLabel(route_key)

    monkeypatch.setattr(DeepLearningWorkspaceHost, "_build_page", fake_build)
    host = DeepLearningWorkspaceHost()
    host.note_run(PinnedRun(run_id="ckpt", label="checkpoint", artifact_path=str(artifact)))
    assert host.pin_run("ckpt") is True
    artifact.unlink()

    host.activate_route("generate")
    pinned = host._spine.pinned_runs()
    assert [run.run_id for run in pinned] == ["ckpt"]
    assert pinned[0].available is False
    chip = host.findChild(QWidget, "dl_pin_chip_ckpt")
    assert chip.property("unavailable") is True
    assert "Unavailable" in chip.text()


def test_generate_apply_writes_safetensors_into_lora_path(q_app):
    from gui.src.tabs.models.generate_tab import UnifiedGenerateTab

    tab = UnifiedGenerateTab()
    tab.model_selector.setCurrentIndex(2)
    tab.apply_pinned_run(
        PinnedRun(
            run_id="lora",
            label="trained",
            artifact_path="/tmp/character.safetensors",
            config={"selected_model": "r3gan", "sub_config": {}},
        )
    )
    assert tab.model_selector.currentData() == "anything"
    assert tab.anything_tab.lora_edit.text() == "/tmp/character.safetensors"


def _write_png(path) -> None:
    from PySide6.QtGui import QImage

    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(0xFF336699)
    assert image.save(str(path))


def test_filmstrip_thumb_is_a_pixmap(q_app, tmp_path):
    from gui.src.tabs.models.dl_comparison_spine import ComparisonSpine

    image = tmp_path / "frame.png"
    _write_png(image)
    spine = ComparisonSpine()
    spine.note_run(PinnedRun(run_id="img", label="frame", artifact_path=str(image)))
    thumb = spine.findChild(QLabel, "dl_film_thumb_img")
    assert thumb.pixmap() is not None
    assert thumb.pixmap().isNull() is False
    assert thumb.text() == ""


def test_uncreated_output_does_not_invalidate_pin(tmp_path):
    from gui.src.tabs.models.dl_comparison_spine import artifact_from_config

    config = {"output_filename": str(tmp_path / "future.png")}
    assert classify_pin(PinnedRun("run", "form", config=config)).available
    assert artifact_from_config(config) == ""


def test_pin_owns_snapshot(q_app):
    from gui.src.tabs.models.dl_comparison_spine import ComparisonSpine

    spine = ComparisonSpine()
    config = {"sub_config": {"steps": 10}}
    spine.note_run(PinnedRun("run", "form", config=config))
    spine.pin("run")
    config["sub_config"]["steps"] = 20
    assert spine.pinned_runs()[0].config["sub_config"]["steps"] == 10


def test_pinning_wrapped_train_keeps_settings(q_app):
    host = DeepLearningWorkspaceHost()
    run = host.pin_current_form()
    assert run is not None
    assert run.artifact_path == ""
    assert run.config["selected_model"] == "anything"
    assert "sub_config" in run.config
    host.deleteLater()


def test_cloning_pin_updates_wrapped_train(q_app):
    host = DeepLearningWorkspaceHost()
    host._clone_pin(
        PinnedRun(
            "run",
            "form",
            config={"selected_model": "anything", "sub_config": {"epochs": 9}},
        )
    )
    assert host._train_tab.anything_tab.widgets["epochs"].value() == 9
    host.deleteLater()


def test_review_canvas_shows_the_clicked_pin(q_app, monkeypatch, tmp_path):
    from gui.src.windows.image_compare_window import ImageCompareWindow

    image = tmp_path / "out.png"
    _write_png(image)
    original = DeepLearningWorkspaceHost._build_page

    def fake_build(self, route_key: str) -> QWidget:
        if route_key == "review":
            return original(self, route_key)
        return QLabel(route_key)

    monkeypatch.setattr(DeepLearningWorkspaceHost, "_build_page", fake_build)
    host = DeepLearningWorkspaceHost()
    host.note_run(
        PinnedRun(run_id="img", label="sample", artifact_path=str(image), config={"seed": 1})
    )
    host.pin_run("img")
    host.activate_route("review")
    host.findChild(QWidget, "dl_pin_chip_img").click()
    view = host.findChild(ImageCompareWindow, "dl_compare_view")
    assert view is not None
    assert view.image_paths == [str(image)]
    assert view.btn_side_by_side.isChecked()
    assert view.btn_diff.isEnabled() is False
