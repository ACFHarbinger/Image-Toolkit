"""Video/GIF runtime editing tab (Track 05, trim/remove-range/splice slice).

First entry in HIE's gui/src/tabs/ package (ASP-style). Backed by the
document.Timeline model: trim/remove-range/splice are list edits on an
ordered tuple of ClipSegment references, committed to a DocumentHistory
for undo/redo. Non-destructive while editing (pure metadata); Export is
the one destructive step, delegated to the main repo's clip_splicer
module (ffmpeg concat, every fork under media_backend_spawn_guard()).
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from document import ClipSegment, DocumentHistory, Timeline

from viewport import HieViewport

VIDEO_FILE_FILTER = (
    "Video/GIF (*.mp4 *.mov *.mkv *.webm *.avi *.gif);;All files (*)"
)


class VideoEditorTab(QWidget):
    """Timeline editor for trimming, removing ranges from, and splicing clips."""

    def __init__(self, parent=None, *, splicer=None) -> None:
        super().__init__(parent)
        # Default timeline: a single empty placeholder is rejected by the
        # model, so we keep None until the first clip is added.
        self._timeline: Timeline | None = None
        self._history: DocumentHistory | None = None
        self._splicer = splicer

        title = QLabel("Video Editor")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")

        self.add_clip_button = QPushButton("Add clip…")
        self.add_clip_button.clicked.connect(self.add_clip_dialog)

        self.trim_start_spin = QSpinBox()
        self.trim_start_spin.setRange(0, 1000000)
        self.trim_start_spin.setSuffix(" ms")
        self.trim_end_spin = QSpinBox()
        self.trim_end_spin.setRange(0, 1000000)
        self.trim_end_spin.setSuffix(" ms")
        self.trim_end_spin.setValue(1000)
        self.trim_button = QPushButton("Trim")
        self.trim_button.clicked.connect(self.trim_timeline)

        self.remove_start_spin = QSpinBox()
        self.remove_start_spin.setRange(0, 1000000)
        self.remove_start_spin.setSuffix(" ms")
        self.remove_end_spin = QSpinBox()
        self.remove_end_spin.setRange(0, 1000000)
        self.remove_end_spin.setValue(500)
        self.remove_end_spin.setSuffix(" ms")
        self.remove_button = QPushButton("Remove range")
        self.remove_button.clicked.connect(self.remove_range)

        self.undo_button = QPushButton("Undo")
        self.undo_button.clicked.connect(self.undo)
        self.redo_button = QPushButton("Redo")
        self.redo_button.clicked.connect(self.redo)
        self.export_button = QPushButton("Export…")
        self.export_button.clicked.connect(self.export_timeline)
        self.export_button.setEnabled(False)

        toolbar = QHBoxLayout()
        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self.add_clip_button)
        toolbar.addWidget(self.undo_button)
        toolbar.addWidget(self.redo_button)
        toolbar.addWidget(self.export_button)

        edit_row = QHBoxLayout()
        edit_row.addWidget(QLabel("Trim [ms]"))
        edit_row.addWidget(self.trim_start_spin)
        edit_row.addWidget(self.trim_end_spin)
        edit_row.addWidget(self.trim_button)
        edit_row.addSpacing(12)
        edit_row.addWidget(QLabel("Remove [ms]"))
        edit_row.addWidget(self.remove_start_spin)
        edit_row.addWidget(self.remove_end_spin)
        edit_row.addWidget(self.remove_button)
        edit_row.addStretch()

        self.segment_list = QListWidget()
        self.segment_list.setMinimumHeight(160)

        self.status_label = QLabel("Add a clip to start editing")
        self.status_label.setStyleSheet("color: #8a97a6;")

        self.viewport = HieViewport()
        self.viewport.show_status("Timeline preview: add clips to enable")

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)

        splitter = QSplitter()
        splitter.addWidget(self.viewport)
        splitter.addWidget(self.segment_list)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([700, 300])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addLayout(toolbar)
        layout.addLayout(edit_row)
        layout.addWidget(divider)
        layout.addWidget(splitter)
        layout.addWidget(self.status_label)

        self._refresh()

    # ------------------------------------------------------------------
    # Timeline state
    # ------------------------------------------------------------------

    @property
    def timeline(self) -> Timeline | None:
        return self._timeline

    @property
    def history(self) -> DocumentHistory | None:
        return self._history

    def _commit(self, timeline: Timeline) -> None:
        """Record a timeline edit (deterministic list edits go straight to
        DocumentHistory, not through the ML ProposalPipeline - see the
        Track 05 design note's open question)."""
        if self._history is None:
            self._history = DocumentHistory(timeline)
        else:
            self._history.commit(timeline)
        self._timeline = timeline
        self._refresh()

    def _refresh(self) -> None:
        self.segment_list.clear()
        if self._timeline is None:
            self.status_label.setText("Add a clip to start editing")
            self.export_button.setEnabled(False)
            self.viewport.show_status("Timeline preview: add clips to enable")
            return
        for i, seg in enumerate(self._timeline.segments):
            item = QListWidgetItem(
                f"{i}: {os.path.basename(seg.source_path)} [{seg.in_ms}ms, {seg.out_ms}ms)"
            )
            self.segment_list.addItem(item)
        total = sum(s.duration_ms for s in self._timeline.segments)
        self.status_label.setText(
            f"{len(self._timeline.segments)} segment(s) · {total}ms total"
        )
        self.export_button.setEnabled(True)

    # ------------------------------------------------------------------
    # Editing operations (list edits on the Timeline)
    # ------------------------------------------------------------------

    def add_clip_dialog(self) -> None:
        path, _selected = QFileDialog.getOpenFileName(self, "Add Clip", "", VIDEO_FILE_FILTER)
        if not path:
            return
        self.add_clip(path)

    def add_clip(self, path: str, duration_ms: int = 1000) -> bool:
        """Add a whole clip as one segment (duration probe can refine later)."""
        if not path or not os.path.exists(path):
            self.status_label.setText(f"Clip not found: {path}")
            return False
        segment = ClipSegment(path, 0, max(duration_ms, 1))
        if self._timeline is None:
            self._commit(Timeline((segment,)))
        else:
            self._commit(self._timeline.splice(len(self._timeline.segments), segment))
        self.viewport.show_status(os.path.basename(path))
        return True

    def trim_timeline(self) -> None:
        if self._timeline is None:
            return
        start = self.trim_start_spin.value()
        end = self.trim_end_spin.value()
        try:
            self._commit(self._timeline.trim(start, end))
        except Exception as exc:
            self.status_label.setText(f"Trim failed: {exc}")

    def remove_range(self) -> None:
        if self._timeline is None:
            return
        start = self.remove_start_spin.value()
        end = self.remove_end_spin.value()
        try:
            self._commit(self._timeline.remove_range(start, end))
        except Exception as exc:
            self.status_label.setText(f"Remove failed: {exc}")

    def splice_at(self, index: int, path: str, in_ms: int = 0, out_ms: int = 1000) -> bool:
        """Splice another clip into the timeline at *index* (programmatic hook)."""
        if self._timeline is None or not os.path.exists(path):
            return False
        segment = ClipSegment(path, in_ms, max(out_ms, in_ms + 1))
        self._commit(self._timeline.splice(index, segment))
        return True

    def undo(self) -> None:
        if self._history is None:
            return
        self._timeline = self._history.undo()
        self._refresh()

    def redo(self) -> None:
        if self._history is None:
            return
        self._timeline = self._history.redo()
        self._refresh()

    # ------------------------------------------------------------------
    # Export (the one destructive step)
    # ------------------------------------------------------------------

    def export_timeline(self) -> None:
        if self._timeline is None:
            return
        output, _selected = QFileDialog.getSaveFileName(
            self, "Export Timeline", "", "Video (*.mp4);;All files (*)"
        )
        if not output:
            return
        try:
            result = self._run_splicer(output)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            self.status_label.setText(f"Export failed: {exc}")
            return
        self.status_label.setText(f"Exported to {os.path.basename(output)}")
        self.viewport.show_status("Export complete")

    def _run_splicer(self, output: str) -> str:
        """Delegate to the main-repo clip_splicer (lazy import so HIE's own
        tests/standalone runs don't need the main repo on sys.path)."""
        if self._splicer is not None:
            return self._splicer(self._timeline, output)
        from gui.src.helpers.video.clip_splicer import (
            ClipSegment as SpliceSegment,
            splice_clips,
        )

        segments = [
            SpliceSegment(seg.source_path, seg.in_ms, seg.out_ms)
            for seg in self._timeline.segments
        ]
        return str(splice_clips(segments, output))


__all__ = ["VideoEditorTab"]
