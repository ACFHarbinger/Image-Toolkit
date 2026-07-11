from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .elements.codec_subtab import CodecSubTab
from .elements.format_subtab import FormatSubTab
from .elements.sampler_subtab import SamplerSubTab


class ConvertTab(QWidget):
    """Outer Convert tab containing Format, Codec, and Sampler subtabs."""

    qml_input_path_changed = Signal(str)

    def __init__(self, dropdown=True):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._subtabs = QTabWidget()
        self._subtabs.setDocumentMode(True)

        self.format_subtab = FormatSubTab(dropdown=dropdown)
        self.codec_subtab = CodecSubTab()
        self.sampler_subtab = SamplerSubTab()

        self._subtabs.addTab(self.format_subtab, "Format")
        self._subtabs.addTab(self.codec_subtab, "Codec")
        self._subtabs.addTab(self.sampler_subtab, "Sampler")

        # Forward the QML signal from the inner FormatSubTab
        self.format_subtab.qml_input_path_changed.connect(self.qml_input_path_changed)

        layout.addWidget(self._subtabs)

    # --- QML / external API forwarded to FormatSubTab ---

    def collect(self) -> dict:
        return self.format_subtab.collect()

    def set_config(self, config: dict):
        return self.format_subtab.set_config(config)

    def get_default_config(self) -> dict:
        return self.format_subtab.get_default_config()

    @Slot(str)
    def browse_directory_and_scan_qml(self, current_path=""):
        return self.format_subtab.browse_directory_and_scan_qml(current_path)

    @Slot(str, str, str, bool)
    def start_conversion_worker_qml(
        self, input_path, output_format, output_dir, delete_original
    ):
        return self.format_subtab.start_conversion_worker_qml(
            input_path, output_format, output_dir, delete_original
        )

    def cancel_loading(self):
        self.format_subtab.cancel_loading()
        self.codec_subtab.cancel_loading()
        self.sampler_subtab.cancel_loading()

    def closeEvent(self, event):
        self.format_subtab.close()
        self.codec_subtab.close()
        self.sampler_subtab.close()
        super().closeEvent(event)
