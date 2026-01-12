import os
import subprocess

from typing import Dict, Any, List, Optional
from PySide6.QtCore import QThread, Signal
from backend.src.core import ImageFormatConverter, VideoFormatConverter
from backend.src.utils.definitions import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS


class ConversionWorker(QThread):
    finished = Signal(int, str)  # (count, message)
    error = Signal(str)
    progress_update = Signal(int)  # Signal for reporting progress (0-100)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self._is_cancelled = False
        self.current_process: Optional[subprocess.Popen] = None

    def cancel(self):
        """Safely cancels the current operation."""
        self._is_cancelled = True
        if self.current_process:
            try:
                # Terminate the subprocess gracefully first
                self.current_process.terminate()
                # If needed, we could wait a bit and kill, but terminate is usually enough for ffmpeg
            except Exception:
                pass

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
            # NEW dimensions
            ar_w = self.config.get("aspect_ratio_w", None)
            ar_h = self.config.get("aspect_ratio_h", None)

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
                if self._is_cancelled:
                    break

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
                    if (
                        output_path_config
                        and not os.path.exists(output_path_config)
                        and total_files > 1
                    ):
                        try:
                            os.makedirs(output_path_config, exist_ok=True)
                            out_dir = output_path_config
                        except:
                            out_dir = os.path.dirname(input_file)
                    elif (
                        output_path_config
                        and not os.path.isdir(output_path_config)
                        and total_files == 1
                    ):
                        out_dir = os.path.dirname(input_file)  # Fallback
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
                is_collision = False
                if os.path.abspath(input_file) == os.path.abspath(final_output_path):
                    is_collision = True
                    # Use a temporary prefix for the actual conversion
                    temp_output_path = os.path.join(
                        out_dir, f"temp_{fname}.{output_format}"
                    )
                else:
                    temp_output_path = final_output_path

                # Perform Conversion
                success = False

                # Case 1: Video -> Video (Safely via subprocess)
                if is_src_video and target_is_video:
                    success = VideoFormatConverter.convert_video(
                        input_path=input_file,
                        output_path=temp_output_path,
                        delete=False,  # We handle delete separately for renaming logic
                        process_callback=self._register_process,
                        target_width=ar_w,
                        target_height=ar_h,
                    )

                # Case 2: Image -> Image (Normal, via internal logic - safe enough for threads usually)
                elif is_src_image and target_is_image:
                    # Image conversion is fast enough/doesn't use process that crashes on cancel usually
                    # But ideally should check _is_cancelled inside loop if it was batch.
                    # Here it is single image.
                    res = ImageFormatConverter.convert_single_image(
                        image_path=input_file,
                        output_name=temp_output_path,
                        format=output_format,
                        delete=False,  # We handle delete separately
                        aspect_ratio=aspect_ratio,
                        ar_mode=aspect_ratio_mode,
                    )
                    success = res is not None
                else:
                    print(f"Skipping {input_file} (Type Mismatch for specified output)")
                    success = False

                if success:
                    # Post-processing Logic
                    if delete_original:
                        try:
                            # 1. Delete original
                            os.remove(input_file)
                            # 2. Rename temp to original name if it was a collision
                            if is_collision:
                                # Start: input.mp4
                                # Temp: temp_input.mp4
                                # Goal: input.mp4
                                os.rename(temp_output_path, final_output_path)
                            else:
                                # Normal case, temp_output_path is final_output_path
                                pass
                        except Exception as e:
                            print(f"Error during post-conversion replacement: {e}")
                    else:
                        # If NOT deleting original, but there was a collision
                        if is_collision:
                            # We have temp_input.mp4.
                            # We need to rename it to something that doesn't conflict, e.g. converted_input.mp4
                            # (As originally requested by user default behavior, or just leave as collision safe name)
                            safe_name = os.path.join(
                                out_dir, f"converted_{fname}.{output_format}"
                            )
                            if os.path.exists(safe_name):
                                os.remove(safe_name)
                            os.rename(temp_output_path, safe_name)

                    converted_count += 1
                else:
                    # Cleanup temp if failed
                    if is_collision and os.path.exists(temp_output_path):
                        try:
                            os.remove(temp_output_path)
                        except:
                            pass

                # Progress Update
                progress = int(((idx + 1) / total_files) * 100)
                self.progress_update.emit(progress)

            if self._is_cancelled:
                self.finished.emit(converted_count, "**Conversion Cancelled**")
            else:
                self.finished.emit(
                    converted_count, f"Processed {converted_count} file(s)!"
                )

        except Exception as e:
            self.progress_update.emit(0)  # Clear progress bar on error
            self.error.emit(str(e))

    def _register_process(self, p: subprocess.Popen):
        self.current_process = p
