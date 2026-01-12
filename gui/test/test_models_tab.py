import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QWidget

from gui.src.tabs.models.generate_tab import UnifiedGenerateTab
from gui.src.tabs.models.train_tab import UnifiedTrainTab
from gui.src.tabs.models.meta_clip_inference_tab import MetaCLIPInferenceTab
from gui.src.tabs.models.r3gan_evaluate_tab import R3GANEvaluateTab


# Helper class for mocking tabs that need to be widgets
class MockTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.collect = MagicMock(return_value={})
        self.set_config = MagicMock()
        self.get_default_config = MagicMock(return_value={})


# --- UnifiedGenerateTab Tests ---


class TestUnifiedGenerateTab:
    @pytest.fixture
    def mock_subtabs(self):
        with (
            patch("gui.src.tabs.models.generate_tab.LoRAGenerateTab") as mock_lora,
            patch("gui.src.tabs.models.generate_tab.SD3GenerateTab") as mock_sd3,
            patch("gui.src.tabs.models.generate_tab.R3GANGenerateTab") as mock_r3gan,
            patch("gui.src.tabs.models.generate_tab.GANGenerateTab") as mock_gan,
        ):

            # Make sure constructors return our MockTab (which is a valid QWidget)
            mock_lora.return_value = MockTab()
            mock_sd3.return_value = MockTab()
            mock_r3gan.return_value = MockTab()
            mock_gan.return_value = MockTab()

            yield mock_lora, mock_sd3, mock_r3gan, mock_gan

    def test_init(self, q_app, mock_subtabs):
        tab = UnifiedGenerateTab()
        assert isinstance(tab, QWidget)
        # Verify sub-tabs are added
        assert tab.stack.count() >= 2

    def test_collect(self, q_app, mock_subtabs):
        mock_lora, _, _, _ = mock_subtabs
        # Mock collect on active widget (LoRA)
        mock_lora.return_value.collect.return_value = {"param": "value"}

        tab = UnifiedGenerateTab()
        data = tab.collect()

        assert data["selected_model_index"] == 0
        assert data["sub_config"] == {"param": "value"}

    def test_set_config(self, q_app, mock_subtabs):
        mock_lora, _, _, _ = mock_subtabs
        tab = UnifiedGenerateTab()

        config = {"selected_model_index": 0, "sub_config": {"new_param": "new_value"}}
        tab.set_config(config)

        assert tab.model_selector.currentIndex() == 0
        mock_lora.return_value.set_config.assert_called_with({"new_param": "new_value"})

    def test_switch_model(self, q_app, mock_subtabs):
        tab = UnifiedGenerateTab()
        # Switch to SD3 (index 1)
        tab.model_selector.setCurrentIndex(1)
        # Ensure the stack index actually changed.
        # Note: In UnifiedGenerateTab, connections are set up to sync combo box and stack.
        assert tab.stack.currentIndex() == 1


# --- UnifiedTrainTab Tests ---


class TestUnifiedTrainTab:
    @pytest.fixture
    def mock_subtabs(self):
        with (
            patch("gui.src.tabs.models.train_tab.LoRATrainTab") as mock_lora,
            patch("gui.src.tabs.models.train_tab.R3GANTrainTab") as mock_r3gan,
            patch("gui.src.tabs.models.train_tab.GANTrainTab") as mock_gan,
        ):

            mock_lora.return_value = MockTab()
            mock_r3gan.return_value = MockTab()
            mock_gan.return_value = MockTab()

            yield mock_lora, mock_r3gan, mock_gan

    def test_init(self, q_app, mock_subtabs):
        tab = UnifiedTrainTab()
        assert isinstance(tab, QWidget)

    def test_collect(self, q_app, mock_subtabs):
        mock_lora, _, _ = mock_subtabs
        mock_lora.return_value.collect.return_value = {"lr": 0.001}

        tab = UnifiedTrainTab()
        data = tab.collect()

        assert data["selected_model_index"] == 0
        assert data["sub_config"] == {"lr": 0.001}

    def test_set_config(self, q_app, mock_subtabs):
        mock_lora, _, _ = mock_subtabs
        tab = UnifiedTrainTab()

        config = {"selected_model_index": 0, "sub_config": {"lr": 0.002}}
        tab.set_config(config)

        mock_lora.return_value.set_config.assert_called_with({"lr": 0.002})


# --- MetaCLIPInferenceTab Tests ---


class TestMetaCLIPInferenceTab:
    def test_init(self, q_app):
        tab = MetaCLIPInferenceTab()
        assert isinstance(tab, QWidget)
        assert "model_version" in tab.widgets
        assert "text_prompts" in tab.widgets

    def test_get_params_prompt_splitting(self, q_app):
        tab = MetaCLIPInferenceTab()
        tab.widgets["text_prompts"].setText("dog\ncat\nbird")

        params = tab.get_params()

        assert params["text_prompts"] == ["dog", "cat", "bird"]


# --- R3GANEvaluateTab Tests ---


class TestR3GANEvaluateTab:
    def test_init(self, q_app):
        tab = R3GANEvaluateTab()
        assert isinstance(tab, QWidget)
        assert "network" in tab.widgets
        assert "metric_fid" in tab.widgets
