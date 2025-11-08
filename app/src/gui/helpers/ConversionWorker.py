import os

from PIL import Image
from PySide6.QtCore import QThread, Signal
from ...utils.definitions import SUPPORTED_IMG_FORMATS


class ConversionWorker(QThread):
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)

    def __init__(self, config):
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
            
            if output_format in input_formats: input_formats.remove(output_format)

            is_dir = os.path.isdir(input_path)
            files_to_convert = []
            if is_dir:
                for file in os.listdir(input_path):
                    if any(file.lower().endswith(f".{fmt}") for fmt in input_formats):
                        files_to_convert.append(os.path.join(input_path, file))
            else:
                if any(input_path.lower().endswith(f".{fmt}") for fmt in input_formats):
                    files_to_convert.append(input_path)

            if not files_to_convert:
                self.error.emit("No supported images found.")
                return

            converted = 0
            _, file_ext = os.path.splitext(input_path)
            file_format = file_ext.lstrip('.')
            for file_path in files_to_convert:
                try:
                    with Image.open(file_path) as img:
                        if file_format == output_format or (
                            file_format in ['jpg', 'jpeg'] and output_format in ['jpg', 'jpeg']
                            ): continue
                        if not output_path:
                            out_dir = os.path.dirname(file_path) if not is_dir else input_path
                        elif os.path.isdir(output_path):
                            out_dir = output_path
                        else:
                            out_dir = os.path.dirname(output_path)
                            os.makedirs(out_dir, exist_ok=True)

                        name = os.path.splitext(os.path.basename(file_path))[0]
                        out_file = os.path.join(out_dir, f"{name}.{output_format}")

                        if not os.path.isfile(out_file):
                            img.save(out_file, format=output_format.upper())
                            converted += 1
                        if delete_original:
                            os.remove(file_path)

                except Exception as e:
                    print(f"Failed {file_path}: {e}")

            self.finished.emit(converted, f"Converted {converted} image(s)!")
        except Exception as e:
            self.error.emit(str(e))
