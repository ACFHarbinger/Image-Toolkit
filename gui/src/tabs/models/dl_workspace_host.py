"""Shared Deep Learning workspace host (#730).

Four destinations on a stacked content region — not a QTabWidget — so
route activation cannot accidentally use a magic tab index.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.modules.events import EventHub, ImportPathsIntent
from gui.src.modules.tab_factory import build_tab
from gui.src.tabs.models.dl_comparison_spine import (
    ComparisonSpine,
    PinnedRun,
    artifact_from_config,
)

_DESTINATIONS = (
    ("train", "Train"),
    ("generate", "Generate"),
    ("review", "Review"),
    ("runs", "Runs"),
)


class DeepLearningWorkspaceHost(QWidget):
    """One host widget for Train / Generate / Review / Runs."""

    def __init__(self, event_hub: EventHub | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._event_hub = event_hub
        self._pages: dict[str, QWidget] = {}
        self._train_tab: QWidget | None = None
        self._current_route = "train"
        self._build_ui()
        if event_hub is not None:
            event_hub.subscribe(ImportPathsIntent, self._on_import_paths, owner=self)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        strip = QHBoxLayout()
        strip.setSpacing(4)
        self._route_group = QButtonGroup(self)
        self._route_group.setExclusive(True)
        self._route_buttons: dict[str, QPushButton] = {}
        for index, (route_key, title) in enumerate(_DESTINATIONS):
            button = QPushButton(title)
            button.setCheckable(True)
            button.setObjectName(f"dl_dest_{route_key}")
            button.clicked.connect(lambda _=False, key=route_key: self.activate_route(key))
            self._route_group.addButton(button, index)
            self._route_buttons[route_key] = button
            strip.addWidget(button)
        strip.addStretch()
        self._pin_current = QPushButton("☆ Pin form")
        self._pin_current.setObjectName("dl_pin_current")
        self._pin_current.setToolTip("Pin the visible form's settings into the comparison strip")
        self._pin_current.clicked.connect(self.pin_current_form)
        strip.addWidget(self._pin_current)
        root.addLayout(strip)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)

        # Spine sits above the filmstrip and outside the stack, so pins
        # survive destination switches (#732).
        self._spine = ComparisonSpine()
        self._spine.pin_activated.connect(self._clone_pin)
        self._spine.pins_changed.connect(self._sync_run_cards)
        root.addWidget(self._spine)
        self.activate_route("train")

    def activate_route(self, route_key: str) -> None:
        if route_key not in dict(_DESTINATIONS):
            raise LookupError(f"Unknown Deep Learning workspace route: {route_key}")
        page = self._ensure_page(route_key)
        self._stack.setCurrentWidget(page)
        self._current_route = route_key
        button = self._route_buttons[route_key]
        if not button.isChecked():
            button.setChecked(True)
        self._spine.revalidate()
        self._sync_run_cards()

    def _ensure_page(self, route_key: str) -> QWidget:
        existing = self._pages.get(route_key)
        if existing is not None:
            return existing
        page = self._build_page(route_key)
        self._pages[route_key] = page
        self._stack.addWidget(page)
        return page

    def _build_page(self, route_key: str) -> QWidget:
        if route_key == "train":
            from gui.src.modules.context import ModuleContext, ModuleServices

            context = ModuleContext(event_hub=self._event_hub or EventHub(self), services=ModuleServices())
            tab = build_tab("ml.training", context)
            self._train_tab = tab
            return tab
        if route_key == "generate":
            from gui.src.modules.context import ModuleContext, ModuleServices

            context = ModuleContext(event_hub=self._event_hub or EventHub(self), services=ModuleServices())
            return build_tab("ml.generation", context)
        if route_key == "review":
            return _ReviewToolsPage()
        return _RunsPlaceholderPage()

    def _on_import_paths(self, intent: ImportPathsIntent) -> None:
        if intent.module_id not in {"dl", "dl.train", "ml.training"}:
            return
        self.activate_route("train")
        tab = self._train_tab
        apply = getattr(tab, "apply_imported_paths", None)
        if callable(apply):
            apply(intent.paths)

    def note_run(self, run: PinnedRun) -> None:
        """Register a run card. The star on that card pins it."""
        self._spine.note_run(run)

    def pin_run(self, run_id: str) -> bool:
        return self._spine.pin(run_id)

    def unpin_run(self, run_id: str) -> None:
        self._spine.unpin(run_id)

    def pin_current_form(self) -> PinnedRun | None:
        """Snapshot the visible form into a run card and pin it."""
        page = self._stack.currentWidget()
        collect = getattr(page, "collect", None)
        config = collect() if callable(collect) else {}
        if not isinstance(config, dict):
            config = {}
        run = PinnedRun(
            run_id=f"{self._current_route}-{len(self._spine.noted_runs()) + 1}",
            label=f"{self._current_route} settings",
            artifact_path=artifact_from_config(config),
            config=config,
        )
        self.note_run(run)
        self.pin_run(run.run_id)
        return run

    def _clone_pin(self, run: PinnedRun) -> None:
        if not run.available:
            return
        page = self._stack.currentWidget()
        apply = getattr(page, "apply_pinned_run", None)
        if callable(apply):
            apply(run)
            return
        set_config = getattr(page, "set_config", None)
        if callable(set_config) and run.config:
            set_config(run.config)

    def _sync_run_cards(self) -> None:
        page = self._pages.get("runs")
        if isinstance(page, _RunsPlaceholderPage):
            page.set_runs(self._spine.noted_runs(), self._spine.pinned_ids())


class _ReviewToolsPage(QWidget):
    """R3GAN eval and MetaCLIP stay tools opened from Review, not destinations."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Review tool:"))
        self._eval_btn = QPushButton("R3GAN Evaluation")
        self._clip_btn = QPushButton("MetaCLIP Inference")
        row.addWidget(self._eval_btn)
        row.addWidget(self._clip_btn)
        row.addStretch()
        layout.addLayout(row)

        self._compare = QLabel("Pin a run, then click it to load it here.")
        self._compare.setObjectName("dl_compare_canvas")
        self._compare.setWordWrap(True)
        layout.addWidget(self._compare)

        self._stack = QStackedWidget()
        from gui.src.tabs.models.meta_clip_inference_tab import MetaCLIPInferenceTab
        from gui.src.tabs.models.r3gan_evaluate_tab import R3GANEvaluateTab

        self._eval = R3GANEvaluateTab()
        self._clip = MetaCLIPInferenceTab()
        self._stack.addWidget(self._eval)
        self._stack.addWidget(self._clip)
        layout.addWidget(self._stack, stretch=1)
        self._eval_btn.clicked.connect(lambda: self._stack.setCurrentWidget(self._eval))
        self._clip_btn.clicked.connect(lambda: self._stack.setCurrentWidget(self._clip))

    def apply_pinned_run(self, run: PinnedRun) -> None:
        """Show the pinned artifact on the compare canvas. Does not remove stale pins."""
        artifact = run.artifact_path or "settings only"
        self._compare.setText(f"{run.label}\n{artifact}")


