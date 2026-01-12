import os
import sys

from backend.src.app import launch_app, log_uncaught_exceptions
from backend.src.utils.arg_parser import parse_params
from backend.src.utils.dispatcher import dispatch_command

# Ensure that your root directory is on the path if needed
sys.path.insert(0, os.path.dirname(__file__))


if __name__ == "__main__":
    sys.excepthook = log_uncaught_exceptions

    # Check if CLI arguments are provided
    if len(sys.argv) > 1:
        command, opts = parse_params()
        if command == "gui":
            launch_app(opts)
        else:
            dispatch_command(command, opts)
    else:
        # Default to GUI
        launch_app({"no_dropdown": False})
