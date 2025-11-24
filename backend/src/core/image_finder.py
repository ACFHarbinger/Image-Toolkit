import cv2
import hashlib
import imagehash
import numpy as np

from PIL import Image
from pathlib import Path
from collections import defaultdict
from .file_system_entries import FSETool


class DuplicateFinder:
    """Tools for identifying exact duplicate files based on content hashing."""

    @staticmethod
    def get_file_hash(filepath: str, hash_algorithm='sha256', chunk_size=65536) -> str | None:
        hasher = hashlib.new(hash_algorithm)
        try:
            with open(filepath, 'rb') as f:
                while True:
                    data = f.read(chunk_size)
                    if not data: break
                    hasher.update(data)
            return hasher.hexdigest()
        except (IOError, OSError):
            return None

    @staticmethod
    @FSETool.ensure_absolute_paths()
    def find_duplicate_images(directory: str, extensions: list[str] = None, recursive: bool = True) -> dict:
        if extensions is None: extensions = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
        extensions = [e.lower() if e.startswith('.') else f'.{e.lower()}' for e in extensions]

        size_groups = defaultdict(list)
        path_obj = Path(directory)
        iterator = path_obj.rglob('*') if recursive else path_obj.glob('*')

        for file_path in iterator:
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                try:
                    size = file_path.stat().st_size
                    size_groups[size].append(str(file_path.resolve()))
                except (OSError, ValueError):
                    continue

        duplicates = defaultdict(list)
        for size, paths in size_groups.items():
            if len(paths) < 2: continue
            
            hash_groups = defaultdict(list)
            for p in paths:
                file_hash = DuplicateFinder.get_file_hash(p)
                if file_hash: hash_groups[file_hash].append(p)
            
            for h, p_list in hash_groups.items():
                if len(p_list) > 1: duplicates[h].extend(p_list)

        return dict(duplicates)


