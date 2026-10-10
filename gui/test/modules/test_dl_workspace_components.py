"""Tests for Deep Learning workspace components: EffectiveConfigBar,
ProgressiveDisclosureControl, GuidedOnboardingCard, and ActionableEmptyState (#731, #735).
"""

from __future__ import annotations

import pytest
from gui.src.classes.base.base_generative_tab import (
    TIER_ADVANCED,
    TIER_SIMPLE,
    TIER_STANDARD,
    BaseGenerativeTab,
)
from gui.src.modules.events import EventHub
from gui.src.preferences import MemoryPreferenceAdapter, PreferenceScope, PreferenceStore, PrefKeys
from gui.src.tabs.models.delta.lora_train_tab import LoRATrainTab
from gui.src.tabs.models.dl_workspace_components import (
    ActionableEmptyState,
    EffectiveConfigBar,
    GuidedOnboardingCard,
    ProgressiveDisclosureControl,
)
from gui.src.tabs.models.dl_workspace_host import (
    DeepLearningWorkspaceHost,
)
from PySide6.QtWidgets import QApplication, QPushButton

pytestmark = pytest.mark.gui


class DummyGenerativeTab(BaseGenerativeTab):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._summary = "engine:sdxl | lr:0.0001"

    def get_effective_config_summary(self) -> str:
        return self._summary

    def set_summary(self, val: str) -> None:
        self._summary = val
        self.notify_effective_config_changed()


def _memory_store() -> PreferenceStore:
    store = PreferenceStore(lazy_adapters=True)
    store.register_adapter(PreferenceScope.ACCOUNT, MemoryPreferenceAdapter())
    return store


def test_effective_config_bar_direct_and_tab_binding(q_app):
    bar = EffectiveConfigBar()
    assert bar.summary() == ""

    bar.set_summary("model:sdxl | trigger:cat")
    assert bar.summary() == "model:sdxl | trigger:cat"

    tab = DummyGenerativeTab()
    bar.connect_tab(tab)
    assert bar.summary() == "engine:sdxl | lr:0.0001"

    tab.set_summary("engine:sdxl | lr:0.0002")
    assert bar.summary() == "engine:sdxl | lr:0.0002"

    # Test copy button copies to clipboard
    bar._copy_btn.click()
    clipboard = QApplication.clipboard()
    if clipboard is not None:
        assert clipboard.text() == "engine:sdxl | lr:0.0002"


def test_progressive_disclosure_control_switching_and_persistence(q_app):
    store = _memory_store()
    control = ProgressiveDisclosureControl(
        preference_def=PrefKeys.DL_DISCLOSURE_TIER_TRAIN,
        preference_store=store,
    )
    assert control.tier() == TIER_STANDARD

    emitted_tiers: list[str] = []
    control.tier_changed.connect(emitted_tiers.append)

    # Click simple
    btn_simple = control.findChild(QPushButton, "dl_tier_simple")
    assert btn_simple is not None
    btn_simple.click()
    assert control.tier() == TIER_SIMPLE
    assert store.get(PrefKeys.DL_DISCLOSURE_TIER_TRAIN.key) == TIER_SIMPLE
    assert emitted_tiers[-1] == TIER_SIMPLE

    # Click advanced
    btn_adv = control.findChild(QPushButton, "dl_tier_advanced")
    assert btn_adv is not None
    btn_adv.click()
    assert control.tier() == TIER_ADVANCED
    assert store.get(PrefKeys.DL_DISCLOSURE_TIER_TRAIN.key) == TIER_ADVANCED
    assert emitted_tiers[-1] == TIER_ADVANCED

    # Reconnect with same store loads persisted tier
    control2 = ProgressiveDisclosureControl(
        preference_def=PrefKeys.DL_DISCLOSURE_TIER_TRAIN,
        preference_store=store,
    )
    assert control2.tier() == TIER_ADVANCED


