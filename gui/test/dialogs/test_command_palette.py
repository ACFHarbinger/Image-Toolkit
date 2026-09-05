import sys

from PySide6.QtWidgets import QApplication

from gui.src.components.dialogs.command_palette_dialog import (
    CommandItem,
    CommandItemDelegate,
    CommandPaletteDialog,
)

if not QApplication.instance():
    app = QApplication(sys.argv)


def test_command_palette_population_and_filter():
    executed = []

    commands = [
        CommandItem(
            id="test.cmd1",
            title="Convert Images to PNG",
            category="Action",
            callback=lambda: executed.append("cmd1"),
            shortcut="Ctrl+Return",
            keywords=["convert", "png"],
        ),
        CommandItem(
            id="test.cmd2",
            title="Go to Stitch Tab",
            category="Navigation",
            callback=lambda: executed.append("cmd2"),
            keywords=["stitch", "asp"],
        ),
        CommandItem(
            id="test.cmd3",
            title="Toggle Theme",
            category="Setting",
            callback=lambda: executed.append("cmd3"),
            keywords=["theme", "dark", "light"],
        ),
    ]

    dlg = CommandPaletteDialog(commands)
    assert dlg.list_widget.count() == 3

    # Filter by keyword
    dlg.search_input.setText("stitch")
    assert dlg.list_widget.count() == 1

    # Activate filtered item
    dlg._activate_current()
    assert executed == ["cmd2"]


def test_command_palette_delegate():
    commands = [
        CommandItem(
            id="test.cmd1",
            title="Undo Last Action",
            category="Action",
            callback=lambda: None,
            shortcut="Ctrl+Z",
        )
    ]
    dlg = CommandPaletteDialog(commands)
    delegate = dlg.list_widget.itemDelegate()
    assert isinstance(delegate, CommandItemDelegate)
