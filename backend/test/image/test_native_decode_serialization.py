"""Assert every native-decode/scan boundary entry is serialized by the
NATIVE_IMAGE_BATCH_LOCK / NATIVE_SCAN_LOCK held while the native call runs.

This is Phase 0.1 (issue #521) regression coverage: the crash class this
project already has scar tissue for (see telemetry.NATIVE_IMAGE_BATCH_LOCK's
docstring) is concurrent *Python-level* entries into the native `base`
image-boundary from independent QThread workers. If a call site we've wrapped
ever stops taking its lock, these tests fail loudly.
"""

from unittest.mock import patch

from backend.src.core import duplicate_finder, file_system_entries, similarity_finder
from backend.src.core.image import image_converter, image_merger
from backend.src.core.telemetry import NATIVE_IMAGE_BATCH_LOCK, NATIVE_SCAN_LOCK


def _assert_held(lock, value):
    """Return a native-mock side effect that asserts `lock` is held when called."""

    def side_effect(*args, **kwargs):
        assert lock.locked(), f"native call ran without {lock} serialized"
        return value

    return side_effect


class TestDuplicateFinderSerialized:
    @patch("backend.src.core.duplicate_finder.base.find_duplicate_images")
    def test_find_duplicate_images_holds_lock(self, mock_find):
        mock_find.side_effect = _assert_held(
            NATIVE_IMAGE_BATCH_LOCK, {"hashA": ["/a.jpg", "/b.jpg"]}
        )
        result = duplicate_finder.DuplicateFinder.find_duplicate_images("/tmp")
        assert result == {"hashA": ["/a.jpg", "/b.jpg"]}
        mock_find.assert_called_once()


class TestSimilarityFinderSerialized:
    @patch("backend.src.core.similarity_finder.base.find_similar_images_phash")
    def test_find_similar_phash_holds_lock(self, mock_find):
        mock_find.side_effect = _assert_held(
            NATIVE_IMAGE_BATCH_LOCK, {"group_0": ["a.jpg", "b.jpg"]}
        )
        result = similarity_finder.SimilarityFinder.find_similar_phash(
            "/tmp", threshold=5
        )
        assert result == {"group_0": ["a.jpg", "b.jpg"]}
        mock_find.assert_called_once()


class TestImageConverterSerialized:
    @patch("backend.src.core.image.image_converter.base.convert_single_image")
    def test_convert_single_image_holds_lock(self, mock_convert, tmp_path):
        src = tmp_path / "in.png"
        src.write_bytes(b"placeholder")
        out = tmp_path / "out.png"
        mock_convert.side_effect = _assert_held(NATIVE_IMAGE_BATCH_LOCK, False)
        image_converter.ImageFormatConverter.convert_single_image(
            str(src), output_name=str(out), format="png"
        )
        mock_convert.assert_called_once()


class TestImageMergerSerialized:
    @patch("backend.src.core.image.image_merger.Image.open")
    @patch("backend.src.core.image.image_merger.base.merge_images_horizontal")
    def test_merge_horizontal_holds_lock(self, mock_merge, mock_open):
        mock_merge.side_effect = _assert_held(NATIVE_IMAGE_BATCH_LOCK, None)
        mock_open.return_value = object()
        image_merger.ImageMerger().merge_images(
            ["/a.jpg", "/b.jpg"], "/out.png", direction="horizontal"
        )
        mock_merge.assert_called_once()


class TestFileSystemEntriesSerialized:
    @patch("backend.src.core.file_system_entries.base.get_files_by_extension")
    def test_get_files_by_extension_holds_scan_lock(self, mock_get, tmp_path):
        mock_get.side_effect = _assert_held(NATIVE_SCAN_LOCK, [str(tmp_path / "a.jpg")])
        result = file_system_entries.FSETool.get_files_by_extension(
            str(tmp_path), "jpg", False
        )
        assert result == [str(tmp_path / "a.jpg")]
        mock_get.assert_called_once()
