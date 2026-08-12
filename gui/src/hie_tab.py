"""Embeddable HIE editor tab backed by the shared middleware contracts."""

from __future__ import annotations

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from document import Document, FrameSequence
from pipeline import (
    PipelineSession,
    ProposalPipeline,
    RestorationPipeline,
    build_default_pipeline,
)

from viewport import HieViewport

IMAGE_FILE_FILTER = (
    "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff *.exr);;All files (*)"
)


class HieTab(QWidget):
    """Hybrid layer/node editing surface suitable for Image-Toolkit tabs."""

    status_changed = Signal(str)
    document_opened = Signal(str)

    def __init__(
        self,
        pipeline: ProposalPipeline | None = None,
        *,
        restoration: RestorationPipeline | None = None,
        session: PipelineSession | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        if session is not None:
            self.session = session
        else:
            untitled = Document(
                "untitled",
                FrameSequence.still(""),
                metadata={"source": "standalone"},
            )
            self.session = PipelineSession(
                untitled,
                pipeline=pipeline if pipeline is not None else build_default_pipeline(),
                restoration=restoration,
            )
        self._last_proposal = None

        # ─── Toolbar: document actions ──────────────────────────────────────
        title_label = QLabel("Hybrid Image Editor")
        title_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        self.open_image_button = QPushButton("Open Image…")
        self.open_image_button.setToolTip("Load a still image as a new HIE document")
        self.open_image_button.clicked.connect(self.open_image)

        toolbar = QHBoxLayout()
        toolbar.addWidget(title_label)
        toolbar.addStretch()
        toolbar.addWidget(self.open_image_button)

        self.document_status_label = QLabel("No document loaded")
        self.document_status_label.setStyleSheet("color: #8a97a6;")
        self.operation_status_label = QLabel("")
        self.operation_status_label.setStyleSheet("color: #8ed8df;")

        status_row = QHBoxLayout()
        status_row.addWidget(self.document_status_label)
        status_row.addStretch()
        status_row.addWidget(self.operation_status_label)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)

        # ─── Canvas ──────────────────────────────────────────────────────────
        self.viewport = HieViewport()
        self.viewport.show_status("Open an image or video sequence to begin")

        # ─── Sidebar: assistance controls, grouped ──────────────────────────
        self.tool_select = QComboBox()
        self.tool_select.addItems(["No assistance tools registered"])
        self.preview_button = QPushButton("Preview assistance")
        self.accept_button = QPushButton("Accept proposal")
        self.accept_button.setEnabled(False)
        self.preview_button.clicked.connect(self.preview_assistance)
        self.accept_button.clicked.connect(self.accept_proposal)

        assistance_group = QGroupBox("HIE Assistance")
        assistance_layout = QVBoxLayout(assistance_group)
        assistance_layout.addWidget(QLabel("Tool"))
        assistance_layout.addWidget(self.tool_select)
        assistance_layout.addWidget(self.preview_button)
        assistance_layout.addWidget(self.accept_button)

        self.restoration_select = QComboBox()
        self.restoration_select.addItems(["No restoration backends"])
        self.restoration_button = QPushButton("Queue restoration preview")
        self.restoration_button.clicked.connect(self.queue_restoration_preview)

        restoration_group = QGroupBox("Restoration")
        restoration_layout = QVBoxLayout(restoration_group)
        restoration_layout.addWidget(QLabel("Operation / backend"))
        restoration_layout.addWidget(self.restoration_select)
        restoration_layout.addWidget(self.restoration_button)

        sidebar = QWidget()
        sidebar.setMinimumWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(assistance_group)
        sidebar_layout.addWidget(restoration_group)
        sidebar_layout.addStretch()

        splitter = QSplitter()
        splitter.addWidget(self.viewport)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([760, 240])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addLayout(toolbar)
        layout.addLayout(status_row)
        layout.addWidget(divider)
        layout.addWidget(splitter)

        self.refresh_capabilities()

    @property
    def pipeline(self) -> ProposalPipeline:
        return self.session.pipeline

    @property
    def _history(self):
        """Compatibility alias used by existing GUI tests and host hooks."""
        return self.session.history

    def open_image(self) -> None:
        """Prompt for an image file and load it as a new HIE document."""
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, "Open Image", "", IMAGE_FILE_FILTER
        )
        if not path:
            return
        self.load_image_path(path)

    def load_image_path(self, path: str) -> bool:
        """Load `path` into the viewport and start a fresh document history for it.

        Returns whether the image loaded successfully — callers (e.g. a host
        application opening a file from elsewhere) can check this without
        going through the file dialog in `open_image`.
        """
        if not self.viewport.load_image(path):
            self._set_status(f"Failed to open image: {path}")
            return False

        document = Document(
            os.path.basename(path) or path,
            FrameSequence.still(path),
            metadata={"source": path},
        )
        self.session = PipelineSession(
            document,
            pipeline=self.session.pipeline,
            restoration=self.session.restoration,
        )
        self._last_proposal = None
        self.accept_button.setEnabled(False)
        self.document_status_label.setText(os.path.basename(path))
        self.document_status_label.setToolTip(path)
        self._set_status(f"Opened {os.path.basename(path)}")
        self.document_opened.emit(path)
        return True

    def refresh_capabilities(self) -> None:
        capabilities = self.session.pipeline.capabilities()
        self.tool_select.clear()
        policies = capabilities["policies"]
        self.tool_select.addItems(policies or ["No assistance tools registered"])

        restoration = self.session.restoration.capabilities()
        self.restoration_select.clear()
        labels: list[str] = []
        for operation, backends in restoration.items():
            for backend in backends:
                labels.append(f"{operation} / {backend}")
        self.restoration_select.addItems(labels or ["No restoration backends"])
        self.restoration_button.setEnabled(bool(labels))

        self.status_changed.emit(
            f"{len(capabilities['models'])} models · {len(policies)} policies · "
            f"{len(labels)} restoration paths"
        )

    def preview_assistance(self) -> None:
        name = self.tool_select.currentText()
        if name == "No assistance tools registered":
            self._set_status("Register a policy before requesting assistance")
            return
        self._last_proposal = self.session.preview_policy(name, {"source": "hie-gui"})
        self.accept_button.setEnabled(True)
        action = self._last_proposal.proposal.action
        self._set_status(f"Preview ready: {action} (accept to record)")

    def accept_proposal(self) -> None:
        if self._last_proposal is None:
            self._set_status("Preview a proposal before accepting")
            return
        self.session.accept(self._last_proposal)
        self.accept_button.setEnabled(False)
        self._last_proposal = None
        self._set_status("Proposal accepted and added to document history")

    def queue_restoration_preview(self) -> None:
        """Submit a cancellable restoration job for the active document source."""
        label = self.restoration_select.currentText()
        if label == "No restoration backends" or " / " not in label:
            self._set_status("No restoration backend selected")
            return
        operation, backend = label.split(" / ", 1)
        source = self.session.document.metadata.get("source") or ""
        if not source or source == "standalone":
            self._set_status("Open an image before queuing restoration")
            return
        handle = self.session.submit_restoration(
            operation, source, backend=backend, options={}
        )
        self._set_status(
            f"Queued {operation} ({backend}) job {handle.job_id} — cancellable preview"
        )

    def set_history(self, history) -> None:
        """Attach host-supplied document history while keeping the same pipelines."""
        self.session = PipelineSession(
            history.current,
            pipeline=self.session.pipeline,
            restoration=self.session.restoration,
        )
        # Preserve undo stack by swapping history after construction.
        self.session.history = history

    def _set_status(self, message: str) -> None:
        """Report an operation status without clearing the canvas."""
        self.operation_status_label.setText(message)
        self.status_changed.emit(message)
