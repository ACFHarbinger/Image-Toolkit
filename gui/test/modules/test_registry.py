"""Tests for ModuleDescriptor and ModuleRegistry (§2.36)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from gui.src.modules.descriptor import ModuleCategory, ModuleDescriptor
from gui.src.modules.registry import ModuleRegistry


class TestModuleRegistry:
    def test_register_and_lookup(self):
        reg = ModuleRegistry()
        reg.clear()

        m1 = ModuleDescriptor(
            id="test.tool1",
            title="Test Tool 1",
            category=ModuleCategory.SYSTEM,
            japanese_subtext="テスト1",
            view_factory=lambda: QLabel("View 1"),
        )
        m2 = ModuleDescriptor(
            id="test.tool2",
            title="Test Tool 2",
            category=ModuleCategory.LIBRARY,
            japanese_subtext="テスト2",
            view_factory=lambda: QLabel("View 2"),
        )

        reg.register(m1)
        reg.register(m2)

        assert reg.get("test.tool1") is m1
        assert reg.get("test.tool2") is m2
        assert len(reg.all_modules()) == 2
        assert reg.categories() == [ModuleCategory.SYSTEM, ModuleCategory.LIBRARY]
        assert reg.by_category(ModuleCategory.SYSTEM) == [m1]

    def test_lazy_widget_instantiation(self, q_app):
        reg = ModuleRegistry()
        reg.clear()

        created = []
        def _factory():
            w = QLabel("Created")
            created.append(w)
            return w

        desc = ModuleDescriptor(
            id="lazy.tool",
            title="Lazy Tool",
            category=ModuleCategory.WEB,
            view_factory=_factory,
        )
        assert len(created) == 0
        w = desc.get_widget()
        assert len(created) == 1
        assert desc.get_widget() is w  # cached instance

    def test_search(self):
        reg = ModuleRegistry()
        reg.clear()

        desc = ModuleDescriptor(
            id="library.search",
            title="Image Search",
            category=ModuleCategory.LIBRARY,
            japanese_subtext="画像検索",
        )
        reg.register(desc)

        assert reg.search("image") == [desc]
        assert reg.search("検索") == [desc]
        assert reg.search("database") == [desc]
        assert reg.search("nonexistent") == []
