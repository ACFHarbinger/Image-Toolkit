# Fixed conftest.py
import os
import sys
import pytest
import tempfile

import numpy as np
from PIL import Image
from pathlib import Path
from unittest.mock import MagicMock, patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
repo_root = os.path.dirname(project_root)
sys.path.insert(0, project_root)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import src.constants as udef  # noqa: E402

from src.core import FSETool  # noqa: E402
from src.web import ImageCrawler  # noqa: E402


# --- Mocking External Dependencies ---
# 1. Mock PyQt/PySide Objects
class MockQObject:
    """Mock the QObject base class and signals."""

    def __init__(self, *args, **kwargs):
        pass

    class Signal(MagicMock):
        pass


class MockQtABCMeta(type):
    """Simple mock for the custom metaclass."""

    pass


# 2. Mock the Base Class (WebCrawler)
class MockWebCrawler:
    """Mock WebCrawler to isolate ImageCrawler's logic."""

    def __init__(self, headless, download_dir, screenshot_dir, browser):
        # Mock core attributes ImageCrawler needs access to
        self.driver = MagicMock()
        self.wait = MagicMock()
        self.download_dir = download_dir
        self.screenshot_dir = screenshot_dir
        self.browser = browser
        # Mock methods called in __init__
        self.setup_driver = MagicMock()
        self.file_loader = MagicMock()

        print(f"✅ WebCrawler base initialized with {self.browser} (Mocked).")

    # Mock abstract methods
    def login(self, credentials=None):
        pass

    def process_data(self):
        pass

    def close(self):
        self.driver = None  # Simulate closing the driver
        return True

    # Mock concrete methods used by ImageCrawler
    def navigate_to_url(self, url, take_screenshot=False):
        # Always return True for success in the mock
        return True

    def wait_for_page_to_load(self, timeout=3, selectors=[], screenshot_name=None):
        return True

    # Mock the combination of metaclasses for the class definition
    class QtABCMeta(MockQtABCMeta, type(MockQObject)):
        pass


# --- Mock Java Classes (Existing) ---
# These mock classes simulate the behavior of your compiled Java code.
class MockKeyStoreManager:
    """Mock the Java KeyStoreManager class."""

    # Store state to simulate keystore and key
    keystore = MagicMock()
    secret_key = MagicMock()

    # Instance methods (non-static) - Note the 'self' argument
    def loadKeyStore(self, keystore_path, keystore_pass):
        """Simulate the non-static loadKeyStore call."""
        if "wrong.p12" in keystore_path:
            # Simulate Java exception
            raise Exception("java.io.IOException: Keystore was tampered with.")
        return self.keystore

    def getSecretKey(self, keystore, key_alias, key_pass):
        """Simulate the non-static getSecretKey call."""
        if key_alias == "non_existent_key":
            # Simulate Java returning null (None in Python)
            return None
        return self.secret_key


class MockSecureJsonVault:
    """Mock the Java SecureJsonVault class."""

    def __init__(self, key, path):
        self.key = key
        self.path = path
        self.data = None

    def saveData(self, json_string):
        self.data = json_string

    def loadData(self):
        return self.data


# ----------------------------------------------------------------------
# Pytest Fixtures
# ----------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    """
    Mocks external dependencies imported by definitions.py or others to isolate tests.
    This fixture runs automatically for every test function.
    """
    # Mock WC_BROWSERS in definitions
    monkeypatch.setattr(udef, "WC_BROWSERS", ["brave", "chrome", "firefox"])


@pytest.fixture
def mock_jpype():
    mock_jclass_map = {
        "com.personal.image_toolkit.KeyStoreManager": MockKeyStoreManager,
        "com.personal.image_toolkit.SecureJsonVault": MockSecureJsonVault,
        "java.lang.String": MagicMock(),
    }

    with (
        patch("src.core.vault_manager.jpype.startJVM") as mock_start_jvm,
        patch(
            "src.core.vault_manager.jpype.JClass",
            side_effect=lambda name: mock_jclass_map.get(name, MagicMock()),
        ) as _mock_jclass,
        patch(
            "src.core.vault_manager.jpype.isJVMStarted",
            side_effect=[False, True, True],
        ),
        patch("src.core.vault_manager.jpype.shutdownJVM") as mock_shutdown_jvm,
    ):
        yield mock_start_jvm, mock_shutdown_jvm


@pytest.fixture
def mock_requests():
    """Mock the requests.get method and its response."""
    with patch("src.web.image_crawler.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content.return_value = [
            b"chunk1",
            b"chunk2",
        ]  # Mock file content
        mock_get.return_value = mock_response
        yield mock_get


@pytest.fixture
def mock_os_path():
    """Mock os.path.exists for unique filename testing."""
    with patch(
        "src.web.image_crawler.os.path.exists", side_effect=[True, True, False]
    ) as mock_exists:
        yield mock_exists


# ----------------------------------------------------------------------
# Image Fixtures
# ----------------------------------------------------------------------
@pytest.fixture
def sample_image():
    """Create a temporary test image (PNG)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample PNG image
        img_path = os.path.join(temp_dir, "test_image.png")
        img = Image.new("RGB", (100, 100), (255, 0, 0))  # Red image
        img.save(img_path, "PNG")
        yield img_path


