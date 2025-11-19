import os
import cv2
import shutil
import hashlib
import imagehash
import functools

from PIL import Image
from pathlib import Path
from collections import defaultdict


class FSETool:
    """
    A comprehensive tool for managing file system entries, including path 
    resolution, directory creation, file searching, and path manipulation.
    """
    # --- Utility Methods ---
    @staticmethod
    def path_contains(parent_path, child_path):
        try:
            parent = Path(parent_path).resolve()
            child = Path(child_path).resolve()
            child.relative_to(parent)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def prefix_create_directory(arg_id=0, kwarg_name='', is_filepath=False):
        def inner(*args, **kwargs):
            path = kwargs.get(kwarg_name, None)
            if path is None and len(args) > arg_id:
                path = args[arg_id]
            if path:
                directory = os.path.dirname(path) if is_filepath else path
                if not directory or os.path.exists(directory):
                    return True
                try:
                    os.makedirs(directory, exist_ok=True)
                    print(f"Created directory: '{directory}'.")
                    return True
                except Exception as e:
                    print(f"ERROR: could not create directory '{directory}': {e}")
                    raise
            return False
        return inner

    @staticmethod
    def ensure_absolute_paths(prefix_func=None, suffix_func=None):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                if prefix_func: prefix_func(*args, **kwargs)
                normalized_args = list(args)
                for id, arg in enumerate(normalized_args):
                    if isinstance(arg, str) and not os.path.isabs(arg) and os.path.exists(arg):
                        normalized_args[id] = os.path.abspath(arg)
                for key, value in kwargs.items():
                    if isinstance(value, str) and not os.path.isabs(value) and os.path.exists(value):
                        kwargs[key] = os.path.abspath(value)
                result = func(*tuple(normalized_args), **kwargs)
                if suffix_func: suffix_func(*normalized_args, **kwargs)
                return result
            return wrapper
        return decorator

    @staticmethod
    @ensure_absolute_paths()
    def get_files_by_extension(directory, extension, recursive=False):
        path = Path(directory)
        if not extension.startswith('.'): extension = '.' + extension
        pattern = f'**/*{extension}' if recursive else f'*{extension}'
        return [str(f.resolve()) for f in path.glob(pattern) if f.is_file()]


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


class FileDeleter:
    @staticmethod
    @FSETool.ensure_absolute_paths()
    def delete_path(path_to_delete: str) -> bool:
        if not os.path.exists(path_to_delete): return False
        try:
            if os.path.isdir(path_to_delete): shutil.rmtree(path_to_delete)
            elif os.path.isfile(path_to_delete): os.remove(path_to_delete)
            return True
        except OSError as e:
            print(f"Delete Error: {e}")
            return False

    @staticmethod
    @FSETool.ensure_absolute_paths()
    def delete_files_by_extensions(directory: str, extensions: list[str]) -> int:
        path = Path(directory)
        deleted = 0
        for ext in extensions:
            if not ext.startswith('.'): ext = '.' + ext
            for f in path.rglob(f'*{ext}'):
                if f.is_file():
                    try:
                        f.unlink()
                        deleted += 1
                    except OSError: pass
        return deleted
