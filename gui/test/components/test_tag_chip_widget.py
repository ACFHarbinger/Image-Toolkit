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

