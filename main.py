import os
import sys

from backend.src.app import launch_app, log_uncaught_exceptions

# Ensure that your root directory is on the path if needed
sys.path.insert(0, os.path.dirname(__file__))


if __name__ == "__main__":
    sys.excepthook = log_uncaught_exceptions
    launch_app({"no_dropdown": False})
