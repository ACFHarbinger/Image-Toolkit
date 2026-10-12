"""Dataset advisor panel (#744) — findings cards for the Train tab.

Deterministic checks (hash duplicates, caption coverage, aspect ratios,
unreadable files, tag entanglement) run automatically via a worker when
the dataset changes; CLIP diversity clustering is an explicit action that
takes the GPU lease. Every action is one-click: select paths in the
contact sheet, exclude duplicates (dataset modification), queue a Hydra
override, or open tag review. Findings without an honest one-click fix
render informational — no button at all.
"""
from __future__ import annotations

from backend.src.comfy_matrix import gpu_lease, try_admit
from backend.src.core.dataset_advisor import (
    ACTION_EXCLUDE,
    ACTION_HYDRA,
    ACTION_REVIEW_TAGS,
    ACTION_SELECT,
    AdvisorFinding,
    ScanSummary,
    analyze_diversity,
    scan_dataset,
)
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.src.helpers.base import BaseQThreadWorker
from gui.src.helpers.worker_retention import retain_until_stopped
from gui.src.helpers.worker_teardown import stop_worker

_SEVERITY_ICON = {"warning": "⚠", "info": "ℹ"}


def embed_paths(paths, progress=None, cancel=None):
    """Chunked CLIP embedding through the similarity stack. Lazy import
    boundary — torch loads only when the clustering action actually runs —
    and monkeypatchable in tests."""
    from backend.src.core.similarity import get_embedder

    embedder = get_embedder("mobileclip")
    if embedder is None:
        raise RuntimeError("No embedding backend is available.")
    embeddings = {}
    try:
        for start in range(0, len(paths), 64):
            if cancel is not None and cancel():
                break
            embeddings.update(embedder.embed_batch(paths[start:start + 64]))
            if progress is not None:
                progress(min(start + 64, len(paths)), len(paths))
        return embeddings
    finally:
        embedder.unload()


class AdvisorScanWorker(BaseQThreadWorker):
    """Deterministic checks off the GUI thread (fs-read-only, no GPU)."""

    def __init__(self, token: int, images, trigger: str, hash_cache: dict) -> None:
        super().__init__()
        self._token = token
        self._images = tuple(images)
        self._trigger = trigger
        self._hash_cache = hash_cache

    def _execute(self):
        report = scan_dataset(
            self._images,
            trigger=self._trigger,
            hash_cache=self._hash_cache,
            progress=lambda done, total: self.progress.emit(done, total),
            cancel=lambda: self._cancelled or self.isInterruptionRequested(),
        )
        return (self._token, report)


class AdvisorClusterWorker(BaseQThreadWorker):
    """CLIP diversity clustering; holds the GPU lease for the whole run."""

    def __init__(self, token: int, images) -> None:
        super().__init__()
        self._token = token
        self._images = tuple(images)

    def _execute(self):
        refusal = try_admit("dataset-advisor")
        if refusal:
            raise RuntimeError(refusal)
        try:
            embeddings = embed_paths(
                self._images,
                progress=lambda done, total: self.progress.emit(done, total),
                cancel=lambda: self._cancelled or self.isInterruptionRequested(),
            )
            findings = analyze_diversity(
                embeddings,
                cancel=lambda: self._cancelled or self.isInterruptionRequested(),
            )
            return (self._token, findings)
        finally:
            gpu_lease.release("dataset-advisor")


