import os
import threading
from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import QFormLayout, QLineEdit, QComboBox, QSpinBox, QCheckBox, QMessageBox, QPushButton
from ....classes.base_generative_tab import BaseGenerativeTab
from backend.src.models.sd3_wrapper import SD3Wrapper
from backend.src.utils.definitions import LOCAL_SOURCE_PATH


class SD3GenerateTab(BaseGenerativeTab):
    """Unified Tab for SD 3.5 Generation (Text-to-Image & ControlNet)."""

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout()

        # --- Base Model Section ---
        base_models = [
            "models/sd3.5_large.safetensors",
            "models/sd3.5_large_turbo.safetensors",
            "models/sd3.5_medium.safetensors",
            "models/sd3_medium.safetensors",
        ]
        self.add_param_widget(layout, "Base Model:", QComboBox(), "model")
        self.widgets["model"].addItems(base_models)
        self.widgets["model"].setEditable(True)

        self.add_param_widget(
            layout, "Prompt:", QLineEdit("cute wallpaper art of a cat"), "prompt"
        )
        self.add_param_widget(layout, "Output Postfix (opt.):", QLineEdit(), "postfix")

        # --- Dimensions & Steps ---
        self.add_param_widget(
            layout, "Width:", QSpinBox(minimum=256, maximum=4096, value=1024), "width"
        )
        self.add_param_widget(
            layout, "Height:", QSpinBox(minimum=256, maximum=4096, value=1024), "height"
        )
        self.add_param_widget(
            layout, "Steps:", QSpinBox(minimum=1, maximum=200, value=28), "steps"
        )
        self.add_param_widget(
            layout, "Skip Layer Cfg (SD3.5-M):", QCheckBox(), "skip_layer_cfg"
        )

        # --- ControlNet Section ---
        cn_models = [
            "None",
            "models/sd3.5_large_controlnet_blur.safetensors",
            "models/sd3.5_large_controlnet_canny.safetensors",
            "models/sd3.5_large_controlnet_depth.safetensors",
        ]
        self.add_param_widget(
            layout, "ControlNet Model:", QComboBox(), "controlnet_ckpt"
        )
        self.widgets["controlnet_ckpt"].addItems(cn_models)
        self.widgets["controlnet_ckpt"].setEditable(True)

        self.add_param_widget(
            layout,
            "ControlNet Cond. Image:",
            QLineEdit("inputs/canny.png"),
            "controlnet_cond_image",
        )

        self.setLayout(layout)

        # Signal for thread communication
        self.generation_finished_signal.connect(self.handle_generation_finished)

    generation_finished_signal = Signal(str, str)

    def run_generation(self, prompt, model_path, output_path, width, height, steps, guidance, batch_size):
        try:
            SD3Wrapper.generate_image(
                prompt=prompt,
                model_path=model_path,
                output_path=output_path,
                width=width,
                height=height,
                steps=steps,
                guidance_scale=guidance,
                batch_size=batch_size
            )
            
            if SD3Wrapper.is_cancelled:
                self.generation_finished_signal.emit("cancel", "Process cancelled.")
            else:
                self.generation_finished_signal.emit("success", f"Saved to {output_path}")

        except Exception as e:
            self.generation_finished_signal.emit("error", str(e))

    @Slot(str, str)
    def handle_generation_finished(self, status, msg):
        if status == "success":
            QMessageBox.information(self, "Success", msg)
        elif status == "error":
            QMessageBox.critical(self, "Error", msg)
        else:
            QMessageBox.warning(self, "Result", msg)

    @Slot(str, str, int, int, int, float, int)
    def generate_from_qml(self, model_name, prompt, width, height, steps, guidance, batch_size):
        """Wrapper for QML"""
        # Map simple model name to path if needed, or assume full path/repo
        # For this prototype we will map the options in QML to paths/repos
        
        # Simple mapping for options in QML (SD3 Medium, SD3 Large, SD3.5 Turbo)
        model_map = {
            "SD3 (Medium)": "stabilityai/stable-diffusion-3-medium-diffusers",
            "SD3 (Large)": "stabilityai/stable-diffusion-3-large-diffusers", # Hypothetical
            "SD3.5 (Turbo)": "stabilityai/stable-diffusion-3.5-large-turbo", # Hypothetical
        }
        
        model_path = model_map.get(model_name, model_name) # Fallback to passed value
        output_path = os.path.join(LOCAL_SOURCE_PATH, "Generated", "sd3_output.png")
        
        thread = threading.Thread(target=self.run_generation, kwargs={
            "prompt": prompt,
            "model_path": model_path,
            "output_path": output_path,
            "width": width,
            "height": height,
            "steps": steps,
            "guidance": guidance,
            "batch_size": batch_size
        })
        thread.start()
