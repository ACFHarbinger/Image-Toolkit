from unittest.mock import MagicMock, patch, mock_open
from src.core.image_finder import DuplicateFinder, SimilarityFinder

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

    def test_find_duplicate_images(self):
        # Setup filesystem structure:
        # /dir/img1.jpg (size 100, hash A)
        # /dir/img2.jpg (size 100, hash A) - Duplicate
        # /dir/img3.jpg (size 100, hash B)
        # /dir/img4.jpg (size 200)

        with patch("src.core.image_finder.Path") as mock_path_cls:
            mock_path_obj = MagicMock()
            mock_path_cls.return_value = mock_path_obj

            # Mock files
            f1, f2, f3, f4 = MagicMock(), MagicMock(), MagicMock(), MagicMock()
            f1.is_file.return_value = True
            f1.suffix = ".jpg"
            f1.stat.return_value.st_size = 100
            f1.resolve.return_value = "/dir/img1.jpg"

            f2.is_file.return_value = True
            f2.suffix = ".jpg"
            f2.stat.return_value.st_size = 100
            f2.resolve.return_value = "/dir/img2.jpg"

            f3.is_file.return_value = True
            f3.suffix = ".jpg"
            f3.stat.return_value.st_size = 100
            f3.resolve.return_value = "/dir/img3.jpg"

            f4.is_file.return_value = True
            f4.suffix = ".jpg"
            f4.stat.return_value.st_size = 200
            f4.resolve.return_value = "/dir/img4.jpg"

            mock_path_obj.rglob.return_value = [f1, f2, f3, f4]

            # Mock Hash
            def side_effect_hash(filepath, **kwargs):
                if "img1" in filepath:
                    return "hashA"
                if "img2" in filepath:
                    return "hashA"
                if "img3" in filepath:
                    return "hashB"
                return "hashC"

            with patch.object(
                DuplicateFinder, "get_file_hash", side_effect=side_effect_hash
            ):
                dupes = DuplicateFinder.find_duplicate_images("/dir")

                assert len(dupes) == 1
                assert "hashA" in dupes
                assert len(dupes["hashA"]) == 2
                assert "/dir/img1.jpg" in dupes["hashA"]
                assert "/dir/img2.jpg" in dupes["hashA"]


# --- SimilarityFinder Tests ---


class TestSimilarityFinder:
    @patch("src.core.image_finder.SimilarityFinder.get_images_list")
    @patch("src.core.image_finder.Image.open")
    @patch("src.core.image_finder.imagehash.average_hash")
    def test_find_similar_phash(self, mock_phash, mock_img_open, mock_get_list):
        mock_get_list.return_value = ["img1.jpg", "img2.jpg", "img3.jpg"]

        # img1 and img2 are similar (diff 2), img3 is different (diff 20)
        h1 = MagicMock()
        h2 = MagicMock()
        h3 = MagicMock()

        # Mock substraction
        h1.__sub__.side_effect = lambda other: (
            0 if other == h1 else (2 if other == h2 else 20)
        )

        mock_phash.side_effect = [h1, h2, h3]

        results = SimilarityFinder.find_similar_phash("/dir", threshold=5)

        assert len(results) == 1
        assert "group_0" in results
        assert results["group_0"] == ["img1.jpg", "img2.jpg"]

    @patch("src.core.image_finder.SimilarityFinder.get_images_list")
    @patch("src.core.image_finder.cv2.ORB_create")
    @patch("src.core.image_finder.cv2.imread")
    @patch("src.core.image_finder.cv2.BFMatcher")
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
