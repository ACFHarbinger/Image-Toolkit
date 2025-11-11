import os
import sys

from app.src import launch_app

# Ensure that your root directory is on the path if needed
sys.path.insert(0, os.path.dirname(__file__))


if __name__ == "__main__":
    launch_app({'no_dropdown': False})