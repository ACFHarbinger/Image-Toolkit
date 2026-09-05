import sys

from PySide6.QtWidgets import QApplication

from gui.src.components.dialogs.shortcut_discovery_dialog import (
    KeycapBadgeDelegate,
    ScopeBadgeDelegate,
    ShortcutDiscoveryDialog,
)
from gui.src.utils.manager.shortcut_manager import get_registry

if not QApplication.instance():
    app = QApplication(sys.argv)


def test_shortcut_discovery_dialog_population():
    dlg = ShortcutDiscoveryDialog()
    reg = get_registry()
    all_actions = reg.get_all()

    # Initial state should show all shortcuts
    assert dlg.table.rowCount() == len(all_actions)
    assert f"Showing {len(all_actions)} of {len(all_actions)}" in dlg.status_label.text()


def test_shortcut_discovery_dialog_scope_filtering():
    dlg = ShortcutDiscoveryDialog()
    dlg._set_scope("Gallery")

    # Only Gallery shortcuts should be displayed
    assert dlg.table.rowCount() > 0
    for row in range(dlg.table.rowCount()):
        assert dlg.table.item(row, 0).text() == "Gallery"


def test_shortcut_discovery_dialog_search_filter():
    dlg = ShortcutDiscoveryDialog()
    dlg.search_input.setText("undo")

    assert dlg.table.rowCount() >= 1
    found_undo = False
    for row in range(dlg.table.rowCount()):
        desc = dlg.table.item(row, 1).text().lower()
        if "undo" in desc:
            found_undo = True
    assert found_undo


def test_shortcut_discovery_dialog_delegates():
    dlg = ShortcutDiscoveryDialog()
    delegate_0 = dlg.table.itemDelegateForColumn(0)
    delegate_2 = dlg.table.itemDelegateForColumn(2)

    assert isinstance(delegate_0, ScopeBadgeDelegate)
    assert isinstance(delegate_2, KeycapBadgeDelegate)
