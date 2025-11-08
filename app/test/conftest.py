# Fixed conftest.py
import os
import sys
import jpype
import pytest
import tempfile

from PIL import Image
from pathlib import Path
from unittest.mock import MagicMock

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core import FSETool


# --- Mock Java Classes (Existing) ---
# These mock classes simulate the behavior of your compiled Java code.
class MockKeyStoreManager:
    def loadKeyStore(self, path, char_array):
        print(f"Mock: Loading keystore from {path}")
        return MagicMock(name="JavaKeyStore")

    def getSecretKey(self, keystore, alias, password):
        print(f"Mock: getSecretKey(alias='{alias}')")
        if alias == "non_existent_key":
            return None
        mock_key = MagicMock()
        mock_key.getAlgorithm.return_value = "AES"
        return mock_key


class MockSecureJsonVault:
    """Mock for the Java SecureJsonVault class."""
    def __init__(self, key, path):
        pass # Initialization successful
        
    def saveData(self, json_string):
        # Simulate successful save
        pass

    def loadData(self):
        # Simulate successful load, return a mock object that acts like a Java String
        mock_java_string = MagicMock(name="JavaString")
        # Ensure the __str__ method (used by str() conversion in Python) returns Python data
        mock_java_string.__str__.return_value = '{"test": "loaded_data"}'
        return mock_java_string

# --- Pytest Fixtures (Combined) ---

# conftest.py

@pytest.fixture
def mock_jpype(monkeypatch):
    # STOP REAL JVM DEAD IN ITS TRACKS
    monkeypatch.setattr("jpype._core._jpype", None)
    monkeypatch.setattr("jpype._core._JVM_started", False)

    mock_start_jvm = MagicMock()
    mock_shutdown_jvm = MagicMock()
    is_jvm_started = [False]

    def mock_is_jvm_started():
        return is_jvm_started[0]

    def start_jvm_side_effect(*args, **kwargs):
        print("MOCK: startJVM called")
        is_jvm_started[0] = True

    mock_start_jvm.side_effect = start_jvm_side_effect
    mock_shutdown_jvm.side_effect = lambda: print("MOCK: shutdownJVM called")

    # MOCK JCLASS
    def mock_jclass(name):
        print(f"MOCK: JClass('{name}')")
        if name == "java.lang.String":
            mock_str = MagicMock()
            mock_inst = MagicMock()
            mock_inst.toCharArray.return_value = "mocked_chars"
            mock_str.return_value = mock_inst
            return mock_str
        if name == "com.personal.image_toolkit.KeyStoreManager":
            return MockKeyStoreManager()
        if name == "com.personal.image_toolkit.SecureJsonVault":
            return MockSecureJsonVault
        return MagicMock()

    def fake_getClass(jc):
        return mock_jclass(jc) if isinstance(jc, str) else jc

    # MOCK EVERYTHING
    monkeypatch.setattr(jpype, "startJVM", mock_start_jvm)
    monkeypatch.setattr(jpype, "shutdownJVM", mock_shutdown_jvm)
    monkeypatch.setattr(jpype, "isJVMStarted", mock_is_jvm_started)
    monkeypatch.setattr(jpype, "JClass", mock_jclass)
    monkeypatch.setattr("jpype._jclass._jpype._getClass", fake_getClass)

    # Fake internal state
    fake_jpype = MagicMock()
    fake_jpype.isStarted.side_effect = mock_is_jvm_started
    monkeypatch.setattr("jpype._core._jpype", fake_jpype)

    return mock_start_jvm, mock_shutdown_jvm

# ----------------------------------------------------------------------
# Fixtures from test_format_converter.py and test_image_merger.py
# ----------------------------------------------------------------------

@pytest.fixture
def sample_image():
    """Create a temporary test image (PNG)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample PNG image
        img_path = os.path.join(temp_dir, "test_image.png")
        img = Image.new('RGB', (100, 100), (255, 0, 0))  # Red image
        img.save(img_path, 'PNG')
        yield img_path


@pytest.fixture
def sample_transparent_image():
    """Create a temporary transparent test image (PNG)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a sample PNG image with transparency
        img_path = os.path.join(temp_dir, "test_transparent.png")
        img = Image.new('RGBA', (100, 100), (255, 0, 0, 128))  # Semi-transparent red
        img.save(img_path, 'PNG')
        yield img_path


@pytest.fixture
def sample_images_directory():
    """Create a directory with multiple test images (PNG, JPEG, WEBP)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create multiple sample images with different formats
        formats = ['png', 'jpeg', 'webp']
        image_paths = []
        
        for i, fmt in enumerate(formats):
            img_path = os.path.join(temp_dir, f"test_image_{i}.{fmt}")
            img = Image.new('RGB', (50 + i*10, 50 + i*10), (i*80, i*60, i*40))
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
        colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]  # Red, Green, Blue, Yellow
        sizes = [(100, 100), (150, 100), (100, 150), (120, 120)]  # Different sizes
        
        for i, (color, size) in enumerate(zip(colors, sizes)):
            img_path = os.path.join(temp_dir, f"test_image_{i}.png")
            img = Image.new('RGB', size, color)
            img.save(img_path)
            image_paths.append(img_path)
        
        yield temp_dir, image_paths

# ----------------------------------------------------------------------
# Fixtures from test_file_system_entries.py
# ----------------------------------------------------------------------

# FSETool is not available in conftest, so we'll mock the decorated function manually, 
# or note that the test depending on this fixture must import FSETool itself.
# Since dummy_decorated_func uses a decorator from an imported module, 
# it's best to keep that logic in the original test file (test_file_system_entries.py) 
# unless the FileSystemEntries module is imported here.
# For simplicity and isolation, we only move the setup fixture.

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
