import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        self.active_processes = set()
        self.process_lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None

    def cancel(self):
        """Safely cancels all current operations."""
        self._is_cancelled = True

        # Shutdown executor immediately
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)

        with self.process_lock:
            for p in list(self.active_processes):
                try:
                    p.terminate()
                except Exception:
                    pass
            self.active_processes.clear()

    def stop(self):
        """Signals the worker to stop (alias for cancel)."""
        self.cancel()

    def run(self):
        try:
            # Config extraction
            files_to_convert: List[str] = self.config.get("files_to_convert", [])

            if not files_to_convert:
                # Fallback to input_path
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
            img_formats = set(f.lstrip(".") for f in SUPPORTED_IMG_FORMATS)
            vid_formats = set(f.lstrip(".") for f in SUPPORTED_VIDEO_FORMATS)

            use_multicore = self.config.get("use_multicore", False)

            if use_multicore and total_files > 1:
                # Parallel Execution
                max_workers = min(os.cpu_count() or 1, 8)
                self._executor = ThreadPoolExecutor(max_workers=max_workers)

                futures = []
                for idx, input_file in enumerate(files_to_convert):
                    if self._is_cancelled:
                        break
                    futures.append(
                        self._executor.submit(
                            self._convert_single_file,
                            input_file,
                            idx,
                            total_files,
                            img_formats,
                            vid_formats,
                        )
                    )

                failures = []
                for idx, future in enumerate(as_completed(futures)):
                    if self._is_cancelled:
                        break
                    try:
                        success = future.result()
                        if success:
                            converted_count += 1
                    except Exception as e:
                        failures.append(str(e))

                    # Progress Update (approximate based on completed tasks)
                    progress = int(((idx + 1) / total_files) * 100)
                    self.progress_update.emit(progress)

                self._executor.shutdown(wait=True)
                self._executor = None
            else:
                failures = []
                # Sequential Execution (Existing)
                for idx, input_file in enumerate(files_to_convert):
                    if self._is_cancelled:
                        break
                    try:
                        if self._convert_single_file(
                            input_file, idx, total_files, img_formats, vid_formats
                        ):
                            converted_count += 1
                    except Exception as e:
                        failures.append(str(e))

                    progress = int(((idx + 1) / total_files) * 100)
                    self.progress_update.emit(progress)

            if self._is_cancelled:
                self.finished.emit(converted_count, "**Conversion Cancelled**")
            elif failures:
                summary = f"Processed {converted_count}/{total_files} successfully.\n{len(failures)} error(s) occurred."
                if len(failures) == 1:
                    summary += f"\n\nError: {failures[0]}"
                else:
                    summary += f"\n\nFirst few errors:\n - " + "\n - ".join(failures[:3])
                self.finished.emit(converted_count, summary)
            else:
                self.finished.emit(
                    converted_count, f"Processed {converted_count} file(s)!"
                )

        except Exception as e:
            self.progress_update.emit(0)
            self.error.emit(str(e))
        finally:
            if self._executor:
                self._executor.shutdown(wait=False)

    def _convert_single_file(
        self, input_file, idx, total_files, img_formats, vid_formats
    ) -> bool:
        """Internal helper to convert a single file. Thread-safe."""
        if self._is_cancelled:
            return False

        if not os.path.exists(input_file):
            return False

        # Config extraction (repeated for thread safety/easy access)
        output_format = self.config["output_format"].lower()
        output_path_config = self.config.get("output_path", "")
        output_filename_prefix = self.config.get("output_filename_prefix", "")
        delete_original = self.config.get("delete_original", False)
        aspect_ratio = self.config.get("aspect_ratio", None)
        aspect_ratio_mode = self.config.get("aspect_ratio_mode", "crop")
        ar_w = self.config.get("aspect_ratio_w", None)
        ar_h = self.config.get("aspect_ratio_h", None)

        _, ext = os.path.splitext(input_file)
        src_ext = ext.lstrip(".").lower()

        is_src_video = src_ext in vid_formats
        is_src_image = src_ext in img_formats

        target_is_video = output_format in vid_formats
        target_is_image = output_format in img_formats
        target_is_gif = output_format == "gif"

        if not (is_src_video or is_src_image):
            return False

        valid_pair = False
        if is_src_video and target_is_video:
            valid_pair = True
        elif is_src_image and target_is_image:
            valid_pair = True
        elif is_src_video and target_is_gif:
            valid_pair = True

        if not valid_pair:
            return False

        # Determine Output Path
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
                except Exception as e:
                    print(f"Error creating directory: {e}")
                    out_dir = os.path.dirname(input_file)
            else:
                out_dir = os.path.dirname(input_file)

        if output_filename_prefix:
            fname = (
                f"{output_filename_prefix}{idx + 1}"
                if total_files > 1
                else output_filename_prefix
            )
        else:
            fname = os.path.splitext(os.path.basename(input_file))[0] + "_converted"

        final_output_path = os.path.join(out_dir, f"{fname}.{output_format}")

        if os.path.exists(final_output_path) and not delete_original:
            return False

        is_collision = os.path.abspath(input_file) == os.path.abspath(final_output_path)
        temp_output_path = (
            os.path.join(out_dir, f"temp_{fname}.{output_format}")
            if is_collision
            else final_output_path
        )

        success = False
        current_p = None

        def register_p(p):
            nonlocal current_p
            current_p = p
            self._register_process(p)

        try:
            if is_src_video and target_is_gif:
                success = VideoFormatConverter.convert_to_gif(
                    input_path=input_file,
                    output_path=temp_output_path,
                    delete=False,
                    process_callback=register_p,
                    target_width=ar_w,
                    target_height=ar_h,
                )
            elif is_src_video and target_is_video:
                success = VideoFormatConverter.convert_video(
                    input_path=input_file,
                    output_path=temp_output_path,
                    delete=False,
                    process_callback=register_p,
                    target_width=ar_w,
                    target_height=ar_h,
                    aspect_ratio=aspect_ratio,
                    ar_mode=aspect_ratio_mode,
                )
            elif is_src_image and target_is_image:
                res = ImageFormatConverter.convert_single_image(
                    image_path=input_file,
                    output_name=temp_output_path,
                    format=output_format,
                    delete=False,
                    aspect_ratio=aspect_ratio,
                    ar_mode=aspect_ratio_mode,
                )
                success = res is not None

            if success:
                if delete_original:
                    try:
                        os.remove(input_file)
                        if is_collision:
                            os.rename(temp_output_path, final_output_path)
                    except Exception as e:
                        print(f"Error removing original file: {e}")
                elif is_collision:
                    safe_name = os.path.join(
                        out_dir, f"{fname}_converted.{output_format}"
                    )
                    if os.path.exists(safe_name):
                        os.remove(safe_name)
                    os.rename(temp_output_path, safe_name)
            else:
                if is_collision and os.path.exists(temp_output_path):
                    try:
                        os.remove(temp_output_path)
                    except Exception as e:
                        print(f"Error removing temp file: {e}")

        finally:
            if current_p:
                self._deregister_process(current_p)

        return success

    def _register_process(self, p):
        with self.process_lock:
            self.active_processes.add(p)

    def _deregister_process(self, p):
        with self.process_lock:
            if p in self.active_processes:
                self.active_processes.remove(p)
