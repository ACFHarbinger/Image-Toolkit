import os
import threading

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QComboBox, QWidget, QFileDialog,
    QFormLayout, QLineEdit, QMessageBox,
    QSpinBox, QDoubleSpinBox, QPushButton,
    QHBoxLayout,
)
from ..base_generative_tab import BaseGenerativeTab
from backend.src.models.lora_diffusion import LoRATuner
from backend.src.models.gan_wrapper import GanWrapper
from backend.src.utils.definitions import LOCAL_SOURCE_PATH


class LoRAGenerateTab(BaseGenerativeTab):
    # Signal to handle GUI updates when processing is done
    # Arguments: (status_type: str, message: str)
    generation_finished_signal = Signal(str, str)

    def __init__(self):
        super().__init__()
        
        # Initialize last browsed directory
        self.last_browsed_scan_dir = LOCAL_SOURCE_PATH
        
        self.init_ui()
        
        # Connect the signal to the slot
        self.generation_finished_signal.connect(self.handle_generation_finished)
        
    def init_ui(self):
        layout = QFormLayout()
        
        # --- Model Selection ---
        self.model_selector = QComboBox()
        models = [
            ("Anything V5", "stablediffusionapi/anything-v5"),
            ("Waifu Diffusion v1.4", "hakurei/waifu-diffusion-v1-4"),
            ("Counterfeit V3.0", "gsdf/Counterfeit-V3.0"),
            ("Animagine XL 3.1", "cagliostrolab/animagine-xl-3.1"),
            ("Animagine XL 4.0", "cagliostrolab/animagine-xl-4.0"),
            ("AnimeGANv2 (Img2Img)", "animegan_v2") 
        ]
        
        for name, model_id in models:
            self.model_selector.addItem(name, model_id)
            
        self.add_param_widget(layout, "Select Model:", self.model_selector, "model_id")
        self.model_selector.currentIndexChanged.connect(self.update_ui_visibility)

        # --- Dynamic Widgets Group ---
        # Diffusion Widgets (Text-to-Image)
        self.diffusion_group = QWidget()
        diff_layout = QFormLayout(self.diffusion_group)
        self.prompt_edit = QLineEdit("1girl, solo, cat ears, library")
        self.neg_prompt_edit = QLineEdit("lowres, bad anatomy, text, error")
        self.lora_edit = QLineEdit("output_lora")
        
        diff_layout.addRow("Prompt:", self.prompt_edit)
        diff_layout.addRow("Negative Prompt:", self.neg_prompt_edit)
        diff_layout.addRow("LoRA Path:", self.lora_edit)
        
        self.steps_box = QSpinBox(minimum=1, value=25, maximum=100)
        self.guidance_box = QDoubleSpinBox()
        self.guidance_box.setValue(7.0)
        
        diff_layout.addRow("Inference Steps:", self.steps_box)
        diff_layout.addRow("Guidance Scale:", self.guidance_box)

        layout.addRow(self.diffusion_group)

        # GAN Widgets (Image-to-Image)
        self.gan_group = QWidget()
        gan_layout = QFormLayout(self.gan_group)
        self.input_image_edit = QLineEdit(self.last_browsed_scan_dir)
        self.input_btn = QPushButton("Browse")
        self.input_btn.clicked.connect(self.browse_input_image)
        
        gan_layout.addRow("Input Image:", self.input_image_edit)
        gan_layout.addRow("", self.input_btn)
        
        layout.addRow(self.gan_group)
        self.gan_group.setVisible(False)

        # Common Output
        self.add_param_widget(layout, "Output Filename:", QLineEdit(os.path.join(LOCAL_SOURCE_PATH, 'Generated', 'output.png')), "output_filename")
        self.batch_size_box = QSpinBox(minimum=1, value=1, maximum=8)
        self.add_param_widget(layout, "Batch Size:", self.batch_size_box, "batch_size")

        # --- Action Buttons ---
        button_layout = QHBoxLayout()
        self.gen_btn = QPushButton("Generate")
        self.cancel_btn = QPushButton("Cancel")
        
        self.gen_btn.clicked.connect(self.start_generation_thread)
        self.cancel_btn.clicked.connect(self.cancel_generation)
        
        button_layout.addWidget(self.gen_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addRow(button_layout)
        
        self.cancel_btn.setEnabled(False) # Disabled by default

        self.setLayout(layout)

    def browse_input_image(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Input Image", 
            self.last_browsed_scan_dir, 
            "Images (*.png *.jpg *.jpeg)"
        )
        if fname:
            self.input_image_edit.setText(fname)
            self.last_browsed_scan_dir = os.path.dirname(fname)

    def update_ui_visibility(self):
        model_id = self.model_selector.currentData()
        is_gan = model_id == "animegan_v2"
        
        self.diffusion_group.setVisible(not is_gan)
        self.gan_group.setVisible(is_gan)
        
        self.gen_btn.setText("Transfer Style" if is_gan else "Generate Image")
        self.cancel_btn.setEnabled(False)

    def cancel_generation(self):
        model_id = self.model_selector.currentData()
        if model_id == "animegan_v2":
            GanWrapper.cancel_process()
        else:
            LoRATuner.cancel_process()
        
        self.cancel_btn.setEnabled(False)
        self.gen_btn.setEnabled(True)
        QMessageBox.information(self, "Cancelled", "Generation cancellation requested.")

    # --- MAIN THREAD: Gather Data & Start Thread ---
    def start_generation_thread(self):
        self.gen_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
        # Collect all data HERE (Main Thread)
        # Reading widgets inside a thread is unsafe
        config = {
            "model_id": self.model_selector.currentData(),
            "output_filename": self.widgets["output_filename"].text(),
            "batch_size": self.batch_size_box.value(),
            "prompt": self.prompt_edit.text(),
            "neg_prompt": self.neg_prompt_edit.text(),
            "lora_path": self.lora_edit.text(),
            "steps": self.steps_box.value(),
            "guidance": self.guidance_box.value(),
            "input_image": self.input_image_edit.text()
        }

        thread = threading.Thread(target=self.run_generation, kwargs=config)
        thread.start()

    # --- WORKER THREAD: Heavy Logic ---
    def run_generation(self, model_id, output_filename, batch_size, prompt, neg_prompt, lora_path, steps, guidance, input_image):
        try:
            if model_id == "animegan_v2":
                if not input_image or not os.path.exists(input_image):
                    # We can't raise UI here, so we throw to catch block
                    raise ValueError("Please select a valid input image for AnimeGAN.")
                
                gan = GanWrapper()
                gan.generate(input_image, output_filename)
                
            else:
                LoRATuner.generate_anime_image(
                    prompt=prompt,
                    negative_prompt=neg_prompt,
                    model_id=model_id,
                    output_filename=output_filename,
                    steps=steps,
                    guidance_scale=guidance,
                    lora_path=lora_path,
                    batch_size=batch_size
                )
            
            # Check for cancellation
            if LoRATuner.is_cancelled or GanWrapper.is_cancelled:
                self.generation_finished_signal.emit("cancel", "Process was cancelled by the user.")
            elif model_id == "animegan_v2":
                self.generation_finished_signal.emit("success", f"Anime style saved to {output_filename}")
            else:
                self.generation_finished_signal.emit("success", f"Generated {batch_size} image(s) saved starting at {output_filename}")

        except Exception as e:
            self.generation_finished_signal.emit("error", str(e))

    # --- MAIN THREAD: Handle Result ---
    @Slot(str, str)
    def handle_generation_finished(self, status_type, message):
        self.gen_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        # Reset cancellation flags
        LoRATuner.is_cancelled = False
        GanWrapper.is_cancelled = False

        if status_type == "success":
            QMessageBox.information(self, "Success", message)
        elif status_type == "cancel":
            QMessageBox.warning(self, "Result", message)
        else:
            QMessageBox.critical(self, "Error", message)