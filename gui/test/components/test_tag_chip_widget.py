"""Unit tests for TagChipWidget and TagChipGroup components (§2.22 Option A)."""

import pytest
from gui.src.components.tag_chip_widget import TagChipGroup, TagChipWidget


@pytest.mark.gui
def test_tag_chip_widget_toggle(q_app):
    chip = TagChipWidget("landscape", active=False)

    assert not chip.is_active()

    chip.set_active(True)
    assert chip.is_active()


@pytest.mark.gui
def test_tag_chip_group_selection(q_app):
    group = TagChipGroup()

    tags = ["cat", "dog", "bird"]
    group.set_tags(tags, selected=["cat"])

    assert group.get_selected_tags() == ["cat"]

    # Toggle dog chip
    group._chips[1].set_active(True)
    assert sorted(group.get_selected_tags()) == ["cat", "dog"]

    # Remove bird chip
    group.remove_tag("bird")
    assert [c.tag_text for c in group._chips] == ["cat", "dog"]


@pytest.mark.gui
def test_tag_chip_group_and_editor_matches_query(q_app):
    from gui.src.components.tag_chip_widget import TagChipEditor

    group = TagChipGroup()
    group.set_tags(["solo", "1girl", "blue_eyes"], selected=["solo", "1girl"])
    assert group.matches_query("solo AND 1girl") is True
    assert group.matches_query("solo AND blue_eyes") is False  # blue_eyes not selected in group
    assert group.matches_query("solo -chibi") is True

    editor = TagChipEditor()
    editor.setText("solo, 1girl, blue_eyes")
    assert editor.tags() == ["solo", "1girl", "blue_eyes"]
    assert editor.matches_query("solo (blue_eyes OR red_eyes) -chibi") is True
    assert editor.matches_query("solo AND chibi") is False


