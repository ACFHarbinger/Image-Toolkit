from unittest.mock import MagicMock, patch

from gui.src.helpers.models.training_worker import TrainingWorker


class TestTrainingWorker:
    def test_run_success(self, q_app):

        mock_torch = MagicMock()
        mock_datasets = MagicMock()
        mock_loader = MagicMock()
        MockGAN = MagicMock()

        mock_torch_utils_data = MagicMock()
        mock_torch_utils_data.DataLoader = mock_loader

        mock_torchvision = MagicMock()
        mock_torchvision.datasets = mock_datasets

        mock_gan_module = MagicMock()
        mock_gan_module.GAN = MockGAN

        # Setup mocks
        mock_datasets.ImageFolder.return_value = "dummy_dataset"

        with patch.dict(
            "sys.modules",
            {
                "torch": mock_torch,
                "torchvision": mock_torchvision,
                "torchvision.datasets": mock_datasets,
                "torch.utils.data": mock_torch_utils_data,
                "backend.src.models.core.gan": mock_gan_module,
            },
        ):
            worker = TrainingWorker(
                data_path="/tmp/data",
                save_path="/tmp/save",
                epochs=1,
                batch_size=4,
                lr=0.001,
                z_dim=100,
                device_name="cpu",
            )

            # Capture signals
            logs = []
            worker.log_signal.connect(lambda s: logs.append(s))

            finished = []
            worker.finished_signal.connect(lambda: finished.append(True))

            worker.run()

            # Verification
            mock_torch.device.assert_called_with("cpu")
            mock_datasets.ImageFolder.assert_called()
            mock_loader.assert_called()
            MockGAN.assert_called()
            MockGAN.return_value.train.assert_called()

            assert len(finished) == 1
            assert "Training complete." in logs[-1]

    def test_run_dataset_error(self, q_app):

        mock_torch = MagicMock()
        mock_datasets = MagicMock()
        mock_loader = MagicMock()
        MockGAN = MagicMock()

        mock_torch_utils_data = MagicMock()
        mock_torch_utils_data.DataLoader = mock_loader

        mock_torchvision = MagicMock()
        mock_torchvision.datasets = mock_datasets

        mock_gan_module = MagicMock()
        mock_gan_module.GAN = MockGAN

        mock_datasets.ImageFolder.side_effect = Exception("Folder structure bad")

        with patch.dict(
            "sys.modules",
            {
                "torch": mock_torch,
                "torchvision": mock_torchvision,
                "torchvision.datasets": mock_datasets,
                "torch.utils.data": mock_torch_utils_data,
                "backend.src.models.core.gan": mock_gan_module,
            },
        ):
            worker = TrainingWorker("/tmp", "/tmp", 1, 1, 0.1, 10, "cpu")

            errors = []
            worker.error_signal.connect(lambda e: errors.append(e))

            worker.run()

            assert len(errors) == 1
            assert "Dataset Error" in errors[0]
