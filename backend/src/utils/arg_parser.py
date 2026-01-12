"""
Argument parsing module for the Image-Toolkit framework.

This module provides a unified interface for parsing command-line arguments
across all entry points of the application.
"""

import sys
import argparse
from typing import Sequence
from .definitions import SUPPORTED_IMG_FORMATS, APP_STYLES


class ConfigsParser(argparse.ArgumentParser):
    """
    Custom ArgumentParser to handle string-based nargs correctly.
    """

    def _str_to_nargs(self, nargs):
        if isinstance(nargs, Sequence) and len(nargs) == 1:
            return nargs[0].split() if isinstance(nargs[0], str) else nargs
        else:
            return nargs

    def parse_process_args(self, args=None):
        if args is None:
            args = sys.argv[1:]

        actions_to_check = list(self._actions)

        # Handle subparser actions
        command_name = None
        if args and not args[0].startswith("-"):
            command_name = args[0]

        if command_name:
            subparsers_action = next(
                (
                    a
                    for a in actions_to_check
                    if isinstance(a, argparse._SubParsersAction)
                ),
                None,
            )
            if subparsers_action and command_name in subparsers_action.choices:
                sub_parser = subparsers_action.choices[command_name]
                actions_to_check.extend(sub_parser._actions)

                # Check for secondary subcommands (e.g., 'core convert')
                if len(args) > 1 and not args[1].startswith("-"):
                    sub_command_name = args[1]
                    inner_subparsers_action = next(
                        (
                            a
                            for a in sub_parser._actions
                            if isinstance(a, argparse._SubParsersAction)
                        ),
                        None,
                    )
                    if (
                        inner_subparsers_action
                        and sub_command_name in inner_subparsers_action.choices
                    ):
                        actions_to_check.extend(
                            inner_subparsers_action.choices[sub_command_name]._actions
                        )

        # Process nargs string-to-list conversion
        for action in actions_to_check:
            if action.dest == "help":
                continue
            if action.nargs is not None and action.type is not None:
                opts = action.option_strings
                idx = next((i for i, x in enumerate(args) if x in opts), None)
                if idx is not None and (idx + 1) < len(args):
                    arg_val = args[idx + 1]
                    if isinstance(arg_val, str) and not arg_val.startswith("-"):
                        arg_parts = arg_val.split()
                        if len(arg_parts) > 1:
                            args[idx + 1 : idx + 2] = arg_parts

        subnamespace = super().parse_args(args)
        parsed_args_dict = vars(subnamespace)
        filtered_args = {
            key: value if value != "" else None
            for key, value in parsed_args_dict.items()
        }

        command = filtered_args.pop("command", None)
        return command, filtered_args

    def error_message(self, message, print_help=True):
        print(message)
        if print_help:
            self.print_help()
        sys.exit(1)


class LowercaseAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values is not None:
            values = str(values).lower()
        setattr(namespace, self.dest, values)


class StoreDictKeyPair(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        my_dict = {}
        for kv in values:
            if "=" in kv:
                k, v = kv.split("=", 1)
                my_dict[k] = v
            else:
                raise argparse.ArgumentError(
                    self, f"Could not parse '{kv}' as key=value"
                )
        setattr(namespace, self.dest, my_dict)


# --- Argument Builder Functions ---


def add_core_args(parser):
    core_subparsers = parser.add_subparsers(dest="core_command", required=True)

    # Convert
    conv = core_subparsers.add_parser("convert", help="Convert image formats")
    conv.add_argument(
        "-i", "--input", nargs="+", required=True, help="Input file(s) or directory"
    )
    conv.add_argument("-o", "--output", help="Output directory or file")
    conv.add_argument(
        "-f",
        "--format",
        default="png",
        choices=SUPPORTED_IMG_FORMATS,
        help="Target format",
    )
    conv.add_argument(
        "-q", "--quality", type=int, default=95, help="JPEG/WebP quality (0-100)"
    )
    conv.add_argument("-r", "--recursive", action="store_true", help="Recursive search")

    # Merge
    merge = core_subparsers.add_parser("merge", help="Merge multiple images")
    merge.add_argument("-i", "--input", nargs="+", required=True, help="Input images")
    merge.add_argument("-o", "--output", required=True, help="Output path")
    merge.add_argument(
        "-d",
        "--direction",
        default="horizontal",
        choices=["horizontal", "vertical", "grid"],
        help="Merge direction",
    )
    merge.add_argument(
        "-s", "--spacing", type=int, default=0, help="Spacing between images"
    )
    merge.add_argument(
        "--grid_size", nargs=2, type=int, help="Grid dimensions (rows cols)"
    )

    return parser


def add_web_args(parser):
    web_subparsers = parser.add_subparsers(dest="web_command", required=True)

    crawl = web_subparsers.add_parser("crawl", help="Crawl images from web")
    crawl.add_argument("-q", "--query", required=True, help="Search query or URL")
    crawl.add_argument(
        "-l", "--limit", type=int, default=10, help="Max images to download"
    )
    crawl.add_argument("-o", "--output", default="./downloads", help="Output directory")

    return parser


def add_database_args(parser):
    db_subparsers = parser.add_subparsers(dest="db_command", required=True)

    search = db_subparsers.add_parser("search", help="Search in image database")
    search.add_argument("-q", "--query", required=True, help="Search query")
    search.add_argument(
        "-n", "--limit", dest="limit", type=int, default=50, help="Max results"
    )

    return parser


def add_model_args(parser):
    model_subparsers = parser.add_subparsers(dest="model_command", required=True)

    gen = model_subparsers.add_parser(
        "generate", help="Generate images using ML models"
    )
    gen.add_argument("-p", "--prompt", required=True, help="Generation prompt")
    gen.add_argument("-o", "--output", required=True, help="Output path")
    gen.add_argument("--model", default="stable-diffusion", help="Model name")

    return parser


def add_gui_args(parser):
    parser.add_argument(
        "--app_style",
        action=LowercaseAction,
        default="fusion",
        choices=APP_STYLES,
        help="GUI Style",
    )
    parser.add_argument(
        "--no_dropdown", action="store_true", help="Disable dropdown menu"
    )
    return parser


def get_main_parser():
    parser = ConfigsParser(
        description="Image-Toolkit CLI", formatter_class=argparse.RawTextHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_core_args(subparsers.add_parser("core", help="Core image operations"))
    add_web_args(subparsers.add_parser("web", help="Web-based operations"))
    add_database_args(subparsers.add_parser("database", help="Database operations"))
    add_model_args(subparsers.add_parser("model", help="ML model operations"))
    add_gui_args(subparsers.add_parser("gui", help="Launch GUI"))
    subparsers.add_parser("slideshow", help="Start slideshow daemon")

    return parser


def validate_core_args(opts):
    if opts.get("core_command") == "merge":
        if opts.get("direction") == "grid" and not opts.get("grid_size"):
            raise argparse.ArgumentError(
                None, "Merge mode 'grid' requires --grid_size R C"
            )
    return opts


def parse_params():
    parser = get_main_parser()
    try:
        command, opts = parser.parse_process_args()

        # Simple validation
        if command == "core":
            opts = validate_core_args(opts)

        return command, opts
    except Exception as e:
        parser.error_message(f"Error: {e}")
