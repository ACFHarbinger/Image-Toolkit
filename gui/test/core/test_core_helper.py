import pytest

from unittest.mock import MagicMock, patch
from gui.src.helpers.core.conversion_worker import ConversionWorker
from gui.src.helpers.core.deletion_worker import DeletionWorker
from gui.src.helpers.core.duplicate_scan_worker import DuplicateScanWorker
from gui.src.helpers.core.search_worker import SearchWorker
from gui.src.helpers.core.wallpaper_worker import WallpaperWorker

# --- ConversionWorker Tests ---


class TestConversionWorker:
    @pytest.fixture
    def mock_converter(self):
        with patch(
            "gui.src.helpers.core.conversion_worker.ImageFormatConverter"
        ) as mock:
            yield mock

    def test_run_single_file(self, mock_converter, q_app):
        config = {
            "input_path": "/tmp/test.jpg",
            "output_format": "png",
            "output_path": "/tmp/out.png",
            "input_formats": None,
            "delete_original": False,
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
        ):

            worker = ConversionWorker(config)

            # Use a list to separate signals from potentially mocked ones
            finished_signals = []
            worker.finished.connect(lambda c, m: finished_signals.append((c, m)))

            worker.run()

            mock_converter.convert_single_image.assert_called_once()
            assert len(finished_signals) == 1
            assert finished_signals[0][0] == 1 or finished_signals[0][0] == 0

    def test_run_batch(self, mock_converter, q_app):
        config = {
            "input_path": "/tmp/images",
            "output_format": "webp",
            "output_path": "/tmp/output",
            "input_formats": [".jpg"],
            "delete_original": False,
            "files_to_convert": ["/tmp/images/1.jpg", "/tmp/images/2.jpg"],
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=False),
        ):  # Treat as files

            # worker.run uses convert_single_image for images
            mock_converter.convert_single_image.return_value = "success"

            worker = ConversionWorker(config)
            finished_signals = []
            worker.finished.connect(lambda c, m: finished_signals.append((c, m)))

            worker.run()

            # Should be called twice, once for each file
            assert mock_converter.convert_single_image.call_count == 2
            assert finished_signals[0][0] == 2


# --- DeletionWorker Tests ---


class TestDeletionWorker:
    @pytest.fixture
    def mock_tools(self):
        with (
            patch("gui.src.helpers.core.deletion_worker.FileDeleter") as fd,
            patch("gui.src.helpers.core.deletion_worker.FSETool") as fse,
        ):
            yield fd, fse

    def test_delete_file(self, mock_tools, q_app):
        mock_deleter, mock_fsetool = mock_tools

        config = {
            "target_path": "/tmp/test.jpg",
            "mode": "files",
            "target_extensions": None,
            "require_confirm": False,
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=True),
        ):

            worker = DeletionWorker(config)

            finished_signals = []
            worker.finished.connect(lambda c, m: finished_signals.append((c, m)))

            mock_deleter.delete_path.return_value = True

            worker.run()

            mock_deleter.delete_path.assert_called_with("/tmp/test.jpg")
            assert finished_signals[0][0] == 1

    def test_delete_directory(self, mock_tools, q_app):
        mock_deleter, mock_fsetool = mock_tools

        config = {
            "target_path": "/tmp/dir",
            "mode": "directory",
            "require_confirm": False,
        }

        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isdir", return_value=True),
        ):

            worker = DeletionWorker(config)

            finished_signals = []
            worker.finished.connect(lambda c, m: finished_signals.append((c, m)))

            mock_deleter.delete_path.return_value = True

            worker.run()

            mock_deleter.delete_path.assert_called_with("/tmp/dir")
            assert finished_signals[0][0] == 1


# --- DuplicateScanWorker Tests ---


class TestDuplicateScanWorker:
    @pytest.fixture
    def mock_finders(self):
        with (
            patch("gui.src.helpers.core.duplicate_scan_worker.DuplicateFinder") as df,
            patch("gui.src.helpers.core.duplicate_scan_worker.SimilarityFinder") as sf,
        ):
            yield df, sf

    def test_exact_scan(self, mock_finders, q_app):
        mock_dup, mock_sim = mock_finders

        worker = DuplicateScanWorker("/tmp", [".jpg"], "exact")

        finished_signals = []
        worker.finished.connect(lambda r: finished_signals.append(r))

        mock_dup.find_duplicate_images.return_value = {"hash": ["a.jpg", "b.jpg"]}

        worker.run()

        mock_dup.find_duplicate_images.assert_called_once()
        assert len(finished_signals) == 1
        assert finished_signals[0] == {"hash": ["a.jpg", "b.jpg"]}

    def test_all_files_mode(self, mock_finders, q_app):
        mock_dup, mock_sim = mock_finders

        worker = DuplicateScanWorker("/tmp", [".jpg"], "all_files")

        finished_signals = []
        worker.finished.connect(lambda r: finished_signals.append(r))

        mock_sim.get_images_list.return_value = ["a.jpg", "b.jpg"]

        worker.run()

        assert finished_signals[0]["0"] == ["a.jpg"]
        assert finished_signals[0]["1"] == ["b.jpg"]


# --- Other Workers (Basic checking) ---


class TestSearchWorker:
    def test_run(self, q_app):
        # SearchWorker takes a db object, it doesn't import FSETool itself
        mock_db = MagicMock()
        mock_db.search_images.return_value = ["res1", "res2"]

        worker = SearchWorker(mock_db, {"query": "test"})

        finished_signals = []
        worker.signals.finished.connect(lambda r: finished_signals.append(r))

        worker.run()

        mock_db.search_images.assert_called_with(query="test")
        assert finished_signals[0] == ["res1", "res2"]


class TestWallpaperWorker:
    def test_run(self, q_app):
        # This one interacts with system, so just check basic connection logic
        with patch("gui.src.helpers.core.wallpaper_worker.WallpaperManager") as mock_wm:
            # Provide dummy monitors and qdbus
            worker = WallpaperWorker("/tmp/img.jpg", [], None)

            finished_signals = []
            # Signal is on .signals and named work_finished
            worker.signals.work_finished.connect(
                lambda s, m: finished_signals.append((s, m))
            )

            worker.run()

            mock_wm.apply_wallpaper.assert_called()
            # Expect success=True because mock didn't raise
            assert finished_signals[0][0] is True
