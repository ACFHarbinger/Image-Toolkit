import concurrent.futures
import os
from typing import List, Optional

from backend.src.core.video_probe import probe_codecs
from PySide6.QtCore import QObject, QRunnable, Signal


class _CodecScanSignals(QObject):
    codec_ready = Signal(str, object, object)  # path, video_codec, audio_codec
    finished = Signal()


class CodecScanWorker(QRunnable):
    """Probes the video/audio codec of a batch of files in parallel background threads."""

    def __init__(self, paths: List[str]):
        super().__init__()
        self.paths = paths
        self.signals = _CodecScanSignals()
        self.is_cancelled = False
        self.executor: Optional[concurrent.futures.ThreadPoolExecutor] = None

    def stop(self):
        self.is_cancelled = True
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def run(self):
        if self.is_cancelled or not self.paths:
            self.signals.finished.emit()
            return

        max_workers = min(os.cpu_count() or 4, 8)
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                self.executor = executor
                futures = {
                    executor.submit(probe_codecs, path): path for path in self.paths
                }

                for future in concurrent.futures.as_completed(futures):
                    if self.is_cancelled:
                        break
                    path = futures[future]
                    try:
                        video_codec, audio_codec = future.result()
                    except Exception:
                        video_codec, audio_codec = None, None
                    self.signals.codec_ready.emit(path, video_codec, audio_codec)
        except Exception:
            pass
        finally:
            self.signals.finished.emit()
