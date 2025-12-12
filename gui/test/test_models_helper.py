from unittest.mock import MagicMock, patch

# Ensure we mock modules BEFORE importing the worker
# But since we use simple imports in the test file, we can patch inside the test function
# or use pytest fixtures to patch sys.modules if needed.
# However, the worker module imports them at top level. 
# So we rely on conftest.py mocks OR we patch where they are used.

from gui.src.helpers.models.training_worker import TrainingWorker

class TestTrainingWorker:
    def test_run_success(self, q_app):
        # We need to mock:
        # 1. torch.device
        # 2. datasets.ImageFolder
        # 3. DataLoader
        # 4. GAN
        
        with patch("gui.src.helpers.models.training_worker.torch") as mock_torch, \
             patch("gui.src.helpers.models.training_worker.datasets") as mock_datasets, \
             patch("gui.src.helpers.models.training_worker.DataLoader") as mock_loader, \
             patch("gui.src.helpers.models.training_worker.GAN") as MockGAN:
             
            # Setup mocks
            mock_datasets.ImageFolder.return_value = "dummy_dataset"
            
            worker = TrainingWorker(
                data_path="/tmp/data",
                save_path="/tmp/save",
                epochs=1,
                batch_size=4,
                lr=0.001,
                z_dim=100,
                device_name="cpu"
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
         with patch("gui.src.helpers.models.training_worker.torch"), \
              patch("gui.src.helpers.models.training_worker.datasets") as mock_datasets, \
              patch("gui.src.helpers.models.training_worker.DataLoader"), \
              patch("gui.src.helpers.models.training_worker.GAN"):
              
            mock_datasets.ImageFolder.side_effect = Exception("Folder structure bad")
            
            worker = TrainingWorker("/tmp", "/tmp", 1, 1, 0.1, 10, "cpu")
            
            errors = []
            worker.error_signal.connect(lambda e: errors.append(e))
            
            worker.run()
            
            assert len(errors) == 1
            assert "Dataset Error" in errors[0]
