from PySide6.QtWidgets import (
    QFormLayout, QLineEdit, QMessageBox,
    QSpinBox, QDoubleSpinBox, QPushButton
)
from ..base_generative_tab import BaseGenerativeTab
from backend.src.models.lora_tuner import LoRATuner


class AnythingGenerateTab(BaseGenerativeTab):
    """
    The specific generation tab for Anything V5.
    """
    def __init__(self):
        super().__init__()
        self.init_ui()
        
    def init_ui(self):
        layout = QFormLayout()
        
        # Model Configuration
        self.add_param_widget(layout, "Model ID:", QLineEdit("stablediffusionapi/anything-v5"), "model_id")
        self.add_param_widget(layout, "LoRA Path (Optional):", QLineEdit("output_lora"), "lora_path")
        self.add_param_widget(layout, "Output Filename:", QLineEdit("anime_output.png"), "output_filename")
        
        # Prompts
        self.add_param_widget(layout, "Prompt:", QLineEdit("1girl, solo, cat ears, library"), "prompt")
        
        default_negative = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
        self.add_param_widget(layout, "Negative Prompt:", QLineEdit(default_negative), "negative_prompt")
        
        # Sampling Settings
        self.add_param_widget(layout, "Inference Steps:", QSpinBox(minimum=1, value=25, maximum=100), "steps")
        
        guidance_box = QDoubleSpinBox()
        guidance_box.setRange(1.0, 20.0)
        guidance_box.setValue(7.0)
        guidance_box.setSingleStep(0.5)
        self.add_param_widget(layout, "Guidance Scale:", guidance_box, "guidance_scale")
        
        # Action Button
        self.gen_btn = QPushButton("Generate Image")
        self.gen_btn.clicked.connect(self.start_generation)
        layout.addRow(self.gen_btn)

        self.setLayout(layout)

    def start_generation(self):
        if LoRATuner is None:
            QMessageBox.critical(self, "Error", "LoRA tuner not found.")
            return

        params = self.get_params()
        
        try:
            # Use the static method from the tuner class
            LoRATuner.generate_anime_image(
                prompt=params["prompt"],
                negative_prompt=params["negative_prompt"],
                model_id=params["model_id"],
                output_filename=params["output_filename"],
                steps=params["steps"],
                guidance_scale=params["guidance_scale"],
                lora_path=params.get("lora_path", "")
            )
            
            QMessageBox.information(self, "Success", f"Image generated: {params['output_filename']}")
            
        except Exception as e:
            QMessageBox.critical(self, "Generation Error", str(e))
