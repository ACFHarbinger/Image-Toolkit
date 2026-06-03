import os
import json
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from gui.src.tabs.core.image_extractor_tab import ImageExtractorTab
from gui.src.windows.settings_window import SettingsWindow
from backend.src.constants import IMAGE_TOOLKIT_DIR, DAEMON_CONFIG_PATH

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_extraction_history_limit_and_pruning(qapp, tmp_path, monkeypatch):
    # Mock IMAGE_TOOLKIT_DIR to use a temporary directory for this test
    test_dir = tmp_path / "toolkit"
    test_dir.mkdir()
    monkeypatch.setattr("gui.src.tabs.core.image_extractor_tab.IMAGE_TOOLKIT_DIR", test_dir)

    # Instantiate tab
    tab = ImageExtractorTab()
    
    # Check initial empty state
    assert tab.recent_runs == []
    assert tab.extraction_metadata == {}

    # Define absolute paths
    f1 = str(Path("file1.png").absolute())
    f2 = str(Path("file2.png").absolute())
    f3 = str(Path("file3.png").absolute())
    f4 = str(Path("file4.png").absolute())
    f5 = str(Path("file5.png").absolute())

    # Record first extraction
    meta1 = {
        "video_path": "video1.mp4",
        "start_ms": 0,
        "end_ms": 1000,
        "timestamp": 100.0,
        "engine": "FFmpeg"
    }
    tab._record_extraction([f1, f2], meta1)

    # Check state after first record
    assert len(tab.recent_runs) == 1
    assert tab.recent_runs[0]["video_path"] == "video1.mp4"
    assert len(tab.extraction_metadata) == 2
    assert f1 in tab.extraction_metadata
    assert f2 in tab.extraction_metadata

    # Set limit to 2
    tab.recent_extractions_limit = 2

    # Record second extraction
    meta2 = {
        "video_path": "video2.mp4",
        "start_ms": 1000,
        "end_ms": 2000,
        "timestamp": 200.0,
        "engine": "MoviePy"
    }
    tab._record_extraction([f3], meta2)

    # Check state
    assert len(tab.recent_runs) == 2
    assert len(tab.extraction_metadata) == 3

    # Record third extraction (exceeding limit of 2)
    meta3 = {
        "video_path": "video3.mp4",
        "start_ms": 2000,
        "end_ms": 3000,
        "timestamp": 300.0,
        "engine": "FFmpeg"
    }
    tab._record_extraction([f4, f5], meta3)

    # The oldest (meta1, timestamp 100.0) should be pruned.
    # The recent runs should only contain meta3 (300.0) and meta2 (200.0).
    assert len(tab.recent_runs) == 2
    assert tab.recent_runs[0]["video_path"] == "video3.mp4"
    assert tab.recent_runs[1]["video_path"] == "video2.mp4"

    # The file_map/extraction_metadata should only retain files associated with meta2 and meta3.
    # f1 and f2 should be pruned.
    assert f1 not in tab.extraction_metadata
    assert f2 not in tab.extraction_metadata
    assert f3 in tab.extraction_metadata
    assert f4 in tab.extraction_metadata
    assert f5 in tab.extraction_metadata

    # Verify that saving/loading keeps it correct
    # Create a new tab instance (it should reload from the same mocked directory)
    tab2 = ImageExtractorTab()
    assert len(tab2.recent_runs) == 2
    assert tab2.recent_runs[0]["video_path"] == "video3.mp4"
    assert f1 not in tab2.extraction_metadata
    assert f3 in tab2.extraction_metadata


