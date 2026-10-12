"""#753: evidence chips, confidence badges, and the abstention panel.

These widgets are the rendering half of "evidence-traced suggestions":
each validated suggestion row can embed an :class:`EvidenceRowExtras`
(confidence badge + clickable evidence chips), and a response whose
schema carries ``needs[]`` renders an :class:`AbstentionPanel` —
"insufficient evidence; capture these" — with a one-click handoff of the
prefiltered dataset image list to Train's panel through the existing
``ImportPathsIntent`` route (the DL workspace host already listens).

Kept dependency-light on purpose: the panel/dialog hosting these widgets
(#752's Diff & Apply widget today) may live on a different branch, so
everything here works standalone and wires in with one or two lines at
integration.
"""
from __future__ import annotations

import threading

from backend.src.core import guidance_evidence as ge
from backend.src.core.guidance_schema import GuidanceValidation, ModelSwap, ParamChange
from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

TRAIN_MODULE_ID = "dl.train"  # dl_workspace_host._on_import_paths accepts this


class ConfidenceBadge(QLabel):
    """Honest confidence indicator per Qwen's spec: distinct color + word
    for high/medium/low, tooltip shows the numeric score."""

    def __init__(self, score: float | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("font-weight: bold;")
        if score is not None:
            self.set_score(score)

    def set_score(self, score: float) -> None:
        band = ge.confidence_band(score)
        self.setText(f"● {band.label}")
        self.setStyleSheet(f"color: {band.color}; font-weight: bold;")
        self.setToolTip(f"heuristic score {score:.2f}" + (f" — {band.hint}" if band.hint else ""))

    def set_band(self, band: ge.ConfidenceBand) -> None:
        self.setText(f"● {band.label}")
        self.setStyleSheet(f"color: {band.color}; font-weight: bold;")


class EvidenceChipBar(QWidget):
    """One clickable chip per resolved evidence signal.

    Chips with a run/artifact folder open it on click; advisor finding
    chips carry image paths and emit :attr:`paths_requested` so the host
    can hand them to Train's dataset panel. Stale chips (artifact gone)
    render gray and say so — the measured signal is never invented.
    """

    paths_requested = Signal(tuple)  # tuple[str, ...]

    def __init__(self, resolved: tuple[ge.ResolvedEvidence, ...] = (), parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._buttons: list[QToolButton] = []
        self.set_resolved(resolved)

    def set_resolved(self, resolved: tuple[ge.ResolvedEvidence, ...]) -> None:
        layout = self.layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons = []
        if not resolved:
            self.hide()
            return
        self.show()
        for ev in resolved:
            chip = QToolButton(self)
            chip.setText(ev.title + (" (stale)" if ev.stale else ""))
            chip.setToolTip(ev.detail or ev.title)
            if ev.stale:
                chip.setStyleSheet("color: #8a8a8a; border: 1px dashed #8a8a8a; border-radius: 6px; padding: 2px 6px;")
            else:
                chip.setStyleSheet("border: 1px solid #5a5a5a; border-radius: 6px; padding: 2px 6px;")
            clickable = bool(ev.target_dir or ev.paths)
            chip.setEnabled(clickable)
            if clickable:
                chip.clicked.connect(lambda _checked=False, e=ev: self._activate(e))
            layout.addWidget(chip)
            self._buttons.append(chip)
        layout.addStretch(1)

    def _activate(self, ev: ge.ResolvedEvidence) -> None:
        if ev.paths:
            self.paths_requested.emit(tuple(ev.paths))
        elif ev.target_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(ev.target_dir))

    def chip_texts(self) -> list[str]:
        return [btn.text() for btn in self._buttons]


class _EvidenceBus(QObject):
    done = Signal(object)


class EvidenceRowExtras(QWidget):
    """The #753 payload for one suggestion row: confidence badge left,
    evidence chips right. Hosts (the Diff & Apply widget) embed this
    beside the reason label."""

    paths_requested = Signal(tuple)

    def __init__(
        self,
        change: ParamChange | ModelSwap,
        validation: GuidanceValidation | None = None,
        *,
        runs_root=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.badge = ConfidenceBadge(parent=self)
        self.badge.set_score(ge.confidence_for_change(change, validation))
        row.addWidget(self.badge)
        self.chips = EvidenceChipBar(parent=self)
        self.chips.paths_requested.connect(self.paths_requested)
        row.addWidget(self.chips, stretch=1)
        self._change = change
        self._validation = validation
        self._bus = _EvidenceBus()
        self._bus.done.connect(self._resolved)
        bus = self._bus

        def resolve():
            try:
                result = tuple(ge.resolve_evidence(ref, runs_root=runs_root) for ref in change.evidence)
            except (OSError, ValueError, TypeError, KeyError):
                result = ()
            bus.done.emit(result)

        self._thread = threading.Thread(target=resolve, daemon=True, name="guidance-evidence")
        self._thread.start()

    def _resolved(self, resolved):
        self.chips.set_resolved(resolved)
        self.badge.set_score(ge.confidence_for_change(self._change, self._validation, resolved=resolved))


class AbstentionPanel(QWidget):
    """First-class "insufficient evidence" output.

    Renders the advisor's ``needs[]`` as a capture list, shows how many
    dataset images the evidence already prefiltered, and sends that
    pick-list to Train's dataset panel (Gate D.4) via the existing
    ``ImportPathsIntent`` handoff — dead-ends become dataset guidance,
    not forced parameter guesses.
    """

    pick_list_requested = Signal(tuple)  # tuple[str, ...]

    def __init__(
        self,
        needs: tuple[str, ...] = (),
        diagnosis: str = "",
        evidence: tuple = (),
        *,
        event_hub=None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._hub = event_hub
        self._paths = ()

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)
        title = QLabel("Insufficient evidence — capture these:")
        title.setStyleSheet("font-weight: bold; color: #c0392b;")
        root.addWidget(title)
        if diagnosis:
            diag = QLabel(diagnosis)
            diag.setWordWrap(True)
            diag.setStyleSheet("color: #8a8a8a;")
            root.addWidget(diag)
        for need in needs:
            item = QLabel(f"• {need}")
            item.setWordWrap(True)
            root.addWidget(item)
        if not needs:
            none = QLabel("• (no specific needs listed by the advisor)")
            none.setStyleSheet("color: #8a8a8a;")
            root.addWidget(none)

        self._pick_label = QLabel(self._pick_text())
        self._pick_label.setStyleSheet("color: #8a8a8a;")
        root.addWidget(self._pick_label)
        self._send_btn = QToolButton(self)
        self._send_btn.setText("Send pick-list to Train's dataset panel")
        self._send_btn.setEnabled(bool(self._paths))
        self._send_btn.setStyleSheet("border: 1px solid #5a5a5a; border-radius: 6px; padding: 3px 8px;")
        self._send_btn.clicked.connect(self._send)
        root.addWidget(self._send_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        for label in self.findChildren(QLabel):
            label.setTextFormat(Qt.TextFormat.PlainText)
        self._bus = _EvidenceBus()
        self._bus.done.connect(self._set_paths)
        bus = self._bus

        def resolve_paths():
            try:
                paths = ge.needs_pick_list(needs, evidence)
            except OSError:
                paths = ()
            bus.done.emit(paths)

        self._thread = threading.Thread(target=resolve_paths, daemon=True, name="guidance-pick-list")
        self._thread.start()

    def _set_paths(self, paths):
        self._paths = paths
        self._pick_label.setText(self._pick_text())
        self._send_btn.setEnabled(bool(paths))

    def _pick_text(self) -> str:
        if not self._paths:
            return "No dataset images matched the evidence paths."
        return f"{len(self._paths)} dataset images prefiltered from the evidence."

    def _send(self) -> None:
        if not self._paths:
            return
        if self._hub is not None:
            from gui.src.modules.events import ImportPathsIntent

            self._hub.publish(
                ImportPathsIntent(
                    module_id=TRAIN_MODULE_ID,
                    paths=tuple(self._paths),
                    origin="guidance",
                )
            )
        self.pick_list_requested.emit(tuple(self._paths))
