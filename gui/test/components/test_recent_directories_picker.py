import sys
from pathlib import Path

from gui.src.components.widgets.recent_directories_picker import RecentDirectoriesPicker
from gui.src.windows.settings.app_settings import AppSettings
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists
if not QApplication.instance():
    app = QApplication(sys.argv)


def test_recent_directories_picker_empty(tmp_path: Path):
    class_name = "TestDummyTabEmpty"
    AppSettings.set_session(class_name, "recent_dirs", [])

    picker = RecentDirectoriesPicker(class_name)
    assert picker.get_recent_dirs() == []
    picker.refresh_menu()

    actions = picker.menu().actions()
    assert len(actions) == 1
    assert "(No recent directories)" in actions[0].text()
    assert not actions[0].isEnabled()


def test_recent_directories_picker_add_and_mru(tmp_path: Path):
    class_name = "TestDummyTabMRU"
    AppSettings.set_session(class_name, "recent_dirs", [])

    dir1 = tmp_path / "folder1"
    dir2 = tmp_path / "folder2"
    dir3 = tmp_path / "folder3"
    dir1.mkdir()
    dir2.mkdir()
    dir3.mkdir()

    picker = RecentDirectoriesPicker(class_name, max_entries=2)
    picker.add_recent_dir(str(dir1))
    picker.add_recent_dir(str(dir2))

    assert picker.get_recent_dirs() == [str(dir2), str(dir1)]

    # Adding dir3 should enforce max_entries=2
    picker.add_recent_dir(str(dir3))
    assert picker.get_recent_dirs() == [str(dir3), str(dir2)]

    # Adding dir2 again should move it to front
    picker.add_recent_dir(str(dir2))
    assert picker.get_recent_dirs() == [str(dir2), str(dir3)]


def test_recent_directories_picker_selection_and_signal(tmp_path: Path):
    class_name = "TestDummyTabSelect"
    AppSettings.set_session(class_name, "recent_dirs", [])

    dir1 = tmp_path / "target_dir"
    dir1.mkdir()

    selected_via_signal: list[str] = []
    selected_via_cb: list[str] = []

    def on_selected(path: str):
        selected_via_cb.append(path)

    picker = RecentDirectoriesPicker(
        class_name,
        on_directory_selected=on_selected,
    )
    picker.directory_selected.connect(lambda p: selected_via_signal.append(p))
    picker.add_recent_dir(str(dir1))

    picker._handle_selection(str(dir1))
    assert selected_via_signal == [str(dir1)]
    assert selected_via_cb == [str(dir1)]


def test_recent_directories_picker_clear(tmp_path: Path):
    class_name = "TestDummyTabClear"
    dir1 = tmp_path / "dir_to_clear"
    dir1.mkdir()

    picker = RecentDirectoriesPicker(class_name)
    picker.add_recent_dir(str(dir1))
    assert len(picker.get_recent_dirs()) == 1

    picker.clear_recent_dirs()
    assert picker.get_recent_dirs() == []
