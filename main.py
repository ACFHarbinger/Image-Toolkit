import os
import sys
import warnings

from backend.src.app import launch_app, log_uncaught_exceptions
from backend.src.utils.arg_parser import parse_params
from backend.src.utils.dispatcher import dispatch_command

# Suppress RequestsDependencyWarning: urllib3/chardet version mismatch
# This can happen when transitive dependencies (like comfyui-manager) pull in
# newer versions of chardet than 'requests' 2.32.x expects.
warnings.filterwarnings(
    "ignore", message=".*urllib3.*doesn't match a supported version!.*"
)

# Ensure that your root directory is on the path if needed
sys.path.insert(0, os.path.dirname(__file__))


if __name__ == "__main__":
    sys.excepthook = log_uncaught_exceptions

    # Check if CLI arguments are provided
    if len(sys.argv) > 1:
        # If the first argument is a flag, default to 'gui' command
        if sys.argv[1].startswith("-") and sys.argv[1] not in ["-h", "--help"]:
            sys.argv.insert(1, "gui")

        command, opts = parse_params()
        if command == "gui":
            sys.exit(launch_app(opts))
        else:
            dispatch_command(command, opts)
    else:
        # Default to GUI
        sys.exit(launch_app({"no_dropdown": False, "enable_manager": False}))
