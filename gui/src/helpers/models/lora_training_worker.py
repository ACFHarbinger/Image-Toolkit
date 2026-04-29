import os
import torch
from PySide6.QtCore import QThread, Signal
from backend.src.models.lora_diffusion import LoRATuner

class LoRATrainingWorker(QThread):
    """
    Background worker thread to handle LoRA fine-tuning for Illustrious-XL v2.0.
    Ensures the GUI remains responsive during the heavy training process.
    """

    log_signal = Signal(str)
    progress_signal = Signal(int)
    finished_signal = Signal()
    error_signal = Signal(str)

    def __init__(
        self,
        model_id="OnomaAIResearch/Illustrious-XL-v2.0",
        data_path="",
        output_dir="output_lora",
        trigger_word="ohwx",
        pruned_tags=None,
        epochs=1,
        batch_size=2,
        rank=4,
        alpha=32,
        lr=1e-4
    ):
        """
        Initializes the LoRA training worker.
        
        Args:
            model_id (str): The Hugging Face model ID or path.
            data_path (str): Path to the directory containing training images and .txt tags.
            output_dir (str): Directory where the trained LoRA weights will be saved.
            trigger_word (str): The unique identifier for the character/style.
            pruned_tags (list): List of tags to remove from Danbooru caption files.
            epochs (int): Number of training epochs.
            batch_size (int): Batch size for training (recommended 2-4 for 24GB VRAM).
            rank (int): LoRA rank (dimension).
            alpha (int): LoRA alpha (scaling factor).
            lr (float): Learning rate.
        """
        super().__init__()
        self.model_id = model_id
        self.data_path = data_path
        self.output_dir = output_dir
        self.trigger_word = trigger_word
        self.pruned_tags = pruned_tags if pruned_tags else []
        self.epochs = epochs
        self.batch_size = batch_size
        self.rank = rank
        self.alpha = alpha
        self.lr = lr

    def run(self):
        """
        Executes the LoRA training loop.
        """
        try:
            self.log_signal.emit(f"Initializing LoRATuner for {self.model_id}...")
            
            # 1. Initialize Tuner
            tuner = LoRATuner(model_id=self.model_id, output_dir=self.output_dir)
            
            # 2. Configure LoRA parameters
            self.log_signal.emit(f"Configuring LoRA: Rank={self.rank}, Alpha={self.alpha}")
            tuner.configure_lora(rank=self.rank, alpha=self.alpha)
            
            # 3. Start Training
            self.log_signal.emit(f"Starting training on dataset: {self.data_path}")
            self.log_signal.emit(f"Trigger Word: {self.trigger_word}")
            if self.pruned_tags:
                self.log_signal.emit(f"Pruning tags: {', '.join(self.pruned_tags)}")

            # We use a custom progress update if the backend supports it, 
            # otherwise we just monitor the tuner's status.
            tuner.train(
                data_dir=self.data_path,
                instance_prompt=self.trigger_word,
                epochs=self.epochs,
                learning_rate=self.lr,
                batch_size=self.batch_size,
                pruned_tags=self.pruned_tags
            )

            # Check if process was cancelled
            if LoRATuner.is_cancelled:
                self.log_signal.emit("Training process was cancelled by user.")
            else:
                self.log_signal.emit(f"Training complete! LoRA weights saved to {self.output_dir}")
                self.finished_signal.emit()

        except Exception as e:
            error_msg = f"LoRA Training Error: {str(e)}"
            self.log_signal.emit(error_msg)
            self.error_signal.emit(error_msg)

    def stop(self):
        """
        Triggers graceful cancellation of the training process.
        """
        LoRATuner.cancel_process()
