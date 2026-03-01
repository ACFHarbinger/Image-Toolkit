import cv2
import numpy as np

from typing import Dict, Any, List, Tuple
from PySide6.QtCore import (
    Slot,
    Signal,
    QObject,
    QThread,
    QThreadPool,
    QEventLoop,
)
from .tasks import PhashTask, OrbTask, SiftTask, SsimTask, SiameseTask
from backend.src.core import DuplicateFinder, SimilarityFinder


class DuplicateScanWorker(QObject):
    """
    Worker orchestrator for scanning duplicates.
    - Runs in a background QThread (provided by DeleteTab).
    - Spawns QRunnables into QThreadPool for heavy processing.
    - Aggregates results using a QEventLoop.
    - Performs final comparison logic sequentially (fast enough in memory).
    """

    finished = Signal(dict)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, directory: str, extensions: list, method: str = "exact"):
        super().__init__()
        self.directory = directory
        self.extensions = extensions
        self.method = method

        self.thread_pool = QThreadPool.globalInstance()
        self.scan_cache = {}
        self.processed_count = 0
        self.total_files = 0

        # Event loop to pause the Worker thread while Pool threads work
        self.aggregator_loop = None

    def _check_interrupt(self):
        if QThread.currentThread().isInterruptionRequested():
            if self.aggregator_loop and self.aggregator_loop.isRunning():
                self.aggregator_loop.quit()
            raise InterruptedError("Scan cancelled by user.")

    @Slot()
    def run(self):
        try:
            results = {}
            self.scan_cache = {}
            self.processed_count = 0

            # --- NEW: ALL FILES (List Directory Contents) ---
            if self.method == "all_files":
                self.status.emit("Listing all supported files...")

                # Reusing the image listing utility from SimilarityFinder
                images = SimilarityFinder.get_images_list(
                    self.directory, self.extensions
                )

                if not images:
                    self.finished.emit({})
                    return

                results = {}
                for i, path in enumerate(images):
                    # For the DeleteTab logic to display it, we must simulate a 'group'.
                    # We create a group of size 1 for each file, using the index as the group ID.
                    results[str(i)] = [path]

                self.status.emit(f"Found {len(images)} files. Completed.")
                self.finished.emit(results)
                return

            # --- 1. EXACT MATCH (Standard Sequential) ---
            if self.method == "exact":
                self.status.emit("Scanning for exact matches (hashing)...")
                # Exact match is typically I/O bound, usually fast enough without granular threading.
                results = DuplicateFinder.find_duplicate_images(
                    self.directory, self.extensions, recursive=True
                )
                self._check_interrupt()

            # --- 2. PARALLEL PROCESSING (pHash / ORB) ---
            elif self.method in ["phash", "orb", "sift", "ssim", "siamese"]:
                self.status.emit("Indexing images...")
                images = SimilarityFinder.get_images_list(
                    self.directory, self.extensions
                )
                self.total_files = len(images)

                if self.total_files == 0:
                    self.finished.emit({})
                    return

                # Start the Aggregation Loop
                self.aggregator_loop = QEventLoop()

                self.status.emit(
                    f"Queueing {self.total_files} images for processing..."
                )

                # Submit all tasks
                for path in images:
                    self._check_interrupt()
                    if self.method == "phash":
                        task = PhashTask(path)
                    elif self.method == "ssim":
                        task = SsimTask(path)
                    elif self.method == "sift":
                        task = SiftTask(path)
                    elif self.method == "siamese":
                        task = SiameseTask(path)
                    else:
                        task = OrbTask(path)

                    task.signals.result.connect(self._on_task_result)
                    self.thread_pool.start(task)

                # Block execution here until all tasks report back via signals
                self.aggregator_loop.exec()

                self._check_interrupt()

                # --- COMPARISON PHASE (Sequential on aggregated data) ---
                self.status.emit("Comparing indexed data...")

                if self.method == "phash":
                    results = self._compare_phash(self.scan_cache)
                elif self.method == "ssim":
                    _C1, _C2 = 6.5025, 58.5225

                    def _ssim_sim(img1, img2) -> bool:
                        mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
                        mu1_sq = mu1 * mu1
                        sigma1_sq = (
                            cv2.GaussianBlur(img1 * img1, (11, 11), 1.5) - mu1_sq
                        )
                        mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)
                        mu2_sq = mu2 * mu2
                        sigma2_sq = (
                            cv2.GaussianBlur(img2 * img2, (11, 11), 1.5) - mu2_sq
                        )
                        mu1_mu2 = mu1 * mu2
                        sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2
                        num = (2 * mu1_mu2 + _C1) * (2 * sigma12 + _C2)
                        den = (mu1_sq + mu2_sq + _C1) * (sigma1_sq + sigma2_sq + _C2)
                        return float(cv2.mean(num / den)[0]) > 0.90

                    results = self._chunked_compare("ssim", _ssim_sim)
                elif self.method == "sift":
                    _bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

                    def _sift_sim(des1, des2) -> bool:
                        try:
                            matches = _bf.knnMatch(des1, des2, k=2)
                            good = [
                                m for m, n in matches if m.distance < 0.75 * n.distance
                            ]
                            return len(good) > 10 and (len(good) / len(des1)) > 0.20
                        except Exception:
                            return False

                    results = self._chunked_compare("sift", _sift_sim)
                    results = self._chunked_compare("sift", _sift_sim)
                elif self.method == "siamese":
                    results = self._compare_siamese(self.scan_cache)
                    from backend.src.models.siamese_network import SiameseModelLoader

                    SiameseModelLoader().unload()
                else:
                    results = self._compare_orb(self.scan_cache)

            else:
                raise ValueError("Unknown method")

            self.finished.emit(results)

        except InterruptedError:
            self.thread_pool.clear()  # Clear pending
            self.status.emit("Scan cancelled.")
        except Exception as e:
            self.error.emit(str(e))

    @Slot(object)
    def _on_task_result(self, data: Tuple[str, Any]):
        """
        Called when a thread finishes processing an image.
        """
        path, result_data = data

        if result_data is not None:
            self.scan_cache[path] = result_data

        self.processed_count += 1

        # Update status sparingly to avoid flooding the event loop
        if self.processed_count % 5 == 0 or self.processed_count == self.total_files:
            self.status.emit(f"Processed {self.processed_count}/{self.total_files}...")

        # If all tasks are accounted for, quit the blocking loop
        if self.processed_count >= self.total_files:
            if self.aggregator_loop and self.aggregator_loop.isRunning():
                self.aggregator_loop.quit()

    def _chunked_compare(
        self, method_prefix: str, is_similar_fn, chunk_size: int = 500
    ) -> Dict[str, List[str]]:
        """
        O(N^2) pairwise comparison processed in sorted chunks to bound peak RAM.

        After chunk_a is compared against all later chunks, its entries are deleted
        from self.scan_cache, keeping at most 2 * chunk_size descriptors alive at
        any time.  A union-find structure accumulates transitive groups across chunk
        boundaries so correctness is identical to the single-pass algorithm.
        """
        all_paths = sorted(self.scan_cache.keys())
        chunks = [
            all_paths[i : i + chunk_size] for i in range(0, len(all_paths), chunk_size)
        ]
        n_chunks = len(chunks)

        # Union-Find for transitive grouping
        parent = {p: p for p in all_paths}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(a: str, b: str):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        for i, chunk_a in enumerate(chunks):
            self.status.emit(f"Comparing chunk {i + 1}/{n_chunks}...")
            for j in range(i, n_chunks):
                self._check_interrupt()
                chunk_b = chunks[j]
                if i == j:
                    # Within-chunk: upper triangle only (each pair once)
                    for ai in range(len(chunk_a)):
                        pa = chunk_a[ai]
                        desc_a = self.scan_cache[pa]
                        for bi in range(ai + 1, len(chunk_a)):
                            pb = chunk_a[bi]
                            if is_similar_fn(desc_a, self.scan_cache[pb]):
                                union(pa, pb)
                else:
                    # Cross-chunk: full cartesian product
                    for pa in chunk_a:
                        desc_a = self.scan_cache[pa]
                        for pb in chunk_b:
                            if is_similar_fn(desc_a, self.scan_cache[pb]):
                                union(pa, pb)

            # chunk_a fully compared — evict from cache to free RAM
            for p in chunk_a:
                del self.scan_cache[p]

        # Collect groups with more than one member
        grouped: Dict[str, List[str]] = {}
        for p in all_paths:
            grouped.setdefault(find(p), []).append(p)

        results: Dict[str, List[str]] = {}
        gid = 0
        for group in grouped.values():
            if len(group) > 1:
                results[f"{method_prefix}_{gid}"] = group
                gid += 1

        return results

    def _compare_phash(self, hashes: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Sequential comparison of cached hashes.
        """
        results = {}
        ungrouped = list(hashes.keys())
        group_id = 0

        while ungrouped:
            self._check_interrupt()
            curr = ungrouped.pop(0)
            group = [curr]
            to_rem = []

            for cand in ungrouped:
                # Check hamming distance
                if hashes[curr] - hashes[cand] <= 5:
                    group.append(cand)
                    to_rem.append(cand)

            for r in to_rem:
                ungrouped.remove(r)

            if len(group) > 1:
                results[f"phash_{group_id}"] = group
                group_id += 1

        return results

    def _compare_ssim(self, cache: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Sequential comparison using Structural Similarity Index.
        """
        results = {}
        ungrouped = list(cache.keys())
        gid = 0

        # SSIM constants for data range 0-255
        C1 = 6.5025  # (0.01 * 255)^2
        C2 = 58.5225  # (0.03 * 255)^2

        while ungrouped:
            self._check_interrupt()
            curr = ungrouped.pop(0)
            group = [curr]
            to_rem = []

            img1 = cache[curr]

            # Pre-calculation for img1 to save time in the inner loop
            mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
            mu1_sq = mu1 * mu1
            sigma1_sq = cv2.GaussianBlur(img1 * img1, (11, 11), 1.5) - mu1_sq

            for cand in ungrouped:
                img2 = cache[cand]

                # --- SSIM CALCULATION (OpenCV Optimized) ---
                mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)
                mu2_sq = mu2 * mu2
                sigma2_sq = cv2.GaussianBlur(img2 * img2, (11, 11), 1.5) - mu2_sq

                mu1_mu2 = mu1 * mu2
                sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2

                # Formula: (2*mu1*mu2 + C1) * (2*sig12 + C2) / ((mu1^2 + mu2^2 + C1) * (sig1^2 + sig2^2 + C2))
                numerator = (2 * mu1_mu2 + C1) * (2 * sigma12 + C2)
                denominator = (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2)

                ssim_map = numerator / denominator
                score = cv2.mean(ssim_map)[0]
                # -------------------------------------------

                # Threshold: 0.90 is usually a very strong structural match
                if score > 0.90:
                    group.append(cand)
                    to_rem.append(cand)

            for r in to_rem:
                ungrouped.remove(r)

            if len(group) > 1:
                results[f"ssim_{gid}"] = group
                gid += 1

        return results

    def _compare_orb(self, cache: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Sequential comparison of cached descriptors.
        """
        results = {}
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
                except:
                    continue

            for r in to_rem:
                ungrouped.remove(r)

            if len(group) > 1:
                results[f"orb_{gid}"] = group
                gid += 1

        return results

    def _compare_sift(self, cache: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Sequential comparison of SIFT descriptors using L2 Norm.
        """
        results = {}
        # SIFT uses Euclidean Distance (NORM_L2), not Hamming
        bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)

        ungrouped = list(cache.keys())
        gid = 0

        while ungrouped:
            self._check_interrupt()
            curr = ungrouped.pop(0)
            group = [curr]
            to_rem = []

            des1 = cache[curr]

            for cand in ungrouped:
                des2 = cache[cand]
                try:
                    # K-Nearest Neighbors Match
                    matches = bf.knnMatch(des1, des2, k=2)

                    # Lowe's Ratio Test
                    good = []
                    for m, n in matches:
                        if m.distance < 0.75 * n.distance:
                            good.append(m)

                    # Similarity Threshold
                    # SIFT creates more features than ORB usually, so we look for a decent ratio match
                    if len(good) > 10 and (len(good) / len(des1)) > 0.20:
                        group.append(cand)
                        to_rem.append(cand)
                except:
                    continue

            for r in to_rem:
                ungrouped.remove(r)

            if len(group) > 1:
                results[f"sift_{gid}"] = group
                gid += 1

        return results

    def _compare_siamese(self, cache: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Matrix-based Cosine Similarity comparison for Embeddings.
        """
        results = {}
        paths = list(cache.keys())
        if not paths:
            return {}

        # 1. Convert dictionary to Matrix (N images x 512 dimensions)
        # Stacking arrays is much faster than looping manually
        matrix = np.array([cache[p] for p in paths])

        # 2. Normalize vectors (L2 norm)
        # Cosine Similarity = (A . B) / (||A|| * ||B||)
        # If we normalize A and B beforehand, Cosine Sim is just the Dot Product.
        norm = np.linalg.norm(matrix, axis=1, keepdims=True)
        normalized_matrix = matrix / (norm + 1e-10)  # Avoid div by zero

        # 3. Compute Similarity Matrix (N x N)
        # Result is a square matrix where [i][j] is the similarity between img i and j
        sim_matrix = np.dot(normalized_matrix, normalized_matrix.T)

        # 4. Grouping Logic
        # We zero out the lower triangle and diagonal to avoid self-matches and duplicates
        processed_indices = set()

        # Threshold: 0.95 is a good baseline for "Semantic Duplicate"
        # 1.0 = Exact, 0.0 = No similarity
        THRESHOLD = 0.95

        for i in range(len(paths)):
            if i in processed_indices:
                continue

            group = [paths[i]]
            processed_indices.add(i)

            # Look at row i, columns i+1 to end
            for j in range(i + 1, len(paths)):
                if j in processed_indices:
                    continue

                if sim_matrix[i][j] >= THRESHOLD:
                    group.append(paths[j])
                    processed_indices.add(j)

            if len(group) > 1:
                results[f"ai_group_{i}"] = group

        return results
