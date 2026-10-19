"""#747: the blind checkpoint tournament.

Pairs of checkpoint sample grids are shown side by side through the
existing ``ImageCompareWindow`` machinery (synced pan/zoom — reused, not
rebuilt) with every identity cue hidden: pane badges read "A"/"B", the
overlay/difference modes that display filenames are removed, and the
mode-switch keys are swallowed. The user votes left/right/tie (skip is
allowed); an ELO table with per-entry uncertainty grows on the run and
persists to ``tournament.json`` so a sitting can resume later. After
~12 comparisons the sitting ends on the standings — fatigue cap — and
"Promote winner" records provenance and emits a ``PinnedRun`` for the
workspace spine so Generate's adapter can be set from the result.
"""
from __future__ import annotations

import random
from pathlib import Path

from middleware.src.core import checkpoint_tournament as ct
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.src.windows.image_compare_window import ImageCompareWindow

SESSION_CAP = 12  # ~comparisons per sitting before the fatigue cap ends it


def _adapter_load_target(checkpoint_path: str) -> str:
    """What Generate's lora_path should point at: the weights file inside a
    diffusers checkpoint dir when there is one, the path itself otherwise."""
    path = Path(checkpoint_path)
    if path.is_file():
        return str(path)
    if path.is_dir():
        try:
            weights = sorted(path.rglob("*.safetensors"))
        except OSError:
            weights = []
        if weights:
            return str(weights[0])
    return str(path)


class _BlindCompareView(ImageCompareWindow):
    """ImageCompareWindow with identity hidden: side-by-side only, pane
    badges forced to A/B, and the overlay/diff modes (which print
    filenames) unreachable from buttons or keys."""

    def __init__(self, image_paths: list[str], parent: QWidget | None = None) -> None:
        super().__init__(
            image_paths,
            parent=parent,
            initial_mode=ImageCompareWindow.MODE_SIDE_BY_SIDE,
            embedded=True,
        )
        self.btn_overlay.hide()
        self.btn_diff.hide()
        self.sub_bar.hide()
        for pane, tag in zip(self.panes, ("A", "B"), strict=False):
            pane.header.setText(tag)

    def keyPressEvent(self, event):  # noqa: N802 - Qt override
        key = event.key()
        if key in (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_Tab):
            event.accept()  # mode switching would leak filenames — swallow
            return
        super().keyPressEvent(event)


