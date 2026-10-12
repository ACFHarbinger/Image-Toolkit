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

import os

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

from gui.src.components.guidance.what_changed_overlay import WhatChangedOverlay
from gui.src.modules.events import EventHub, ImportPathsIntent
from gui.src.modules.tab_factory import build_tab
from gui.src.preferences import PreferenceStore, PrefKeys
from gui.src.tabs.models.dl_comparison_spine import (
    ComparisonSpine,
    PinnedRun,
    is_image_artifact,
)
from gui.src.tabs.models.dl_workspace_components import (
    ActionableEmptyState,
    EffectiveConfigBar,
    GuidedOnboardingCard,
    ProgressiveDisclosureControl,
)
from gui.src.tabs.models.review_vision_tools import ReviewVisionPanel
from gui.src.tabs.models.guidance_diff_widget import GuidanceDiffWidget
from gui.src.tabs.models.upscale_handoff import UpscaleRunner

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
        self._spine.pins_changed.connect(self._show_compare)
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
        self._show_compare()

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
            from gui.src.tabs.models.gen.generate_surface import GenerateSurface

            context = ModuleContext(
                event_hub=self._event_hub or EventHub(self),
                services=ModuleServices(),
            )
            tab = build_tab("ml.generation", context)
            comfy = GenerateSurface()
            self._generate_tab = tab
            page = _GenerateDestinationPage(
                tab, preference_store=self._preference_store, comfy_surface=comfy,
            )
            self._generate_page = page
            return page
        if route_key == "review":
            page = _ReviewToolsPage(self, preference_store=self._preference_store)
            self._review_page = page
            return page
        page = _RunsPage(self)
        self._runs_page = page
        return page

    def disposal_ready(self) -> bool:
        ready = getattr(self._train_tab, "disposal_ready", None)
        return not callable(ready) or ready()

    def prepare_dispose(self) -> None:
        """Cancel child workers before deleteLater skips closeEvent."""
        seen: set[int] = set()
        pages = list(self._pages.values())
        if self._train_tab is not None:
            pages.append(self._train_tab)
        for page in pages:
            marker = id(page)
            if marker in seen:
                continue
            seen.add(marker)
            prepare = getattr(page, "prepare_dispose", None)
            if callable(prepare):
                prepare()

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

    def generate_selection(self):
        """(prompt_id, workflow, surface_mode) of the Generate filmstrip selection.

        Duck-typed so Review never imports the Generate surface (#752).
        None when nothing (selectable) is selected.
        """
        page = self._pages.get("generate")
        surface = getattr(page, "_comfy_surface", None)
        strip = getattr(surface, "_filmstrip", None)
        record = strip.selected_record() if strip is not None else None
        workflow = getattr(record, "workflow", None) if record is not None else None
        if not isinstance(workflow, dict):
            return None
        return (record.prompt_id, workflow, getattr(record, "surface_mode", None))

    def pin_current_form(self) -> PinnedRun | None:
        """Snapshot the visible form into a run card and pin it.

        The snapshot is settings only. A future output filename is not an
        artifact, and a missing input must not be inferred from it.
        """
        page = self._stack.currentWidget()
        page = getattr(page, "tab", page)
        collect = getattr(page, "collect", None)
        if not callable(collect):
            return None
        config = collect()
        if not isinstance(config, dict):
            config = {}
        run = PinnedRun(
            run_id=f"{self._current_route}-{len(self._spine.noted_runs()) + 1}",
            label=f"{self._current_route} settings",
            artifact_path="",
            config=config,
        )
        self.note_run(run)
        self.pin_run(run.run_id)
        return run

    def _clone_pin(self, run: PinnedRun) -> None:
        if not run.available:
            return
        self._show_compare(focus=run)
        page = self._stack.currentWidget()
        page = getattr(page, "tab", page)
        if isinstance(page, _ReviewToolsPage):
            return
        apply = getattr(page, "apply_pinned_run", None)
        if callable(apply):
            apply(run)
            return
        set_config = getattr(page, "set_config", None)
        if callable(set_config) and run.config:
            set_config(run.config)

    def _show_compare(self, focus: PinnedRun | None = None) -> None:
        page = self._pages.get("review")
        if not isinstance(page, _ReviewToolsPage):
            return
        runs = list(self._spine.pinned_runs())
        if focus is not None and focus.available:
            runs = [focus] + [item for item in runs if item.run_id != focus.run_id]
        paths = [
            os.path.expanduser(run.artifact_path)
            for run in runs
            if run.available and is_image_artifact(run.artifact_path)
        ]
        page.set_compare_paths(paths)

    def _sync_run_cards(self) -> None:
        page = self._pages.get("runs")
        if isinstance(page, _RunsPage):
            page.set_runs(self._spine.noted_runs(), self._spine.pinned_ids())


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
        comfy_surface: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tab = tab
        self._comfy_surface = comfy_surface
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

        if comfy_surface is None:
            self._body = None
            layout.addWidget(tab, stretch=1)
        else:
            switch = QHBoxLayout()
            self._models_btn = QPushButton("Models")
            self._comfy_btn = QPushButton("Comfy")
            self._models_btn.setObjectName("dl_generate_models")
            self._comfy_btn.setObjectName("dl_generate_comfy")
            self._models_btn.setCheckable(True)
            self._comfy_btn.setCheckable(True)
            self._models_btn.clicked.connect(lambda: self._show_generate_body("models"))
            self._comfy_btn.clicked.connect(lambda: self._show_generate_body("comfy"))
            switch.addWidget(self._models_btn)
            switch.addWidget(self._comfy_btn)
            switch.addStretch()
            layout.addLayout(switch)
            self._body = QStackedWidget()
            self._body.addWidget(tab)
            self._body.addWidget(comfy_surface)
            layout.addWidget(self._body, stretch=1)
            self._show_generate_body("comfy")

        # Wire connections
        if hasattr(tab, "apply_disclosure_tier"):
            self.disclosure.tier_changed.connect(tab.apply_disclosure_tier)
            tab.apply_disclosure_tier(self.disclosure.tier())
        if hasattr(tab, "effective_config_changed") and hasattr(tab, "get_effective_config_summary"):
            self.config_bar.connect_tab(tab)

    def _show_generate_body(self, which: str) -> None:
        comfy = which == "comfy" and self._comfy_surface is not None
        if self._body is not None:
            self._body.setCurrentWidget(self._comfy_surface if comfy else self.tab)
        if hasattr(self, "_models_btn"):
            self._models_btn.setChecked(not comfy)
            self._comfy_btn.setChecked(comfy)
        # The model summary describes the checkpoint form, not the Comfy draft.
        self.config_bar.setVisible(not comfy)
        self.disclosure.setVisible(not comfy)

    def _visible_generate_body(self) -> QWidget:
        if self._body is None:
            return self.tab
        current = self._body.currentWidget()
        return current if current is not None else self.tab

    def collect(self) -> dict:
        target = self._visible_generate_body()
        collect_fn = getattr(target, "collect", None)
        return collect_fn() if callable(collect_fn) else {}

    def set_config(self, config: dict) -> None:
        set_fn = getattr(self._visible_generate_body(), "set_config", None)
        if callable(set_fn):
            set_fn(config)

    def apply_pinned_run(self, run) -> None:
        target = self._visible_generate_body()
        apply_fn = getattr(target, "apply_pinned_run", None)
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

        self._compare_host = QWidget()
        self._compare_host.setObjectName("dl_compare_canvas")
        self._compare_host.setMinimumHeight(280)
        self._compare_layout = QVBoxLayout(self._compare_host)
        self._compare_layout.setContentsMargins(0, 0, 0, 0)
        self._what_changed = WhatChangedOverlay(self._compare_host)
        self._what_changed.setObjectName("dl_what_changed")
        self._compare_layout.addWidget(self._what_changed)
        layout.addWidget(self._compare_host, stretch=1)

        upscale_row = QHBoxLayout()
        self._upscale_btn = QPushButton("Send to Upscale")
        self._upscale_btn.setObjectName("dl_review_upscale_btn")
        self._upscale_btn.setToolTip("Upscale the first compared image with Real-ESRGAN anime_6B (#749)")
        self._upscale_btn.clicked.connect(self._on_upscale)
        self._upscale_status = QLabel("")
        self._upscale_status.setWordWrap(True)
        self._upscale_status.setObjectName("dl_review_upscale_status")
        upscale_row.addWidget(self._upscale_btn)
        upscale_row.addWidget(self._upscale_status, stretch=1)
        layout.addLayout(upscale_row)
        self._upscaler = UpscaleRunner(self)
        self._upscaler.finished.connect(self._on_upscale_finished)
        self._upscaler.error.connect(self._on_upscale_error)

        self._vision = ReviewVisionPanel()
        layout.addWidget(self._vision)
        load_row = QHBoxLayout()
        self._load_selection_btn = QPushButton("Load selected Generate run")
        self._load_selection_btn.setObjectName("dl_guidance_load_btn")
        self._load_selection_btn.setToolTip("Use the Generate filmstrip selection as the critiqued run (#752)")
        self._load_selection_btn.clicked.connect(self._on_load_generate_selection)
        load_row.addWidget(self._load_selection_btn)
        load_row.addStretch()
        layout.addLayout(load_row)
        from gui.src.modules.comfy_workspace_controller import ComfyWorkspaceController

        _controller = ComfyWorkspaceController.instance()
        self._guidance = GuidanceDiffWidget(controller=_controller, manager=_controller.manager)
        self._guidance.setObjectName("dl_guidance_diff")
        layout.addWidget(self._guidance)
        self._what_changed.feedback_changed.connect(self._guidance.set_feedback)
        self._what_changed.verdict_chosen.connect(self._on_guidance_verdict)
        self._guidance.trajectory_updated.connect(self._on_trajectory_updated)

        self.set_compare_paths([])

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

    def set_compare_paths(self, paths: list[str]) -> None:
        """Show *paths* in the shared pan/zoom/A-B/diff view."""
        from gui.src.windows.image_compare_window import ImageCompareWindow

        self.empty_state.setVisible(not paths)
        self._vision.set_image(paths[0] if paths else None)
        if getattr(self, "_compare_paths", None) == paths:
            return
        self._compare_paths = list(paths)
        self._clear_compare_view()
        if not paths:
            empty = QLabel("Pin an image to compare it.")
            empty.setObjectName("dl_compare_empty")
            self._compare_layout.insertWidget(0, empty)
            return
        view = ImageCompareWindow(paths, parent=self._compare_host, embedded=True)
        view.setObjectName("dl_compare_view")
        self._compare_layout.insertWidget(0, view)

    def _clear_compare_view(self) -> None:
        """Replace the compare view/empty label without disposing the overlay."""
        for index in range(self._compare_layout.count() - 1, -1, -1):
            item = self._compare_layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is None or widget is self._what_changed:
                continue
            self._compare_layout.takeAt(index)
            widget.setParent(None)
            widget.deleteLater()

    def _on_trajectory_updated(self, traj) -> None:
        self._what_changed.set_trajectory(traj)

    def advisor_trajectory(self):
        """Payload for the next advisor call (#750): trajectory, not just now."""
        from backend.src.core.guidance_trajectory import format_for_advisor

        traj = self._what_changed.trajectory()
        return format_for_advisor(traj) if traj is not None else None

    def _on_guidance_verdict(self, _verdict: str) -> None:
        traj = self._what_changed.trajectory()
        if traj is None:
            return
        payload = {"guidance_trajectory": traj.to_dict()}
        latest = traj.latest
        variant_id = latest.variant_prompt_id if latest is not None else None
        updater = getattr(self._guidance._manager, "update_run_meta", None)
        if callable(updater) and variant_id:
            updater(variant_id, payload)
        persist = getattr(self._guidance, "_persist_sidecar", None)
        if callable(persist):
            persist(traj)

    def _on_upscale(self) -> None:
        """Upscale the focused (first) compared image on the shared admission (#749)."""
        paths = list(getattr(self, "_compare_paths", ()))
        if not paths:
            self._upscale_status.setText("No output to upscale — pin an image first.")
            return
        self._upscale_btn.setEnabled(False)
        self._upscale_status.setText(f"Upscaling {os.path.basename(paths[0])}…")
        self._upscaler.start([paths[0]])

    def _on_upscale_finished(self, outputs) -> None:
        self._upscale_btn.setEnabled(True)
        if not outputs:
            self._upscale_status.setText("Upscale finished with no output.")
            return
        paths = list(getattr(self, "_compare_paths", ()))
        for path in outputs:
            if path not in paths:
                paths.append(path)
        self.set_compare_paths(paths)
        self._upscale_status.setText(f"Upscaled → {os.path.basename(outputs[-1])}")

    def _on_upscale_error(self, message: str) -> None:
        self._upscale_btn.setEnabled(True)
        self._upscale_status.setText(message)

    def show_guidance(self, *, workflow, validation, source_prompt_id=None, source_mode=None) -> None:
        """Render validated suggestions (#750/#753 produce these; #754 reads the outcome)."""
        self._guidance.set_guidance(
            workflow=workflow,
            validation=validation,
            source_prompt_id=source_prompt_id,
            source_mode=source_mode,
        )

    def _on_load_generate_selection(self) -> None:
        selection = self._host.generate_selection()
        if selection is None:
            self._guidance.note("Select a run in Generate's filmstrip first.")
            return
        prompt_id, workflow, mode = selection
        self._guidance.set_source(prompt_id, workflow, mode)


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
        self.update_empty_state()

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
