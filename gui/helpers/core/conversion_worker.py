import os

from typing import Dict, Any
from PySide6.QtCore import QThread, Signal
from backend.src.core import FSETool, ImageFormatConverter
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class ConversionWorker(QThread):
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config

    def run(self):
        try:
            input_path = self.config["input_path"]
            output_format = self.config["output_format"].lower()
            output_path = self.config["output_path"]
            input_formats = self.config["input_formats"] or SUPPORTED_IMG_FORMATS
            delete_original = self.config.get("delete_original", False)
            aspect_ratio = self.config.get("aspect_ratio", None)
            aspect_ratio_mode = self.config.get("aspect_ratio_mode", "crop") # Added mode

            if not input_path or not os.path.exists(input_path):
                self.error.emit("Input path does not exist.")
                return

            is_dir = os.path.isdir(input_path)

            if is_dir:
                # Batch conversion
                self.progress.emit(f"Starting batch conversion in {os.path.basename(input_path)}...")

                converted_images = ImageFormatConverter.convert_batch(
                    input_dir=input_path,
                    inputs_formats=input_formats,
                    output_dir=(
                        output_path
                        if output_path and os.path.isdir(output_path)
                        else input_path
                    ),
                    output_format=output_format,
                    delete=delete_original,
                    aspect_ratio=aspect_ratio,
                    ar_mode=aspect_ratio_mode, # Passed mode
                )
                converted = len(converted_images)

            else:
                # Single file conversion
                self.progress.emit(f"Starting single file conversion for {os.path.basename(input_path)}...")

                output_name = output_path
                if output_path and os.path.isdir(output_path):
                    output_name = os.path.join(
                        output_path, os.path.splitext(os.path.basename(input_path))[0]
                    )

                if FSETool.path_contains(input_path, output_path):
                    output_name = FSETool.ensure_absolute_paths(
                        prefix_func=ImageFormatConverter.SINGLE_CONVERSION_PREFIX
                    )(output_name)

                result = ImageFormatConverter.convert_single_image(
                    image_path=input_path,
                    output_name=output_name,
                    format=output_format,
                    delete=delete_original,
                    aspect_ratio=aspect_ratio,
                    ar_mode=aspect_ratio_mode, # Passed mode
                )
                converted = 1 if result is not None else 0

            self.finished.emit(converted, f"Processed {converted} image(s)!")
        except Exception as e:
            self.error.emit(str(e))