"""Widget construction for LoRATrainTab."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.prompt_edit import PromptEdit
from gui.src.components.prompt_vocabulary import default_vocabulary
from gui.src.tabs.models.delta.live_training_panel import LiveTrainingPanel

from ....classes.base.base_generative_tab import (
    TIER_ADVANCED,
    TIER_SIMPLE,
    TIER_STANDARD,
    model_choice_label,
)
from .lora_dataset_staging import (  # noqa: F401
    _DATASET_IMAGE_EXTS,
    _TRAINING_ENGINES,
    ImportedDataset,
    _exclusive_parent,
    _existing_images,
    _image_paths_under,
    _signal_process_group,
    _stage_images,
    _unique_staged_name,
    combine_trigger_and_prompt,
    dataset_folder_from_paths,
    resolve_imported_dataset,
)


class LoRATrainUiMixin:
    """Builds the LoRA Train tab widgets."""

    def init_ui(self):
        layout = QFormLayout()

        # --- Model Selection ---
        self.model_selector = QComboBox()
        models = [
            (
                "Illustrious XL V2.0 (Base SDXL)",
                "stabilityai/stable-diffusion-xl-base-1.0",
            ),
            (
                "Illustrious Lumina (Base SDXL)",
                "stabilityai/stable-diffusion-xl-base-1.0",
            ),
            ("Anything V3", "ckpt/anything-v3.0"),
            ("Anything V4.5", "ckpt/anything-v4.5"),
            ("Anything V5", "stablediffusionapi/anything-v5"),
            ("Waifu Diffusion v1.4", "hakurei/waifu-diffusion"),
            ("Counterfeit V2.5", "gsdf/Counterfeit-V2.5"),
            ("Animagine XL 3.1", "cagliostrolab/animagine-xl-3.1"),
            ("Animagine XL 4.0", "cagliostrolab/animagine-xl-4.0"),
            ("AnimeGANv2", "animegan_v2"),
        ]
        for name, model_id in models:
            self.model_selector.addItem(model_choice_label(name, model_id), model_id)

        self.add_param_widget(layout, "Base Model:", self.model_selector, "model_id", tier=TIER_SIMPLE)
        self.model_selector.currentIndexChanged.connect(self.update_ui_visibility)

        # Dataset Folder
        folder_container = QWidget()
        self.tag_field(folder_container, tier=TIER_SIMPLE)
        folder_layout = QHBoxLayout(folder_container)
        folder_layout.setContentsMargins(0, 0, 0, 0)

        self.data_dir_edit = QLineEdit(self.last_browsed_scan_dir)
        self.data_dir_edit.editingFinished.connect(self._on_dataset_path_edited)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.clicked.connect(self.browse_dataset)

        folder_layout.addWidget(self.data_dir_edit)
        folder_layout.addWidget(self.browse_btn)
        layout.addRow("Dataset Folder:", folder_container)

        self.add_param_widget(
            layout, "Output Name:", QLineEdit("my_model"), "output_name", tier=TIER_SIMPLE
        )

        # --- Training Engine (Content Gen §1.3: LyCORIS variants) ---
        self.engine_combo = QComboBox()
        for name, engine_id in _TRAINING_ENGINES:
            self.engine_combo.addItem(name, engine_id)
        self.engine_combo.setToolTip(
            "Standard uses this project's original LoRA trainer, unchanged.\n"
            "LyCORIS options route through the LoRATunerV2 pipeline (Hydra\n"
            "presets under middleware/config/training/) for LoCon/LoHa/LoKr\n"
            "adaptation instead of plain LoRA — see content_generation.md §1.3."
        )
        self.add_param_widget(layout, "Training Engine:", self.engine_combo, "engine", tier=TIER_ADVANCED)

        # --- Dynamic Configs ---
        self.lora_group = QWidget()
        self.tag_field(self.lora_group, tier=TIER_STANDARD)
        lora_layout = QFormLayout(self.lora_group)
        self.prompt_edit = PromptEdit("1girl, style of my_char")
        self.prompt_edit.set_vocabulary(default_vocabulary())
        self.tag_field(self.prompt_edit, tier=TIER_STANDARD)
        self.trigger_edit = QLineEdit()
        self.trigger_edit.setPlaceholderText("activation token only — not the instance prompt")
        self.tag_field(self.trigger_edit, tier=TIER_STANDARD)
        self.rank_box = QSpinBox()
        self.rank_box.setValue(4)
        self.tag_field(self.rank_box, tier=TIER_ADVANCED)

        lora_layout.addRow("Instance Prompt:", self.prompt_edit)
        lora_layout.addRow("Trigger Token:", self.trigger_edit)
        lora_layout.addRow("LoRA Rank:", self.rank_box)
        layout.addRow(self.lora_group)

        # Common Params
        self.add_param_widget(
            layout, "Epochs:", QSpinBox(minimum=1, value=5, maximum=100), "epochs", tier=TIER_STANDARD
        )
        self.add_param_widget(
            layout,
            "Batch Size:",
            QSpinBox(minimum=1, value=1, maximum=32),
            "batch_size",
            tier=TIER_STANDARD,
        )

        lr_box = QDoubleSpinBox()
        lr_box.setRange(1e-6, 1e-3)
        lr_box.setValue(1e-4)
        lr_box.setDecimals(6)
        self.add_param_widget(layout, "Learning Rate:", lr_box, "learning_rate", tier=TIER_STANDARD)

        # Connect live changes to effective-config notifications
        self.data_dir_edit.textChanged.connect(lambda *_: self.notify_effective_config_changed())
        for field in (self.prompt_edit, self.trigger_edit):
            sig = getattr(field, "promptChanged", None) or getattr(field, "textChanged", None)
            if sig is not None:
                sig.connect(lambda *_: self.notify_effective_config_changed())
        self.rank_box.valueChanged.connect(lambda *_: self.notify_effective_config_changed())
        self.model_selector.currentIndexChanged.connect(lambda *_: self.notify_effective_config_changed())
        self.engine_combo.currentIndexChanged.connect(lambda *_: self.notify_effective_config_changed())

        # --- Action Buttons ---
        button_container = QWidget()
        self.tag_field(button_container, tier=TIER_SIMPLE)
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        self.train_btn = QPushButton("Start Training")
        self.cancel_btn = QPushButton("Cancel")
        self.train_btn.clicked.connect(self.start_training_thread)
        self.cancel_btn.clicked.connect(self.cancel_training)
        button_layout.addWidget(self.train_btn)
        button_layout.addWidget(self.cancel_btn)

        inspect_btn = QPushButton("Inspect .safetensors...")
        inspect_btn.setToolTip("Open a .safetensors file and view its metadata")
        inspect_btn.clicked.connect(self._inspect_safetensors)
        button_layout.addWidget(inspect_btn)

        review_tags_btn = QPushButton("Review Tags...")
        review_tags_btn.setToolTip(
            "Run the WD14 auto-tagger in the dataset panel — does not block this form"
        )
        review_tags_btn.clicked.connect(self._review_tags)
        button_layout.addWidget(review_tags_btn)

        layout.addRow(button_container)
        self.cancel_btn.setEnabled(False)
        self.status_label = QLabel("Ready")
        layout.addRow(self.status_label)
        self._live_panel = LiveTrainingPanel()
        layout.addRow(self._live_panel)


        form_host = QWidget()
        form_host.setLayout(layout)
        from gui.src.components.dialogs.dataset_advisor_panel import AdvisorPanel
        from gui.src.components.dialogs.tag_review_panel import TagReviewPanel
        from gui.src.components.virtual_gallery.widget import VirtualGallery

        # #744: contact sheet under the form on the left; Advisor and Review
        # Tags share the right side as tabs (the panel object is unchanged).
        self._gallery = VirtualGallery()
        gallery_box = QGroupBox("Dataset Contact Sheet")
        gallery_layout = QVBoxLayout(gallery_box)
        gallery_layout.setContentsMargins(4, 4, 4, 4)
        gallery_layout.addWidget(self._gallery)
        left_split = QSplitter(Qt.Orientation.Vertical)
        left_split.addWidget(form_host)
        left_split.addWidget(gallery_box)
        left_split.setStretchFactor(0, 3)
        left_split.setStretchFactor(1, 2)

        self._review_panel = TagReviewPanel(modal_chrome=False)
        self._review_panel.review_saved.connect(self._on_review_saved)

        self._advisor_panel = AdvisorPanel()
        self._advisor_panel.exclude_requested.connect(self._on_advisor_exclude)
        self._advisor_panel.restore_requested.connect(self._on_advisor_restore)
        self._advisor_panel.selection_requested.connect(self._on_advisor_selection)
        self._advisor_panel.review_tags_requested.connect(self._on_advisor_review_tags)
        self._advisor_panel.set_training_guard(self._training_running)
        self._right_tabs = QTabWidget()
        self._right_tabs.addTab(self._advisor_panel, "Advisor")
        self._right_tabs.addTab(self._review_panel, "Review Tags")
        self._update_advisor_hydra_availability()
        self.engine_combo.currentIndexChanged.connect(
            lambda *_: self._update_advisor_hydra_availability()
        )
        self.trigger_edit.textChanged.connect(self._on_trigger_for_advisor)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_split)
        splitter.addWidget(self._right_tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root = QVBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(splitter)
        self.setLayout(root)