class SimilarityFinder:
    """
    Tools for finding similar images using Perceptual Hashing or Feature Matching.
    """
    
    @staticmethod
    def get_images_list(directory: str, extensions: list[str] = None, recursive: bool = True) -> list[str]:
        if extensions is None: extensions = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
        extensions = [e.lower() if e.startswith('.') else f'.{e.lower()}' for e in extensions]
        
        path_obj = Path(directory)
        iterator = path_obj.rglob('*') if recursive else path_obj.glob('*')
        return [str(p.resolve()) for p in iterator if p.is_file() and p.suffix.lower() in extensions]

    @staticmethod
    def find_similar_phash(directory: str, extensions: list[str] = None, threshold: int = 5) -> dict:
        """
        Finds similar images using Average Hash (aHash). 
        Good for resized or color-corrected duplicates.
        """
        images = SimilarityFinder.get_images_list(directory, extensions)
        hashes = {}
        
        # 1. Calculate Hashes
        for img_path in images:
            try:
                with Image.open(img_path) as img:
                    hashes[img_path] = imagehash.average_hash(img)
            except Exception:
                continue
        
        # 2. Group by Similarity (Simplified O(N*M) Grouping)
        # We pick a leader, find all close matches, remove them, repeat.
        results = {}
        ungrouped = list(hashes.keys())
        group_id = 0

        while ungrouped:
            current_path = ungrouped.pop(0)
            current_hash = hashes[current_path]
            
            group = [current_path]
            to_remove = []
            
            for candidate_path in ungrouped:
                candidate_hash = hashes[candidate_path]
                if (current_hash - candidate_hash) <= threshold:
                    group.append(candidate_path)
                    to_remove.append(candidate_path)
            
            for r in to_remove:
                ungrouped.remove(r)
                
            if len(group) > 1:
                results[f"group_{group_id}"] = group
                group_id += 1
                
        return results

    @staticmethod
    def find_similar_ssim(directory: str, extensions: list[str] = None, threshold: float = 0.90) -> dict:
        """
        Finds similar images using Structural Similarity Index (SSIM).
        Uses a fixed 256x256 resize for comparison.
        """
        images = SimilarityFinder.get_images_list(directory, extensions)
        cache = {}
        process_size = (256, 256)
        
        # 1. Preprocess
        for img_path in images:
            try:
                with Image.open(img_path) as img:
                    # Convert to standard gray numpy array
                    img_gray = img.convert('L').resize(process_size, Image.Resampling.LANCZOS)
                    cache[img_path] = np.array(img_gray).astype(np.float32)
            except Exception:
                continue

        # 2. Compare (Sequential SSIM)
        results = {}
        ungrouped = list(cache.keys())
        gid = 0
        
        # Constants
        C1 = 6.5025
        C2 = 58.5225
        
        while ungrouped:
            curr = ungrouped.pop(0)
            group = [curr]
            to_remove = []
            
            img1 = cache[curr]
            
            # Calc stats for img1
            mu1 = cv2.GaussianBlur(img1, (11, 11), 1.5)
            mu1_sq = mu1 * mu1
            sigma1_sq = cv2.GaussianBlur(img1 * img1, (11, 11), 1.5) - mu1_sq
            
            for candidate_path in ungrouped:
                img2 = cache[candidate_path]
                
                mu2 = cv2.GaussianBlur(img2, (11, 11), 1.5)
                mu2_sq = mu2 * mu2
                sigma2_sq = cv2.GaussianBlur(img2 * img2, (11, 11), 1.5) - mu2_sq
                
                mu1_mu2 = mu1 * mu2
                sigma12 = cv2.GaussianBlur(img1 * img2, (11, 11), 1.5) - mu1_mu2
                
                numerator = (2 * mu1_mu2 + C1) * (2 * sigma12 + C2)
                denominator = (mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2)
                
                score = cv2.mean(numerator / denominator)[0]
                
                if score > threshold:
                    group.append(candidate_path)
                    to_remove.append(candidate_path)
            
            for r in to_remove:
                ungrouped.remove(r)
                
            if len(group) > 1:
                results[f"ssim_group_{gid}"] = group
                gid += 1
                
        return results

    @staticmethod
    def find_similar_orb(directory: str, extensions: list[str] = None, match_threshold: float = 0.65) -> dict:
        """
        Finds similar images using ORB Feature Matching.
        Good for cropped, rotated, or partially obscured images.
        Note: This is computationally expensive.
        """
        images = SimilarityFinder.get_images_list(directory, extensions)
        orb = cv2.ORB_create(nfeatures=500)
        descriptors_cache = {}

        # 1. Compute Descriptors
        for img_path in images:
            try:
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is None: continue
                kp, des = orb.detectAndCompute(img, None)
                if des is not None and len(des) > 10:
                    descriptors_cache[img_path] = des
            except Exception:
                continue

        # 2. Match
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        results = {}
        ungrouped = list(descriptors_cache.keys())
        group_id = 0

        while ungrouped:
            current_path = ungrouped.pop(0)
            des1 = descriptors_cache[current_path]
            
            group = [current_path]
            to_remove = []
            
            for candidate_path in ungrouped:
                des2 = descriptors_cache[candidate_path]
                
                # KNN Match
                try:
                    matches = bf.knnMatch(des1, des2, k=2)
                    good_matches = []
                    for m, n in matches:
                        if m.distance < 0.75 * n.distance:
                            good_matches.append(m)
                    
                    # Ratio of matched features to total features in the base image
                    similarity = len(good_matches) / len(des1)
                    
                    if similarity > 0.20: # Lower threshold for ORB as it's strict
                         # Double check reverse
                         if len(good_matches) > 10: # At least 10 strong points
                            group.append(candidate_path)
                            to_remove.append(candidate_path)
                except Exception:
                    continue

            for r in to_remove:
                ungrouped.remove(r)
                
            if len(group) > 1:
                results[f"orb_group_{group_id}"] = group
                group_id += 1
                
        return results
    
    @staticmethod
    def find_similar_sift(directory: str, extensions: list[str] = None) -> dict:
        """
        Finds similar images using SIFT Feature Matching.
        More robust to scale/rotation than ORB, but slower.
        """
        images = SimilarityFinder.get_images_list(directory, extensions)
        sift = cv2.SIFT_create(nfeatures=1000)
        descriptors_cache = {}

        # 1. Compute Descriptors
        for img_path in images:
            try:
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is None: continue
                kp, des = sift.detectAndCompute(img, None)
                if des is not None and len(des) > 10:
                    descriptors_cache[img_path] = des
            except Exception:
                continue

        # 2. Match (L2 Norm)
        bf = cv2.BFMatcher(cv2.NORM_L2, crossCheck=False)
        results = {}
        ungrouped = list(descriptors_cache.keys())
        group_id = 0

        while ungrouped:
            current_path = ungrouped.pop(0)
            des1 = descriptors_cache[current_path]
            
            group = [current_path]
            to_remove = []
            
            for candidate_path in ungrouped:
                des2 = descriptors_cache[candidate_path]
                
                try:
                    matches = bf.knnMatch(des1, des2, k=2)
                    good_matches = []
                    for m, n in matches:
                        if m.distance < 0.75 * n.distance:
                            good_matches.append(m)
                    
                    similarity = len(good_matches) / len(des1)
                    
                    if similarity > 0.20: 
                        group.append(candidate_path)
                        to_remove.append(candidate_path)
                except Exception:
                    continue

            for r in to_remove:
                ungrouped.remove(r)
                
            if len(group) > 1:
                results[f"sift_group_{group_id}"] = group
                group_id += 1
                
        return results
