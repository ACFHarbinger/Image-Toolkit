import os
import sys
import warnings

# Qt Multimedia's FFmpeg backend lazily loads VA-API hardware video decode
# libraries (e.g. iHD_drv_video.so) on first video playback/probe. Loading
# those native libs alongside JPype's JVM triggers the same libstdc++ RTTI
# symbol-conflict SIGSEGV documented for QWebEngineView/Chromium. Restrict
# decoding to "cuda" (this box's NVIDIA GPU) so vaapi is never the *selected*
# decode device.
#
# Deliberately NOT an empty/"," value (Qt's documented syntax for "disable hw
# decode entirely"): empirically that value made AV1 playback *reliably*
# fail ("Failed to get pixel format" / blank frame on effectively every
# load), while both "no override at all" and "cuda" decoded AV1 correctly
# across repeated runs. The raw hw-context enumeration log line
# ("Checking HW context: vaapi ... Using above hw context.") still appears
# with every value tried here, including "cuda" -- that enumeration step
# seems unavoidable in this Qt build -- but per-codec device *selection*
# does respect this list, which is what actually matters for both the
# original vaapi/JVM crash risk and today's AV1 bug.
os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "cuda")

# `import base` links the pixi env's OpenCV videoio, whose FFmpeg
# (libavdevice) drags in the pixi build of libpulse.so.0 as a transitive
# dependency. Once that copy is in the process, Qt Multimedia's later
# dlopen("libpulse.so.0") is deduplicated by SONAME onto the pixi build
# instead of the system one Qt/PipeWire were tested against — the same
# mismatched-libpulse failure documented for the old base.so RPATH bug
# ("QSocketNotifier: Socket notifiers cannot be enabled or disabled from
# another thread" → SIGSEGV in libQt6Core, or a frozen event loop spamming
# "QSocketNotifier: Invalid socket"). Preloading the system copy first
# makes every later consumer — pixi FFmpeg included — bind to it instead.
# Must run before any import that pulls in `base`/cv2/Qt.
import contextlib
import ctypes

with contextlib.suppress(OSError):
    ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libpulse.so.0")

from backend.src.app import launch_app, log_uncaught_exceptions
from backend.src.utils.io.arg_parser import parse_params
from backend.src.utils.io.dispatcher import dispatch_command
from gui.src.windows.settings.file_dialog_patch import apply_patch

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
