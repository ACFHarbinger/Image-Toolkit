
import os
import cv2
import concurrent.futures
import multiprocessing

from pathlib import Path
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Signal, QRunnable, QObject
from backend.src.utils.definitions import SUPPORTED_VIDEO_FORMATS

try:
    import base
    HAS_NATIVE_IMAGING = True
except ImportError:
    HAS_NATIVE_IMAGING = False



class VideoScanSignals(QObject):
    thumbnail_ready = Signal(str, QPixmap)  # path, pixmap
    finished = Signal()


def extract_thumbnail_process(path):
    """
    Standalone function to be run in a separate process.
    Captures a frame from the video at different positions until successful.
    Returns (path, byte_data, width, height, bytes_per_line) or None.
    """
    try:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return None

        # Try multiple positions: 10s, 1s, start
        positions = [300, 30, 0]
        
        frame = None
        for pos in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
            ret, attempt_frame = cap.read()
            if ret and attempt_frame is not None:
                frame = attempt_frame
                break
        
        cap.release()

        if frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = frame_rgb.shape
            # We return raw bytes.
            return (path, frame_rgb.tobytes(), w, h, ch * w)
            
    except Exception:
        pass
    return None


def process_batch_rust(video_paths):
    """
    Process a batch of videos using the Rust backend in a separate process.
    Returns a list of (path, buffer, width, height) tuples.
    """
    try:
        import base
        # Calls the Rust implementation which handles the batch
        # 180 is the target height (or similar parameter depending on base impl)
        # Assuming base.extract_video_thumbnails_batch signature: (paths: List[str], target_size: int) -> List[Tuple]
        results = base.extract_video_thumbnails_batch(video_paths, 180)
        return results
    except Exception:
        return []

class VideoScannerWorker(QRunnable):
    """
    Scans a directory for videos/gifs and generates thumbnails using multiprocessing.
    """

    def __init__(self, directory):
        super().__init__()
        self.directory = directory
        self.signals = VideoScanSignals()
        self.is_cancelled = False
        self.executor = None
        self.batch_size = 8

    def stop(self):
        """Signals the worker to stop scanning."""
        self.is_cancelled = True
        if self.executor:
            self.executor.shutdown(wait=False, cancel_futures=True)

    def run(self):
        if self.is_cancelled:
            return

        if not os.path.isdir(self.directory):
            self.signals.finished.emit()
            return

        try:
            # 1. Gather all video paths
            video_paths = []
            if HAS_NATIVE_IMAGING:
                 video_paths = base.scan_files(
                    [self.directory], list(SUPPORTED_VIDEO_FORMATS), False
                )
            else:
                entries = sorted(os.scandir(self.directory), key=lambda e: e.name.lower())
                video_paths = [
                    e.path
                    for e in entries
                    if e.is_file() and Path(e.path).suffix.lower() in SUPPORTED_VIDEO_FORMATS
                ]

            if not video_paths:
                self.signals.finished.emit()
                return

            if self.is_cancelled:
                return

            # 2. Process in Parallel
            # Limit workers to prevent memory explosion (each process consumes ~GBs if not careful with video buffers)
            max_workers = 4 
            ctx = multiprocessing.get_context('spawn')
            
            with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers, mp_context=ctx) as executor:
                self.executor = executor
                
                # Prepare tasks iterator
                tasks_iter = []
                if HAS_NATIVE_IMAGING:
                    # Create batches generator
                    tasks_iter = [
                        ("batch", video_paths[i : i + self.batch_size]) 
                        for i in range(0, len(video_paths), self.batch_size)
                    ]
                else:
                    tasks_iter = [("single", path) for path in video_paths]
                
                tasks_iterator = iter(tasks_iter)
                pending_futures = {} # Future -> type ("batch" or "single")
                MAX_QUEUE_SIZE = max_workers * 2
                
                # Initial population
                while len(pending_futures) < MAX_QUEUE_SIZE:
                    try:
                        task_type, payload = next(tasks_iterator)
                        if task_type == "batch":
                            fut = executor.submit(process_batch_rust, payload)
                            pending_futures[fut] = "batch"
                        else:
                            fut = executor.submit(extract_thumbnail_process, payload)
                            pending_futures[fut] = "single"
                    except StopIteration:
                        break
                
                # Loop until all done
                while pending_futures:
                    if self.is_cancelled:
                        return
                    
                    # Wait for at least one
                    done, _ = concurrent.futures.wait(
                        pending_futures.keys(), 
                        return_when=concurrent.futures.FIRST_COMPLETED
                    )
                    
                    for fut in done:
                        try:
                            res_type = pending_futures.pop(fut)
                            result = fut.result()
                            
                            if res_type == "batch":
                                for item in result:
                                    if item:
                                        r_path, r_buf, r_w, r_h = item
                                        q_img = QImage(r_buf, r_w, r_h, QImage.Format_RGBA8888)
                                        pixmap = QPixmap.fromImage(q_img.copy())
                                        self.signals.thumbnail_ready.emit(r_path, pixmap)
                                        
                            elif res_type == "single":
                                 if result:
                                    path, data, w, h, bpl = result
                                    q_img = QImage(data, w, h, bpl, QImage.Format_RGB888)
                                    pixmap = QPixmap.fromImage(q_img)
                                    self.signals.thumbnail_ready.emit(path, pixmap)
                        except Exception:
                            pass
                        
                        # Submit next task if available
                        try:
                            task_type, payload = next(tasks_iterator)
                            if task_type == "batch":
                                new_fut = executor.submit(process_batch_rust, payload)
                                pending_futures[new_fut] = "batch"
                            else:
                                new_fut = executor.submit(extract_thumbnail_process, payload)
                                pending_futures[new_fut] = "single"
                        except StopIteration:
                            pass
                    if self.is_cancelled:
                        return
                    
                    try:
                        res_type = futures[future]
                        result = future.result()
                        
                        if res_type == "batch":
                            # result is list of tuples
                            for item in result:
                                if item:
                                    # Rust returns (path, buffer, w, h)
                                    # buffer is strictly raw bytes or bytearray
                                    r_path, r_buf, r_w, r_h = item
                                    q_img = QImage(r_buf, r_w, r_h, QImage.Format_RGBA8888)
                                    pixmap = QPixmap.fromImage(q_img.copy())
                                    self.signals.thumbnail_ready.emit(r_path, pixmap)
                                    
                        elif res_type == "single":
                             if result:
                                path, data, w, h, bpl = result
                                q_img = QImage(data, w, h, bpl, QImage.Format_RGB888)
                                pixmap = QPixmap.fromImage(q_img)
                                self.signals.thumbnail_ready.emit(path, pixmap)
                            
                    except Exception:
                        pass
        
        except Exception:
            pass
        finally:
            self.signals.finished.emit()

    def _generate_thumbnail_opencv(self, path):
         # Kept for compatibility if called directly or strictly needed, but run() uses ProcessPool
         # Re-implementing essentially what extract_thumbnail_process does but returning QPixmap
         res = extract_thumbnail_process(path)
         if res:
             path, data, w, h, bpl = res
             q_img = QImage(data, w, h, bpl, QImage.Format_RGB888)
             return QPixmap.fromImage(q_img)
         return None

