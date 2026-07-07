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

# Ensure that your root directory is on the path if needed
sys.path.insert(0, os.path.dirname(__file__))


if __name__ == "__main__":
    launch_app({"no_dropdown": False, "enable_manager": True})
