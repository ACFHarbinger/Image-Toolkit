"""Tests for BilingualHeader component (§2.37, #505)."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QWidget

from gui.src.components.labels.bilingual_header import BilingualHeader

pytestmark = pytest.mark.gui


class TestBilingualHeader:
    def test_header_creation_with_subtext(self, q_app):
        header = BilingualHeader(title="LIBRARY DATABASE", japanese_subtext="ライブラリ", level=1)
        assert header.title_label.text() == "LIBRARY DATABASE"
        assert header.sub_label is not None
        assert "ライブラリ" in header.sub_label.text()
        assert header.accent_bar is not None

    def test_header_creation_without_subtext(self, q_app):
        header = BilingualHeader(title="SETTINGS", show_accent_bar=False)
        assert header.title_label.text() == "SETTINGS"
        assert header.sub_label is None
        assert not hasattr(header, "accent_bar")

    def test_set_text(self, q_app):
        header = BilingualHeader(title="ORIGINAL", japanese_subtext="元")
        header.set_text("UPDATED", "更新")
        assert header.title_label.text() == "UPDATED"
        assert "更新" in header.sub_label.text()
