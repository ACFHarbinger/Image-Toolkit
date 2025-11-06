import os

from PIL import Image
from typing import Dict, Any, List
from PySide6.QtCore import QThread, Signal
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class MergeWorker(QThread):
    progress = Signal(int, int)  # (current, total)
    finished = Signal(str)      # output path
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
            grid_size = self.config["grid_size"]
            formats = self.config["input_formats"] or SUPPORTED_IMG_FORMATS

            # Resolve input files
            image_files: List[str] = []
            for path in input_paths:
                if os.path.isfile(path):
                    if any(path.lower().endswith(f".{fmt}") for fmt in formats):
                        image_files.append(path)
                elif os.path.isdir(path):
                    for file in sorted(os.listdir(path)):
                        if any(file.lower().endswith(f".{fmt}") for fmt in formats):
                            image_files.append(os.path.join(path, file))

            if not image_files:
                self.error.emit("No images found.")
                return

            if len(image_files) == 1:
                self.error.emit("Need at least 2 images to merge.")
                return

            # Load images
            images = []
            for path in image_files:
                try:
                    img = Image.open(path).convert("RGBA")
                    images.append(img)
                except Exception as e:
                    print(f"Failed to load {path}: {e}")

            if len(images) < 2:
                self.error.emit("Failed to load 2+ valid images.")
                return

            total = len(images)
            for i in range(total):
                self.progress.emit(i + 1, total)

            # Determine output size
            if direction == "grid":
                rows, cols = grid_size
                per_row = cols
            else:
                per_row = len(images) if direction == "horizontal" else 1

            # Calculate canvas size
            widths, heights = [], []
            for img in images:
                widths.append(img.width)
                heights.append(img.height)

            if direction == "horizontal":
                canvas_w = sum(widths) + spacing * (len(images) - 1)
                canvas_h = max(heights)
            elif direction == "vertical":
                canvas_w = max(widths)
                canvas_h = sum(heights) + spacing * (len(images) - 1)
            else:  # grid
                row_widths = []
                for r in range(rows):
                    start = r * cols
                    end = min(start + cols, len(images))
                    row_imgs = images[start:end]
                    row_w = sum(img.width for img in row_imgs) + spacing * (len(row_imgs) - 1)
                    row_widths.append(row_w)
                canvas_w = max(row_widths)
                canvas_h = sum(max(img.height for img in images[r*cols:(r+1)*cols] or [images[0]]) 
                              for r in range(rows)) + spacing * (rows - 1)

            canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 0))

            # Paste images
            x, y = 0, 0
            max_h_in_row = 0
            for i, img in enumerate(images):
                if direction == "horizontal":
                    canvas.paste(img, (x, (canvas_h - img.height) // 2), img)
                    x += img.width + spacing
                    max_h_in_row = max(max_h_in_row, img.height)
                elif direction == "vertical":
                    canvas.paste(img, ((canvas_w - img.width) // 2, y), img)
                    y += img.height + spacing
                else:  # grid
                    row = i // cols
                    col = i % cols
                    if col == 0 and i > 0:
                        y += max_h_in_row + spacing
                        x = 0
                        max_h_in_row = 0
                    row_start = row * cols
                    row_images = images[row_start:row_start + cols]
                    col_x = sum(img.width for img in row_images[:col]) + spacing * col
                    canvas.paste(img, (col_x, y), img)
                    max_h_in_row = max(max_h_in_row, img.height)
                    x = col_x

            # Save
            if not output_path:
                output_path = os.path.join(os.path.expanduser("~"), "merged_image.png")
            elif os.path.isdir(output_path):
                output_path = os.path.join(output_path, "merged_image.png")

            canvas = canvas.convert("RGB")
            canvas.save(output_path, "PNG")
            self.finished.emit(output_path)

        except Exception as e:
            self.error.emit(str(e))
