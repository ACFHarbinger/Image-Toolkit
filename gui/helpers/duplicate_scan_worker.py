import cv2
import imagehash
import numpy as np

from PIL import Image
from PySide6.QtCore import Slot, Signal, QObject, QThread
from backend.src.core.file_system_entries import DuplicateFinder, SimilarityFinder


class DuplicateScanWorker(QObject):
    """
    Worker thread for scanning duplicates/similar images.
    Handles cancellation and robust image loading.
    """
    finished = Signal(dict)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, directory: str, extensions: list, method: str = "exact"):
        super().__init__()
        self.directory = directory
        self.extensions = extensions
        self.method = method

    def _check_interrupt(self):
        if QThread.currentThread().isInterruptionRequested():
            raise InterruptedError("Scan cancelled by user.")

    @Slot()
    def run(self):
        try:
            results = {}

            if self.method == "exact":
                self.status.emit("Scanning for exact matches...")
                results = DuplicateFinder.find_duplicate_images(
                    self.directory, 
                    self.extensions, 
                    recursive=True
                )
                self._check_interrupt()

            elif self.method == "phash":
                self.status.emit("Indexing images...")
                images = SimilarityFinder.get_images_list(self.directory, self.extensions)
                hashes = {}
                
                total = len(images)
                for i, img_path in enumerate(images):
                    self._check_interrupt()
                    if i % 10 == 0: self.status.emit(f"Hashing {i}/{total}...")
                    try:
                        with Image.open(img_path) as img:
                            hashes[img_path] = imagehash.average_hash(img)
                    except: continue

                self.status.emit("Comparing hashes...")
                ungrouped = list(hashes.keys())
                group_id = 0
                while ungrouped:
                    self._check_interrupt()
                    curr = ungrouped.pop(0)
                    group = [curr]
                    to_rem = []
                    for cand in ungrouped:
                        if hashes[curr] - hashes[cand] <= 5:
                            group.append(cand)
                            to_rem.append(cand)
                    for r in to_rem: ungrouped.remove(r)
                    if len(group) > 1:
                        results[f"phash_{group_id}"] = group
                        group_id += 1

            elif self.method == "orb":
                self.status.emit("Initializing ORB...")
                images = SimilarityFinder.get_images_list(self.directory, self.extensions)
                orb = cv2.ORB_create(nfeatures=500)
                cache = {}
                
                # Compute
                total = len(images)
                for i, path in enumerate(images):
                    self._check_interrupt()
                    if i % 5 == 0: self.status.emit(f"Extracting {i}/{total}...")
                    try:
                        # Robust load: PIL -> Numpy -> OpenCV
                        pil_img = Image.open(path).convert('L')
                        img_np = np.array(pil_img)
                        kp, des = orb.detectAndCompute(img_np, None)
                        if des is not None and len(des) > 10: cache[path] = des
                    except: continue

                # Match
                self.status.emit("Matching features...")
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
                ungrouped = list(cache.keys())
                gid = 0
                while ungrouped:
                    self._check_interrupt()
                    curr = ungrouped.pop(0)
                    group = [curr]
                    to_rem = []
                    for cand in ungrouped:
                        try:
                            matches = bf.knnMatch(cache[curr], cache[cand], k=2)
                            good = [m for m, n in matches if m.distance < 0.75 * n.distance]
                            if len(good) > 10 and (len(good) / len(cache[curr])) > 0.25:
                                group.append(cand)
                                to_rem.append(cand)
                        except: continue
                    for r in to_rem: ungrouped.remove(r)
                    if len(group) > 1:
                        results[f"orb_{gid}"] = group
                        gid += 1

            else: raise ValueError("Unknown method")

            self.finished.emit(results)

        except InterruptedError:
            self.status.emit("Scan cancelled.")
        except Exception as e:
            self.error.emit(str(e))