class _RunsPlaceholderPage(QWidget):
    """Run list lives here later; not VirtualGallery / ThumbnailScheduler."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        hint = QLabel("Run history will appear here. This list is not the library gallery.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self._list = QListWidget()
        self._list.setObjectName("dl_runs_list")
        layout.addWidget(self._list, stretch=1)

    def set_runs(self, runs: list[PinnedRun], pinned_ids: set[str]) -> None:
        self._list.clear()
        for run in runs:
            item = QListWidgetItem()
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)
            title = run.label if run.available else f"Unavailable · {run.label}"
            row_layout.addWidget(QLabel(title), stretch=1)
            star = QPushButton("★" if run.run_id in pinned_ids else "☆")
            star.setObjectName(f"dl_run_star_{run.run_id}")
            want_pin = run.run_id not in pinned_ids
            star.clicked.connect(
                lambda _=False, run_id=run.run_id, pin=want_pin: self._on_star(run_id, pin)
            )
            row_layout.addWidget(star)
            item.setSizeHint(QSize(0, 36))
            self._list.addItem(item)
            self._list.setItemWidget(item, row)

    def _on_star(self, run_id: str, pin: bool) -> None:
        host = self.parent()
        while host is not None and not hasattr(host, "pin_run"):
            host = host.parent()
        if host is None:
            return
        if pin:
            host.pin_run(run_id)
        else:
            host.unpin_run(run_id)
