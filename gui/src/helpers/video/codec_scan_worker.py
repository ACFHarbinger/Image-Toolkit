import concurrent.futures
import logging
import os
from typing import List, Optional

from backend.src.core.video.video_probe import probe_codecs
from PySide6.QtCore import Signal

from gui.src.helpers.base import BaseQRunnableWorker, _WorkerSignals

logger = logging.getLogger(__name__)


class _CodecScanSignals(_WorkerSignals):
    codec_ready = Signal(str, object, object)  # path, video_codec, audio_codec


class CodecScanWorker(BaseQRunnableWorker):
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

    def _execute(self) -> object:
        if self.is_cancelled or not self.paths:
            return None

        max_workers = min(os.cpu_count() or 4, 8)
        try:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                self.executor = executor
                # Issue #81 crash family: probe_codecs forks ffprobe on
                # these background threads, possibly concurrently with the
                # first QMediaPlayer construction -- serialize each fork.
                from gui.src.helpers.video.video_thumbnailer import media_backend_spawn_guard


                def _probe_guarded(path):
                    with media_backend_spawn_guard():
                        return probe_codecs(path)

                futures = {
                    executor.submit(_probe_guarded, path): path for path in self.paths
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
            logger.debug("Suppressed Exception in CodecScanWorker.run", exc_info=True)
        finally:
            self.executor = None
        return None
