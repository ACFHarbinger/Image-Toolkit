"""What Changed overlay for the Review comparison canvas (#754).

Sits under the reused ``ImageCompareWindow`` — this is not a canvas
rebuild. Lists applied node/field/old→new/reason rows, the expected
effect, and Better/Same/Worse/Unsure verdicts. After enough unresolved
iterations the structural-steer hint replaces another parameter nudge.
"""
from __future__ import annotations

from backend.src.core.guidance_trajectory import (
    STRUCTURAL_HINT,
    VERDICTS,
    GuidanceTrajectory,
    record_verdict,
    should_steer_structural,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_VERDICT_LABELS = (
    ("better", "Better"),
    ("same", "Same"),
    ("worse", "Worse"),
    ("unsure", "Unsure"),
)


def _short_id(prompt_id: str | None) -> str:
    text = (prompt_id or "").strip()
    if not text:
        return ""
    return text if len(text) <= 12 else text[:8]


class WhatChangedOverlay(QWidget):
    """Baseline/variant labels + applied-change list + verdict buttons."""

    verdict_chosen = Signal(str)
    feedback_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dl_what_changed")
        self._trajectory: GuidanceTrajectory | None = None
        self._variant_id: str | None = None
        self._voting_allowed = False
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        title = QLabel("What Changed?")
        title.setObjectName("dl_what_changed_title")
        root.addWidget(title)

        labels = QHBoxLayout()
        self._baseline = QLabel("Baseline")
        self._baseline.setObjectName("dl_what_changed_baseline")
        self._variant = QLabel("Variant (assistant-suggested)")
        self._variant.setObjectName("dl_what_changed_variant")
        labels.addWidget(self._baseline, stretch=1)
        labels.addWidget(self._variant, stretch=1)
        root.addLayout(labels)

        self._changes = QLabel("No applied changes yet.")
        self._changes.setObjectName("dl_what_changed_changes")
        self._changes.setWordWrap(True)
        root.addWidget(self._changes)

        self._expected = QLabel("")
        self._expected.setObjectName("dl_what_changed_expected")
        self._expected.setWordWrap(True)
        root.addWidget(self._expected)

        self._feedback = QLineEdit()
        self._feedback.setObjectName("dl_what_changed_feedback")
        self._feedback.setPlaceholderText("Describe the problem (original feedback)")
        self._feedback.textChanged.connect(self.feedback_changed.emit)
        root.addWidget(self._feedback)

        verdicts = QHBoxLayout()
        verdicts.addWidget(QLabel("Your verdict:"))
        self._buttons: dict[str, QPushButton] = {}
        for key, label in _VERDICT_LABELS:
            button = QPushButton(label)
            button.setObjectName(f"dl_what_changed_verdict_{key}")
            button.clicked.connect(lambda _=False, verdict=key: self._on_verdict(verdict))
            self._buttons[key] = button
            verdicts.addWidget(button)
        verdicts.addStretch()
        root.addLayout(verdicts)

        self._hint = QLabel(STRUCTURAL_HINT)
        self._hint.setObjectName("dl_what_changed_hint")
        self._hint.setWordWrap(True)
        self._hint.setVisible(False)
        root.addWidget(self._hint)
        for label in self.findChildren(QLabel):
            label.setTextFormat(Qt.TextFormat.PlainText)

    def trajectory(self) -> GuidanceTrajectory | None:
        return self._trajectory

    def feedback(self) -> str:
        return self._feedback.text().strip()

    def set_feedback(self, text: str) -> None:
        if self._feedback.text() == text:
            return
        self._feedback.setText(text)

    def set_trajectory(
        self,
        traj: GuidanceTrajectory | None,
        *,
        variant_prompt_id: str | None = None,
    ) -> None:
        self._trajectory = traj
        latest = traj.latest if traj is not None else None
        self._variant_id = variant_prompt_id or (latest.variant_prompt_id if latest else None)
        selected = self._selected_step()
        self._feedback.setText(selected.feedback if selected else "")
        self._refresh()

    def clear(self) -> None:
        self._trajectory = None
        self._variant_id = None
        self._voting_allowed = False
        self._feedback.clear()
        self._refresh()

    def variant_id(self) -> str | None:
        return self._variant_id

    def set_voting_enabled(self, enabled: bool) -> None:
        """Host enables this only after the provenance-bound pair is on the canvas."""
        self._voting_allowed = bool(enabled)
        self._refresh()

    def _on_verdict(self, verdict: str) -> None:
        if (
            not self._voting_allowed
            or verdict not in VERDICTS
            or self._trajectory is None
            or not self._variant_id
            or self._selected_step() is None
        ):
            return
        self._trajectory = record_verdict(
            self._trajectory,
            verdict,
            variant_prompt_id=self._variant_id,
            feedback=self.feedback(),
        )
        self.verdict_chosen.emit(verdict)
        self._refresh()

    def _selected_step(self):
        if self._trajectory is None:
            return None
        return next((step for step in self._trajectory.steps if step.variant_prompt_id == self._variant_id), None)

    def _refresh(self) -> None:
        traj = self._trajectory
        latest = self._selected_step()
        if traj is None or latest is None:
            self._baseline.setText("Baseline")
            self._variant.setText("Variant (assistant-suggested)")
            self._changes.setText("No applied changes yet.")
            self._expected.setText("")
            self._hint.setVisible(False)
            for button in self._buttons.values():
                button.setEnabled(False)
                button.setDown(False)
            self.hide()
            return
        parent = _short_id(latest.parent_prompt_id)
        variant = _short_id(latest.variant_prompt_id)
        self._baseline.setText(f"Baseline (Run {parent})" if parent else "Baseline")
        if variant:
            self._variant.setText(f"Variant (Run {variant})")
        else:
            self._variant.setText("Variant (assistant-suggested)")
        if latest.applied:
            lines = ["Changes applied:"]
            lines.extend(f"  • {change.summary()}" for change in latest.applied)
            self._changes.setText("\n".join(lines))
        else:
            self._changes.setText("Changes applied: (none recorded)")
        self._expected.setText(f"Expected: {latest.expected}" if latest.expected else "")
        self._hint.setVisible(should_steer_structural(traj))
        current = latest.verdict
        can_vote = self._voting_allowed and bool(self._variant_id)
        for key, button in self._buttons.items():
            button.setEnabled(can_vote)
            button.setDown(key == current)
            button.setToolTip(
                "" if can_vote else "Variant comparison outputs must be loaded before recording a verdict."
            )
        self.show()
