import os
import sys
import warnings

from backend.src.app import launch_app
from gui.src.windows.settings.file_dialog_patch import apply_patch

os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "")

# Apply the patch to add the favorites side bar to the file dialogs
apply_patch()

# Suppress RequestsDependencyWarning: urllib3/chardet version mismatch
# This can happen when transitive dependencies (like comfyui-manager) pull in
# newer versions of chardet than 'requests' 2.32.x expects.
warnings.filterwarnings(
    "ignore", message=".*urllib3.*doesn't match a supported version!.*"
)

# Ensure that the repo root directory is on the path if needed. This file
# lives in gui/, so the repo root is one level up from here.
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)
# Register ASP's collision-proof aliases and CSG's ordinary,
# independently installable package roots.
from git.scripts._submodule_bootstrap import register_submodule_packages  # noqa: E402

register_submodule_packages(repo_root)

# Qt Multimedia backend pinning (#374): PySide6's bundled Qt ships only the
# FFmpeg backend, but a machine-wide QT_MEDIA_BACKEND=gstreamer (left over
# from the #373 KDE-wallpaper investigation in /etc/environment) makes every
# QMediaPlayer fail to initialize -> Extractor tab video player black. Pin
# the backend before any QtMultimedia object can be constructed.
from backend.src.qt_runtime_env import pin_qt_media_backend  # noqa: E402

pin_qt_media_backend()


if __name__ == "__main__":
    launch_app({"no_dropdown": False, "enable_manager": True})
