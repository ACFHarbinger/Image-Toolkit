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
from .delta import GANTrainTab, LoRATrainTab, R3GANTrainTab


class UnifiedTrainTab(BaseGenerativeTab):
    """
    Master tab that allows selecting the Model Architecture (Anything V5 vs R3GAN vs Basic GAN)
    and switches the interface accordingly.
    """

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        # 1. Model Selector
        self.model_selector = QComboBox()
        self.model_selector.addItem("LoRA (Diffusion and GANs)", "anything")
        self.model_selector.addItem("R3GAN (NVLabs)", "r3gan")
        self.model_selector.addItem("Basic GAN (Custom)", "basic_gan")

        selector_layout = QFormLayout()
        selector_layout.addRow(
            QLabel("<b>Model Architecture:</b>"), self.model_selector
        )
        main_layout.addLayout(selector_layout)

        # 2. Stacked Widget
        self.stack = QStackedWidget()

        # Initialize sub-tabs
        self.anything_tab = LoRATrainTab()
        self.stack.addWidget(self.anything_tab)

        self.r3gan_tab = R3GANTrainTab()
        self.stack.addWidget(self.r3gan_tab)

        self.basic_gan_tab = GANTrainTab()
        self.stack.addWidget(self.basic_gan_tab)

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

    def get_default_config(self) -> dict:
        data = collect_selected_model(self.model_selector)
        data[SELECTED_MODEL_KEY] = "anything"
        data["sub_config"] = self.anything_tab.get_default_config()
        return data

    def apply_imported_paths(self, paths: tuple[str, ...]) -> None:
        self.model_selector.setCurrentIndex(0)
        self.anything_tab.apply_imported_paths(paths)
