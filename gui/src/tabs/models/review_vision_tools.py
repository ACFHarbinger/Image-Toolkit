"""Standalone Review OCR and VLM actions (#750).

The file read and the model call run on a worker. Widgets are updated
only from the signals below. A cloud call stays disabled until the user
approves the departure preview.
"""
from __future__ import annotations

import threading
from pathlib import Path

from backend.src.core.guidance_vision import (
    ChatVlmAdvisor,
    TesseractOcrBackend,
    run_ocr,
    run_vlm,
    vlm_api_key_from_vault,
)
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_LOCAL_ENDPOINT = "http://127.0.0.1:11434"
_CLOUD_ENDPOINT = "https://api.openai.com"


class _VisionBus(QObject):
    ocr_done = Signal(int, str, str)
    vlm_done = Signal(int, str, str)


class ReviewVisionPanel(QWidget):
    """Read text and describe the pinned image without a guidance schema."""

    def __init__(self, ocr=None, advisor_factory=None, vault=None, parent=None) -> None:
        super().__init__(parent)
        self._ocr = ocr or TesseractOcrBackend()
        self._advisor_factory = advisor_factory
        self._vault = vault
        self._image: str | None = None
        self._generation = 0
        self._thread: threading.Thread | None = None
        self._leaves = False
        self._previewed = False
        self._bus = _VisionBus()
        self._closed = threading.Event()
        closed = self._closed
        self.destroyed.connect(lambda *_: closed.set())
        self._bus.ocr_done.connect(self._show_ocr)
        self._bus.vlm_done.connect(self._show_vlm)
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        buttons = QHBoxLayout()
        self._ocr_btn = QPushButton("Read text (OCR)")
        self._ocr_btn.setObjectName("dl_review_ocr_btn")
        self._ocr_btn.clicked.connect(self.read_text)
        self._preview_btn = QPushButton("Preview departure")
        self._preview_btn.setObjectName("dl_review_vlm_preview_btn")
        self._preview_btn.clicked.connect(self.preview_departure)
        self._vlm_btn = QPushButton("Describe image (VLM)")
        self._vlm_btn.setObjectName("dl_review_vlm_btn")
        self._vlm_btn.clicked.connect(self.describe_image)
        buttons.addWidget(self._ocr_btn)
        buttons.addWidget(self._preview_btn)
        buttons.addWidget(self._vlm_btn)
        buttons.addStretch()
        root.addLayout(buttons)

        options = QHBoxLayout()
        self._placement = QComboBox()
        self._placement.setObjectName("dl_review_vlm_placement")
        self._placement.addItem("Local", "local")
        self._placement.addItem("Cloud", "cloud")
        self._placement.currentIndexChanged.connect(self._on_placement)
        self._model = QLineEdit("llava")
        self._model.setObjectName("dl_review_vlm_model")
        self._endpoint = QLineEdit(_LOCAL_ENDPOINT)
        self._endpoint.setObjectName("dl_review_vlm_endpoint")
        options.addWidget(QLabel("Placement:"))
        options.addWidget(self._placement)
        options.addWidget(self._model, stretch=1)
        options.addWidget(self._endpoint, stretch=2)
        root.addLayout(options)

        self._note = QLineEdit()
        self._note.setObjectName("dl_review_vlm_note")
        self._note.setPlaceholderText("Optional note. It is sent as data, not as instructions.")
        root.addWidget(self._note)
        self._approve = QCheckBox("I approve sending this image and note to the host in the preview.")
        self._approve.setObjectName("dl_review_vlm_approve")
        self._approve.toggled.connect(lambda *_args: self._sync_run())
        root.addWidget(self._approve)
        self._preview = QLabel("Preview a departure before a cloud description.")
        self._preview.setObjectName("dl_review_vlm_preview")
        self._preview.setWordWrap(True)
        root.addWidget(self._preview)
        self._ocr_text = QPlainTextEdit()
        self._ocr_text.setObjectName("dl_review_ocr_text")
        self._ocr_text.setReadOnly(True)
        self._ocr_text.setPlaceholderText("OCR transcription")
        self._ocr_text.setFixedHeight(72)
        root.addWidget(self._ocr_text)
        self._vlm_text = QPlainTextEdit()
        self._vlm_text.setObjectName("dl_review_vlm_text")
        self._vlm_text.setReadOnly(True)
        self._vlm_text.setPlaceholderText("VLM observations")
        self._vlm_text.setFixedHeight(72)
        root.addWidget(self._vlm_text)
        self._status = QLabel("")
        self._status.setObjectName("dl_review_vision_status")
        self._status.setWordWrap(True)
        root.addWidget(self._status)
        for label in self.findChildren(QLabel):
            label.setTextFormat(Qt.TextFormat.PlainText)
        for field in (self._endpoint, self._model, self._note):
            field.textChanged.connect(self._invalidate_approval)
        self._sync_run()

    def _invalidate_approval(self, *_args) -> None:
        self._previewed = False
        self._approve.setChecked(False)
        self._sync_run()

    def set_image(self, path: str | None) -> None:
        self._generation += 1
        self._ocr_text.clear()
        self._vlm_text.clear()
        self._image = path or None
        self._approve.setChecked(False)
        self._leaves = False
        self._previewed = False
        self._sync_run()

    def read_text(self) -> None:
        if not self._image:
            self._status.setText("No output to read — pin an image first.")
            return
        self._start("ocr")

    def preview_departure(self) -> None:
        if not self._image:
            self._preview.setText("No output to describe — pin an image first.")
            self._status.setText("No output to describe — pin an image first.")
            return
        preview = self._make_advisor().preview(Path(self._image), note=self._note.text())
        self._leaves = preview.leaves_machine
        self._previewed = True
        self._preview.setText(preview.summary())
        if not preview.leaves_machine:
            self._approve.setChecked(False)
        self._sync_run()

    def describe_image(self) -> None:
        if not self._image:
            self._status.setText("No output to describe — pin an image first.")
            return
        if self._cloud_blocked():
            self._status.setText("Cloud analysis needs an explicit send approval.")
            return
        self._start("vlm")

    def _on_placement(self) -> None:
        current = self._endpoint.text().strip()
        if self._placement.currentData() == "cloud":
            if current == _LOCAL_ENDPOINT:
                self._endpoint.setText(_CLOUD_ENDPOINT)
            if self._model.text().strip() == "llava":
                self._model.setText("gpt-4o-mini")
        elif current == _CLOUD_ENDPOINT:
            self._endpoint.setText(_LOCAL_ENDPOINT)
            if self._model.text().strip() == "gpt-4o-mini":
                self._model.setText("llava")
        self._approve.setChecked(False)
        self._leaves = False
        self._previewed = False
        self._sync_run()

    def _cloud_blocked(self) -> bool:
        cloud = self._placement.currentData() == "cloud" or self._leaves
        return cloud and not (self._previewed and self._approve.isChecked())

    def _sync_run(self) -> None:
        self._vlm_btn.setEnabled(not self._cloud_blocked())

    def _start(self, kind: str) -> None:
        if self._thread is not None and self._thread.is_alive():
            self._status.setText("A review read is already running.")
            return
        self._generation += 1
        snapshot = self._snapshot(kind, self._generation)
        self._status.setText("Reading text…" if kind == "ocr" else "Describing image…")
        self._thread = threading.Thread(target=self._worker, args=(snapshot,), name="review-vision", daemon=True)
        self._thread.start()

    def _snapshot(self, kind: str, generation: int) -> dict:
        return {
            "kind": kind,
            "generation": generation,
            "image": self._image,
            "note": self._note.text(),
            "approved": self._approve.isChecked(),
            "placement": self._placement.currentData(),
            "endpoint": self._endpoint.text().strip(),
            "model": self._model.text().strip(),
            "api_key": None,
        }

    def _worker(self, snapshot: dict) -> None:
        generation = snapshot["generation"]
        try:
            if snapshot["kind"] == "ocr":
                result = run_ocr(self._ocr, snapshot["image"])
                text = "" if result.unavailable else f"{result.text}\n({len(result.boxes)} boxes)"
                detail = result.unavailable or ""
                if generation == self._generation and not self._closed.is_set():
                    self._bus.ocr_done.emit(generation, text, detail)
                return
            if snapshot["placement"] == "cloud":
                snapshot["api_key"] = vlm_api_key_from_vault(self._vault)
            advisor = self._advisor_for(snapshot)
            result = run_vlm(
                advisor, snapshot["image"], note=snapshot["note"], approved=snapshot["approved"],
            )
            text = "" if result.unavailable else "\n".join(result.observations)
            detail = result.unavailable or ""
            if generation == self._generation and not self._closed.is_set():
                self._bus.vlm_done.emit(generation, text, detail)
        except Exception as exc:
            if generation == self._generation and not self._closed.is_set():
                self._bus.vlm_done.emit(generation, "", str(exc)[:300])

    def _advisor_for(self, snapshot: dict):
        if self._advisor_factory is not None:
            return self._advisor_factory(
                snapshot["placement"], snapshot["endpoint"], snapshot["model"], snapshot["api_key"],
            )
        return ChatVlmAdvisor(
            placement=snapshot["placement"],
            endpoint=snapshot["endpoint"],
            model=snapshot["model"] or "llava",
            api_key=snapshot["api_key"],
        )

    def _make_advisor(self):
        return self._advisor_for(self._snapshot("vlm", self._generation))

    def _show_ocr(self, generation: int, text: str, detail: str) -> None:
        if generation != self._generation:
            return
        self._ocr_text.setPlainText(text)
        self._status.setText(detail or "OCR finished.")

    def _show_vlm(self, generation: int, text: str, detail: str) -> None:
        if generation != self._generation:
            return
        self._vlm_text.setPlainText(text)
        self._status.setText(detail or "VLM finished.")