def test_guided_onboarding_card_dismiss_and_reset(q_app):
    store = _memory_store()
    card = GuidedOnboardingCard(
        destination="train",
        preference_def=PrefKeys.DL_ONBOARDING_TRAIN_DISMISSED,
        preference_store=store,
    )
    card.show()
    assert not card.isHidden()
    assert card.is_dismissed() is False

    dismissed_called = []
    card.dismissed.connect(lambda: dismissed_called.append(True))

    dismiss_btn = card.findChild(QPushButton, "dl_onboarding_dismiss_btn")
    assert dismiss_btn is not None
    dismiss_btn.click()

    assert card.isHidden() is True
    assert card.is_dismissed() is True
    assert store.get(PrefKeys.DL_ONBOARDING_TRAIN_DISMISSED.key) is True
    assert dismissed_called == [True]

    # Recreating with same store starts hidden
    card2 = GuidedOnboardingCard(
        destination="train",
        preference_def=PrefKeys.DL_ONBOARDING_TRAIN_DISMISSED,
        preference_store=store,
    )
    assert card2.isHidden() is True
    assert card2.is_dismissed() is True

    # Reset makes visible again
    card2.reset()
    assert not card2.isHidden()
    assert card2.is_dismissed() is False
    assert store.get(PrefKeys.DL_ONBOARDING_TRAIN_DISMISSED.key) is False


def test_actionable_empty_state_action_triggers(q_app):
    called = []
    state = ActionableEmptyState(
        title="Empty",
        description="Nothing here",
        actions=[("Do Something", lambda: called.append("action_done"))],
    )
    btn = state.findChild(QPushButton, "dl_empty_action_do_something")
    assert btn is not None
    btn.click()
    assert called == ["action_done"]


def test_base_generative_tab_tier_filtering(q_app):
    tab = LoRATrainTab()
    tab.show()
    q_app.processEvents()

    model_widget = tab.widgets["model_id"]
    epochs_widget = tab.widgets["epochs"]
    engine_widget = tab.widgets["engine"]

    # Check tagged tiers in _param_rows
    assert tab._param_rows["model_id"][2] == TIER_SIMPLE
    assert tab._param_rows["epochs"][2] == TIER_STANDARD
    assert tab._param_rows["engine"][2] == TIER_ADVANCED

    # Apply simple
    tab.apply_disclosure_tier(TIER_SIMPLE)
    assert not model_widget.isHidden()
    assert epochs_widget.isHidden()
    assert engine_widget.isHidden()

    # Apply standard
    tab.apply_disclosure_tier(TIER_STANDARD)
    assert not model_widget.isHidden()
    assert not epochs_widget.isHidden()
    assert engine_widget.isHidden()

    # Apply advanced
    tab.apply_disclosure_tier(TIER_ADVANCED)
    assert not model_widget.isHidden()
    assert not epochs_widget.isHidden()
    assert not engine_widget.isHidden()


def test_dl_workspace_host_train_and_generate_pages(q_app):
    store = _memory_store()
    event_hub = EventHub(q_app)
    host = DeepLearningWorkspaceHost(event_hub=event_hub, preference_store=store)
    host.show()
    q_app.processEvents()

    # Train route is active by default
    assert host._stack.currentWidget() is host._train_page
    assert host._train_page is not None

    onboarding = host.findChild(GuidedOnboardingCard, "dl_onboarding_train")
    assert onboarding is not None
    assert not onboarding.isHidden()

    bar = host.findChild(EffectiveConfigBar, "dl_effective_config_bar")
    assert bar is not None
    assert "model:" in bar.summary() or "model_id:" in bar.summary() or "LoRA" in bar.summary()

    # Disclosure control switching applies to train form
    disclosure = host.findChild(ProgressiveDisclosureControl, "dl_tier_train_control")
    assert disclosure is not None
    disclosure.set_tier(TIER_SIMPLE)
    active_subtab = host._train_page.tab.stack.currentWidget()
    assert active_subtab.widgets["epochs"].isHidden() is True

    # Generate route
    host.activate_route("generate")
    assert host._stack.currentWidget() is host._generate_page
    gen_onboarding = host.findChild(GuidedOnboardingCard, "dl_onboarding_generate")
    assert gen_onboarding is not None