@pytest.fixture
def sample_transparent_image():
    """Create a temporary transparent test image (PNG)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample PNG image with transparency
        img_path = os.path.join(temp_dir, "test_transparent.png")
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))  # Semi-transparent red
        img.save(img_path, "PNG")
        img.save(img_path, "PNG")
        yield img_path


@pytest.fixture
def sample_video():
    """Create a temporary test video file (dummy content)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        vid_path = os.path.join(temp_dir, "test_video.mp4")
        # Create a dummy file with video extension
        with open(vid_path, "wb") as f:
            f.write(b"fake video content")
        yield vid_path


@pytest.fixture
def sample_video_directory():
    """Create a directory with multiple test videos (MP4, AVI, MKV)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        formats = ["mp4", "avi", "mkv"]
        video_paths = []

        for i, fmt in enumerate(formats):
            vid_path = os.path.join(temp_dir, f"test_video_{i}.{fmt}")
            with open(vid_path, "wb") as f:
                f.write(b"fake video content")
            video_paths.append(vid_path)

        yield temp_dir, video_paths


@pytest.fixture
def sample_images_directory():
    """Create a directory with multiple test images (PNG, JPEG, WEBP)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple sample images with different formats
        formats = ["png", "jpeg", "webp"]
        image_paths = []

        for i, fmt in enumerate(formats):
            img_path = os.path.join(temp_dir, f"test_image_{i}.{fmt}")
            img = Image.new("RGB", (50 + i * 10, 50 + i * 10), (i * 80, i * 60, i * 40))
            img.save(img_path, fmt.upper())
            image_paths.append(img_path)

        # Yield the directory path and the list of absolute image paths
        yield temp_dir, image_paths


@pytest.fixture
def output_dir():
    """Create a temporary output directory (used for conversion tests)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def sample_images():
    """
    Create temporary test images for merging/image processing tests.
    (Red, Green, Blue, Yellow in different sizes).
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create sample images
        image_paths = []

        # Create 4 different colored images
        colors = [
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
            (255, 255, 0),
        ]  # Red, Green, Blue, Yellow
        sizes = [(100, 100), (150, 100), (100, 150), (120, 120)]  # Different sizes

        for i, (color, size) in enumerate(zip(colors, sizes)):
            img_path = os.path.join(temp_dir, f"test_image_{i}.png")
            img = Image.new("RGB", size, color)
            img.save(img_path)
            image_paths.append(img_path)

        yield temp_dir, image_paths


