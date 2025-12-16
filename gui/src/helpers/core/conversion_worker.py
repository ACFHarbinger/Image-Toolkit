import os

from typing import Dict, Any, List
from PySide6.QtCore import QThread, Signal
from backend.src.core import FSETool, ImageFormatConverter, VideoFormatConverter
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS


class ConversionWorker(QThread):
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)
    progress_update = Signal(int) # Signal for reporting progress (0-100)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config

    def run(self):
        try:
            # Config extraction
            files_to_convert: List[str] = self.config.get("files_to_convert", [])
            output_format = self.config["output_format"].lower()
            output_path_config = self.config.get("output_path", "")
            output_filename_prefix = self.config.get("output_filename_prefix", "")
            delete_original = self.config.get("delete_original", False)
            aspect_ratio = self.config.get("aspect_ratio", None)
            aspect_ratio_mode = self.config.get("aspect_ratio_mode", "crop")
            video_engine = self.config.get("video_engine", "auto")

            if not files_to_convert:
                # Fallback to input_path for legacy/safety (though UI provides list)
                input_path = self.config.get("input_path")
                if input_path and os.path.exists(input_path):
                    if os.path.isdir(input_path):
                        # Naive walk
                        for root, _, files in os.walk(input_path):
                            for f in files:
                                files_to_convert.append(os.path.join(root, f))
                    else:
                        files_to_convert.append(input_path)
            
            if not files_to_convert:
                self.error.emit("No files to convert.")
                return

            total_files = len(files_to_convert)
            converted_count = 0
            
            self.progress_update.emit(0)

            # Define format sets for quick lookup
            # Use lstrip to ensure no dots
            img_formats = set(f.lstrip(".") for f in SUPPORTED_IMG_FORMATS)
            vid_formats = set(f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS)
            
            # Target category
            target_is_video = output_format in vid_formats
            target_is_image = output_format in img_formats

            for idx, input_file in enumerate(files_to_convert):
                if not os.path.exists(input_file):
                    continue

                _, ext = os.path.splitext(input_file)
                src_ext = ext.lstrip(".").lower()

                # Determine file type
                is_src_video = src_ext in vid_formats
                is_src_image = src_ext in img_formats

                # Skip if source is not supported
                if not (is_src_video or is_src_image):
                    continue

                # Determine Output Path
                # 1. Determine directory
                if output_path_config and os.path.isdir(output_path_config):
                    out_dir = output_path_config
                else:
                    # If output config is not a dir, use source dir
                    # (Unless it's a single file case where output_path_config is the full filename? 
                    # The UI logic suggests output_path is mostly directory or empty. 
                    # We'll treat it as directory if it exists as dir, or if it doesn't exist we make it?
                    # For safety, defaults to source dir)
                    if output_path_config and not os.path.exists(output_path_config) and total_files > 1:
                         # Attempt to create directory?
                         try:
                             os.makedirs(output_path_config, exist_ok=True)
                             out_dir = output_path_config
                         except:
                             out_dir = os.path.dirname(input_file)
                    elif output_path_config and not os.path.isdir(output_path_config) and total_files == 1:
                        # Single file specific case: user might have typed a full path including filename
                        # But we handle prefix/format below. 
                        # Let's assume output_path_config IS the directory unless obvious otherwise.
                        out_dir = os.path.dirname(input_file) # Fallback
                    else:
                        out_dir = os.path.dirname(input_file)

                # 2. Determine Filename
                if output_filename_prefix:
                    if total_files > 1:
                        fname = f"{output_filename_prefix}{idx + 1}"
                    else:
                        fname = output_filename_prefix
                else:
                    fname = os.path.splitext(os.path.basename(input_file))[0]

                final_output_path = os.path.join(out_dir, f"{fname}.{output_format}")
                
                # Handling path conflict (input == output)
                if os.path.abspath(input_file) == os.path.abspath(final_output_path):
                     # Prefix to avoid overwrite until needed
                     final_output_path = os.path.join(out_dir, f"converted_{fname}.{output_format}")

                # Perform Conversion
                success = False
                
                # Case 1: Video -> Video (Normal)
                if is_src_video and target_is_video:
                    success = VideoFormatConverter.convert_video(
                        input_path=input_file,
                        output_path=final_output_path,
                        engine=video_engine,
                        delete=delete_original
                    )
                
                # Case 2: Image -> Image (Normal)
                elif is_src_image and target_is_image:
                     res = ImageFormatConverter.convert_single_image(
                        image_path=input_file,
                        output_name=final_output_path, # convert_single handles the full path if provided?
                        # actually convert_single expects output_name to be the path without extension 
                        # OR full path if we tricked it? 
                        # Let's look at convert_single signature in Step 6.
                        # output_name: str = None. 
                        # Code: output_path = f"{output_name}.{format}"
                        # So it APPENDS extension. 
                        # So we should pass the path WITHOUT extension.
                        format=output_format,
                        delete=delete_original,
                        aspect_ratio=aspect_ratio,
                        ar_mode=aspect_ratio_mode
                     )
                     success = res is not None

                # Case 3: Video -> Image (Frame extraction? Not implemented here generally, but maybe requested?)
                # Case 4: Image -> Video (Slideshow? Not implemented here)
                else:
                    # Skip cross-type conversion for now
                    print(f"Skipping {input_file} (Type Mismatch for specified output)")
                    success = False

                if success:
                    converted_count += 1
                
                # Progress Update
                progress = int(((idx + 1) / total_files) * 100)
                self.progress_update.emit(progress)

            self.finished.emit(converted_count, f"Processed {converted_count} file(s)!")

        except Exception as e:
            self.progress_update.emit(0) # Clear progress bar on error
            self.error.emit(str(e))