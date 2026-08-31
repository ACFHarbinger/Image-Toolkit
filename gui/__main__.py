import os
import sys
import warnings

# ASP's `asp_backend` alias must be registered BEFORE any `backend.src.*`
# import — `backend.src.app` transitively pulls `windows.settings.app_config`,
# which does `from asp_backend.core.config import ...` at module load. In a
# PyInstaller bundle `__file__` is not a usable repo path, so resolve the root
# from `sys._MEIPASS` when frozen.
if getattr(sys, "frozen", False):
    repo_root = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from git.scripts._submodule_bootstrap import register_submodule_packages  # noqa: E402

register_submodule_packages(repo_root)

from backend.src.app import launch_app  # noqa: E402

from gui.src.windows.settings.file_dialog_patch import apply_patch  # noqa: E402

os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "")

# Apply the patch to add the favorites side bar to the file dialogs
apply_patch()

# Suppress RequestsDependencyWarning: urllib3/chardet version mismatch
# This can happen when transitive dependencies (like comfyui-manager) pull in
# newer versions of chardet than 'requests' 2.32.x expects.
warnings.filterwarnings(
    "ignore", message=".*urllib3.*doesn't match a supported version!.*"
)

# Qt Multimedia backend pinning (#374): PySide6's bundled Qt ships only the
# FFmpeg backend, but a machine-wide QT_MEDIA_BACKEND=gstreamer (left over
# from the #373 KDE-wallpaper investigation in /etc/environment) makes every
# QMediaPlayer fail to initialize -> Extractor tab video player black. Pin
# the backend before any QtMultimedia object can be constructed.
from backend.src.qt_runtime_env import pin_qt_media_backend  # noqa: E402

pin_qt_media_backend()


if __name__ == "__main__":
    launch_app({"no_dropdown": False, "enable_manager": True})
