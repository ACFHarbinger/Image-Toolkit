"""#728: browse dialogs across the Train/Generate tabs must pass
QFileDialog.Option.DontUseNativeDialog — the native-dialog path is this
app's documented crash class (see the safetensors inspector and
cbir_train_tab/_browsers.py, which already set it).
"""

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QFileDialog

from gui.src.tabs.models.delta.gan_train_tab import GANTrainTab
from gui.src.tabs.models.gen.gan_generate_tab import GANGenerateTab
from gui.src.tabs.models.gen.lora_generate_tab import LoRAGenerateTab

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _no_modal_dialogs():
    with patch("gui.src.tabs.models.delta.gan_train_tab.QMessageBox"), patch(
        "gui.src.tabs.models.gen.lora_generate_tab.QMessageBox"
    ), patch("gui.src.tabs.models.gen.gan_generate_tab.QMessageBox"):
        yield


def test_lora_generate_browse_uses_non_native_dialog(q_app):
    tab = LoRAGenerateTab()
    with patch(
        "gui.src.tabs.models.gen.lora_generate_tab.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ) as mock_dialog:
        tab.browse_input_image()
    assert (
        mock_dialog.call_args.kwargs["options"] == QFileDialog.Option.DontUseNativeDialog
    )


def test_lora_generate_model_combo_shows_resolved_id(q_app):
    tab = LoRAGenerateTab()
    texts = [tab.model_selector.itemText(i) for i in range(tab.model_selector.count())]
    assert (
        "Illustrious XL V2.0 (Base SDXL) · stabilityai/stable-diffusion-xl-base-1.0"
        in texts
    )
    assert tab.model_selector.itemData(0) == "stabilityai/stable-diffusion-xl-base-1.0"


def test_gan_generate_browse_uses_non_native_dialog(q_app):
    tab = GANGenerateTab()
    with patch(
        "gui.src.tabs.models.gen.gan_generate_tab.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ) as mock_dialog:
        tab.browse_file(tab.txt_checkpoint)
    assert (
        mock_dialog.call_args.kwargs["options"] == QFileDialog.Option.DontUseNativeDialog
    )


def test_gan_train_browse_folder_uses_non_native_dialog(q_app):
    tab = GANTrainTab()
    with patch(
        "gui.src.tabs.models.delta.gan_train_tab.QFileDialog.getExistingDirectory",
        return_value="",
    ) as mock_dialog:
        tab.browse_folder(tab.txt_data_path)
    assert mock_dialog.call_args.args[3] == QFileDialog.Option.DontUseNativeDialog
