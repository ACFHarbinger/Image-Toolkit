"""Embeddable HIE editor tab backed by the shared middleware contracts."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from hie_middleware.document import Document, DocumentHistory, FrameSequence
from hie_middleware.pipeline import (
    ProposalAcceptanceService,
    ProposalPipeline,
    build_default_pipeline,
)

from .viewport import HieViewport


class HieTab(QWidget):
    """Hybrid layer/node editing surface suitable for Image-Toolkit tabs."""

    status_changed = Signal(str)

    def __init__(self, pipeline: ProposalPipeline | None = None, parent=None) -> None:
        super().__init__(parent)
        self.pipeline = pipeline if pipeline is not None else build_default_pipeline()
        self._last_proposal = None
        self._history = DocumentHistory(
            Document("untitled", FrameSequence.still(""), metadata={"source": "standalone"})
        )

        self.viewport = HieViewport()
        self.viewport.show_status("Open an image or video sequence to begin")
        self.tool_select = QComboBox()
        self.tool_select.addItems(["No assistance tools registered"])
        self.preview_button = QPushButton("Preview assistance")
        self.accept_button = QPushButton("Accept proposal")
        self.accept_button.setEnabled(False)
        self.preview_button.clicked.connect(self.preview_assistance)
        self.accept_button.clicked.connect(self.accept_proposal)

        sidebar = QWidget()
        controls = QVBoxLayout(sidebar)
        controls.addWidget(QLabel("HIE assistance"))
        controls.addWidget(self.tool_select)
        controls.addWidget(self.preview_button)
        controls.addWidget(self.accept_button)
        controls.addStretch()

        splitter = QSplitter()
        splitter.addWidget(self.viewport)
        splitter.addWidget(sidebar)
        splitter.setStretchFactor(0, 1)
        splitter.setSizes([720, 220])

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Hybrid Image Editor"))
        layout.addWidget(splitter)
        self.refresh_capabilities()

    def refresh_capabilities(self) -> None:
        capabilities = self.pipeline.capabilities()
        self.tool_select.clear()
        policies = capabilities["policies"]
        self.tool_select.addItems(policies or ["No assistance tools registered"])
        self.status_changed.emit(
            f"{len(capabilities['models'])} models · {len(policies)} policies available"
        )

    def preview_assistance(self) -> None:
        name = self.tool_select.currentText()
        if name == "No assistance tools registered":
            self._set_status("Register a policy before requesting assistance")
            return
        self._last_proposal = self.pipeline.policy_proposal(name, {"source": "hie-gui"})
        self.accept_button.setEnabled(True)
        action = self._last_proposal.proposal.action
        self._set_status(f"Preview ready: {action} (accept to record)")

    def accept_proposal(self) -> None:
        if self._last_proposal is None or self._history is None:
            self._set_status("Create a document history before accepting a proposal")
            return
        ProposalAcceptanceService().accept(self._history, self._last_proposal)
        self.accept_button.setEnabled(False)
        self._set_status("Proposal accepted and added to document history")

    def set_history(self, history) -> None:
        """Attach the active document history supplied by the host application."""
        self._history = history

    def _set_status(self, message: str) -> None:
        self.viewport.show_status(message)
        self.status_changed.emit(message)
