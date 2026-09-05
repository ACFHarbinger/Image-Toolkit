import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from gui.src.utils.undo_manager import (
    FileDeletionCommand,
    FileRenameCommand,
    UndoManager,
)

# Ensure QApplication exists
if not QApplication.instance():
    app = QApplication(sys.argv)


def test_file_deletion_command_undo_redo(tmp_path: Path):
    data_dir = tmp_path / "data"
    trash_dir = tmp_path / "trash"
    data_dir.mkdir()
    trash_dir.mkdir()

    f1 = data_dir / "img1.png"
    f2 = data_dir / "img2.png"
    f1.write_text("image 1 content")
    f2.write_text("image 2 content")

    deleted_cb_calls: list[list[str]] = []
    restored_cb_calls: list[list[str]] = []

    cmd = FileDeletionCommand(
        paths=[str(f1), str(f2)],
        trash_dir=trash_dir,
        on_deleted=lambda paths: deleted_cb_calls.append(paths),
        on_restored=lambda paths: restored_cb_calls.append(paths),
    )

    # Initial Redo (move to trash)
    cmd.redo()
    assert not f1.exists()
    assert not f2.exists()
    assert len(deleted_cb_calls) == 1
    assert str(f1) in deleted_cb_calls[0]
    assert str(f2) in deleted_cb_calls[0]

    # Undo (restore to original location)
    cmd.undo()
    assert f1.exists()
    assert f2.exists()
    assert f1.read_text() == "image 1 content"
    assert f2.read_text() == "image 2 content"
    assert len(restored_cb_calls) == 1

    # Redo again
    cmd.redo()
    assert not f1.exists()
    assert not f2.exists()


def test_file_rename_command_undo_redo(tmp_path: Path):
    orig = tmp_path / "original.txt"
    renamed = tmp_path / "renamed.txt"
    orig.write_text("sample content")

    renamed_cb_calls: list[tuple[str, str]] = []

    cmd = FileRenameCommand(
        old_path=str(orig),
        new_path=str(renamed),
        on_renamed=lambda old, new: renamed_cb_calls.append((old, new)),
    )

    cmd.redo()
    assert not orig.exists()
    assert renamed.exists()
    assert renamed.read_text() == "sample content"
    assert renamed_cb_calls == [(str(orig), str(renamed))]

    cmd.undo()
    assert orig.exists()
    assert not renamed.exists()
    assert orig.read_text() == "sample content"
    assert renamed_cb_calls == [(str(orig), str(renamed)), (str(renamed), str(orig))]


def test_undo_manager_signals_and_stack(tmp_path: Path):
    mgr = UndoManager()
    trash_dir = tmp_path / "trash"
    trash_dir.mkdir()

    f1 = tmp_path / "sample.png"
    f1.write_text("hello")

    can_undo_states: list[bool] = []
    can_redo_states: list[bool] = []
    undo_texts: list[str] = []

    mgr.can_undo_changed.connect(lambda s: can_undo_states.append(s))
    mgr.can_redo_changed.connect(lambda s: can_redo_states.append(s))
    mgr.undo_performed.connect(lambda t: undo_texts.append(t))

    mgr.delete_files_undoable([str(f1)], trash_dir=trash_dir, description="Delete sample.png")
    assert not f1.exists()
    assert mgr.can_undo()
    assert not mgr.can_redo()
    assert "Delete sample.png" in mgr.undo_text()

    # Undo
    assert mgr.undo()
    assert f1.exists()
    assert not mgr.can_undo()
    assert mgr.can_redo()
    assert "Delete sample.png" in undo_texts[0]

    # Redo
    assert mgr.redo()
    assert not f1.exists()
    assert mgr.can_undo()
    assert not mgr.can_redo()


def test_undo_manager_clear_trash(tmp_path: Path):
    mgr = UndoManager()
    trash_dir = tmp_path / "trash"
    trash_dir.mkdir()

    batch_dir = trash_dir / "batch123"
    batch_dir.mkdir()
    (batch_dir / "test.png").write_text("trash data")

    assert any(trash_dir.iterdir())
    mgr.clear_trash(trash_dir=trash_dir)
    assert not any(trash_dir.iterdir())
