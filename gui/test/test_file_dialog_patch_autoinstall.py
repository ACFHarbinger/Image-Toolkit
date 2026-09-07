"""ui-arch-29/#551: importing ``gui.src`` installs the non-native QFileDialog patch."""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog

import gui.src  # noqa: F401
from gui.src import file_dialog_patch as fdp


def test_static_getters_are_patched_by_package_import():
    assert QFileDialog.getExistingDirectory is fdp.my_getExistingDirectory
    assert QFileDialog.getOpenFileName is fdp.my_getOpenFileName
    assert QFileDialog.getOpenFileNames is fdp.my_getOpenFileNames
    assert QFileDialog.getSaveFileName is fdp.my_getSaveFileName


def test_apply_patch_is_idempotent():
    before = QFileDialog.getOpenFileName
    fdp.apply_patch()
    assert QFileDialog.getOpenFileName is before
