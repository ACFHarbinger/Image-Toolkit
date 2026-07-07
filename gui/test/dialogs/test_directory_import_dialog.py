"""Tests for DirectoryImportDialog and EntityDirectoryImportDialog subdirectory scanning."""

from __future__ import annotations

import re
from pathlib import Path
import pytest
from PySide6.QtWidgets import QMessageBox

from gui.src.tabs.core.elements.dialog.directory_import_dialog import (
    _DirectoryImportDialog,
)
from gui.src.tabs.core.elements.dialog.entity_directory_import_dialog import (
    _EntityDirectoryImportDialog,
)

pytestmark = pytest.mark.gui


class TestDirectoryImportDialogSubdirScan:
    def test_content_subdirectory_scan_happy_path(self, q_app, tmp_path, monkeypatch):
        # Create standard test directory structure
        scan_dir = tmp_path / "scan_target"
        scan_dir.mkdir()

        # Valid subdirectories
        sub1 = scan_dir / "Alice_Margatroid"
        sub1.mkdir()
        sub2 = scan_dir / "Marisa_Kirisame"
        sub2.mkdir()
        # Invalid subdirectory (contains spaces/hyphens)
        sub3 = scan_dir / "Reimu-Hakurei"
        sub3.mkdir()

        # Add dummy video files
        (sub1 / "Alice_Margatroid - 01.mp4").write_text("dummy")
        (sub1 / "Alice_Margatroid - 02.mkv").write_text("dummy")
        (sub2 / "Marisa 05.mp4").write_text("dummy")
        (sub3 / "Reimu - 01.mp4").write_text("dummy") # Should be ignored because directory name is invalid

        # Instantiate dialog
        dialog = _DirectoryImportDialog(set())
        dialog._directory = str(scan_dir)
        dialog._dir_edit.setText(str(scan_dir))

        # Mock app settings recursive scan
        from gui.src.windows.settings.app_settings import AppSettings
        monkeypatch.setattr(AppSettings, "recursive_scan", lambda: False)

        # Act
        dialog._do_subdirectory_scan()

        # Assert
        assert "Alice Margatroid" in dialog._scan_result
        assert "Marisa Kirisame" in dialog._scan_result
        assert "Reimu-Hakurei" not in dialog._scan_result
        assert "Reimu Hakurei" not in dialog._scan_result

        # Check parsed episodes
        alice_eps = dialog._scan_result["Alice Margatroid"]
        assert len(alice_eps) == 2
        assert alice_eps[0][0] == 1
        assert alice_eps[0][1].endswith("Alice_Margatroid - 01.mp4")
        assert alice_eps[1][0] == 2
        assert alice_eps[1][1].endswith("Alice_Margatroid - 02.mkv")

        marisa_eps = dialog._scan_result["Marisa Kirisame"]
        assert len(marisa_eps) == 1
        assert marisa_eps[0][0] == 5
        assert marisa_eps[0][1].endswith("Marisa 05.mp4")

        # Test Deselect All
        from PySide6.QtWidgets import QCheckBox
        dialog._deselect_all()
        for r in range(dialog._table.rowCount()):
            cw = dialog._table.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox)
            assert not chk.isChecked()

        # Test Select All New
        dialog._select_all_new()
        for r in range(dialog._table.rowCount()):
            cw = dialog._table.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox)
            assert chk.isChecked()



class TestEntityDirectoryImportDialogSubdirScan:
    def test_entity_subdirectory_scan_happy_path(self, q_app, tmp_path):
        # Create standard test directory structure
        scan_dir = tmp_path / "entity_scan_target"
        scan_dir.mkdir()

        # Valid subdirectories
        sub1 = scan_dir / "Alice_Margatroid"
        sub1.mkdir()
        sub2 = scan_dir / "Marisa"
        sub2.mkdir()
        # Invalid subdirectory
        sub3 = scan_dir / "Reimu-Hakurei"
        sub3.mkdir()

        # Add image files
        img1 = sub1 / "profile.png"
        img1.write_text("dummy")
        img2 = sub2 / "avatar.jpg"
        img2.write_text("dummy")
        # Sub3 has an image, but the folder name is invalid
        (sub3 / "profile.png").write_text("dummy")

        # Instantiate dialog
        dialog = _EntityDirectoryImportDialog(set())
        dialog._directory = str(scan_dir)
        dialog._dir_edit.setText(str(scan_dir))

        # Act
        dialog._do_subdirectory_scan()

        # Assert
        # Expected scan results: [(first_name, last_name, image_path)]
        scan_res = dialog._scan_result
        assert len(scan_res) == 2

        # Verify Alice Margatroid
        alice = next((r for r in scan_res if r[0] == "Alice"), None)
        assert alice is not None
        assert alice[1] == "Margatroid"
        assert Path(alice[2]).name == "profile.png"

        # Verify Marisa (single name, so last name is empty)
        marisa = next((r for r in scan_res if r[0] == "Marisa"), None)
        assert marisa is not None
        assert marisa[1] == ""
        assert Path(marisa[2]).name == "avatar.jpg"

        # Verify Reimu-Hakurei is not in results
        reimu = next((r for r in scan_res if r[0] == "Reimu"), None)
        assert reimu is None

        # Test Deselect All
        from PySide6.QtWidgets import QCheckBox
        dialog._deselect_all()
        for r in range(dialog._table.rowCount()):
            cw = dialog._table.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox)
            assert not chk.isChecked()

        # Test Select All New
        dialog._select_all_new()
        for r in range(dialog._table.rowCount()):
            cw = dialog._table.cellWidget(r, 0)
            chk = cw.findChild(QCheckBox)
            assert chk.isChecked()

