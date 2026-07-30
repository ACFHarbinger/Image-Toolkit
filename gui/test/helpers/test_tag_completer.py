"""Unit tests for TagCompleter helper (§2.22 Option D)."""

import pytest
from PySide6.QtWidgets import QLineEdit
from gui.src.helpers.core.tag_completer import TagCompleter


@pytest.mark.gui
def test_tag_completer_matching(q_app):
    tags = ["blue_hair", "blue_eyes", "red_hair", "sword"]
    completer = TagCompleter(tags)

    matches = completer.get_matching_tags("blue")
    assert sorted(matches) == ["blue_eyes", "blue_hair"]

    matches_r = completer.get_matching_tags("red")
    assert matches_r == ["red_hair"]

    completer.add_tag("shield")
    assert "shield" in completer.get_matching_tags("s")


@pytest.mark.gui
def test_tag_completer_line_edit_activation(q_app):
    line_edit = QLineEdit()

    tags = ["blue_hair", "red_eyes", "scenery"]
    completer = TagCompleter(tags, line_edit)

    line_edit.setText("scenery, bl")
    completer._on_tag_activated(line_edit, "blue_hair")

    assert line_edit.text() == "scenery, blue_hair, "

