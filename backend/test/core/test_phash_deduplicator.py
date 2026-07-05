"""Tests for §4.6 PhashDeduplicator and compute_phash."""

import unittest
from unittest.mock import MagicMock, patch


class TestComputePhash(unittest.TestCase):
    """compute_phash: signed-BIGINT output, error handling."""

    def _make_hash_obj(self, hex_str: str):
        """Return a mock ImageHash that str() produces hex_str."""
        mock_hash = MagicMock()
        mock_hash.__str__ = MagicMock(return_value=hex_str)
        return mock_hash

    def test_returns_signed_bigint_for_small_value(self):
        """Values < 2^63 are returned as-is (already signed)."""
        from backend.src.core.phash_deduplicator import compute_phash

        hex_val = "0000000000000001"  # 1
        mock_hash = self._make_hash_obj(hex_val)

        with patch("imagehash.phash", return_value=mock_hash), \
             patch("PIL.Image.open"):
            result = compute_phash("fake.png")

        self.assertEqual(result, 1)
        self.assertIsInstance(result, int)

    def test_large_value_converted_to_signed(self):
        """Values >= 2^63 are two's-complement converted to negative BIGINT."""
        from backend.src.core.phash_deduplicator import compute_phash

        # 0xFFFFFFFFFFFFFFFF = 2^64-1 → signed = -1
        hex_val = "ffffffffffffffff"
        mock_hash = self._make_hash_obj(hex_val)

        with patch("imagehash.phash", return_value=mock_hash), \
             patch("PIL.Image.open"):
            result = compute_phash("fake.png")

        self.assertEqual(result, -1)
        self.assertGreaterEqual(result, -(2 ** 63))
        self.assertLess(result, 2 ** 63)

    def test_all_zeros_hash(self):
        from backend.src.core.phash_deduplicator import compute_phash

        mock_hash = self._make_hash_obj("0000000000000000")
        with patch("imagehash.phash", return_value=mock_hash), \
             patch("PIL.Image.open"):
            result = compute_phash("fake.png")
        self.assertEqual(result, 0)

    def test_returns_none_on_import_error(self):
        """Returns None gracefully when imagehash is absent."""
        from backend.src.core.phash_deduplicator import compute_phash

        with patch.dict("sys.modules", {"imagehash": None}):
            # Re-import to trigger ImportError path
            import importlib

            import backend.src.core.phash_deduplicator as mod
            importlib.reload(mod)
            # patch imagehash inside the reloaded module
            with patch.object(mod, "compute_phash", wraps=mod.compute_phash):
                pass  # just verify no crash

        # Patch at call site level
        with patch("imagehash.phash", side_effect=ImportError("no imagehash")):
            result = compute_phash("fake.png")
        self.assertIsNone(result)

    def test_returns_none_on_file_error(self):
        """Returns None when the image cannot be opened."""
        from backend.src.core.phash_deduplicator import compute_phash

        with patch("PIL.Image.open", side_effect=OSError("not found")):
            result = compute_phash("/nonexistent/path.png")
        self.assertIsNone(result)


class TestPhashDeduplicator(unittest.TestCase):
    """PhashDeduplicator: index_image, find_duplicates_for, context manager."""

    def _make_db(self):
        db = MagicMock()
        db.update_phash = MagicMock()
        db.find_near_duplicates_by_phash = MagicMock(return_value=[])
        db.get_image_by_path = MagicMock(return_value={"id": 1, "phash": None})
        db.conn = MagicMock()
        db.close = MagicMock()
        return db

    def test_index_image_calls_update_phash(self):
        from backend.src.core.phash_deduplicator import PhashDeduplicator

        db = self._make_db()
        ded = PhashDeduplicator(db=db)

        with patch("backend.src.core.phash_deduplicator.compute_phash", return_value=42):
            ok = ded.index_image(image_id=7, path="img.png")

        self.assertTrue(ok)
        db.update_phash.assert_called_once_with(7, 42)

    def test_index_image_returns_false_when_phash_none(self):
        from backend.src.core.phash_deduplicator import PhashDeduplicator

        db = self._make_db()
        ded = PhashDeduplicator(db=db)

        with patch("backend.src.core.phash_deduplicator.compute_phash", return_value=None):
            ok = ded.index_image(image_id=7, path="img.png")

        self.assertFalse(ok)
        db.update_phash.assert_not_called()

    def test_find_duplicates_for_calls_db(self):
        from backend.src.core.phash_deduplicator import PhashDeduplicator

        db = self._make_db()
        db.find_near_duplicates_by_phash.return_value = [
            {"id": 2, "file_path": "/b.png", "hamming_dist": 3}
        ]
        ded = PhashDeduplicator(db=db, threshold=8)

        with patch("backend.src.core.phash_deduplicator.compute_phash", return_value=-99):
            results = ded.find_duplicates_for("query.png")

        db.find_near_duplicates_by_phash.assert_called_once_with(-99, threshold=8, limit=50)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["hamming_dist"], 3)

    def test_find_duplicates_for_returns_empty_when_phash_none(self):
        from backend.src.core.phash_deduplicator import PhashDeduplicator

        db = self._make_db()
        ded = PhashDeduplicator(db=db)

        with patch("backend.src.core.phash_deduplicator.compute_phash", return_value=None):
            results = ded.find_duplicates_for("broken.png")

        self.assertEqual(results, [])
        db.find_near_duplicates_by_phash.assert_not_called()

    def test_context_manager_calls_close(self):
        from backend.src.core.phash_deduplicator import PhashDeduplicator

        db = self._make_db()
        with PhashDeduplicator(db=db) as ded:
            self.assertIsInstance(ded, PhashDeduplicator)

        db.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
