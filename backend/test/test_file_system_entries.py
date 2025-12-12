import os
import sys
import tempfile

from unittest.mock import patch

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.core import FSETool, FileDeleter

class FSEToolTest:
    def test_path_contains_true(self, temp_test_setup):
        parent = temp_test_setup
        child = os.path.join(temp_test_setup, "subdirectory")
        assert FSETool.path_contains(parent, child) is True

    def test_path_contains_equal(self, temp_test_setup):
        assert FSETool.path_contains(temp_test_setup, temp_test_setup) is True

    def test_path_contains_false(self, temp_test_setup):
        with tempfile.TemporaryDirectory() as external_dir:
            assert FSETool.path_contains(temp_test_setup, external_dir) is False

    def test_path_contains_nonexistent_paths(self):
        parent = "/some/nonexistent/parent"
        child = "/some/nonexistent/parent/child"
        assert FSETool.path_contains(parent, child) is True
        assert FSETool.path_contains(child, parent) is False

    # --- Decorator Logic Tests (Prefix Directory Creation) ---
    def test_prefix_create_directory_filepath_creation(self, temp_test_setup):
        new_dir = os.path.join(temp_test_setup, "new_output_dir")
        output_filepath = os.path.join(new_dir, "output.png")
        prefix_func = FSETool.prefix_create_directory(arg_id=1, is_filepath=True)
        prefix_func(None, output_filepath, None)
        assert os.path.isdir(new_dir)

    def test_prefix_create_directory_directory_creation(self, temp_test_setup):
        new_dir = os.path.join(temp_test_setup, "another_new_dir")
        prefix_func = FSETool.prefix_create_directory(arg_id=1, is_filepath=False)
        prefix_func(None, new_dir)
        assert os.path.isdir(new_dir)

    def test_prefix_create_directory_no_creation_on_simple_filename(self):
        output_filepath = "output.png"
        prefix_func = FSETool.prefix_create_directory(arg_id=1, is_filepath=True)
        # Should not raise exception
        assert prefix_func(None, output_filepath) is True

    # --- Decorator Logic Tests (Ensure Absolute Paths) ---
    def test_ensure_absolute_paths_relative_to_absolute(self, dummy_decorated_func, temp_test_setup):
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_test_setup)
            relative_path = "file_a.txt"
            abs_path_1, abs_path_2, *_, kwarg_path = dummy_decorated_func(
                relative_path,
                os.path.join("subdirectory", "image_2.jpg"),
                123,
                kwarg_path="file_b.log",
            )
            assert os.path.isabs(abs_path_1)
            assert abs_path_1 == os.path.abspath(relative_path)
            assert os.path.isabs(abs_path_2)
            assert os.path.isabs(kwarg_path)
        finally:
            os.chdir(original_cwd)

    def test_ensure_absolute_paths_nonexistent_and_absolute_paths(self, dummy_decorated_func):
        abs_path = os.path.abspath(__file__)
        non_existent_rel_path = "non_existent_file.xyz"
        path_arg_1, path_arg_2, *_, kwarg_path = dummy_decorated_func(
            abs_path,
            non_existent_rel_path,
            123,
            kwarg_path="/nonexistent/absolute/path",
        )
        assert path_arg_1 == abs_path
        assert path_arg_2 == non_existent_rel_path
        assert kwarg_path == "/nonexistent/absolute/path"

    # --- Core FSETool Method Tests (Decorated Methods) ---
    def test_get_files_by_extension_no_recursive(self, temp_test_setup):
        files = FSETool.get_files_by_extension(temp_test_setup, "txt", recursive=False)
        assert len(files) == 1
        assert os.path.basename(files[0]) == "file_a.txt"

    def test_get_files_by_extension_recursive(self, temp_test_setup):
        files = FSETool.get_files_by_extension(temp_test_setup, "txt", recursive=True)
        assert len(files) == 2
        basenames = sorted([os.path.basename(f) for f in files])
        assert basenames == ["file_a.txt", "file_c.txt"]

    # --- FileDeleter Method Tests ---
    def test_delete_files_by_extensions(self, temp_test_setup):
        # Delete all .txt and .log files
        deleted_count = FileDeleter.delete_files_by_extensions(
            temp_test_setup, ["txt", "log"]
        )
        
        # Expect: file_a.txt, file_b.log, subdirectory/file_c.txt -> 3 files
        assert deleted_count == 3
        
        assert not os.path.exists(os.path.join(temp_test_setup, "file_a.txt"))
        assert not os.path.exists(os.path.join(temp_test_setup, "file_b.log"))
        assert not os.path.exists(os.path.join(temp_test_setup, "subdirectory", "file_c.txt"))
        assert os.path.exists(os.path.join(temp_test_setup, "image_1.png"))

    def test_delete_path_file(self, temp_test_setup):
        file_path = os.path.join(temp_test_setup, "image_1.png")
        assert os.path.exists(file_path)
        result = FileDeleter.delete_path(file_path)
        assert result is True
        assert not os.path.exists(file_path)

    def test_delete_path_directory(self, temp_test_setup):
        dir_path = os.path.join(temp_test_setup, "subdirectory")
        assert os.path.isdir(dir_path)
        result = FileDeleter.delete_path(dir_path)
        assert result is True
        assert not os.path.exists(dir_path)

    def test_delete_path_non_existent(self):
        with patch("builtins.print") as mock_print:
            result = FileDeleter.delete_path("/this/path/never/existed")
            assert result is False
