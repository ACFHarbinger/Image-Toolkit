import sys
import argparse

from typing import Iterable
from src.utils.definitions import (
    APP_STYLES,
    SUPPORTED_IMG_FORMATS,
    WC_BROWSERS,
)


class ConfigsParser(argparse.ArgumentParser):
    """
    Custom ArgumentParser to handle string-based nargs correctly.
    """

    def _str_to_nargs(self, nargs):
        if isinstance(nargs, Iterable) and len(nargs) == 1:
            return nargs[0].split() if isinstance(nargs[0], str) else nargs
        else:
            return nargs

    def _process_args(self, namespace):
        for action in self._actions:
            if action.nargs is not None:
                if action.dest == "help":
                    continue

                # Check if the argument has nargs and process it
                value = getattr(namespace, action.dest)
                if value is not None:
                    transformed_value = self._str_to_nargs(value)
                    setattr(namespace, action.dest, transformed_value)

    def parse_command(self, args=None):
        if args is None:
            args = sys.argv[1:]

        namespace = super().parse_args(args)
        return getattr(namespace, "command", None)

    def parse_process_args(self, args=None, command=None):
        if args is None:
            args = sys.argv[1:]

        # Get all actions to iterate over: main actions + current subparser actions
        actions_to_check = list(self._actions)

        # Attempt to find the actions of the specific subparser command
        command_name = None
        if args and not args[0].startswith("-"):
            command_name = args[0]

        if command_name:
            # Find the SubParsersAction to get the sub-parser object
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
                # Add subparser actions to the list to be checked
                actions_to_check.extend(sub_parser._actions)
                
                # Check for nested subparsers (e.g., core -> merge)
                if len(args) > 1 and not args[1].startswith("-"):
                    sub_command_name = args[1]
                    nested_subparsers_action = next(
                        (
                            a
                            for a in sub_parser._actions
                            if isinstance(a, argparse._SubParsersAction)
                        ),
                        None,
                    )
                    if nested_subparsers_action and sub_command_name in nested_subparsers_action.choices:
                        nested_sub_parser = nested_subparsers_action.choices[sub_command_name]
                        actions_to_check.extend(nested_sub_parser._actions)

        for action in actions_to_check:
            if action.dest == "help":
                continue

            # Split strings with whitespace for nargs
            if action.nargs is not None and action.type is not None:
                opts = action.option_strings
                idx = next((i for i, x in enumerate(args) if x in opts), None)
                if idx is not None and (idx + 1) < len(args):
                    arg_val = args[idx + 1]
                    # Check if the argument value is a single string and not an option flag
                    if isinstance(arg_val, str) and not arg_val.startswith("-"):
                        arg_parts = arg_val.split()
                        if len(arg_parts) > 1:
                            args[idx + 1 : idx + 2] = arg_parts

        # This will parse known args and verify them
        subnamespace = super().parse_args(args)
        parsed_args_dict = vars(subnamespace)
        
        # Filter strictly
        filtered_args = {key: value for key, value in parsed_args_dict.items()}

        command = filtered_args.get("command")
        # For nested commands, we might want to capture the sub-command too
        # But 'command' dest is set at the top level. 
        # If we have sub-sub-commands, they will be in their respective dest attributes.
        
        return command, filtered_args

    def error_message(self, message, print_help=True):
        print(message, end=" ")
        if print_help:
            self.print_help()
        raise


class LowercaseAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if values is not None:
            values = str(values).lower()
        setattr(namespace, self.dest, values)


# ==============================================================================
#
# ARGUMENT BUILDER FUNCTIONS
#
# ==============================================================================


