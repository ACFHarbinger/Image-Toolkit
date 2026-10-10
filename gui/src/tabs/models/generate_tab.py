from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
)

from ...classes.base.base_generative_tab import (
    SELECTED_MODEL_KEY,
    BaseGenerativeTab,
    apply_selected_model,
    collect_selected_model,
)
from .gen import GANGenerateTab, LoRAGenerateTab, R3GANGenerateTab, SD3GenerateTab


class UnifiedGenerateTab(BaseGenerativeTab):
    """
    Master tab that allows selecting the Model Architecture
    (Anything V5 vs R3GAN vs SD3 vs Basic GAN) for image generation.
    """

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # 1. Model Selector
        self.model_selector = QComboBox()
        self.model_selector.addItem("LoRA (Diffusion and GANs)", "anything")
        self.model_selector.addItem("Stable Diffusion 3.5", "sd3")
        self.model_selector.addItem("R3GAN (NVLabs)", "r3gan")
        self.model_selector.addItem("Basic GAN (Custom)", "basic_gan")

        selector_layout = QFormLayout()
        selector_layout.addRow(
            QLabel("<b>Model Architecture:</b>"), self.model_selector
        )
        main_layout.addLayout(selector_layout)

        # 2. Stacked Widget
        self.stack = QStackedWidget()

        self.anything_tab = LoRAGenerateTab()
        self.stack.addWidget(self.anything_tab)

        self.sd3_tab = SD3GenerateTab()
        self.stack.addWidget(self.sd3_tab)

        self.r3gan_tab = R3GANGenerateTab()
        self.stack.addWidget(self.r3gan_tab)

        # ADD CUSTOM GAN GENERATE TAB TO STACK
        self.basic_gan_gen_tab = GANGenerateTab()
        self.stack.addWidget(self.basic_gan_gen_tab)

        main_layout.addWidget(self.stack)

        # Connect signal
        self.model_selector.currentIndexChanged.connect(self.stack.setCurrentIndex)

        self.setLayout(main_layout)

    def collect(self) -> dict:
        active_widget = self.stack.currentWidget()

        sub_config = {}
        if hasattr(active_widget, "collect"):
            sub_config = active_widget.collect()

        data = collect_selected_model(self.model_selector)
        data["sub_config"] = sub_config
        return data

    def set_config(self, config: dict):
        note = apply_selected_model(self.model_selector, config)
        notes = [note] if note else []
        self.show_config_migration_note(notes)

        if "sub_config" in config:
            active_widget = self.stack.currentWidget()
            if hasattr(active_widget, "set_config"):
                active_widget.set_config(config["sub_config"])

    def apply_pinned_run(self, run: object) -> None:
        """Load a pin into this form. A ``.safetensors`` artifact fills the LoRA path."""
        config = dict(getattr(run, "config", {}) or {})
        artifact = str(getattr(run, "artifact_path", "") or "")
        if artifact.endswith(".safetensors"):
            sub = dict(config.get("sub_config") or {})
            sub["lora_path"] = artifact
            config["sub_config"] = sub
            config["selected_model"] = "anything"
        if config:
            self.set_config(config)

    def get_default_config(self) -> dict:
        data = collect_selected_model(self.model_selector)
        data[SELECTED_MODEL_KEY] = "anything"
        data["sub_config"] = self.anything_tab.get_default_config()
        return data
