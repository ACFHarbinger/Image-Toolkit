import os

from typing import Dict, Any, List
from PySide6.QtCore import QObject, Signal
from backend.src.core import FSETool, ImageMerger
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS


class MergeWorker(QObject):
    progress = Signal(int, int)  # (current, total)
    finished = Signal(str)  # output path
    error = Signal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config

    def run(self):
        try:
            input_paths = self.config["input_path"]
            output_path = self.config["output_path"]
            direction = self.config["direction"]
            spacing = self.config["spacing"]
            align_mode = self.config["align_mode"]
            grid_size = self.config["grid_size"]
            formats = self.config["input_formats"] or SUPPORTED_IMG_FORMATS

            # 1. Resolve all image files into a single absolute list
            image_files: List[str] = []

            # The original logic handled mixed files/directories. We emulate that
            # using FSETool to resolve paths from directories.
            for path in input_paths:
                if os.path.isfile(path):
                    if any(path.lower().endswith(f".{fmt}") for fmt in formats):
                        image_files.append(path)
                elif os.path.isdir(path):
                    # Get files using FSETool for path normalization and recursion (if needed)
                    for fmt in formats:
                        image_files.extend(
                            FSETool.get_files_by_extension(path, fmt, recursive=False)
                        )

            image_files = list(dict.fromkeys(input_paths))
            if not image_files:
                self.error.emit("No images found to merge.")
                return

            if len(image_files) < 2:
                self.error.emit("Need at least 2 images to merge.")
                return

            # 2. Update progress signals (This is tricky for ImageMerger, we skip full loop)
            # The core merge operation is a single blocking call.
            self.progress.emit(0, len(image_files))

            # 3. Perform the merge using the core class
            merged_img = ImageMerger.merge_images(
                image_paths=image_files,
                output_path=output_path,
                direction=direction,
                grid_size=grid_size,
                align_mode=align_mode,
                spacing=spacing,
            )

            # 4. Final progress update
            self.progress.emit(len(image_files), len(image_files))

            # 5. Emit output path (ImageMerger saves and returns the image object)
            self.finished.emit(output_path)

        except Exception as e:
            self.error.emit(f"Merge failed: {str(e)}")
