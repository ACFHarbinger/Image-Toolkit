"""Comparison spine for the Deep Learning workspace (#732).

Pinned runs live on the workspace, not on a destination page, so they
survive Train → Generate → Review. A pin whose file is gone stays
visible and marked unavailable.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

MAX_PINNED_RUNS = 5
_LOCAL_SUFFIXES = {
    ".safetensors",
    ".pt",
    ".ckpt",
    ".bin",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
_PATH_KEYS = ("model_id", "lora_path", "model_path", "checkpoint")
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class PinnedRun:
    """One noted run. ``available`` is refreshed by :func:`classify_pin`."""

    run_id: str
    label: str
    artifact_path: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    available: bool = True
    unavailable_reason: str = ""


def _is_local_path(value: str) -> bool:
    """True for filesystem targets. Hugging Face ids contain a slash and are not local."""
    if value.startswith(("/", "./", "../", "~")):
        return True
    return Path(value).suffix.lower() in _LOCAL_SUFFIXES


def _config_paths(config: dict[str, Any]) -> list[str]:
    bags: list[dict[str, Any]] = [config]
    sub = config.get("sub_config")
    if isinstance(sub, dict):
        bags.append(sub)
    found: list[str] = []
    for bag in bags:
        for key in _PATH_KEYS:
            value = bag.get(key)
            if isinstance(value, str) and value.strip():
                found.append(value.strip())
    return found


def classify_pin(
    run: PinnedRun,
    *,
    exists: Callable[[str], bool] = os.path.exists,
) -> PinnedRun:
    """Mark a pin unavailable when its artifact or a local model path is gone."""
    artifact = run.artifact_path.strip()
    if artifact and not exists(os.path.expanduser(artifact)):
        return replace(run, available=False, unavailable_reason="deleted run")
    for value in _config_paths(run.config):
        if _is_local_path(value) and not exists(os.path.expanduser(value)):
            return replace(run, available=False, unavailable_reason="deleted model")
    return replace(run, available=True, unavailable_reason="")


def is_image_artifact(path: str) -> bool:
    """True when *path* is an image file that exists and can be shown."""
    if not path:
        return False
    if Path(path).suffix.lower() not in _IMAGE_SUFFIXES:
        return False
    return os.path.exists(os.path.expanduser(path))


def artifact_from_config(config: dict[str, Any]) -> str:
    """Pick a filesystem artifact out of a form ``collect()`` payload, if any."""
    for value in _config_paths(config):
        if _is_local_path(value):
            return value
    return ""


class ComparisonSpine(QWidget):
    """Pinned-run chips above the filmstrip, plus stars on filmstrip thumbnails."""

    pin_activated = Signal(object)
    pins_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dl_comparison_spine")
        self._runs: dict[str, PinnedRun] = {}
        self._noted: list[str] = []
        self._pin_order: list[str] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(4)

        chips = QHBoxLayout()
        chips.setSpacing(4)
        self._chip_row = QWidget()
        self._chip_row.setObjectName("dl_comparison_chips")
        self._chip_layout = QHBoxLayout(self._chip_row)
        self._chip_layout.setContentsMargins(0, 0, 0, 0)
        self._chip_layout.setSpacing(4)
        chips.addWidget(self._chip_row, stretch=1)
        self._limit_label = QLabel("")
        self._limit_label.setObjectName("dl_pin_limit")
        self._limit_label.setVisible(False)
        chips.addWidget(self._limit_label)
        root.addLayout(chips)

        self._filmstrip = QWidget()
        self._filmstrip.setObjectName("dl_filmstrip")
        self._film_layout = QHBoxLayout(self._filmstrip)
        self._film_layout.setContentsMargins(0, 0, 0, 0)
        self._film_layout.setSpacing(4)
        root.addWidget(self._filmstrip)
        self._rebuild()

    def noted_runs(self) -> list[PinnedRun]:
        return [self._runs[run_id] for run_id in self._noted if run_id in self._runs]

    def pinned_runs(self) -> list[PinnedRun]:
        return [self._runs[run_id] for run_id in self._pin_order if run_id in self._runs]

    def pinned_ids(self) -> set[str]:
        return set(self._pin_order)

    def note_run(self, run: PinnedRun) -> None:
        """Remember a run card. Noting does not pin it."""
        classified = classify_pin(replace(run, config=deepcopy(run.config)))
        if run.run_id not in self._runs:
            self._noted.append(run.run_id)
        self._runs[run.run_id] = classified
        self._rebuild()
        self.pins_changed.emit()

    def pin(self, run_id: str) -> bool:
        """Pin a noted run. Returns False when the run is unknown or the strip is full."""
        if run_id not in self._runs:
            return False
        if run_id in self._pin_order:
            return True
        if len(self._pin_order) >= MAX_PINNED_RUNS:
            self._show_limit()
            return False
        self._pin_order.append(run_id)
        self._limit_label.setVisible(False)
        self._rebuild()
        self.pins_changed.emit()
        return True

    def unpin(self, run_id: str) -> None:
        if run_id not in self._pin_order:
            return
        self._pin_order.remove(run_id)
        self._limit_label.setVisible(False)
        self._rebuild()
        self.pins_changed.emit()

    def revalidate(self) -> None:
        """Refresh availability. Stale pins stay in the strip."""
        self._runs = {run_id: classify_pin(run) for run_id, run in self._runs.items()}
        self._rebuild()

    def _show_limit(self) -> None:
        self._limit_label.setText("5 pins maximum")
        self._limit_label.setVisible(True)

    def _toggle_star(self, run_id: str) -> None:
        if run_id in self._pin_order:
            self.unpin(run_id)
            return
        self.pin(run_id)

    def _activate(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if run is None or not run.available:
            return
        self.pin_activated.emit(run)

    def _clear(self, layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _rebuild(self) -> None:
        self._clear(self._chip_layout)
        self._clear(self._film_layout)
        pinned = self.pinned_runs()
        if not pinned:
            empty = QLabel("No pinned runs")
            empty.setObjectName("dl_comparison_empty")
            self._chip_layout.addWidget(empty)
        for run in pinned:
            chip = QPushButton(run.label if run.available else f"Unavailable · {run.label}")
            chip.setObjectName(f"dl_pin_chip_{run.run_id}")
            chip.setProperty("unavailable", not run.available)
            if run.unavailable_reason:
                chip.setToolTip(run.unavailable_reason)
            chip.clicked.connect(lambda _=False, run_id=run.run_id: self._activate(run_id))
            self._chip_layout.addWidget(chip)
        self._chip_layout.addStretch()

        for run in self.noted_runs():
            thumb = QLabel()
            thumb.setObjectName(f"dl_film_thumb_{run.run_id}")
            thumb.setFixedSize(72, 72)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_image_artifact(run.artifact_path):
                pixmap = QPixmap(os.path.expanduser(run.artifact_path))
                if not pixmap.isNull():
                    thumb.setPixmap(
                        pixmap.scaled(
                            72,
                            72,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
            if thumb.pixmap() is None or thumb.pixmap().isNull():
                thumb.setText(run.label)
            star = QPushButton("★" if run.run_id in self._pin_order else "☆")
            star.setObjectName(f"dl_film_star_{run.run_id}")
            star.setToolTip("Unpin" if run.run_id in self._pin_order else "Pin")
            star.clicked.connect(lambda _=False, run_id=run.run_id: self._toggle_star(run_id))
            self._film_layout.addWidget(thumb)
            self._film_layout.addWidget(star)
        self._film_layout.addStretch()


__all__ = [
    "MAX_PINNED_RUNS",
    "ComparisonSpine",
    "PinnedRun",
    "artifact_from_config",
    "classify_pin",
]
