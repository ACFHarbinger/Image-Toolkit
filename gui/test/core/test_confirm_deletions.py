"""Regression coverage for the shared §2.9D deletion preference."""

from __future__ import annotations

from types import SimpleNamespace

from gui.src.tabs.core.similarity_tab import _deletion as similarity_deletion
from gui.src.tabs.core.similarity_tab._deletion import _DeletionMixin
from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base import (
    _image_preview_delete as wallpaper_deletion,
)
from gui.src.tabs.core.wallpaper_tab.common.wallpaper_common_base._image_preview_delete import (
    _ImagePreviewDeleteMixin,
)


class _SimilarityHarness(_DeletionMixin):
    def __init__(self) -> None:
        self.selected_files: list[str] = []
        self.found_files: list[str] = []
        self.path_to_label_map: dict[str, object] = {}
        self.status_label = SimpleNamespace(setText=lambda *_: None)

    def _prefs(self) -> dict:
        return {"send_to_trash": True}

    def _confirm_deletions_enabled(self) -> bool:
        return False

    def refresh_found_gallery(self) -> None:
        pass

    def refresh_selected_panel(self) -> None:
        pass

    def on_selection_changed(self) -> None:
        pass


class _WallpaperHarness(_ImagePreviewDeleteMixin):
    def __init__(self) -> None:
        self.gallery_image_paths: list[str] = []
        self.path_to_label_map: dict[str, object] = {}
        self.linked_tabs: list[object] = []
        self.monitor_slideshow_queues = {"monitor": []}
        self.monitor_image_paths = {"monitor": None}
        self.updated_monitor_ids: list[str] = []

    def window(self):
        return SimpleNamespace(
            cached_creds={"preferences": {"confirm_deletions": False}}
        )

    def update_monitor_widget_ui(self, monitor_id: str) -> None:
        self.updated_monitor_ids.append(monitor_id)

    def refresh_gallery_view(self) -> None:
        pass

    def check_all_monitors_set(self) -> None:
        pass


def test_similarity_single_delete_skips_dialog_when_preference_disabled(
    monkeypatch, tmp_path
):
    path = tmp_path / "image.png"
    path.write_bytes(b"image")
    tab = _SimilarityHarness()
    tab.selected_files = [str(path)]
    tab.found_files = [str(path)]
    questions: list[tuple] = []
    trashed: list[str] = []
    monkeypatch.setattr(similarity_deletion.QMessageBox, "question", lambda *args: questions.append(args))
    monkeypatch.setattr(similarity_deletion.QMessageBox, "information", lambda *_: None)
    monkeypatch.setattr(similarity_deletion, "send2trash", trashed.append)

    tab.delete_single_file(str(path))

    assert questions == []
    assert trashed == [str(path)]


def test_wallpaper_delete_skips_dialog_when_preference_disabled(monkeypatch, tmp_path):
    path = tmp_path / "wallpaper.png"
    path.write_bytes(b"image")
    tab = _WallpaperHarness()
    tab.gallery_image_paths = [str(path)]
    questions: list[tuple] = []
    trashed: list[str] = []
    monkeypatch.setattr(wallpaper_deletion.QMessageBox, "question", lambda *args: questions.append(args))
    monkeypatch.setattr(wallpaper_deletion.QMessageBox, "information", lambda *_: None)
    monkeypatch.setattr(wallpaper_deletion, "send2trash", trashed.append)

    tab.handle_delete_image(str(path))

    assert questions == []
    assert trashed == [str(path)]
    assert tab.updated_monitor_ids == ["monitor"]
