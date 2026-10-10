"""Shared Deep Learning workspace host (#730).

Four destinations on a stacked content region — not a QTabWidget — so
route activation cannot accidentally use a magic tab index.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.modules.events import EventHub, ImportPathsIntent
from gui.src.modules.tab_factory import build_tab

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
        root.addLayout(strip)

        self._stack = QStackedWidget()
        root.addWidget(self._stack, stretch=1)
        self.activate_route("train")

    def activate_route(self, route_key: str) -> None:
        if route_key not in dict(_DESTINATIONS):
            raise LookupError(f"Unknown Deep Learning workspace route: {route_key}")
        page = self._ensure_page(route_key)
        self._stack.setCurrentWidget(page)
        button = self._route_buttons[route_key]
        if not button.isChecked():
            button.setChecked(True)

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
