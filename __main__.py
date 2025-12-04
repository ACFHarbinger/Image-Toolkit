import os
import sys

from backend.src.app import launch_app
from backend.src.utils.print import HiddenPrints

# Ensure that your root directory is on the path if needed
sys.path.insert(0, os.path.dirname(__file__))


if __name__ == "__main__":
    with HiddenPrints():
        launch_app({"no_dropdown": False})
