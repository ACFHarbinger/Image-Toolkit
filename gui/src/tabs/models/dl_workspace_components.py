"""Reusable UX components for Deep Learning workspace (#731, #735).

Components:
- EffectiveConfigBar: Read-only summary bar showing the resolved configuration
  dispatched to the launcher/engine (#731).
- ProgressiveDisclosureControl: Segmented control (Simple / Standard / Advanced)
  persisted per destination in preferences (#731).
- GuidedOnboardingCard: Dismissable first-run contextual onboarding card (#735).
- ActionableEmptyState: Styled placeholder guiding users to the next action (#731).
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.src.classes.base.base_generative_tab import (
    DISCLOSURE_TIERS,
    TIER_STANDARD,
    BaseGenerativeTab,
)
from gui.src.preferences import PreferenceDefinition, PreferenceStore
from gui.src.theming.theme_api import color


class EffectiveConfigBar(QFrame):
    """Read-only bar displaying the resolved configuration dispatched to the engine (#731).

    Always displays the full resolved configuration regardless of the active
    progressive disclosure tier, ensuring users know exactly what will run.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dl_effective_config_bar")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._connected_tab: BaseGenerativeTab | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self._badge = QLabel("Config to run:")
        self._badge.setObjectName("dl_effective_config_badge")
        self._badge.setStyleSheet(
            f"font-weight: bold; color: {color('accent')};"
        )
        layout.addWidget(self._badge)

        self._summary_edit = QLineEdit()
        self._summary_edit.setObjectName("dl_effective_config_summary")
        self._summary_edit.setReadOnly(True)
        self._summary_edit.setStyleSheet(
            f"background: transparent; border: none; color: {color('text')}; font-family: monospace;"
        )
        layout.addWidget(self._summary_edit, stretch=1)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setObjectName("dl_effective_config_copy_btn")
        self._copy_btn.setToolTip("Copy effective configuration summary to clipboard")
        self._copy_btn.setFixedWidth(54)
        self._copy_btn.clicked.connect(self._copy_to_clipboard)
        layout.addWidget(self._copy_btn)

    def set_summary(self, summary_text: str) -> None:
        """Update the displayed effective configuration string."""
        self._summary_edit.setText(summary_text)
        self._summary_edit.setToolTip(summary_text)

    def summary(self) -> str:
        """Return the currently displayed effective configuration string."""
        return self._summary_edit.text()

    def connect_tab(self, tab: BaseGenerativeTab) -> None:
        """Connect to a generative tab to reactively follow parameter changes."""
        self._connected_tab = tab
        tab.effective_config_changed.connect(self.set_summary)
        self.set_summary(tab.get_effective_config_summary())

    def _copy_to_clipboard(self) -> None:
        text = self.summary()
        if text:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(text)


class ProgressiveDisclosureControl(QWidget):
    """Segmented 3-tier control (Simple / Standard / Advanced) for form disclosure (#731)."""

    tier_changed = Signal(str)

    def __init__(
        self,
        preference_def: PreferenceDefinition | None = None,
        preference_store: PreferenceStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dl_progressive_disclosure_control")
        self._pref_def = preference_def
        self._pref_store = preference_store or PreferenceStore.instance()
        self._tier = TIER_STANDARD
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        lbl = QLabel("Tier:")
        lbl.setStyleSheet(f"color: {color('muted_text')}; font-size: 11px;")
        layout.addWidget(lbl)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}

        for tier in DISCLOSURE_TIERS:
            btn = QPushButton(tier.capitalize())
            btn.setCheckable(True)
            btn.setObjectName(f"dl_tier_{tier}")
            btn.setToolTip(f"Show {tier} complexity parameters")
            btn.clicked.connect(lambda _=False, t=tier: self.set_tier(t))
            self._group.addButton(btn)
            self._buttons[tier] = btn
            layout.addWidget(btn)

        initial_tier = TIER_STANDARD
        if self._pref_def is not None:
            initial_tier = str(self._pref_store.get(self._pref_def.key, TIER_STANDARD))
        self.set_tier(initial_tier)

    def tier(self) -> str:
        return self._tier

    def set_tier(self, tier: str) -> None:
        if tier not in DISCLOSURE_TIERS:
            tier = TIER_STANDARD
        self._tier = tier
        btn = self._buttons.get(tier)
        if btn and not btn.isChecked():
            btn.setChecked(True)
        if self._pref_def is not None:
            self._pref_store.set(self._pref_def.key, tier)
        self.tier_changed.emit(tier)


class GuidedOnboardingCard(QFrame):
    """One-time, dismissable contextual onboarding card per destination (#735)."""

    dismissed = Signal()

    _CONTENT = {
        "train": (
            "💡 Quick Start: Train Custom Character or Style",
            (
                "• <b>Dataset Folder:</b> Pick a folder of images or send frames from Extractor / Library.",
                "• <b>Base Model:</b> Choose a base checkpoint (e.g. SDXL Base or Anything V5).",
                "• <b>Start Training:</b> Sensible defaults are pre-configured for everything else.",
            ),
        ),
        "generate": (
            "💡 Quick Start: Image Generation",
            (
                "• <b>Base Model:</b> Choose your target model architecture.",
                "• <b>Prompt:</b> Enter positive and negative description prompts.",
                "• <b>LoRA & Generate:</b> Select a trained LoRA adapter (if any) and press Generate.",
            ),
        ),
        "review": (
            "💡 Quick Start: Output Review & Quality Diagnosis",
            (
                "• <b>Output Selection:</b> Select an output from the filmstrip or past runs.",
                "• <b>Region Mark:</b> Mark a region with the inspection tool to examine artifacts.",
                "• <b>Diagnostic Feedback:</b> Describe what to adjust or diagnose quality.",
            ),
        ),
    }

    def __init__(
        self,
        destination: str,
        preference_def: PreferenceDefinition | None = None,
        preference_store: PreferenceStore | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.destination = destination
        self.setObjectName(f"dl_onboarding_{destination}")
        self._pref_def = preference_def
        self._pref_store = preference_store or PreferenceStore.instance()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._build_ui()
        self._check_initial_visibility()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QFrame#{self.objectName()} {{"
            f"  background-color: {color('surface')};"
            f"  border: 1px solid {color('border')};"
            f"  border-left: 4px solid {color('accent')};"
            f"  border-radius: 4px;"
            f"}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title_text, bullets = self._CONTENT.get(
            self.destination,
            ("💡 Quick Start Guide", ("• Follow the steps on this screen to get started.",)),
        )
        title_label = QLabel(f"<b>{title_text}</b>")
        title_label.setStyleSheet(f"color: {color('text')};")
        header.addWidget(title_label)
        header.addStretch()

        self._dismiss_btn = QPushButton("✕")
        self._dismiss_btn.setObjectName("dl_onboarding_dismiss_btn")
        self._dismiss_btn.setToolTip("Dismiss this quick start guide")
        self._dismiss_btn.setFixedSize(22, 22)
        self._dismiss_btn.clicked.connect(self.dismiss)
        header.addWidget(self._dismiss_btn)
        layout.addLayout(header)

        for bullet in bullets:
            lbl = QLabel(bullet)
            lbl.setStyleSheet(f"color: {color('muted_text')}; font-size: 11px;")
            lbl.setWordWrap(True)
            layout.addWidget(lbl)

    def _check_initial_visibility(self) -> None:
        if self._pref_def is not None:
            is_dismissed = bool(self._pref_store.get(self._pref_def.key, False))
            self.setVisible(not is_dismissed)

    def is_dismissed(self) -> bool:
        if self._pref_def is not None:
            return bool(self._pref_store.get(self._pref_def.key, False))
        return not self.isVisible()

    def dismiss(self) -> None:
        if self._pref_def is not None:
            self._pref_store.set(self._pref_def.key, True)
        self.setVisible(False)
        self.dismissed.emit()

    def reset(self) -> None:
        if self._pref_def is not None:
            self._pref_store.set(self._pref_def.key, False)
        self.setVisible(True)


class ActionableEmptyState(QFrame):
    """Designed, actionable empty state guiding users to the next step (#731)."""

    def __init__(
        self,
        title: str,
        description: str,
        actions: list[tuple[str, Callable[[], None]]] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dl_actionable_empty_state")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._title = title
        self._description = description
        self._actions = actions or []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QFrame#dl_actionable_empty_state {{"
            f"  background-color: {color('surface')};"
            f"  border: 1px dashed {color('border')};"
            f"  border-radius: 6px;"
            f"}}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)

        title_lbl = QLabel(f"<b>{self._title}</b>")
        title_lbl.setObjectName("dl_empty_state_title")
        title_lbl.setStyleSheet(f"color: {color('text')}; font-size: 14px;")
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(self._description)
        desc_lbl.setObjectName("dl_empty_state_desc")
        desc_lbl.setStyleSheet(f"color: {color('muted_text')}; font-size: 12px;")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        if self._actions:
            btn_layout = QHBoxLayout()
            btn_layout.setSpacing(8)
            for btn_label, callback in self._actions:
                btn = QPushButton(btn_label)
                btn.setObjectName(f"dl_empty_action_{btn_label.lower().replace(' ', '_')}")
                btn.clicked.connect(callback)
                btn_layout.addWidget(btn)
            btn_layout.addStretch()
            layout.addLayout(btn_layout)
