"""
Command Palette / Quick Launcher Mixin (GUI/UX §2.16).

Binds Ctrl+K to open a floating CommandPaletteDialog populated with all
navigable tabs/modules, app actions, and keyboard shortcuts.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer

from ...components.dialogs.command_palette_dialog import CommandItem, CommandPaletteDialog
from ...utils.undo_manager import UndoManager


class _CommandPaletteMixin:
    """Provides the floating command palette launcher."""

    def _open_command_palette(self) -> None:
        items: list[CommandItem] = []

        # 1. Navigation items
        if getattr(self, "_using_runtime_shell", False) and hasattr(self, "module_catalog"):
            for category in self.module_catalog.categories():
                for descriptor in self.module_catalog.navigable_by_category(category):
                    mod_id = descriptor.module_id
                    title = f"Go to: {descriptor.title} ({category.value})"
                    items.append(
                        CommandItem(
                            id=f"nav.{mod_id}",
                            title=title,
                            category="Navigation",
                            callback=lambda m=mod_id: self.shell_layout_manager.activate_module(m),
                            keywords=[descriptor.title, category.value, mod_id],
                        )
                    )
        elif hasattr(self, "all_tabs"):
            for category, tab_names in self.all_tabs.items():
                for tab_name in tab_names:
                    cat = category
                    name = tab_name
                    items.append(
                        CommandItem(
                            id=f"nav.{cat}.{name}",
                            title=f"Go to: {name} ({cat})",
                            category="Navigation",
                            callback=lambda c=cat, t=name: self._navigate_to_tab(c, t),
                            keywords=[name, cat],
                        )
                    )

        # 2. General App Actions
        if hasattr(self, "toggle_theme"):
            items.append(
                CommandItem(
                    id="action.theme_toggle",
                    title="Appearance: Toggle Theme (Dark / Light)",
                    category="Action",
                    callback=self.toggle_theme,
                    keywords=["theme", "dark", "light", "color", "appearance"],
                )
            )

        if hasattr(self, "_open_shortcut_overlay"):
            items.append(
                CommandItem(
                    id="action.shortcuts_overlay",
                    title="Help: Keyboard Shortcuts Cheat Sheet",
                    category="Action",
                    shortcut="Ctrl+/",
                    callback=self._open_shortcut_overlay,
                    keywords=["shortcuts", "keys", "hotkeys", "help"],
                )
            )

        if hasattr(self, "_open_global_search"):
            items.append(
                CommandItem(
                    id="action.global_search",
                    title="Search: Global Cross-Gallery Search",
                    category="Action",
                    shortcut="Ctrl+Shift+F",
                    callback=self._open_global_search,
                    keywords=["find", "search", "gallery", "image"],
                )
            )

        if hasattr(self, "_open_workflow_templates_dialog"):
            items.append(
                CommandItem(
                    id="action.workflow_templates",
                    title="Workflow: Templates Manager",
                    category="Action",
                    shortcut="Ctrl+Shift+M",
                    callback=self._open_workflow_templates_dialog,
                    keywords=["workflow", "template", "preset", "batch"],
                )
            )

        items.append(
            CommandItem(
                id="action.undo",
                title="Edit: Undo Last Operation",
                category="Action",
                shortcut="Ctrl+Z",
                callback=lambda: UndoManager.instance().undo(),
                keywords=["undo", "revert", "delete"],
            )
        )

        items.append(
            CommandItem(
                id="action.redo",
                title="Edit: Redo Operation",
                category="Action",
                shortcut="Ctrl+Shift+Z",
                callback=lambda: UndoManager.instance().redo(),
                keywords=["redo", "restore"],
            )
        )

        dlg = CommandPaletteDialog(items, parent=self)
        dlg.exec()

    def _navigate_to_tab(self, category: str, tab_name: str) -> None:
        if hasattr(self, "command_combo"):
            self.command_combo.setCurrentText(category)
        QTimer.singleShot(0, lambda: self._select_tab_by_name(tab_name))


__all__ = ["_CommandPaletteMixin"]