class AdvisorPanel(QWidget):
    exclude_requested = Signal(list)         # paths to drop from the dataset
    restore_requested = Signal()             # clear exclusions, restage
    selection_requested = Signal(list)       # highlight paths in the contact sheet
    review_tags_requested = Signal()         # open the Review Tags flow
    hydra_overrides_changed = Signal(list)   # pending Hydra fragments

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._token = 0
        self._images: tuple[str, ...] = ()
        self._trigger = ""
        self._hash_cache: dict = {}
        self._findings: list[AdvisorFinding] = []
        self._summary: ScanSummary | None = None
        self._pending_overrides: list[str] = []
        self._exclusion_count = 0
        self._hydra_available = False
        self._training_guard = lambda: False
        self._scan_worker: AdvisorScanWorker | None = None
        self._cluster_worker: AdvisorClusterWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        header = QHBoxLayout()
        header.addWidget(QLabel("Dataset Advisor"))
        header.addStretch()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setToolTip("Re-run the deterministic checks")
        self.refresh_btn.clicked.connect(self._start_scan)
        header.addWidget(self.refresh_btn)
        self.cluster_btn = QPushButton("Cluster (GPU)")
        self.cluster_btn.setToolTip(
            "Embed the dataset with CLIP and cluster for diversity — takes the "
            "GPU lease, so training cannot start meanwhile"
        )
        self.cluster_btn.clicked.connect(self._on_cluster_clicked)
        header.addWidget(self.cluster_btn)
        root.addLayout(header)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.summary_label = QLabel("No dataset loaded")
        root.addWidget(self.summary_label)

        self.exclusions_row = QWidget()
        exclusions_layout = QHBoxLayout(self.exclusions_row)
        exclusions_layout.setContentsMargins(0, 0, 0, 0)
        self.exclusions_label = QLabel()
        restore_btn = QPushButton("Restore")
        restore_btn.setToolTip("Clear advisor exclusions and restage the original dataset")
        restore_btn.clicked.connect(lambda: self.restore_requested.emit())
        exclusions_layout.addWidget(self.exclusions_label)
        exclusions_layout.addWidget(restore_btn)
        exclusions_layout.addStretch()
        self.exclusions_row.setVisible(False)
        root.addWidget(self.exclusions_row)

        self.overrides_row = QWidget()
        overrides_layout = QVBoxLayout(self.overrides_row)
        overrides_layout.setContentsMargins(0, 0, 0, 0)
        overrides_layout.addWidget(QLabel("Pending Hydra overrides (appended at launch):"))
        self.overrides_chips = QHBoxLayout()
        self.overrides_chips.addStretch()
        overrides_layout.addLayout(self.overrides_chips)
        self.overrides_row.setVisible(False)
        root.addWidget(self.overrides_row)

        self.cards_host = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(4)
        self.cards_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.cards_host)
        root.addWidget(scroll, stretch=1)

    def _build_card(self, finding: AdvisorFinding) -> QFrame:
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        head = QHBoxLayout()
        icon = QLabel(_SEVERITY_ICON.get(finding.severity, "ℹ"))
        icon.setToolTip(finding.severity)
        head.addWidget(icon)
        title = QLabel(finding.title)
        title.setWordWrap(True)
        head.addWidget(title, stretch=1)
        layout.addLayout(head)

        if finding.detail:
            detail = QLabel(finding.detail)
            detail.setWordWrap(True)
            layout.addWidget(detail)

        button = self._action_button(finding)
        if button is not None:
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(button)
            layout.addLayout(row)
        return card

    def _action_button(self, finding: AdvisorFinding) -> QPushButton | None:
        action = finding.action
        if action is None:
            return None
        if action == ACTION_HYDRA and not self._hydra_available:
            action, label = ACTION_REVIEW_TAGS, "Review Tags"
        else:
            label = finding.action_label
        if action == ACTION_HYDRA and finding.action_payload in self._pending_overrides:
            queued = QPushButton("Queued ✓")
            queued.setEnabled(False)
            return queued
        button = QPushButton(label)
        if action == ACTION_SELECT:
            button.clicked.connect(lambda _c=False, f=finding: self.selection_requested.emit(list(f.paths)))
        elif action == ACTION_EXCLUDE:
            button.clicked.connect(
                lambda _c=False, f=finding: self.exclude_requested.emit(list(f.paths[1:] or f.paths))
            )
        elif action == ACTION_HYDRA:
            payload = finding.action_payload
            button.clicked.connect(lambda _c=False, p=payload: self._queue_override(p))
        elif action == ACTION_REVIEW_TAGS:
            button.clicked.connect(lambda: self.review_tags_requested.emit())
        return button

    def _render(self) -> None:
        while self.cards_layout.count() > 1:  # keep trailing stretch
            item = self.cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if self._summary is not None:
            coverage = f"{self._summary.caption_coverage:.0%} captioned"
            self.summary_label.setText(
                f"{self._summary.image_count} images · {coverage} · "
                f"{self._summary.scene_count} scene(s)"
            )
        if not self._findings and self._summary is not None:
            ok = QLabel("✓ No issues found")
            self.cards_layout.insertWidget(0, ok)
        for index, finding in enumerate(self._findings):
            self.cards_layout.insertWidget(index, self._build_card(finding))
        self._render_chips()

    def _render_chips(self) -> None:
        while self.overrides_chips.count() > 1:  # keep trailing stretch
            item = self.overrides_chips.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for fragment in self._pending_overrides:
            chip = QPushButton(f"{fragment} ×")
            chip.setToolTip("Remove this override")
            chip.clicked.connect(lambda _c=False, f=fragment: self._remove_override(f))
            self.overrides_chips.insertWidget(self.overrides_chips.count() - 1, chip)
        self.overrides_row.setVisible(bool(self._pending_overrides))
        self.exclusions_row.setVisible(self._exclusion_count > 0)
        self.exclusions_label.setText(f"{self._exclusion_count} file(s) excluded from training")

    # ------------------------------------------------------------------
    # Public API (used by LoRATrainTab)
    # ------------------------------------------------------------------

    def set_images(self, images, trigger: str) -> None:
        self._token += 1
        self._images = tuple(images)
        self._trigger = trigger
        self._findings = []
        self._summary = None
        self._render()
        self._start_scan()

    def refresh_trigger(self, trigger: str) -> None:
        if trigger == self._trigger or not self._images:
            return
        self.set_images(self._images, trigger)

    def set_hydra_available(self, available: bool) -> None:
        if available != self._hydra_available:
            self._hydra_available = available
            self._render()

    def set_exclusion_count(self, count: int) -> None:
        self._exclusion_count = count
        self._render_chips()

    def set_training_guard(self, guard) -> None:
        self._training_guard = guard or (lambda: False)
        self._update_cluster_enabled()

    def hydra_overrides(self) -> list[str]:
        return list(self._pending_overrides)

    def findings(self) -> list:
        """Current finding list — consumed by the #746 report card when a
        training run finishes (duck-typed AdvisorFinding objects)."""
        return list(self._findings)

    def busy(self) -> bool:
        scan = self._scan_worker
        cluster = self._cluster_worker
        return ((scan is not None and scan.isRunning())
                or (cluster is not None and cluster.isRunning()))

    def stop(self) -> None:
        self._token += 1
        for worker in (self._scan_worker, self._cluster_worker):
            if worker is not None:
                stop_worker(worker, join=False)

    # ------------------------------------------------------------------
    # Workers
    # ------------------------------------------------------------------

    def _start_scan(self) -> None:
        if not self._images:
            self.summary_label.setText("No dataset loaded")
            return
        previous = self._scan_worker
        if previous is not None:
            stop_worker(previous, join=False)
        worker = AdvisorScanWorker(self._token, self._images, self._trigger, self._hash_cache)
        worker.finished.connect(self._on_scan_finished)
        worker.error.connect(self._on_worker_error)
        self._scan_worker = worker
        worker.start()
        retain_until_stopped(worker)

    def _on_cluster_clicked(self) -> None:
        worker = self._cluster_worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            return
        if not self._images:
            self.summary_label.setText("Load a dataset before clustering.")
            return
        worker = AdvisorClusterWorker(self._token, self._images)
        worker.finished.connect(self._on_cluster_finished)
        worker.error.connect(self._on_worker_error)
        worker.progress.connect(self._progress_show)
        self._cluster_worker = worker
        worker.start()
        retain_until_stopped(worker)
        self.cluster_btn.setText("Cancel")
        self._update_cluster_enabled()

    @Slot(int, int)
    def _progress_show(self, done: int, total: int) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(done)
        self.progress.setVisible(True)

    @Slot(object)
    def _on_scan_finished(self, payload) -> None:
        if self.sender() is not self._scan_worker:
            return
        self._scan_worker = None
        self.progress.setVisible(False)
        if payload is None:
            return
        token, report = payload
        if token != self._token:
            return
        self._findings = list(report.findings) + [f for f in self._findings if f.category == "diversity"]
        self._summary = report.summary
        self._render()

    @Slot(object)
    def _on_cluster_finished(self, payload) -> None:
        if self.sender() is not self._cluster_worker:
            return
        self._cluster_worker = None
        self.progress.setVisible(False)
        self.cluster_btn.setText("Cluster (GPU)")
        self._update_cluster_enabled()
        if payload is None:
            return
        token, findings = payload
        if token != self._token:
            return
        self._findings = [f for f in self._findings if f.category != "diversity"]
        self._findings.extend(findings)
        self._render()

    @Slot(object)
    def _on_worker_error(self, exc) -> None:
        sender = self.sender()
        if sender not in (self._scan_worker, self._cluster_worker):
            return
        if sender is self._scan_worker:
            self._scan_worker = None
            self.progress.setVisible(False)
        elif sender is self._cluster_worker:
            self._cluster_worker = None
            self.progress.setVisible(False)
            self.cluster_btn.setText("Cluster (GPU)")
            self._update_cluster_enabled()
        self.summary_label.setText(str(exc))

    def _update_cluster_enabled(self) -> None:
        worker = self._cluster_worker
        running = worker is not None and worker.isRunning()
        self.cluster_btn.setEnabled(running or not self._training_guard())

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def _queue_override(self, fragment: str) -> None:
        if fragment and fragment not in self._pending_overrides:
            self._pending_overrides.append(fragment)
            self.hydra_overrides_changed.emit(self.hydra_overrides())
            self._render()

    def _remove_override(self, fragment: str) -> None:
        if fragment in self._pending_overrides:
            self._pending_overrides.remove(fragment)
            self.hydra_overrides_changed.emit(self.hydra_overrides())
            self._render()
