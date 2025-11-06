import os
import sys
import pytest
import tempfile

from pathlib import Path
from unittest.mock import patch

# Adjust path to import the module from the 'src' directory
# This assumes the project structure is:
# project_root/
# ├── src/
# │   ├── FileSystemEntries.py
# ├── tests/
# │   └── test_file_system_entries.py
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core.FileSystemEntries import FSETool


# --- FIXTURES ---
@pytest.fixture
def temp_test_setup():
    """
    Creates a temporary directory with a structured set of files and subdirectories
    for testing file system operations.
    
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


# --- TESTS ---

# --- Utility Tests ---

def test_path_contains_true(temp_test_setup):
    """Test path_contains when the child is inside the parent."""
    parent = temp_test_setup
    child = os.path.join(temp_test_setup, "subdirectory")
    assert FSETool.path_contains(parent, child) is True

def test_path_contains_equal(temp_test_setup):
    """Test path_contains when parent and child are the same."""
    assert FSETool.path_contains(temp_test_setup, temp_test_setup) is True

def test_path_contains_false(temp_test_setup):
    """Test path_contains when the child is outside the parent."""
    # Use a different temporary directory as the non-contained path
    with tempfile.TemporaryDirectory() as external_dir:
        assert FSETool.path_contains(temp_test_setup, external_dir) is False

def test_path_contains_nonexistent_paths():
    """Test path_contains with non-existent paths (should still work based on path structure)."""
    parent = "/some/nonexistent/parent"
    child = "/some/nonexistent/parent/child"
    assert FSETool.path_contains(parent, child) is True
    assert FSETool.path_contains(child, parent) is False


# --- Decorator Logic Tests (Prefix Directory Creation) ---

def test_prefix_create_directory_filepath_creation(temp_test_setup):
    """Test that a directory is created when given an output file path."""
    new_dir = os.path.join(temp_test_setup, "new_output_dir")
    output_filepath = os.path.join(new_dir, "output.png")
    
    # Get the inner function from the decorator
    prefix_func = FSETool.prefix_create_directory(arg_id=1, is_filepath=True)
    
    # Call the inner function with the file path
    prefix_func(None, output_filepath, None) # args for a dummy method
    
    assert os.path.isdir(new_dir)
    assert prefix_func.__name__ == 'inner' # Check the internal function name

def test_prefix_create_directory_directory_creation(temp_test_setup):
    """Test that a directory is created when given an output directory path."""
    new_dir = os.path.join(temp_test_setup, "another_new_dir")
    
    # Get the inner function from the decorator
    prefix_func = FSETool.prefix_create_directory(arg_id=1, is_filepath=False)
    
    # Call the inner function with the directory path
    prefix_func(None, new_dir) 
    
    assert os.path.isdir(new_dir)

def test_prefix_create_directory_no_creation_on_simple_filename():
    """Test that directory creation is skipped for a simple filename ('output')."""
    
    # Simple filename provided for output path
    output_filepath = "output.png"
    
    # Get the inner function from the decorator (is_filepath=True)
    prefix_func = FSETool.prefix_create_directory(arg_id=1, is_filepath=True)
    
    # Directory part is '' (empty string), creation should be skipped/pass
    # FIX: This tests the fix where os.path.dirname('output.png') == '' and should pass
    try:
        result = prefix_func(None, output_filepath)
        assert result is True
    except Exception as e:
        pytest.fail(f"prefix_create_directory raised exception for simple filename: {e}")


# --- Decorator Logic Tests (Ensure Absolute Paths) ---

def test_ensure_absolute_paths_relative_to_absolute(dummy_decorated_func, temp_test_setup):
    """Test conversion of an existing relative path to an absolute path."""
    # Save current CWD
    original_cwd = os.getcwd()
    
    try:
        # Change CWD to the temporary directory
        os.chdir(temp_test_setup)
        
        # Create a relative path that exists
        relative_path = "file_a.txt"
        
        # Call the decorated function
        abs_path_1, abs_path_2, *_, kwarg_path = dummy_decorated_func(
            relative_path, 
            os.path.join("subdirectory", "image_2.jpg"), 
            123, 
            kwarg_path="file_b.log"
        )
        
        # The returned paths should now be absolute and match the CWD
        expected_abs_path_1 = os.path.abspath(relative_path)
        
        assert os.path.isabs(abs_path_1)
        assert abs_path_1 == expected_abs_path_1
        
        assert os.path.isabs(abs_path_2)
        assert os.path.isabs(kwarg_path)

    finally:
        # Restore CWD
        os.chdir(original_cwd)

def test_ensure_absolute_paths_nonexistent_and_absolute_paths(dummy_decorated_func):
    """Test that absolute paths are unchanged and non-existent relative paths are unchanged."""
    
    abs_path = os.path.abspath(__file__)
    non_existent_rel_path = "non_existent_file.xyz"
    
    path_arg_1, path_arg_2, *_, kwarg_path = dummy_decorated_func(
        abs_path, 
        non_existent_rel_path, 
        123, 
        kwarg_path="/nonexistent/absolute/path"
    )
    
    # Existing absolute path remains absolute
    assert path_arg_1 == abs_path
    
    # Non-existent relative path remains relative
    assert path_arg_2 == non_existent_rel_path
    
    # Non-existent absolute path remains absolute
    assert kwarg_path == "/nonexistent/absolute/path"


# --- Core FSETool Method Tests (Decorated Methods) ---

def test_get_files_by_extension_no_recursive(temp_test_setup):
    """Test listing files in the top directory only."""
    files = FSETool.get_files_by_extension(temp_test_setup, 'txt', recursive=False)
    
    assert len(files) == 1
    assert os.path.basename(files[0]) == 'file_a.txt'

def test_get_files_by_extension_recursive(temp_test_setup):
    """Test listing files across all subdirectories."""
    files = FSETool.get_files_by_extension(temp_test_setup, 'txt', recursive=True)
    
    assert len(files) == 2
    basenames = sorted([os.path.basename(f) for f in files])
    assert basenames == ['file_a.txt', 'file_c.txt']
    
    # Test a different extension
    files_png = FSETool.get_files_by_extension(temp_test_setup, '.png', recursive=True)
    assert len(files_png) == 1
    assert os.path.basename(files_png[0]) == 'image_1.png'

def test_delete_files_by_extensions(temp_test_setup):
    """Test recursive deletion of files by extension."""
    # Delete all .txt and .log files
    deleted_count = FSETool.delete_files_by_extensions(temp_test_setup, ['txt', 'log'])
    
    assert deleted_count == 3
    
    # Check that they are gone
    assert not os.path.exists(os.path.join(temp_test_setup, "file_a.txt"))
    assert not os.path.exists(os.path.join(temp_test_setup, "file_b.log"))
    assert not os.path.exists(os.path.join(temp_test_setup, "subdirectory", "file_c.txt"))
    
    # Check that others remain
    assert os.path.exists(os.path.join(temp_test_setup, "image_1.png"))

def test_delete_path_file(temp_test_setup):
    """Test deleting a single file."""
    file_path = os.path.join(temp_test_setup, "image_1.png")
    
    assert os.path.exists(file_path)
    result = FSETool.delete_path(file_path)
    
    assert result is True
    assert not os.path.exists(file_path)

def test_delete_path_directory(temp_test_setup):
    """Test deleting a directory (recursively)."""
    dir_path = os.path.join(temp_test_setup, "subdirectory")
    
    assert os.path.isdir(dir_path)
    result = FSETool.delete_path(dir_path)
    
    assert result is True
    assert not os.path.exists(dir_path)

def test_delete_path_non_existent():
    """Test calling delete_path on a non-existent path."""
    # Use patch to suppress the print warning during the test run
    with patch('builtins.print') as mock_print:
        result = FSETool.delete_path("/this/path/never/existed")
        assert result is False
        mock_print.assert_called_with("WARNING: specified path does not exist - did not delete '/this/path/never/existed'.")
