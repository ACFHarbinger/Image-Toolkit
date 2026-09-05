"""Undo/Redo command infrastructure for file operations and gallery edits (§2.15)."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack


def get_default_trash_dir() -> Path:
    """Return session trash directory path."""
    override = os.environ.get("IMAGE_TOOLKIT_TRASH_DIR")
    p = Path(override) if override else Path.home() / ".image-toolkit" / "trash"
    p.mkdir(parents=True, exist_ok=True)
    return p


class FileDeletionCommand(QUndoCommand):
    """Undoable command that moves files to a session trash buffer on deletion and restores on undo."""

    def __init__(
        self,
        paths: List[str],
        trash_dir: Optional[Path] = None,
        on_restored: Optional[Callable[[List[str]], None]] = None,
        on_deleted: Optional[Callable[[List[str]], None]] = None,
        description: str = "Delete Files",
    ) -> None:
        super().__init__(description)
        self.original_paths = [str(p) for p in paths if os.path.exists(p)]
        self._trash_dir = trash_dir or get_default_trash_dir()
        self._batch_id = uuid.uuid4().hex[:8]
        self._batch_trash_folder = self._trash_dir / self._batch_id
        self._moved_pairs: List[Tuple[str, str]] = []  # (original, trash_location)
        self._on_restored = on_restored
        self._on_deleted = on_deleted
        self._executed = False

    def redo(self) -> None:
        """Move files to session trash."""
        self._batch_trash_folder.mkdir(parents=True, exist_ok=True)
        self._moved_pairs.clear()
        deleted: List[str] = []

        for orig in self.original_paths:
            if os.path.exists(orig):
                name = os.path.basename(orig)
                dest = str(self._batch_trash_folder / name)
                # Handle filename collisions in same batch
                if os.path.exists(dest):
                    dest = str(self._batch_trash_folder / f"{uuid.uuid4().hex[:4]}_{name}")
                try:
                    shutil.move(orig, dest)
                    self._moved_pairs.append((orig, dest))
                    deleted.append(orig)
                except Exception as e:
                    print(f"[UndoManager] Failed to move {orig} to trash: {e}")

        self._executed = True
        if self._on_deleted is not None and deleted:
            self._on_deleted(deleted)

    def undo(self) -> None:
        """Restore files from session trash to original locations."""
        restored: List[str] = []
        for orig, trash_loc in self._moved_pairs:
            if os.path.exists(trash_loc):
                parent = Path(orig).parent
                parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.move(trash_loc, orig)
                    restored.append(orig)
                except Exception as e:
                    print(f"[UndoManager] Failed to restore {trash_loc} -> {orig}: {e}")

        # Clean up batch trash folder if empty
        try:
            if self._batch_trash_folder.exists() and not any(self._batch_trash_folder.iterdir()):
                self._batch_trash_folder.rmdir()
        except Exception:
            pass

        if self._on_restored is not None and restored:
            self._on_restored(restored)


class FileRenameCommand(QUndoCommand):
    """Undoable command for file renaming (§2.26)."""

    def __init__(
        self,
        old_path: str,
        new_path: str,
        on_renamed: Optional[Callable[[str, str], None]] = None,
        description: str = "Rename File",
    ) -> None:
        super().__init__(description)
        self.old_path = old_path
        self.new_path = new_path
        self._on_renamed = on_renamed

    def redo(self) -> None:
        if os.path.exists(self.old_path) and not os.path.exists(self.new_path):
            shutil.move(self.old_path, self.new_path)
            if self._on_renamed:
                self._on_renamed(self.old_path, self.new_path)

    def undo(self) -> None:
        if os.path.exists(self.new_path) and not os.path.exists(self.old_path):
            shutil.move(self.new_path, self.old_path)
            if self._on_renamed:
                self._on_renamed(self.new_path, self.old_path)


class UndoManager(QObject):
    """Central manager coordinating the application's QUndoStack and file operations."""

    can_undo_changed = Signal(bool)
    can_redo_changed = Signal(bool)
    undo_performed = Signal(str)
    redo_performed = Signal(str)

    _instance: Optional[UndoManager] = None

    def __init__(self, parent: Optional[QObject] = None, undo_limit: int = 50) -> None:
        super().__init__(parent)
        self.stack = QUndoStack(self)
        self.stack.setUndoLimit(undo_limit)
        self.stack.canUndoChanged.connect(self.can_undo_changed)
        self.stack.canRedoChanged.connect(self.can_redo_changed)

    @classmethod
    def instance(cls) -> UndoManager:
        if cls._instance is None:
            cls._instance = UndoManager()
        return cls._instance

    @classmethod
    def set_instance(cls, mgr: Optional[UndoManager]) -> None:
        cls._instance = mgr

    def push(self, cmd: QUndoCommand) -> None:
        self.stack.push(cmd)

    def undo(self) -> bool:
        if self.stack.canUndo():
            text = self.stack.undoText()
            self.stack.undo()
            self.undo_performed.emit(text)
            return True
        return False

    def redo(self) -> bool:
        if self.stack.canRedo():
            text = self.stack.redoText()
            self.stack.redo()
            self.redo_performed.emit(text)
            return True
        return False

    def can_undo(self) -> bool:
        return self.stack.canUndo()

    def can_redo(self) -> bool:
        return self.stack.canRedo()

    def undo_text(self) -> str:
        return self.stack.undoText()

    def redo_text(self) -> str:
        return self.stack.redoText()

    def delete_files_undoable(
        self,
        paths: List[str],
        trash_dir: Optional[Path] = None,
        on_restored: Optional[Callable[[List[str]], None]] = None,
        on_deleted: Optional[Callable[[List[str]], None]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Create and push an undoable file deletion command."""
        desc = description or f"Delete {len(paths)} file{'s' if len(paths) != 1 else ''}"
        cmd = FileDeletionCommand(
            paths=paths,
            trash_dir=trash_dir,
            on_restored=on_restored,
            on_deleted=on_deleted,
            description=desc,
        )
        self.push(cmd)

    def rename_file_undoable(
        self,
        old_path: str,
        new_path: str,
        on_renamed: Optional[Callable[[str, str], None]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Create and push an undoable file rename command."""
        desc = description or f"Rename {os.path.basename(old_path)} -> {os.path.basename(new_path)}"
        cmd = FileRenameCommand(
            old_path=old_path,
            new_path=new_path,
            on_renamed=on_renamed,
            description=desc,
        )
        self.push(cmd)

    def clear_trash(self, trash_dir: Optional[Path] = None) -> None:
        """Purge session trash directory contents."""
        target = trash_dir or get_default_trash_dir()
        if target.exists():
            for child in target.iterdir():
                try:
                    if child.is_dir():
                        shutil.rmtree(child)
                    else:
                        child.unlink()
                except Exception as e:
                    print(f"[UndoManager] Could not delete trash item {child}: {e}")


__all__ = [
    "FileDeletionCommand",
    "FileRenameCommand",
    "UndoManager",
    "get_default_trash_dir",
]
