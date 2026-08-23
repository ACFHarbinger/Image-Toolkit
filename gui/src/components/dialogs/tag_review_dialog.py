"""
TagReviewDialog — new_features.md §4.4C (human-in-the-loop tagging queue).

Runs WD14 auto-tagging over a dataset folder (via ``TagReviewWorker``,
built on the already-existing ``WDTaggerWrapper.tag_with_review`` §4.4E
split) and lets a human page through each untagged image, confirming or
correcting the predicted tags before they're written as .txt caption
sidecars — the same format ``HybridCaptioner.write_caption_file`` produces,
so reviewed captions are indistinguishable from auto-generated ones to the
training pipeline.

Auto-confidence tags start pre-checked; borderline (review-threshold) tags
start unchecked — the human's job is mainly to promote a few review-zone
tags, not to re-tag every image from scratch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.src.constants.components import _PREVIEW_MAX
from gui.src.helpers.models.tag_review_worker import TagReviewWorker


class TagReviewDialog(QDialog):
    def __init__(
        self,
        image_paths: List[Path],
        trigger: Optional[str] = None,
        general_thresh: float = 0.35,
        review_thresh: float = 0.15,
        model_repo: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("WD-Tagger Review Queue")
        self.resize(760, 560)

        self._trigger = trigger or None
        # path -> [(tag, confidence, category, checked)]
        self._entries: Dict[str, List[Tuple[str, float, str, bool]]] = {}
        self._order: List[str] = []
        self._current_idx = 0
        self._checkboxes: List[QCheckBox] = []

        self._build_ui()

        self._worker = TagReviewWorker(
            image_paths,
            general_thresh=general_thresh,
            review_thresh=review_thresh,
            model_repo=model_repo,
        )
        self._worker.sig_progress.connect(self._on_progress)
        self._worker.sig_result.connect(self._on_result)
        self._worker.sig_finished.connect(self._on_tagging_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    # ── UI construction ─────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)

        self._progress_label = QLabel("Tagging images…")
        root.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # busy indicator until first progress signal
        root.addWidget(self._progress_bar)

        self._review_widget = QWidget()
        self._review_widget.setVisible(False)
        rv = QVBoxLayout(self._review_widget)

        top = QHBoxLayout()
        self._preview_label = QLabel()
        self._preview_label.setFixedSize(_PREVIEW_MAX, _PREVIEW_MAX)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setStyleSheet("background: #111;")
        top.addWidget(self._preview_label)

        self._tags_box = QGroupBox("Predicted tags")
        self._tags_layout = QGridLayout(self._tags_box)
        tags_scroll = QScrollArea()
        tags_scroll.setWidgetResizable(True)
        tags_scroll.setWidget(self._tags_box)
        top.addWidget(tags_scroll, stretch=1)
        rv.addLayout(top, stretch=1)

        add_row = QHBoxLayout()
        self._add_tag_edit = QLineEdit()
        self._add_tag_edit.setPlaceholderText("Add a tag…")
        self._add_tag_edit.returnPressed.connect(self._add_custom_tag)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_custom_tag)
        add_row.addWidget(self._add_tag_edit)
        add_row.addWidget(add_btn)
        rv.addLayout(add_row)

        nav = QHBoxLayout()
        self._name_label = QLabel()
        nav.addWidget(self._name_label, stretch=1)
        prev_btn = QPushButton("< Prev")
        prev_btn.clicked.connect(self._go_prev)
        next_btn = QPushButton("Next >")
        next_btn.clicked.connect(self._go_next)
        nav.addWidget(prev_btn)
        nav.addWidget(next_btn)
        rv.addLayout(nav)

        bottom = QHBoxLayout()
        save_btn = QPushButton("Save All && Close")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_all)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        bottom.addStretch()
        bottom.addWidget(save_btn)
        bottom.addWidget(cancel_btn)
        rv.addLayout(bottom)

        root.addWidget(self._review_widget, stretch=1)

    # ── worker signal handlers ──────────────────────────────────────────────

    def _on_progress(self, done: int, total: int):
        if self._progress_bar.maximum() == 0 and total > 0:
            self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(done)
        self._progress_label.setText(f"Tagging images… {done}/{total}")

    def _on_result(self, path: str, entries: list):
        self._entries[path] = list(entries)
        self._order.append(path)

    def _on_error(self, message: str):
        QMessageBox.warning(self, "Tag Review", message)

    def _on_tagging_finished(self):
        self._progress_label.setText(f"{len(self._order)} image(s) ready for review.")
        self._progress_bar.setVisible(False)
        if not self._order:
            QMessageBox.information(
                self,
                "Tag Review",
                "No untagged images found (all already have a .txt caption).",
            )
            self.reject()
            return
        self._review_widget.setVisible(True)
        self._show_current()

    # ── review navigation ───────────────────────────────────────────────────

    def _show_current(self):
        path = self._order[self._current_idx]
        self._name_label.setText(
            f"{self._current_idx + 1}/{len(self._order)} — {Path(path).name}"
        )
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(
                _PREVIEW_MAX,
                _PREVIEW_MAX,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview_label.setPixmap(pix)
        else:
            self._preview_label.setText("(preview unavailable)")

        while self._tags_layout.count():
            item = self._tags_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._checkboxes = []

        entries = self._entries.get(path, [])
        for row, (tag, confidence, category, checked) in enumerate(entries):
            cb = QCheckBox(f"{tag} ({category}, {confidence:.2f})")
            cb.setChecked(checked)
            cb.setProperty("tag_name", tag)
            self._tags_layout.addWidget(cb, row // 2, row % 2)
            self._checkboxes.append(cb)

    def _go_prev(self):
        if self._current_idx > 0:
            self._sync_current_checks()
            self._current_idx -= 1
            self._show_current()

    def _go_next(self):
        if self._current_idx < len(self._order) - 1:
            self._sync_current_checks()
            self._current_idx += 1
            self._show_current()

    def _add_custom_tag(self):
        text = self._add_tag_edit.text().strip()
        if not text:
            return
        self._add_tag_edit.clear()
        cb = QCheckBox(f"{text} (custom, 1.00)")
        cb.setChecked(True)
        cb.setProperty("tag_name", text)
        row = len(self._checkboxes)
        self._tags_layout.addWidget(cb, row // 2, row % 2)
        self._checkboxes.append(cb)

    def accepted_tags(self, path: str) -> List[str]:
        """Tags currently checked for *path*. Syncs the on-screen checkbox
        state for the currently-displayed image first, so this is accurate
        even before the user navigates away or saves."""
        if path == self._order[self._current_idx]:
            self._sync_current_checks()
        return [
            tag for tag, _conf, _cat, checked in self._entries.get(path, []) if checked
        ]

    def _sync_current_checks(self):
        """Persist the current image's checkbox states back into
        ``self._entries`` before moving away from it or saving."""
        if not self._order:
            return
        path = self._order[self._current_idx]
        checked_names = {
            cb.property("tag_name") for cb in self._checkboxes if cb.isChecked()
        }
        existing = self._entries.get(path, [])
        existing_names = {e[0] for e in existing}
        updated = [
            (tag, conf, cat, tag in checked_names) for tag, conf, cat, _c in existing
        ]
        for cb in self._checkboxes:
            name = cb.property("tag_name")
            if name not in existing_names and cb.isChecked():
                updated.append((name, 1.0, "custom", True))
        self._entries[path] = updated

    def _save_all(self):
        self._sync_current_checks()
        written = 0
        for path in self._order:
            tags = [
                tag for tag, _conf, _cat, checked in self._entries.get(path, []) if checked
            ]
            if self._trigger and self._trigger not in tags:
                tags = [self._trigger] + tags
            caption = ", ".join(tags)
            Path(path).with_suffix(".txt").write_text(caption, encoding="utf-8")
            written += 1
        QMessageBox.information(
            self, "Tag Review", f"Saved {written} caption file(s)."
        )
        self.accept()
