from unittest.mock import MagicMock, patch, mock_open
from backend.src.core.duplicate_finder import DuplicateFinder
from backend.src.core.similarity_finder import SimilarityFinder

# --- DuplicateFinder Tests ---


class TestDuplicateFinder:
    def test_get_file_hash_success(self):
        data = b"content"
        expected_hash = "ed7002b439e9ac845f22357d822bac1444730fbdb6016d3ec9432297b9ec9f73"  # sha256 of "content"

        with patch("builtins.open", mock_open(read_data=data)):
            h = DuplicateFinder.get_file_hash("dummy.txt")
            assert h == expected_hash

    def test_get_file_hash_ioerror(self):
        with patch("builtins.open", mock_open()) as m:
            m.side_effect = IOError
            h = DuplicateFinder.get_file_hash("dummy.txt")
            assert h is None

    @patch("backend.src.core.duplicate_finder.base.find_duplicate_images")
    def test_find_duplicate_images(self, mock_find_duplicates):
        mock_find_duplicates.return_value = {
            "hashA": ["/dir/img1.jpg", "/dir/img2.jpg"]
        }
        dupes = DuplicateFinder.find_duplicate_images("/dir")
        assert len(dupes) == 1
        assert "hashA" in dupes
        assert len(dupes["hashA"]) == 2
        assert "/dir/img1.jpg" in dupes["hashA"]
        assert "/dir/img2.jpg" in dupes["hashA"]


# --- SimilarityFinder Tests ---


class TestSimilarityFinder:
    @patch("backend.src.core.similarity_finder.base.find_similar_images_phash")
    def test_find_similar_phash(self, mock_find_similar_phash):
        mock_find_similar_phash.return_value = {
            "group_0": ["img1.jpg", "img2.jpg"]
        }
        results = SimilarityFinder.find_similar_phash("/dir", threshold=5)
        assert len(results) == 1
        assert "group_0" in results
        assert results["group_0"] == ["img1.jpg", "img2.jpg"]

    @patch("backend.src.core.similarity_finder.SimilarityFinder.get_images_list")
    @patch("backend.src.core.similarity_finder.cv2.ORB_create")
    @patch("backend.src.core.similarity_finder.cv2.imread")
    @patch("backend.src.core.similarity_finder.cv2.BFMatcher")
    def test_find_similar_orb(self, mock_bf, mock_imread, mock_orb, mock_get_list):
        mock_get_list.return_value = ["img1.jpg", "img2.jpg"]

        # Mock ORB detector
        orb_instance = MagicMock()
        mock_orb.return_value = orb_instance
        # Return dummy keypoints and descriptors
        # Descriptors must be numpy arrays or similar for len() checks inside code if not mocked carefully
        # The logic checks len(des) > 10.
        des1 = MagicMock(__len__=lambda x: 100)
        des2 = MagicMock(__len__=lambda x: 100)
        orb_instance.detectAndCompute.side_effect = [(None, des1), (None, des2)]

        # Mock Matcher
        bf_instance = MagicMock()
        mock_bf.return_value = bf_instance

        # Mock matches. Need good matches to trigger similarity
        # match.distance comparison: m.distance < 0.75 * n.distance
        m = MagicMock(distance=10)
        n = MagicMock(distance=20)
        matches = [
            (m, n)
        ] * 80  # 80 good matches out of 100 = 0.8 similarity > 0.20 threshold
        bf_instance.knnMatch.return_value = matches

        results = SimilarityFinder.find_similar_orb("/dir")

        assert len(results) == 1
        assert "orb_group_0" in results
        assert results["orb_group_0"] == ["img1.jpg", "img2.jpg"]
