import contextlib
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from backend.src.core import VideoFormatConverter
from backend.src.core.video_probe import probe_codecs
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


def _matches_target(current_codec: Optional[str], target_codec: str) -> bool:
    """A stream "matches" a target if the target is unset (we won't touch it),
    or if the probed source codec already equals the target."""
    if target_codec in (None, "", "copy"):
        return True
    return bool(current_codec) and current_codec.lower() == target_codec.lower()


class CodecConversionWorker(QThread):
    """Re-encodes the video and/or audio stream of a batch of video files to a
    different codec, keeping the original container/extension. Files that
    already match every requested target codec are skipped without an
    unnecessary re-encode."""

    progress_signal = Signal(int)  # 0-100
    finished_signal = Signal(int, str)  # (converted_count, message)
    error_signal = Signal(str)

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self._is_cancelled = False
        self.active_processes = set()
        self.process_lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._skip_lock = threading.Lock()
        self._skipped_count = 0

    def cancel(self):
        self._is_cancelled = True
        if self._executor:
            self._executor.shutdown(wait=False, cancel_futures=True)
        with self.process_lock:
            for p in list(self.active_processes):
                with contextlib.suppress(Exception):
                    p.terminate()
            self.active_processes.clear()

    def stop(self):
        self.cancel()

    def run(self):
        try:
            files_to_convert: List[str] = list(self.config.get("files_to_convert", []))

            if not files_to_convert:
                self.error_signal.emit("No files to convert.")
                return

            total_files = len(files_to_convert)
            converted_count = 0
            self.progress_signal.emit(0)

            use_multicore = self.config.get("use_multicore", False)
            failures: List[str] = []

            if use_multicore and total_files > 1:
                max_workers = min(os.cpu_count() or 1, 8)
                self._executor = ThreadPoolExecutor(max_workers=max_workers)

                futures = []
                for idx, input_file in enumerate(files_to_convert):
                    if self._is_cancelled:
                        break
                    futures.append(
                        self._executor.submit(
                            self._convert_single_file, input_file, idx, total_files
                        )
                    )

                for idx, future in enumerate(as_completed(futures)):
                    if self._is_cancelled:
                        break
                    try:
                        if future.result():
                            converted_count += 1
                    except Exception as e:
                        failures.append(str(e))

                    self.progress_signal.emit(int(((idx + 1) / total_files) * 100))

                self._executor.shutdown(wait=True)
                self._executor = None
            else:
                for idx, input_file in enumerate(files_to_convert):
                    if self._is_cancelled:
                        break
                    try:
                        if self._convert_single_file(input_file, idx, total_files):
                            converted_count += 1
                    except Exception as e:
                        failures.append(str(e))

                    self.progress_signal.emit(int(((idx + 1) / total_files) * 100))

            if self._is_cancelled:
                self.finished_signal.emit(converted_count, "**Conversion Cancelled**")
            elif failures:
                summary = f"Processed {converted_count}/{total_files} successfully.\n{len(failures)} error(s) occurred."
                if len(failures) == 1:
                    summary += f"\n\nError: {failures[0]}"
                else:
                    summary += "\n\nFirst few errors:\n - " + "\n - ".join(failures[:3])
                self.finished_signal.emit(converted_count, summary)
            else:
                msg = f"Processed {converted_count} file(s)!"
                if self._skipped_count:
                    msg += f" ({self._skipped_count} already in the target codec, skipped)"
                self.finished_signal.emit(converted_count, msg)

        except Exception as e:
            self.progress_signal.emit(0)
            self.error_signal.emit(str(e))
        finally:
            if self._executor:
                self._executor.shutdown(wait=False)

    def _convert_single_file(self, input_file: str, idx: int, total_files: int) -> bool:
        if self._is_cancelled or not os.path.exists(input_file):
            return False

        video_codec = self.config.get("video_codec") or "copy"
        audio_codec = self.config.get("audio_codec") or "copy"
        crf = self.config.get("crf", 28)
        speed = self.config.get("speed", 2)
        output_path_config = self.config.get("output_path", "")
        output_filename_prefix = self.config.get("output_filename_prefix", "")
        delete_original = self.config.get("delete_original", False)

        if video_codec != "copy" or audio_codec != "copy":
            src_video_codec, src_audio_codec = probe_codecs(input_file)
            if _matches_target(src_video_codec, video_codec) and _matches_target(
                src_audio_codec, audio_codec
            ):
                with self._skip_lock:
                    self._skipped_count += 1
                return False

        base_name, ext = os.path.splitext(os.path.basename(input_file))

        if output_path_config and os.path.isdir(output_path_config):
            out_dir = output_path_config
        elif (
            output_path_config
            and not os.path.exists(output_path_config)
            and total_files > 1
        ):
            try:
                os.makedirs(output_path_config, exist_ok=True)
                out_dir = output_path_config
            except Exception as e:
                logger.warning(
                    "Could not create output directory %s: %s", output_path_config, e
                )
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
            fname = f"{base_name}_recoded"

        # Keep the original container/extension -- this tab only re-encodes
        # streams, it doesn't remux to a different format.
        final_output_path = os.path.join(out_dir, f"{fname}{ext}")

        if os.path.exists(final_output_path) and not delete_original:
            return False

        is_collision = os.path.abspath(input_file) == os.path.abspath(final_output_path)
        temp_output_path = (
            os.path.join(out_dir, f"temp_{fname}{ext}")
            if is_collision
            else final_output_path
        )

        current_p = None

        def register_p(p):
            nonlocal current_p
            current_p = p
            self._register_process(p)

        success = False
        try:
            success = VideoFormatConverter.convert_codec(
                input_path=input_file,
                output_path=temp_output_path,
                video_codec=None if video_codec == "copy" else video_codec,
                audio_codec=None if audio_codec == "copy" else audio_codec,
                crf=crf,
                speed=speed,
                delete=False,
                process_callback=register_p,
            )

            if success:
                if delete_original:
                    try:
                        os.remove(input_file)
                        if is_collision:
                            os.rename(temp_output_path, final_output_path)
                    except Exception as e:
                        logger.warning(
                            "Could not remove original file %s: %s", input_file, e
                        )
                elif is_collision:
                    safe_name = os.path.join(out_dir, f"{fname}_recoded{ext}")
                    if os.path.exists(safe_name):
                        os.remove(safe_name)
                    os.rename(temp_output_path, safe_name)
            else:
                if is_collision and os.path.exists(temp_output_path):
                    try:
                        os.remove(temp_output_path)
                    except Exception as e:
                        logger.warning(
                            "Could not remove temp file %s: %s", temp_output_path, e
                        )
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
