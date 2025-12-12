import os

from typing import Dict, Any
from PySide6.QtCore import QThread, Signal
from backend.src.core import FSETool, ImageFormatConverter
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class ConversionWorker(QThread):
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)
    progress_update = Signal(int) # Signal for reporting progress (0-100)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config

    def run(self):
        try:
            input_path = self.config["input_path"]
            output_format = self.config["output_format"].lower()
            output_path = self.config["output_path"]
            output_filename_prefix = self.config.get("output_filename_prefix", "") # NEW: Get prefix
            input_formats = self.config["input_formats"] or SUPPORTED_IMG_FORMATS
            delete_original = self.config.get("delete_original", False)
            aspect_ratio = self.config.get("aspect_ratio", None)
            aspect_ratio_mode = self.config.get("aspect_ratio_mode", "crop")

            if not input_path or not os.path.exists(input_path):
                self.error.emit("Input path does not exist.")
                return

            is_dir = os.path.isdir(input_path)
            
            # Start progress bar at 0 for both modes
            self.progress_update.emit(0)


            if is_dir:
                # Batch conversion
                
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
                    ar_mode=aspect_ratio_mode,
                    output_filename_prefix=output_filename_prefix, # NEW: Pass prefix
                    progress_callback=self.progress_update.emit,
                )
                converted = len(converted_images)

            else:
                # Single file conversion
                output_name = output_path
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                
                # Logic for output_name: (No numbering needed here)
                if output_filename_prefix:
                    # If prefix is provided, it completely replaces the original filename
                    final_base_name = output_filename_prefix
                else:
                    # Otherwise, use the original base name
                    final_base_name = base_name

                if output_path and os.path.isdir(output_path):
                    output_name = os.path.join(
                        output_path, final_base_name
                    )
                else:
                    # If output_path is empty, use the input directory but the new name
                    output_name = os.path.join(
                        os.path.dirname(input_path), final_base_name
                    )

                if FSETool.path_contains(input_path, output_path):
                    output_name = FSETool.ensure_absolute_paths(
                        prefix_func=ImageFormatConverter.SINGLE_CONVERSION_PREFIX
                    )(output_name)

                result = ImageFormatConverter.convert_single_image(
                    image_path=input_path,
                    output_name=output_name, # Note: this is the full path/basename now
                    format=output_format,
                    delete=delete_original,
                    aspect_ratio=aspect_ratio,
                    ar_mode=aspect_ratio_mode,
                )
                converted = 1 if result is not None else 0
                
                self.progress_update.emit(100) 

            self.finished.emit(converted, f"Processed {converted} image(s)!")
        except Exception as e:
            self.progress_update.emit(0) # Clear progress bar on error
            self.error.emit(str(e))