import os
from typing import Dict, Any
from PySide6.QtCore import QThread, Signal
from backend.src.core import FSETool, ImageFormatConverter
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class ConversionWorker(QThread):
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config

    def run(self):
        try:
            input_path = self.config["input_path"]
            output_format = self.config["output_format"].lower()
            output_path = self.config["output_path"]
            input_formats = self.config["input_formats"] or SUPPORTED_IMG_FORMATS
            delete_original = self.config["delete"]

            if not input_path or not os.path.exists(input_path):
                self.error.emit("Input path does not exist.")
                return
            
            is_dir = os.path.isdir(input_path)

            if is_dir:
                # Batch conversion
                converted_images = ImageFormatConverter.convert_batch(
                    input_dir=input_path,
                    inputs_formats=input_formats,
                    output_dir=output_path if output_path and os.path.isdir(output_path) else input_path,
                    output_format=output_format,
                    delete=delete_original
                )
                converted = len(converted_images)

            else:
                # Single file conversion (needs directory setup before calling core logic)
                output_name = output_path
                
                # If output_path is provided and is a directory, use the input filename
                if output_path and os.path.isdir(output_path):
                    output_name = os.path.join(output_path, os.path.splitext(os.path.basename(input_path))[0])

                if FSETool.path_contains(input_path, output_path):
                    # Handle scenario where output path is a sub-directory of the input file
                    output_name = FSETool.ensure_absolute_paths(
                        prefix_func=ImageFormatConverter.SINGLE_CONVERSION_PREFIX
                    )(output_name)


                result = ImageFormatConverter.convert_single_image(
                    image_path=input_path,
                    output_name=output_name,
                    format=output_format,
                    delete=delete_original
                )
                converted = 1 if result is not None else 0

            self.finished.emit(converted, f"Converted {converted} image(s)!")
        except Exception as e:
            self.error.emit(str(e))