def add_core_args(parser):
    """
    Adds arguments for Core features (Convert, Merge, Wallpaper, Delete, Find).
    """
    core_subparsers = parser.add_subparsers(
        help="Core operations", dest="core_command", required=True
    )

    # --- Convert ---
    convert_parser = core_subparsers.add_parser("convert", help="Convert images")
    convert_parser.add_argument("--input", "-i", type=str, nargs="+", required=True, help="Input file(s) or directory")
    convert_parser.add_argument("--output", "-o", type=str, required=True, help="Output directory")
    convert_parser.add_argument("--format", "-f", type=str, required=True, choices=SUPPORTED_IMG_FORMATS, help="Target format")
    convert_parser.add_argument("--quality", "-q", type=int, default=100, help="Image quality (1-100)")
    convert_parser.add_argument("--recursive", "-r", action="store_true", help="Recursive search for directory inputs")

    # --- Merge ---
    merge_parser = core_subparsers.add_parser("merge", help="Merge images")
    merge_parser.add_argument("--input", "-i", type=str, nargs="+", required=True, help="Input images or directory")
    merge_parser.add_argument("--output", "-o", type=str, required=True, help="Output file path")
    merge_parser.add_argument(
        "--direction", "-d",
        type=str,
        required=True,
        choices=["horizontal", "vertical", "grid", "panorama", "stitch", "sequential", "gif"],
        help="Merge direction/mode",
    )
    merge_parser.add_argument("--spacing", "-s", type=int, default=0, help="Spacing between images")
    merge_parser.add_argument("--grid_size", "-g", type=int, nargs=2, metavar=("ROWS", "COLS"), help="Grid size (rows cols)")
    merge_parser.add_argument("--align", "-a", type=str, default="Default (Top/Center)", help="Alignment mode")

    # --- Wallpaper ---
    wallpaper_parser = core_subparsers.add_parser("wallpaper", help="Manage wallpapers")
    wallpaper_parser.add_argument("--set", "-s", type=str, required=True, help="Image path to set as wallpaper")
    wallpaper_parser.add_argument("--monitor", "-m", type=int, default=0, help="Monitor index (0 for all/default)")
    wallpaper_parser.add_argument("--style", type=str, help="Wallpaper style (e.g., 'Fill', 'Center')")

    # --- Delete ---
    delete_parser = core_subparsers.add_parser("delete", help="Delete files securely")
    delete_parser.add_argument("--target", "-t", type=str, nargs="+", required=True, help="Target file(s) or directory")
    delete_parser.add_argument("--secure", action="store_true", help="Use secure deletion (overwrite)")
    delete_parser.add_argument("--recursive", "-r", action="store_true", help="Recursive delete")
    
    # --- Find ---
    find_parser = core_subparsers.add_parser("find", help="Find duplicates or similar images")
    find_parser.add_argument("--directory", "-d", type=str, required=True, help="Directory to search")
    find_parser.add_argument("--mode", "-m", type=str, required=True, choices=["duplicates", "similarity"], help="Find mode")
    find_parser.add_argument("--threshold", type=float, default=0.9, help="Similarity threshold (0.0-1.0)")

    return parser


def add_web_args(parser):
    """
    Adds arguments for Web features (Crawl, Reverse Search, Drive Sync).
    """
    web_subparsers = parser.add_subparsers(
        help="Web operations", dest="web_command", required=True
    )

    # --- Crawl ---
    crawl_parser = web_subparsers.add_parser("crawl", help="Crawl images from web")
    crawl_parser.add_argument("--query", "-q", type=str, required=True, help="Search query")
    crawl_parser.add_argument("--limit", "-l", type=int, default=10, help="Max images to download")
    crawl_parser.add_argument("--browser", "-b", type=str, default="chrome", choices=WC_BROWSERS, help="Browser to use")
    crawl_parser.add_argument("--output", "-o", type=str, required=True, help="Download directory")
    crawl_parser.add_argument("--headless", action="store_true", help="Run in headless mode")

    # --- Reverse Search ---
    rev_parser = web_subparsers.add_parser("reverse_search", help="Reverse image search")
    rev_parser.add_argument("--image", "-i", type=str, required=True, help="Image file or URL")
    rev_parser.add_argument("--engine", "-e", type=str, default="google", choices=["google", "bing", "yandex", "tineye"], help="Search engine")

    # --- Cloud Sync ---
    sync_parser = web_subparsers.add_parser("cloud_sync", help="Sync with cloud storage")
    sync_parser.add_argument("--service", "-s", type=str, required=True, choices=["gdrive", "onedrive"], help="Cloud service")
    sync_parser.add_argument("--operation", "-op", type=str, required=True, choices=["upload", "download", "list"], help="Operation")
    sync_parser.add_argument("--local", "-l", type=str, help="Local path")
    sync_parser.add_argument("--remote", "-r", type=str, help="Remote path")

    return parser


