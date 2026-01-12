import pytest
import sys

from unittest.mock import MagicMock, patch

# --- Mock imports BEFORE importing modules under test ---
# This generic mock prevents real generic imports from triggering environment errors
mock_torch = MagicMock()
mock_torch.device.return_value = "cpu"
mock_torch.cuda.is_available.return_value = False
sys.modules["torch"] = mock_torch
sys.modules["torch.nn"] = MagicMock()
sys.modules["torch.optim"] = MagicMock()
sys.modules["torch.utils.data"] = MagicMock()
sys.modules["torchvision"] = MagicMock()
sys.modules["torchvision.models"] = MagicMock()
sys.modules["torchvision.utils"] = MagicMock()
sys.modules["torchvision.transforms"] = MagicMock()

from src.models.gan_wrapper import GanWrapper
from src.models.siamese_network import SiameseModelLoader


class TestGanWrapper:
    @pytest.fixture
    def mock_torch_hub(self):
        with patch("src.models.gan_wrapper.torch.hub.load") as mock:
            # Mock the model object returned
            mock_model = MagicMock()
            mock.return_value = mock_model
            yield mock_model

    @pytest.fixture
    def mock_transforms(self):
        with patch("src.models.gan_wrapper.transforms") as mock:
            mock.Compose.return_value = MagicMock()
            yield mock

    def test_init_success(self, mock_torch_hub, mock_transforms):
        with patch(
            "src.models.gan_wrapper.torch.cuda.is_available", return_value=False
        ):
            gw = GanWrapper(device="cpu")
            assert gw.netG is not None
            assert gw.device == "cpu"

    def test_generate_success(self, mock_torch_hub, mock_transforms):
        gw = GanWrapper()
        gw.netG = MagicMock()

        with (
            patch("src.models.gan_wrapper.os.path.exists", return_value=True),
            patch("src.models.gan_wrapper.Image.open") as mock_open,
            patch("src.models.gan_wrapper.save_image") as mock_save,
        ):

            mock_img = MagicMock()
            mock_open.return_value.convert.return_value = mock_img
            gw.transform.return_value.unsqueeze.return_value.to.return_value = "tensor"

            gw.netG.return_value = MagicMock()  # Output tensor

            gw.generate("input.jpg", "output.jpg")

            gw.netG.assert_called_with("tensor")
            mock_save.assert_called()

    def test_cancel_process(self):
        GanWrapper.cancel_process()
        assert GanWrapper.is_cancelled is True

        gw = GanWrapper()  # Should reset flag
        assert GanWrapper.is_cancelled is False


class TestSiameseModelLoader:
    @pytest.fixture
    def mock_resnet(self):
        with patch("src.models.siamese_network.models.resnet18") as mock:
            mock_model = MagicMock()
            mock.return_value = mock_model
            yield mock_model

    def test_singleton(self):
        s1 = SiameseModelLoader()
        s2 = SiameseModelLoader()
        assert s1 is s2

    def test_get_embedding(self, mock_resnet):
        loader = SiameseModelLoader()
        loader._model = None

        with (
            patch("src.models.siamese_network.Image.open") as mock_open,
            patch("src.models.siamese_network.torch") as mock_torch,
        ):

            mock_open.return_value.convert.return_value = MagicMock()

            # Setup torch mocks
            mock_torch.device.return_value = "cpu"
            mock_torch.cuda.is_available.return_value = False
            # Mock unsqueeze to return a mock that has .to()
            mock_batch = MagicMock()
            mock_torch.unsqueeze.return_value = mock_batch
            mock_batch.to.return_value = mock_batch

            mock_weights = MagicMock()
            mock_weights.DEFAULT.transforms.return_value = MagicMock()

            with patch(
                "src.models.siamese_network.models.ResNet18_Weights", mock_weights
            ):
                emb = loader.get_embedding("img.jpg")

                # Debug if still failing
                if emb is None:
                    print("Embedding is None!")

                assert loader._model is not None
                assert emb is not None
                mock_resnet.assert_called()
                loader._model.assert_called()
