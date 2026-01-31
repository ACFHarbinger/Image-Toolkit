import pytest
import sys
from unittest.mock import patch
from src.utils.arg_parser import parse_params


class TestConfigsParser:
    """Test suite for the modular argument parser"""

    @pytest.fixture
    def mock_sys_argv(self):
        """Helper to mock sys.argv"""
        with patch("sys.argv", ["prog"]) as mock:
            yield mock

    def test_parse_core_convert_success(self, mock_sys_argv):
        """Test valid conversion arguments"""
        test_args = [
            "core",
            "convert",
            "-i",
            "input.jpg",
            "-o",
            "output_dir",
            "-f",
            "png",
            "-q",
            "90",
            "-r",
        ]
        with patch.object(sys, "argv", ["prog"] + test_args):
            cmd, args = parse_params()
            assert cmd == "core"
            assert args["core_command"] == "convert"
            assert args["input"] == ["input.jpg"]  # nargs='+' returns list
            assert args["output"] == "output_dir"
            assert args["format"] == "png"
            assert args["quality"] == 90
            assert args["recursive"] is True

    def test_parse_core_merge_success(self, mock_sys_argv):
        """Test valid merge arguments"""
        test_args = [
            "core",
            "merge",
            "-i",
            "img1.png",
            "img2.png",
            "-o",
            "merged.png",
            "-d",
            "horizontal",
            "-s",
            "10",
        ]
        with patch.object(sys, "argv", ["prog"] + test_args):
            cmd, args = parse_params()
            assert cmd == "core"
            assert args["core_command"] == "merge"
            assert args["input"] == ["img1.png", "img2.png"]
            assert args["direction"] == "horizontal"
            assert args["spacing"] == 10

    def test_parse_core_merge_grid_validation(self, mock_sys_argv):
        """Test merge grid validation logic"""
        # Case 1: Failure (Missing grid size)
        test_args_fail = [
            "core",
            "merge",
            "-i",
            "img1.png",
            "img2.png",
            "-o",
            "merged.png",
            "-d",
            "grid",
        ]
        with patch.object(sys, "argv", ["prog"] + test_args_fail):
            # Should catch error message
            with pytest.raises(SystemExit):
                parse_params()

        # Case 2: Success
        test_args_success = [
            "core",
            "merge",
            "-i",
            "img1.png",
            "img2.png",
            "-o",
            "merged.png",
            "-d",
            "grid",
            "--grid_size",
            "2",
            "2",
        ]
        with patch.object(sys, "argv", ["prog"] + test_args_success):
            cmd, args = parse_params()
            assert args["grid_size"] == [2, 2]

    def test_parse_web_crawl(self, mock_sys_argv):
        """Test web crawl arguments"""
        test_args = ["web", "crawl", "-q", "cats", "-l", "5", "-o", "./downloads"]
        with patch.object(sys, "argv", ["prog"] + test_args):
            cmd, args = parse_params()
            assert cmd == "web"
            assert args["query"] == "cats"
            assert args["limit"] == 5
            assert args["output"] == "./downloads"

    def test_parse_database_search(self, mock_sys_argv):
        """Test database search arguments"""
        test_args = ["database", "search", "-q", "sunset", "-n", "50"]
        with patch.object(sys, "argv", ["prog"] + test_args):
            cmd, args = parse_params()
            assert cmd == "database"
            assert args["query"] == "sunset"
            assert args["limit"] == 50

    def test_parse_model_generate(self, mock_sys_argv):
        """Test model generation arguments"""
        test_args = ["model", "generate", "-p", "A futuristic city", "-o", "city.png"]
        with patch.object(sys, "argv", ["prog"] + test_args):
            cmd, args = parse_params()
            assert cmd == "model"
            assert args["prompt"] == "A futuristic city"
            assert args["output"] == "city.png"
            assert args["model"] == "stable-diffusion"  # Check default
