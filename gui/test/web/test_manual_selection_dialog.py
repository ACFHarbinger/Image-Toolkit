import os
from PySide6.QtWidgets import QWidget, QLineEdit
from gui.src.components.dialogs.crawler_selection_dialogs import ManualSelectionDialog


def test_manual_selection_dialog_card_states_and_paths(tmp_path):
    # Create two test image files on disk
    img1 = tmp_path / "img1.jpeg"
    img2 = tmp_path / "img2.jpeg"
    img1.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00")
    img2.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00")

    items = [
        {"path": str(img1) + "?query=1", "page_url": "https://example.com/1", "page_num": 1, "index_on_page": 1},
        {"path": str(img2) + "?query=2", "page_url": "https://example.com/2", "page_num": 1, "index_on_page": 2},
    ]

    parent = QWidget()
    parent.download_dir_path = QLineEdit()
    parent.download_dir_path.setText(str(tmp_path))

    dialog = ManualSelectionDialog(items, parent=parent)

    # Initial state: Both cards are KEEP (is_kept = True)
    assert len(dialog.cards) == 2
    assert dialog.cards[0].is_kept is True
    assert dialog.cards[1].is_kept is True
    assert set(dialog.get_kept_paths()) == {str(img1), str(img2)}
    assert dialog.get_pruned_paths() == []

    # Toggle card 1 to DISCARD (is_kept = False)
    dialog.cards[1].set_kept(False)

    assert dialog.cards[1].is_kept is False
    assert dialog.get_kept_paths() == [str(img1)]
    assert dialog.get_pruned_paths() == [str(img2)]

    # Test Select All / Deselect All
    dialog.deselect_all()
    assert dialog.get_kept_paths() == []
    assert set(dialog.get_pruned_paths()) == {str(img1), str(img2)}

    dialog.select_all()
    assert set(dialog.get_kept_paths()) == {str(img1), str(img2)}
    assert dialog.get_pruned_paths() == []


def test_manual_selection_dialog_skip_first_pre_marking(tmp_path):
    img1 = tmp_path / "img1.jpeg"
    img2 = tmp_path / "img2.jpeg"
    img3 = tmp_path / "img3.jpeg"
    for img in (img1, img2, img3):
        img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00")

    items = [
        {"path": str(img1), "index_on_page": 1},
        {"path": str(img2), "index_on_page": 2},
        {"path": str(img3), "index_on_page": 3},
    ]

    parent = QWidget()
    parent.download_dir_path = QLineEdit()
    parent.download_dir_path.setText(str(tmp_path))

    # Open dialog with skip_first=2
    dialog = ManualSelectionDialog(items, parent=parent, skip_first=2)

    # Card 0 (index 1) and Card 1 (index 2) must be DISCARD, Card 2 (index 3) must be KEEP
    assert dialog.cards[0].is_kept is False
    assert dialog.cards[1].is_kept is False
    assert dialog.cards[2].is_kept is True

    assert set(dialog.get_pruned_paths()) == {str(img1), str(img2)}
    assert dialog.get_kept_paths() == [str(img3)]

