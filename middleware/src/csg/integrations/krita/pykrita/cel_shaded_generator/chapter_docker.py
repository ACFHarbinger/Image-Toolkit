"""Separate offline Krita Docker for the batch chapter review queue."""

from __future__ import annotations

import uuid
from pathlib import Path

from krita import DockWidget, Krita
from PyQt5.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .engine_client import EngineClient
from .engine_worker import WorkerBusyMixin


class ChapterQueueDocker(WorkerBusyMixin, DockWidget):
    """Track a batch chapter's page review queue and navigate between pages.

    Execution-agnostic project state (roadmap milestone 6, issue #22) drives
    this Docker; it only opens pages and reports status transitions back,
    never inferring correspondence across pages.

    Every engine round trip runs on an EngineWorker (issue #23) so the engine
    subprocess call never blocks Krita's UI thread; the action buttons are
    disabled for the duration and failures land in the status label.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chapter Queue")
        container = QWidget(self)
        layout = QVBoxLayout(container)
        self._status = QLabel("Bind a portable project to begin.", container)
        self._status.setWordWrap(True)
        actions = (
            ("Bind Portable Project", self._bind_project),
            ("Add Page to Chapter", self._add_page),
            ("Open Next Pending Page", self._open_next_pending),
            ("Mark Active Page Reviewed", lambda: self._set_active_page_status("reviewed")),
            ("Mark Active Page Accepted", lambda: self._set_active_page_status("accepted")),
            ("Refresh Queue", self._refresh_queue),
        )
        self._buttons = []
        for label, callback in actions:
            button = QPushButton(label, container)
            button.clicked.connect(callback)
            layout.addWidget(button)
            self._buttons.append(button)
        layout.addWidget(self._status)
        self.setWidget(container)
        self._project_directory = None
        self._init_worker_state(self._buttons)

    def _bind_project(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Portable Project")
        if not directory:
            return
        if not (Path(directory) / "project.json").is_file():
            self._status.setText("Selected directory has no portable project.json.")
            return
        self._project_directory = directory
        self._refresh_queue()

    def _add_page(self):
        if self._project_directory is None:
            self._status.setText("Bind a portable project first.")
            return
        source, _ = QFileDialog.getOpenFileName(
            self, "Add Page", self._project_directory, "Krita Documents (*.kra)"
        )
        if not source:
            return
        relative = self._relative_to_project(source)
        if relative is None:
            self._status.setText("Page must already be inside the bound project directory.")
            return
        panel_id = self._text("Add Page", "Panel id (kebab-case):", Path(source).stem)
        if panel_id is None:
            return
        project_directory = self._project_directory
        self._run_worker(
            lambda: EngineClient().add_chapter_page(
                str(uuid.uuid4()), project_directory, relative, panel_id
            ),
            lambda _result: self._refresh_queue(),
            "Could not add chapter page: ",
        )

    def _open_next_pending(self):
        if self._project_directory is None:
            self._status.setText("Bind a portable project first.")
            return
        project_directory = self._project_directory
        self._run_worker(
            lambda: EngineClient().next_pending_chapter_page(
                str(uuid.uuid4()), project_directory
            ),
            self._open_pending_page,
            "Could not read the chapter queue: ",
        )

    def _open_pending_page(self, page):
        if page.get("page_id") is None:
            self._status.setText("No pending pages; the chapter queue is empty or complete.")
            return
        application = Krita.instance()
        window = application.activeWindow()
        if window is None:
            self._status.setText("Krita needs an active window to open a page.")
            return
        absolute_path = str(Path(self._project_directory) / page["document_asset"])
        document = application.openDocument(absolute_path)
        if document is None:
            self._status.setText("Krita could not open " + page["document_asset"])
            return
        window.addView(document)
        project_directory = self._project_directory
        page_id = page["page_id"]
        document_asset = page["document_asset"]
        panel_id = page["panel_id"]
        self._run_worker(
            lambda: EngineClient().set_chapter_page_status(
                str(uuid.uuid4()), project_directory, page_id, "in_progress"
            ),
            lambda _result: self._status.setText(
                f"Opened {document_asset} (panel {panel_id})."
            ),
            "Opened the page but could not update its status: ",
        )

    def _set_active_page_status(self, status):
        if self._project_directory is None:
            self._status.setText("Bind a portable project first.")
            return
        document = Krita.instance().activeDocument()
        if document is None or not document.fileName():
            self._status.setText("Open a saved chapter page document first.")
            return
        relative = self._relative_to_project(document.fileName())
        if relative is None:
            self._status.setText("The active document is not inside the bound project.")
            return
        project_directory = self._project_directory
        self._run_worker(
            lambda: EngineClient().project_progress_snapshot(
                str(uuid.uuid4()), project_directory
            ),
            lambda snapshot: self._mark_page_status(snapshot, relative, status),
            "Could not read the chapter queue: ",
        )

    def _mark_page_status(self, snapshot, relative, status):
        matching = [
            entry
            for entry in snapshot.get("chapter", {}).get("pages", [])
            if entry["document_asset"] == relative
        ]
        if len(matching) != 1:
            self._status.setText("Active document is not a page in the bound chapter.")
            return
        project_directory = self._project_directory
        page_id = matching[0]["page_id"]
        self._run_worker(
            lambda: EngineClient().set_chapter_page_status(
                str(uuid.uuid4()), project_directory, page_id, status
            ),
            lambda _result: self._refresh_queue(),
            "Could not update the page status: ",
        )

    def _refresh_queue(self):
        if self._project_directory is None:
            self._status.setText("Bind a portable project first.")
            return
        project_directory = self._project_directory
        self._run_worker(
            lambda: EngineClient().project_progress_snapshot(
                str(uuid.uuid4()), project_directory
            ),
            self._show_queue_snapshot,
            "Could not read project: ",
        )

    def _show_queue_snapshot(self, snapshot):
        chapter = snapshot.get("chapter", {})
        pages = chapter.get("pages", [])
        accepted = sum(1 for page in pages if page["status"] == "accepted")
        self._status.setText(
            f"Chapter has {len(pages)} page(s), {accepted} accepted. "
            f"Next pending: {chapter.get('next_pending_page_id') or 'none'}."
        )

    def _relative_to_project(self, path):
        try:
            relative = Path(path).resolve().relative_to(Path(self._project_directory).resolve())
        except ValueError:
            return None
        # .as_posix(), not str(): on Windows the latter yields backslashes,
        # which the engine's document_asset validation always rejects, and
        # which can never match the POSIX-stored path when matching the
        # active document back to its chapter-page record.
        return relative.as_posix()

    def _text(self, title, prompt, default=""):
        value, accepted = QInputDialog.getText(self, title, prompt, QLineEdit.Normal, default)
        if not accepted:
            return None
        value = value.strip()
        return value if value else None

    def canvasChanged(self, canvas) -> None:  # noqa: N802
        """Krita callback; this docker does not inspect the canvas."""