def test_settings_window_resets(qapp, tmp_path, monkeypatch):
    # Mock IMAGE_TOOLKIT_DIR to use a temporary directory for this test
    test_dir = tmp_path / "toolkit"
    test_dir.mkdir()
    monkeypatch.setattr("gui.src.windows.settings_window.IMAGE_TOOLKIT_DIR", test_dir)
    monkeypatch.setattr("gui.src.windows.settings_window.DAEMON_CONFIG_PATH", test_dir / ".myapp_slideshow_config.json")

    # Mock QMessageBox popups
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    # Create dummy config and history files
    daemon_conf = test_dir / ".myapp_slideshow_config.json"
    daemon_conf.write_text(json.dumps({"running": True}))

    history_file = test_dir / "extraction_history.json"
    history_file.write_text(json.dumps({"recent_runs": [], "file_map": {}}))

    pid_file = test_dir / ".myapp_slideshow.pid"
    pid_file.write_text("12345")

    # Instantiate settings window
    settings = SettingsWindow()

    # Reset slideshow daemon
    settings._reset_slideshow_daemon()
    assert not pid_file.exists()
    assert not daemon_conf.exists()

    # Reset extraction history
    settings._reset_extraction_history()
    assert not history_file.exists()


def test_settings_window_reload_and_profile_update(qapp, monkeypatch):
    # Mock QMessageBox popups
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    class MockVaultManager:
        def __init__(self):
            self.data = {
                "account_name": "test_user",
                "theme": "dark",
                "active_tab_configs": {"ImageExtractorTab": "None (Default)"},
                "system_preference_profiles": {
                    "ExistingProfile": {
                        "theme": "light",
                        "active_tab_configs": {"ImageExtractorTab": "None (Default)"}
                    }
                },
                "preferences": {
                    "thumbnail_size": 180,
                    "page_size": 100,
                    "recent_extractions_count": 10
                }
            }
        def load_account_credentials(self):
            return self.data
        def save_data(self, data_str):
            self.data = json.loads(data_str)
            return True

    # Instantiate SettingsWindow
    settings = SettingsWindow()
    settings.vault_manager = MockVaultManager()

    # Call reload to initialize with mock data
    settings.reload_settings()

    # Check initially loaded values
    assert settings.current_account_name == "test_user"
    assert settings.pref_thumbnail_size == 180
    assert settings.profile_combo.count() == 1
    assert settings.profile_combo.itemText(0) == "ExistingProfile"

    # Modify values in UI widgets directly
    settings.thumbnail_size_spinbox.setValue(256)
    settings.light_theme_radio.setChecked(True)

    # Trigger reload_settings to revert changes (since update settings was not clicked)
    settings.reload_settings()
    assert settings.thumbnail_size_spinbox.value() == 180
    assert settings.dark_theme_radio.isChecked()

    # Now, select a profile in profile_combo and update it
    settings.profile_combo.setCurrentText("ExistingProfile")
    settings.thumbnail_size_spinbox.setValue(256)
    settings.light_theme_radio.setChecked(True)

    # Click/call update profile
    settings._update_selected_profile()

    # Check that mock vault data has been updated with the new theme (light)
    creds = settings.vault_manager.load_account_credentials()
    assert creds["system_preference_profiles"]["ExistingProfile"]["theme"] == "light"


def test_export_finished_records_history(qapp, tmp_path, monkeypatch):
    test_dir = tmp_path / "toolkit"
    test_dir.mkdir()
    monkeypatch.setattr("gui.src.tabs.core.image_extractor_tab.IMAGE_TOOLKIT_DIR", test_dir)

    tab = ImageExtractorTab()
    assert tab.recent_runs == []

    # Mock extraction_dir
    tab.extraction_dir = test_dir

    # Create dummy output file
    output_file = test_dir / "test_output.mp4"
    output_file.touch()

    # Set active metadata
    tab._active_metadata = {
        "video_path": "video_test.mp4",
        "start_ms": 100,
        "end_ms": 200,
        "timestamp": 1234.56,
        "engine": "FFmpeg",
        "mode": "video"
    }

    # Call _on_export_finished
    tab._on_export_finished(str(output_file))

    # Assert that history was updated and _active_metadata was cleared
    assert len(tab.recent_runs) == 1
    assert tab.recent_runs[0]["video_path"] == "video_test.mp4"
    assert tab._active_metadata is None
    assert str(output_file) in tab.extraction_metadata