# ----------------------------------------------------------------------
# File System Entries Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def temp_test_setup():
    """
    Creates a temporary directory with a structured set of files and subdirectories
    for testing file system operations (used by test_file_system_entries.py).

    Structure:
    /temp_dir
    ├── file_a.txt
    ├── file_b.log
    ├── image_1.png
    ├── subdirectory/
    │   ├── file_c.txt
    │   ├── image_2.jpg
    └── empty_subdir/
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create files
        Path(temp_dir, "file_a.txt").touch()
        Path(temp_dir, "file_b.log").touch()
        Path(temp_dir, "image_1.png").touch()

        # Create subdirectory and its contents
        subdir = Path(temp_dir, "subdirectory")
        subdir.mkdir()
        Path(subdir, "file_c.txt").touch()
        Path(subdir, "image_2.jpg").touch()

        # Create an empty subdirectory
        Path(temp_dir, "empty_subdir").mkdir()

        yield temp_dir


@pytest.fixture
def dummy_decorated_func():
    """
    A simple function decorated with ensure_absolute_paths to test its behavior.
    The dummy function just returns its arguments.
    """

    @FSETool.ensure_absolute_paths()
    def target_func(path_arg_1, path_arg_2, non_path_arg, kwarg_path=None):
        return path_arg_1, path_arg_2, non_path_arg, kwarg_path

    return target_func


# ----------------------------------------------------------------------
# Image Crawler Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def crawler_config():
    return {
        "url": "http://example.com/page-X.html",
        "download_dir": "/tmp/test_downloads",
        "skip_first": 1,
        "skip_last": 1,
        "browser": "brave",
        "headless": True,
    }


@pytest.fixture
def crawler(crawler_config):
    # Instantiate the crawler
    c = ImageCrawler(crawler_config)

    # Mock the signals (since patching class-level Signal doesn't affect existing class)
    c.on_status = MagicMock()
    c.on_image_saved = MagicMock()

    # Mock driver explicitly if missing (though Base MockWebCrawler usually handles it,
    # but ImageCrawler inheritance structure makes it tricky)
    if not hasattr(c, "driver") or c.driver is None:
        c.driver = MagicMock()

    # Mock Base Class methods to ensure isolation from Real WebCrawler
    # This is necessary because ImageCrawler class inherits from Real WebCrawler
    # (imported before tests patched it)
    def mock_close():
        c.driver = None
        return True

    c.close = MagicMock(side_effect=mock_close)
    c.login = MagicMock(return_value=True)
    c.navigate_to_url = MagicMock(return_value=True)
    c.wait_for_page_to_load = MagicMock(return_value=True)

    return c


# ----------------------------------------------------------------------
# Anime stitch pipeline helpers
# Shared builders for backend/test/anim/ tests — pure NumPy/OpenCV so
# tests run without any GPU or model dependency.
# ----------------------------------------------------------------------


def make_frame(h: int = 480, w: int = 640, color=(128, 128, 128)) -> np.ndarray:
    """BGR uint8 frame filled with a solid colour."""
    return np.full((h, w, 3), color, dtype=np.uint8)


def make_gradient_frame(h: int = 480, w: int = 640, top=100, bottom=180) -> np.ndarray:
    """BGR frame with a vertical brightness gradient (mimics scene lighting)."""
    grad = np.linspace(top, bottom, h, dtype=np.float32)
    frame = np.stack([grad] * w, axis=1)[:, :, np.newaxis]
    return np.repeat(frame, 3, axis=2).astype(np.uint8)


def make_translation_affine(tx: float = 0.0, ty: float = 0.0) -> np.ndarray:
    """Identity 2×3 affine with specified translation."""
    M = np.eye(2, 3, dtype=np.float32)
    M[0, 2] = tx
    M[1, 2] = ty
    return M


def make_rotation_affine(tx: float, ty: float, angle_deg: float = 5.0) -> np.ndarray:
    """2×3 affine with translation AND a small rotation (off-diagonal elements)."""
    theta = np.deg2rad(angle_deg)
    return np.array(
        [
            [np.cos(theta), -np.sin(theta), tx],
            [np.sin(theta), np.cos(theta), ty],
        ],
        dtype=np.float32,
    )


def make_edge(
    i: int,
    j: int,
    dx: float = 0.0,
    dy: float = 300.0,
    n_pts: int = 50,
    weight: float = 1.0,
) -> dict:
    """Synthetic edge dict matching the format produced by the matching stages."""
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]], dtype=np.float32)
    rng = np.random.default_rng(i * 1000 + j)
    pts_i = rng.uniform(50, 400, (n_pts, 2)).astype(np.float32)
    pts_j = pts_i + np.array([dx, dy], dtype=np.float32)
    return {"i": i, "j": j, "M": M, "pts_i": pts_i, "pts_j": pts_j, "weight": weight}


def compute_ty_gaps(affines: list) -> np.ndarray:
    """Extract sorted ty values and return consecutive gaps."""
    tys = sorted(float(a[1, 2]) for a in affines)
    return np.diff(tys)


@pytest.fixture
def single_frame():
    return make_frame(h=200, w=300)


@pytest.fixture
def three_frames():
    return [make_frame(h=200, w=300, color=(c, c, c)) for c in (80, 128, 180)]


@pytest.fixture
def chain_edges_300():
    """Perfect sequential chain: 4 frames, each 300 px below the previous."""
    return [make_edge(i, i + 1, dx=0.0, dy=300.0) for i in range(3)]


@pytest.fixture
def chain_edges_5frames():
    """5-frame sequential chain with dy=250."""
    return [make_edge(i, i + 1, dx=0.0, dy=250.0) for i in range(4)]
