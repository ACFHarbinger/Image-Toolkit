"""Shared Deep Learning workspace host (#730, #731, #735).

Four destinations on a stacked content region — not a QTabWidget — so
route activation cannot accidentally use a magic tab index.

Equipped with:
- Effective-config bars on Train and Generate (#731)
- Progressive disclosure controls (Simple / Standard / Advanced) (#731)
- Actionable empty states on Runs and Review (#731)
- One-time dismissable guided onboarding cards per destination (#735)
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
from gui.src.preferences import PreferenceStore, PrefKeys
from gui.src.tabs.models.dl_workspace_components import (
    ActionableEmptyState,
    EffectiveConfigBar,
    GuidedOnboardingCard,
    ProgressiveDisclosureControl,
)

_DESTINATIONS = (
    ("train", "Train"),
    ("generate", "Generate"),
    ("review", "Review"),
    ("runs", "Runs"),
)


class DeepLearningWorkspaceHost(QWidget):
    """One host widget for Train / Generate / Review / Runs."""

    def __init__(
        self,
        event_hub: EventHub | None = None,
        preference_store: PreferenceStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._event_hub = event_hub
        self._preference_store = preference_store or PreferenceStore.instance()
        self._pages: dict[str, QWidget] = {}
        self._train_tab: QWidget | None = None
        self._generate_tab: QWidget | None = None
        self._train_page: _TrainDestinationPage | None = None
        self._generate_page: _GenerateDestinationPage | None = None
        self._review_page: _ReviewToolsPage | None = None
        self._runs_page: _RunsPage | None = None
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

            context = ModuleContext(
                event_hub=self._event_hub or EventHub(self),
                services=ModuleServices(),
            )
            tab = build_tab("ml.training", context)
            self._train_tab = tab
            page = _TrainDestinationPage(tab, preference_store=self._preference_store)
            self._train_page = page
            return page
        if route_key == "generate":
            from gui.src.modules.context import ModuleContext, ModuleServices

            context = ModuleContext(
                event_hub=self._event_hub or EventHub(self),
                services=ModuleServices(),
            )
            tab = build_tab("ml.generation", context)
            self._generate_tab = tab
            page = _GenerateDestinationPage(tab, preference_store=self._preference_store)
            self._generate_page = page
            return page
        if route_key == "review":
            page = _ReviewToolsPage(self, preference_store=self._preference_store)
            self._review_page = page
            return page
        page = _RunsPage(self)
        self._runs_page = page
        return page

    def _on_import_paths(self, intent: ImportPathsIntent) -> None:
        if intent.module_id not in {"dl", "dl.train", "ml.training"}:
            return
        self.activate_route("train")
        tab = self._train_tab
        apply = getattr(tab, "apply_imported_paths", None)
        if callable(apply):
            apply(intent.paths)


class _TrainDestinationPage(QWidget):
    """Train destination wrapper with onboarding, effective config bar, and disclosure tiers."""

    def __init__(
        self,
        tab: QWidget,
        preference_store: PreferenceStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tab = tab
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.onboarding = GuidedOnboardingCard(
            destination="train",
            preference_def=PrefKeys.DL_ONBOARDING_TRAIN_DISMISSED,
            preference_store=preference_store,
        )
        layout.addWidget(self.onboarding)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.config_bar = EffectiveConfigBar()
        controls_row.addWidget(self.config_bar, stretch=1)

        self.disclosure = ProgressiveDisclosureControl(
            preference_def=PrefKeys.DL_DISCLOSURE_TIER_TRAIN,
            preference_store=preference_store,
        )
        self.disclosure.setObjectName("dl_tier_train_control")
        controls_row.addWidget(self.disclosure)
        layout.addLayout(controls_row)

        layout.addWidget(tab, stretch=1)

        # Wire connections
        if hasattr(tab, "apply_disclosure_tier"):
            self.disclosure.tier_changed.connect(tab.apply_disclosure_tier)
            tab.apply_disclosure_tier(self.disclosure.tier())
        if hasattr(tab, "effective_config_changed") and hasattr(tab, "get_effective_config_summary"):
            self.config_bar.connect_tab(tab)

    def collect(self) -> dict:
        collect_fn = getattr(self.tab, "collect", None)
        return collect_fn() if callable(collect_fn) else {}

    def set_config(self, config: dict) -> None:
        set_fn = getattr(self.tab, "set_config", None)
        if callable(set_fn):
            set_fn(config)

    def apply_pinned_run(self, run) -> None:
        apply_fn = getattr(self.tab, "apply_pinned_run", None)
        if callable(apply_fn):
            apply_fn(run)


class _GenerateDestinationPage(QWidget):
    """Generate destination wrapper with onboarding, effective config bar, and disclosure tiers."""

    def __init__(
        self,
        tab: QWidget,
        preference_store: PreferenceStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tab = tab
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.onboarding = GuidedOnboardingCard(
            destination="generate",
            preference_def=PrefKeys.DL_ONBOARDING_GENERATE_DISMISSED,
            preference_store=preference_store,
        )
        layout.addWidget(self.onboarding)

        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.config_bar = EffectiveConfigBar()
        controls_row.addWidget(self.config_bar, stretch=1)

        self.disclosure = ProgressiveDisclosureControl(
            preference_def=PrefKeys.DL_DISCLOSURE_TIER_GENERATE,
            preference_store=preference_store,
        )
        self.disclosure.setObjectName("dl_tier_generate_control")
        controls_row.addWidget(self.disclosure)
        layout.addLayout(controls_row)

        layout.addWidget(tab, stretch=1)

        # Wire connections
        if hasattr(tab, "apply_disclosure_tier"):
            self.disclosure.tier_changed.connect(tab.apply_disclosure_tier)
            tab.apply_disclosure_tier(self.disclosure.tier())
        if hasattr(tab, "effective_config_changed") and hasattr(tab, "get_effective_config_summary"):
            self.config_bar.connect_tab(tab)

    def collect(self) -> dict:
        collect_fn = getattr(self.tab, "collect", None)
        return collect_fn() if callable(collect_fn) else {}

    def set_config(self, config: dict) -> None:
        set_fn = getattr(self.tab, "set_config", None)
        if callable(set_fn):
            set_fn(config)

    def apply_pinned_run(self, run) -> None:
        apply_fn = getattr(self.tab, "apply_pinned_run", None)
        if callable(apply_fn):
            apply_fn(run)


class _ReviewToolsPage(QWidget):
    """Review destination with onboarding, empty state, and evaluation/inference tools (#731, #735)."""

    def __init__(
        self,
        host: DeepLearningWorkspaceHost,
        preference_store: PreferenceStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._host = host
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.onboarding = GuidedOnboardingCard(
            destination="review",
            preference_def=PrefKeys.DL_ONBOARDING_REVIEW_DISMISSED,
            preference_store=preference_store,
        )
        layout.addWidget(self.onboarding)

        self.empty_state = ActionableEmptyState(
            title="No Output Selected for Review",
            description="Select an output from your recent runs or generate a new image to inspect with R3GAN or MetaCLIP.",
            actions=[("Go to Generate", lambda: host.activate_route("generate"))],
        )
        self.empty_state.setObjectName("dl_review_empty_state")
        layout.addWidget(self.empty_state)

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


class _RunsPage(QWidget):
    """Run list with designed actionable empty state (#731)."""

    def __init__(
        self,
        host: DeepLearningWorkspaceHost,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._host = host
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.empty_state = ActionableEmptyState(
            title="No Runs Yet",
            description="Pick a capability, set a dataset, and press Start to record training or generation runs.",
            actions=[
                ("Start Training", lambda: host.activate_route("train")),
                ("Generate Image", lambda: host.activate_route("generate")),
            ],
        )
        self.empty_state.setObjectName("dl_runs_empty_state")
        layout.addWidget(self.empty_state)

        self._list = QListWidget()
        self._list.setObjectName("dl_runs_list")
        layout.addWidget(self._list, stretch=1)
        self.update_empty_state()

    def add_run_item(self, text: str) -> None:
        self._list.addItem(text)
        self.update_empty_state()

    def update_empty_state(self) -> None:
        has_items = self._list.count() > 0
        self.empty_state.setVisible(not has_items)
        self._list.setVisible(has_items)