class CheckpointTournamentDialog(QDialog):
    """Blind pairwise ELO over a finished run's checkpoint sample grids.

    Emits :attr:`promote_requested` with a ``PinnedRun``-shaped winner
    (provenance is also persisted into ``tournament.json`` in the run dir).
    """

    promote_requested = Signal(object)

    def __init__(
        self,
        run_dir: str,
        *,
        parent: QWidget | None = None,
        session_cap: int = SESSION_CAP,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Checkpoint Tournament")
        self.setModal(False)
        self.resize(1080, 720)
        self._run_dir = str(run_dir)
        self._session_cap = max(1, int(session_cap))
        self._rng = rng or random.Random()
        self._votes = 0
        self._skipped: set[frozenset] = set()
        self._state: ct.TournamentState | None = None
        self._current_pair: tuple[str, str] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        title = QLabel("Checkpoint Tournament — blind pairwise comparison")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        root.addWidget(title)

        self._note_label = QLabel("")
        self._note_label.setWordWrap(True)
        root.addWidget(self._note_label)

        self._compare_host = QVBoxLayout()
        self._compare_host.setSpacing(0)
        root.addLayout(self._compare_host, 1)

        votes = QHBoxLayout()
        votes.setSpacing(6)
        self._vote_a = QPushButton("← A wins")
        self._tie_btn = QPushButton("Tie (T)")
        self._vote_b = QPushButton("B wins →")
        self._skip_btn = QPushButton("Skip (N)")
        for btn in (self._vote_a, self._tie_btn, self._vote_b, self._skip_btn):
            votes.addWidget(btn)
        votes.addStretch(1)
        root.addLayout(votes)
        self._vote_a.clicked.connect(lambda: self._vote(ct.RESULT_A))
        self._tie_btn.clicked.connect(lambda: self._vote(ct.RESULT_TIE))
        self._vote_b.clicked.connect(lambda: self._vote(ct.RESULT_B))
        self._skip_btn.clicked.connect(self._skip)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Checkpoint", "ELO", "±", "Games", "W–T"])
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setMaximumHeight(180)
        root.addWidget(self._table)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._promote_btn = QPushButton("Promote Winner…")
        self._save_btn = QPushButton("Save && Close")
        buttons.addWidget(self._promote_btn)
        buttons.addWidget(self._save_btn)
        root.addLayout(buttons)
        self._promote_btn.clicked.connect(self._promote)
        self._save_btn.clicked.connect(self._save_and_close)

        self._shortcuts: list[QShortcut] = []
        for key_seq, handler in (
            (Qt.Key.Key_Left, lambda: self._vote(ct.RESULT_A)),
            (Qt.Key.Key_Right, lambda: self._vote(ct.RESULT_B)),
            (Qt.Key.Key_T, lambda: self._vote(ct.RESULT_TIE)),
            (Qt.Key.Key_N, self._skip),
        ):
            short = QShortcut(QKeySequence(key_seq), self)
            short.setContext(Qt.ShortcutContext.WindowShortcut)
            short.activated.connect(handler)
            self._shortcuts.append(short)

        self._reload()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def _reload(self) -> None:
        entries = ct.build_entries(self._run_dir, rng=self._rng)
        if len(entries) < 2:
            self._state = None
            self._set_interstitial(
                "Not enough to compare: the tournament needs at least two "
                "checkpoints with sample grids. Grids land in "
                f"'{self._run_dir}/samples' when training logs them."
            )
            self._set_voting_enabled(False)
            self._promote_btn.setEnabled(False)
            self._note_label.setText("Waiting on checkpoints + sample grids.")
            return
        self._state = ct.attach_state(self._run_dir, entries)
        self._refresh_standings()
        self._set_voting_enabled(True)
        self._advance()

    def _set_interstitial(self, text: str) -> None:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._swap_compare_widget(label)

    def _swap_compare_widget(self, widget: QWidget) -> None:
        while self._compare_host.count():
            item = self._compare_host.takeAt(0)
            old = item.widget()
            if old is not None:
                old.deleteLater()
        self._compare_host.addWidget(widget)

    def _set_voting_enabled(self, enabled: bool) -> None:
        for btn in (self._vote_a, self._tie_btn, self._vote_b, self._skip_btn):
            btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    # voting flow
    # ------------------------------------------------------------------

    def _advance(self) -> None:
        if self._state is None:
            return
        if self._votes >= self._session_cap:
            self._finish_sitting()
            return
        pair = ct.suggest_pair(self._state, self._rng, avoid=self._skipped)
        if pair is None and self._skipped:
            self._skipped.clear()
            pair = ct.suggest_pair(self._state, self._rng)
        if pair is None:
            self._set_interstitial(
                "Every pair has been compared — see the final table below."
            )
            self._set_voting_enabled(False)
            self._current_pair = None
            self._refresh_standings()
            return
        self._show_pair(pair[0], pair[1])

    def _show_pair(self, a_key: str, b_key: str) -> None:
        a_path = self._state.entries[a_key].sample_path
        b_path = self._state.entries[b_key].sample_path
        self._current_pair = (a_key, b_key)
        self._swap_compare_widget(_BlindCompareView([a_path, b_path], parent=self))

    def _vote(self, result: str) -> None:
        if self._state is None or self._current_pair is None:
            return
        a_key, b_key = self._current_pair
        if ct.record_result(self._state, a_key, b_key, result):
            self._votes += 1
            ct.save_state(self._run_dir, self._state)
        self._current_pair = None
        self._refresh_standings()
        self._advance()

    def _skip(self) -> None:
        if self._current_pair is None:
            return
        self._skipped.add(frozenset(self._current_pair))
        self._current_pair = None
        self._advance()

    def _finish_sitting(self) -> None:
        self._set_interstitial(
            f"Sitting complete — {self._session_cap} comparisons. The table is "
            "saved; close and reopen the tournament to resume."
        )
        self._set_voting_enabled(False)
        self._current_pair = None
        self._refresh_standings()

    # ------------------------------------------------------------------
    # standings + promote
    # ------------------------------------------------------------------

    def _refresh_standings(self) -> None:
        if self._state is None:
            self._table.setRowCount(0)
            return
        rows = ct.standings(self._state)
        self._table.setRowCount(len(rows))
        for i, s in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(s.label))
            self._table.setItem(i, 1, QTableWidgetItem(f"{s.rating:.0f}"))
            self._table.setItem(i, 2, QTableWidgetItem(f"±{s.margin:.0f}"))
            self._table.setItem(i, 3, QTableWidgetItem(str(s.games)))
            self._table.setItem(i, 4, QTableWidgetItem(f"{s.wins}–{s.ties}"))
        total = ct.total_games(self._state)
        note = (
            "ELO is provisional — ~10+ comparisons before rankings mean much."
            if not ct.is_significant(self._state)
            else "Rankings are starting to mean something."
        )
        self._note_label.setText(
            f"Comparison {min(self._votes, self._session_cap)} of {self._session_cap} "
            f"this sitting · {total} recorded. {note}"
        )
        self._promote_btn.setEnabled(total > 0)

    def _promote(self) -> None:
        if self._state is None:
            return
        rows = ct.standings(self._state)
        if not rows:
            return
        leader = rows[0]
        prov = ct.promote(self._state, leader.key)
        ct.save_state(self._run_dir, self._state)
        entry = self._state.entries[leader.key]
        target = _adapter_load_target(entry.checkpoint_path)

        from gui.src.tabs.models.dl_comparison_spine import PinnedRun

        pin = PinnedRun(
            run_id=f"{self._state.run_id}:{entry.key}",
            label=ct.sanitize_label(f"{entry.label} (tournament winner)"),
            artifact_path=target,
            config={
                "selected_model": "anything",
                "sub_config": {"lora_path": target},
            },
        )
        self.promote_requested.emit(pin)
        QMessageBox.information(
            self,
            "Winner promoted",
            f"{entry.label} leads at ELO {prov['rating']:.0f} "
            f"±{prov['margin']:.0f} over {prov['games']} comparisons.\n"
            f"Provenance recorded in {ct.STATE_FILE_NAME}.\n\n{target}",
        )

    def _save_and_close(self) -> None:
        if self._state is not None:
            ct.save_state(self._run_dir, self._state)
        self.close()