def add_database_args(parser):
    """
    Adds arguments for Database features (Search, Scan).
    """
    db_subparsers = parser.add_subparsers(
        help="Database operations", dest="db_command", required=True
    )

    # --- Search ---
    search_parser = db_subparsers.add_parser("search", help="Search database")
    search_parser.add_argument("--query", "-q", type=str, help="Text query")
    search_parser.add_argument("--image", "-i", type=str, help="Image query (path)")
    search_parser.add_argument("--limit", "-n", type=int, default=20, help="Number of results")

    # --- Scan ---
    scan_parser = db_subparsers.add_parser("scan", help="Scan directory for metadata")
    scan_parser.add_argument("--directory", "-d", type=str, required=True, help="Directory to scan")
    scan_parser.add_argument("--recursive", "-r", action="store_true", help="Recursive scan")
    scan_parser.add_argument("--update", "-u", action="store_true", help="Update existing entries")

    return parser


def add_model_args(parser):
    """
    Adds arguments for Model features (Generate, Train).
    """
    model_subparsers = parser.add_subparsers(
        help="Model operations", dest="model_command", required=True
    )

    # --- Generate ---
    gen_parser = model_subparsers.add_parser("generate", help="Generate images")
    gen_parser.add_argument("--prompt", "-p", type=str, required=True, help="Text prompt")
    gen_parser.add_argument("--model", "-m", type=str, default="stable-diffusion", help="Model name")
    gen_parser.add_argument("--steps", type=int, default=50, help="Inference steps")
    gen_parser.add_argument("--output", "-o", type=str, required=True, help="Output path")

    # --- Train ---
    train_parser = model_subparsers.add_parser("train", help="Train model")
    train_parser.add_argument("--dataset", "-d", type=str, required=True, help="Path to dataset")
    train_parser.add_argument("--epochs", "-e", type=int, default=10, help="Number of epochs")
    train_parser.add_argument("--batch_size", "-b", type=int, default=32, help="Batch size")
    train_parser.add_argument("--learning_rate", "-lr", type=float, default=0.001, help="Learning rate")
    train_parser.add_argument("--output", "-o", type=str, required=True, help="Output directory for weights")

    return parser


def get_main_parser():
    """
    Builds the main parser with all sub-commands.
    """
    parser = ConfigsParser(
        description="Image-Toolkit Backend CLI",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    # --- App Style Global Arg ---
    parser.add_argument(
        "--app_style",
        type=str,
        default="fusion",
        choices=APP_STYLES,
        help="Application GUI style (if applicable)",
    )

    # --- Main Subparsers (Modules) ---
    subparsers = parser.add_subparsers(help="Module selection", dest="command", required=True)

    # 1. Core
    core_parser = subparsers.add_parser("core", help="Core utilities (Convert, Merge, etc.)")
    add_core_args(core_parser)

    # 2. Web
    web_parser = subparsers.add_parser("web", help="Web tools (Crawler, Cloud Sync)")
    add_web_args(web_parser)

    # 3. Database
    db_parser = subparsers.add_parser("database", help="Database interactions")
    add_database_args(db_parser)

    # 4. Model
    model_parser = subparsers.add_parser("model", help="AI Model operations")
    add_model_args(model_parser)

    return parser


def parse_params():
    """
    Parses arguments, determines the command, and performs necessary validation.
    Returns: (command, validated_opts)
    """
    parser = get_main_parser()

    try:
        command, opts = parser.parse_process_args()

        # Basic Validation Logic
        if command == "core":
            if opts.get("core_command") == "merge":
                if opts.get("direction") == "grid" and not opts.get("grid_size"):
                    parser.error("Grid direction requires --grid_size")
        
        elif command == "web":
            if opts.get("web_command") == "cloud_sync":
                if opts.get("operation") in ["upload", "download"] and not (opts.get("local") and opts.get("remote")):
                     parser.error("Upload/Download operations require --local and --remote paths")

        return command, opts

    except (argparse.ArgumentError, AssertionError) as e:
        parser.error_message(f"Error: {e}", print_help=True)
    except Exception as e:
        # Fallback for unexpected exceptions
        print(f"An unexpected error occurred: {e}")
        return None, None
