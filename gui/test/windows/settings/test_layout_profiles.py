import json
import sys
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtWidgets import QApplication, QLabel, QSplitter, QWidget

from gui.src.windows.settings.layout_profiles import LayoutProfileManager
from gui.src.windows.settings.app_settings import AppSettings

if not QApplication.instance():
    app = QApplication(sys.argv)


def test_layout_profile_save_and_load():
    win = QWidget()
    win.resize(1024, 768)

    splitters = {
        "splitters/test_split_1": b"state_data_1",
        "splitters/test_split_2": b"state_data_2",
    }

    saved = LayoutProfileManager.save_profile(
        name="TestStudio",
        window=win,
        splitters=splitters,
    )
    assert saved is True
    assert "TestStudio" in LayoutProfileManager.list_profiles()

    profile = LayoutProfileManager.load_profile("TestStudio")
    assert profile is not None
    assert "geometry" in profile
    assert profile["splitters"]["splitters/test_split_1"] == b"state_data_1"


def test_layout_profile_apply():
    win = QWidget()
    win.resize(800, 600)

    splitters = {
        "splitters/apply_test_split": b"state_apply_bytes",
    }

    LayoutProfileManager.save_profile("ApplyTarget", window=win, splitters=splitters)

    target_win = QWidget()
    applied = LayoutProfileManager.apply_profile("ApplyTarget", window=target_win)
    assert applied is True
    assert AppSettings.get("splitters/apply_test_split") is not None


def test_layout_profile_delete_and_defaults():
    # 'Default' cannot be deleted
    assert LayoutProfileManager.delete_profile("Default") is False

    LayoutProfileManager.save_profile("TemporaryProfile", geometry=b"temp_geom")
    assert "TemporaryProfile" in LayoutProfileManager.list_profiles()

    deleted = LayoutProfileManager.delete_profile("TemporaryProfile")
    assert deleted is True
    assert "TemporaryProfile" not in LayoutProfileManager.list_profiles()


def test_layout_profile_export_and_import():
    LayoutProfileManager.save_profile("ExportedProfile1", geometry=b"geom1")
    LayoutProfileManager.save_profile("ExportedProfile2", geometry=b"geom2")

    json_str = LayoutProfileManager.export_profiles_json()
    assert "ExportedProfile1" in json_str
    assert "ExportedProfile2" in json_str

    # Modify and re-import
    data = json.loads(json_str)
    data["ImportedProfileNew"] = data["ExportedProfile1"]
    count = LayoutProfileManager.import_profiles_json(json.dumps(data))
    assert count >= 1
    assert "ImportedProfileNew" in LayoutProfileManager.list_profiles()