def test_dl_workspace_host_runs_page_empty_state_and_navigation(q_app):
    store = _memory_store()
    event_hub = EventHub(q_app)
    host = DeepLearningWorkspaceHost(event_hub=event_hub, preference_store=store)
    host.show()
    q_app.processEvents()

    host.activate_route("runs")
    runs_page = host._runs_page
    assert runs_page is not None
    assert not runs_page.empty_state.isHidden()
    assert runs_page._list.isHidden()

    # Click Start Training action button in empty state
    btn_train = runs_page.empty_state.findChild(QPushButton, "dl_empty_action_start_training")
    assert btn_train is not None
    btn_train.click()
    assert host._stack.currentWidget() is host._train_page

    # Go back to runs and add an item
    host.activate_route("runs")
    runs_page.add_run_item("Run #1 (SDXL LoRA completed)")
    assert runs_page.empty_state.isHidden()
    assert not runs_page._list.isHidden()


def test_dl_workspace_host_review_page_empty_state_and_navigation(q_app):
    store = _memory_store()
    event_hub = EventHub(q_app)
    host = DeepLearningWorkspaceHost(event_hub=event_hub, preference_store=store)
    host.show()
    q_app.processEvents()

    host.activate_route("review")
    review_page = host._review_page
    assert review_page is not None
    assert not review_page.empty_state.isHidden()

    # Click Go to Generate action button in empty state
    btn_gen = review_page.empty_state.findChild(QPushButton, "dl_empty_action_go_to_generate")
    assert btn_gen is not None
    btn_gen.click()
    assert host._stack.currentWidget() is host._generate_page


def test_disclosure_preserves_model_visibility_and_labels(q_app):
    from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab
    from PySide6.QtWidgets import QFormLayout

    tab = LoRAGenerateTab()
    tab.model_selector.setCurrentIndex(0)
    tab.update_ui_visibility()
    tab.apply_disclosure_tier("simple")
    assert tab.gan_group.isHidden()
    assert tab.neg_prompt_edit.isHidden()
    layout = tab.diffusion_group.layout()
    assert isinstance(layout, QFormLayout)
    assert layout.labelForField(tab.neg_prompt_edit).isHidden()
    tab.apply_disclosure_tier("advanced")
    assert tab.gan_group.isHidden()
    assert not tab.neg_prompt_edit.isHidden()
    tab.deleteLater()


def test_generation_summary_tracks_negative_and_batch(q_app):
    from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab

    tab = LoRAGenerateTab()
    tab.neg_prompt_edit.setText("review-negative")
    tab.batch_size_box.setValue(3)
    summary = tab.get_effective_config_summary()
    assert "review-negative" in summary
    assert "Batch: 3" in summary
    tab.deleteLater()


def test_training_summary_tracks_trigger_and_instance_prompt(q_app):
    tab = LoRATrainTab()
    tab.trigger_edit.setText("my_char")
    tab.prompt_edit.setText("1girl, solo")
    summary = tab.get_effective_config_summary()
    assert "Trigger: 'my_char'" in summary
    assert "Instance Prompt: 'my_char, 1girl, solo'" in summary

    # Switch to LyCORIS engine
    tab.engine_combo.setCurrentIndex(1)  # locon
    summary_lycoris = tab.get_effective_config_summary()
    assert "Trigger: 'my_char'" in summary_lycoris
    assert "Prompt: '1girl, solo'" in summary_lycoris
    tab.deleteLater()


def test_destination_wrappers_delegate_collect_and_set_config(q_app):
    store = _memory_store()
    event_hub = EventHub(q_app)
    host = DeepLearningWorkspaceHost(event_hub=event_hub, preference_store=store)

    train_page = host._train_page
    assert train_page is not None
    train_config = train_page.collect()
    assert isinstance(train_config, dict)
    assert "selected_model" in train_config
    assert "sub_config" in train_config

    # Modify and set_config
    sub = train_config.get("sub_config", {})
    sub["epochs"] = 7
    train_page.set_config(train_config)
    assert train_page.tab.anything_tab.widgets["epochs"].value() == 7
    host.deleteLater()
