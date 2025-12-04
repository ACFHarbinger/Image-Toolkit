import os
import sys
import pytest
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import src.utils.arg_parser as arg_parser


class ArgParserTest:
    # --- Test Failure Cases ---
    def test_parser_fails_no_command(self, monkeypatch):
        """
        Tests that the parser exits if no command (e.g., 'convert', 'merge') is provided.
        """
        monkeypatch.setattr(sys, "argv", ["script_name.py"])
        # argparse should raise SystemExit when no command is given
        with pytest.raises(SystemExit):
            arg_parser.parse_args()

    def test_parser_fails_invalid_command(self, monkeypatch):
        """
        Tests that the parser exits if an unknown command is provided.
        """
        monkeypatch.setattr(sys, "argv", ["script_name.py", "fly_to_moon"])
        with pytest.raises(SystemExit):
            arg_parser.parse_args()

    def test_search_command_fails_as_unregistered(self, monkeypatch):
        """
        Tests that the 'search' command fails.
        Reason: 'search_parser' is defined in arg_parser.py but
        never added to the subparsers.
        """
        monkeypatch.setattr(sys, "argv", ["script_name.py", "search", "--names", "cat"])
        with pytest.raises(SystemExit):
            arg_parser.parse_args()

    # --- Test 'convert' Command ---

    def test_convert_command_required_args(self, monkeypatch):
        """
        Tests the 'convert' command with only its required arguments.
        """
        test_argv = [
            "script_name.py",
            "convert",
            "--output_format",
            "webp",
            "--input_path",
            "/my/images/img.jpg",
        ]
        monkeypatch.setattr(sys, "argv", test_argv)

        command, args = arg_parser.parse_args()

        assert command == "convert"
        assert args["output_format"] == "webp"
        assert args["input_path"] == "/my/images/img.jpg"

        # Test default values
        assert args["output_path"] is None
        assert args["input_formats"] is None
        # 'action='store_false'' means the default is True
        assert args["delete"] is True

    def test_convert_command_all_args(self, monkeypatch):
        """
        Tests the 'convert' command with all arguments provided.
        """
        test_argv = [
            "script_name.py",
            "convert",
            "--output_format",
            "png",
            "--input_path",
            "/my/images/",
            "--output_path",
            "/my/converted_images/",
            "--input_formats",
            "jpg",
            "bmp",
            "tiff",
            "--delete",  # Passing the flag sets it to False
        ]
        monkeypatch.setattr(sys, "argv", test_argv)

        command, args = arg_parser.parse_args()

        assert command == "convert"
        assert args["output_format"] == "png"
        assert args["input_path"] == "/my/images/"
        assert args["output_path"] == "/my/converted_images/"
        assert args["input_formats"] == ["jpg", "bmp", "tiff"]
        # 'action='store_false'' means passing the flag sets it to False
        assert args["delete"] is False

    def test_convert_command_missing_required(self, monkeypatch):
        """
        Tests that 'convert' fails if a required argument is missing.
        """
        # Missing --input_path
        test_argv = ["script_name.py", "convert", "--output_format", "png"]
        monkeypatch.setattr(sys, "argv", test_argv)

        with pytest.raises(SystemExit):
            arg_parser.parse_args()

    # --- Test 'merge' Command ---

    def test_merge_command_grid(self, monkeypatch):
        """
        Tests the 'merge' command, checking 'nargs' behavior.
        """
        test_argv = [
            "script_name.py",
            "merge",
            "--direction",
            "grid",
            "--input_path",
            "img1.png",
            "img2.png",
            "img3.png",
            "--output_path",
            "merged.png",
            "--spacing",
            "10",
            "--grid_size",
            "2",
            "2",  # nargs=2
        ]
        monkeypatch.setattr(sys, "argv", test_argv)

        command, args = arg_parser.parse_args()

        assert command == "merge"
        assert args["direction"] == "grid"
        assert args["input_path"] == ["img1.png", "img2.png", "img3.png"]  # nargs='+'
        assert args["output_path"] == "merged.png"
        assert args["spacing"] == 10
        assert args["grid_size"] == [2, 2]  # nargs=2

    def test_merge_command_missing_required(self, monkeypatch):
        """
        Tests that 'merge' fails if required arguments are missing.
        """
        # Missing --direction and --input_path
        test_argv = ["script_name.py", "merge"]
        monkeypatch.setattr(sys, "argv", test_argv)

        with pytest.raises(SystemExit):
            arg_parser.parse_args()

    # --- Test 'delete' Command ---

    def test_delete_command(self, monkeypatch):
        """
        Tests the 'delete' command.
        """
        test_argv = [
            "script_name.py",
            "delete",
            "--target_path",
            "/tmp/logs/",
            "--target_extensions",
            "log",
            "tmp",
            "bak",
        ]
        monkeypatch.setattr(sys, "argv", test_argv)

        command, args = arg_parser.parse_args()

        assert command == "delete"
        assert args["target_path"] == "/tmp/logs/"
        assert args["target_extensions"] == ["log", "tmp", "bak"]  # nargs='*'

    # --- Test 'web_crawler' Command ---

    def test_web_crawler_command_basic(self, monkeypatch):
        """
        Tests the 'web_crawler' command with required args and defaults.

        NOTE: The parser definition has type=int for --url, which is
        unusual for a URL. This test respects that definition.
        """
        # NOTE: Your parser defines --url as type=int.
        # If this is a typo and it should be type=str, this test will fail
        # and should be updated (e.g., to --url "http://example.com").
        test_argv = [
            "script_name.py",
            "web_crawler",
            "--url",
            "12345",  # Passing an int as defined in the parser
        ]
        monkeypatch.setattr(sys, "argv", test_argv)

        command, args = arg_parser.parse_args()

        assert command == "web_crawler"
        assert args["url"] == 12345

        # Test defaults
        assert args["browser"] == "brave"  # Default
        assert args["headless"] is False  # Default (action='store_true')
        assert args["download_dir"] == "downloads"
        assert args["screenshot_dir"] is None
        assert args["skip_first"] == 0
        assert args["skip_last"] == 9

    def test_web_crawler_command_invalid_browser(self, monkeypatch):
        """
        Tests that 'web_crawler' fails if an invalid 'browser' choice is given.
        """
        test_argv = [
            "script_name.py",
            "web_crawler",
            "--url",
            "123",
            "--browser",
            "netscape",  # Not in the mocked WC_BROWSERS list
        ]
        monkeypatch.setattr(sys, "argv", test_argv)

        with pytest.raises(SystemExit):
            arg_parser.parse_args()

    # --- Test 'gui' Command ---

    def test_gui_command_defaults(self, monkeypatch):
        """
        Tests the 'gui' command and its default values.
        """
        test_argv = ["script_name.py", "gui"]
        monkeypatch.setattr(sys, "argv", test_argv)

        command, args = arg_parser.parse_args()

        assert command == "gui"
        # Note: type=bool with default=False is an unusual pattern.
        # It means the default is False.
        assert args["no_dropdown"] is False

    def test_gui_command_store_true_action(self, monkeypatch):
        """
        Tests the 'gui' command when the '--no_dropdown' flag is present.
        (Tests that action='store_true' sets the destination to True).
        """
        # Assuming the flag is named --no_dropdown and dest='dropdown'
        test_argv = ["script_name.py", "gui", "--no_dropdown"]
        monkeypatch.setattr(sys, "argv", test_argv)

        command, args = arg_parser.parse_args()

        assert command == "gui"
        # Flag is present, action='store_true' sets args['dropdown'] to True.
        assert args["no_dropdown"] is True
