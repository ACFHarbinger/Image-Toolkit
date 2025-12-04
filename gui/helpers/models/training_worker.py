import torch

from PySide6.QtCore import QThread, Signal
from torchvision import datasets, transforms
from torch.utils.data import DataLoader
from backend.src.models.gan import GAN


class TrainingWorker(QThread):
    """
    Background worker thread to handle the GAN training loop.
    """
    log_signal = Signal(str)
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(self, data_path, save_path, epochs, batch_size, lr, z_dim, device_name):
        super().__init__()
        self.data_path = data_path
        self.save_path = save_path
        self.epochs = epochs
        self.batch_size = batch_size
        self.lr = lr
        self.z_dim = z_dim
        self.device_name = device_name
        self.is_running = True

    def run(self):
        try:
            self.log_signal.emit(f"Setting up training on {self.device_name}...")
            device = torch.device(self.device_name)

            # 1. Prepare Dataset
            # We assume the images are in a structure compatible with ImageFolder
            # i.e., root/class_x/xxx.png
            # If the user selects a flat folder, we might need a custom loader, 
            # but ImageFolder is standard.
            transform = transforms.Compose([
                transforms.Resize((32, 32)), # Resizing to 32x32 as per the GAN implementation notes
                transforms.ToTensor(),
                transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
            ])
            
            self.log_signal.emit(f"Loading dataset from: {self.data_path}")
            try:
                dataset = datasets.ImageFolder(root=self.data_path, transform=transform)
            except Exception as e:
                # Fallback: specific error if folder structure is wrong
                self.error_signal.emit(f"Dataset Error: {str(e)}\nEnsure folder has subdirectories (e.g. images/classA/).")
                return

            dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True, num_workers=2)

            # 2. Initialize GAN
            gan = GAN(
                z_dim=self.z_dim,
                channels=3,
                n_filters=32,
                n_blocks=3,
                lr=self.lr,
                device=device
            )

            # 3. Train
            # We wrap the train method to capture logs if possible, 
            # but since GAN.train prints to stdout, we just run it.
            # Ideally, we would modify GAN.train to accept a callback or yield progress.
            # Here we assume it runs and saves images to save_path.
            self.log_signal.emit("Starting training loop...")
            gan.train(dataloader, epochs=self.epochs, save_path=self.save_path)
            
            self.log_signal.emit("Training complete.")
            self.finished_signal.emit()

        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self.is_running = False