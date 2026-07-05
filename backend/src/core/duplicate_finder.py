import hashlib
import sys

import base

from backend.src.core.file_system_entries import FSETool


class DuplicateFinder:
    """Tools for identifying exact duplicate files based on content hashing."""

    @staticmethod
    def get_file_hash(
        filepath: str, hash_algorithm="sha256", chunk_size=65536
    ) -> str | None:
        # Fallback helper, or for single file use
        hasher = hashlib.new(hash_algorithm)
        try:
            with open(filepath, "rb") as f:
                while True:
                    data = f.read(chunk_size)
                    if not data:
                        break
                    hasher.update(data)
            return hasher.hexdigest()
        except (IOError, OSError):
            return None

    @staticmethod
    @FSETool.ensure_absolute_paths()
    def find_duplicate_images(
        directory: str, extensions: list[str] = None, recursive: bool = True
    ) -> dict:
        if extensions is None:
            extensions = [".jpg", ".jpeg", ".png", ".webp", ".bmp"]

        try:
            # C++ returns HashMap<hash, Vec<path>>
            # Python expects dict
            duplicates = base.find_duplicate_images(directory, extensions, recursive)
            return duplicates
        except Exception as e:
            print(f"Error in find_duplicate_images (C++): {e}", file=sys.stderr)
            return {}


