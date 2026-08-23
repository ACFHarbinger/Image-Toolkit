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

# Same SONAME-dedup hazard as libpulse above, this time with libfontconfig:
# `import base` -> pixi OpenCV videoio -> (GTK/Pango font stack in that
# build's transitive deps) loads the pixi build of libfontconfig.so.1 into
# the process first. Once loaded, Qt's later font lookups dedup onto that
# copy by SONAME instead of the system one Qt was built/tested against —
# and the pixi build's parser chokes on this system's on-disk
# ~/.cache/fontconfig/*.cache-11 files (a different cache format/version),
# crashing with SIGSEGV in FcCharSetFindLeafForward during MainWindow's
# first font lookup. Preloading the system copy first makes every later
# consumer, pixi OpenCV included, bind to it instead.
with contextlib.suppress(OSError):
    ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libfontconfig.so.1")

# Ensure that the repo root directory is on the path if needed. This file
# lives in backend/, so the repo root is one level up from here.
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)
# ASP and Manga Colorization & Animation live in their own submodules;
# see git/scripts/_submodule_bootstrap.py for why this isn't a plain
# sys.path.insert.
# Must run before any backend/gui import below -- gui.src.windows.settings.
# app_config imports asp_backend at module load time.
from git.scripts._submodule_bootstrap import register_submodule_packages  # noqa: E402

register_submodule_packages(repo_root)

# Qt Multimedia backend pinning (#374): PySide6's bundled Qt ships only the
# FFmpeg backend, but a machine-wide QT_MEDIA_BACKEND=gstreamer (left over
# from the #373 KDE-wallpaper investigation in /etc/environment) makes every
# QMediaPlayer fail to initialize -> Extractor tab video player black. Pin
# the backend before any QtMultimedia object can be constructed.
from backend.src.qt_runtime_env import pin_qt_media_backend  # noqa: E402

pin_qt_media_backend()

from gui.src.windows.settings.file_dialog_patch import apply_patch  # noqa: E402

from backend.controllers.backend_dispatch import dispatch_command  # noqa: E402
from backend.controllers.cli.arg_parser import parse_params  # noqa: E402
from backend.src.app import launch_app, log_uncaught_exceptions  # noqa: E402

# Apply the patch to add the favorites side bar to the file dialogs
apply_patch()

# Suppress RequestsDependencyWarning: urllib3/chardet version mismatch
# This can happen when transitive dependencies (like comfyui-manager) pull in
# newer versions of chardet than 'requests' 2.32.x expects.
warnings.filterwarnings(
    "ignore", message=".*urllib3.*doesn't match a supported version!.*"
)


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
            assert command is not None
            dispatch_command(command, opts)
    else:
        # Default to GUI
        sys.exit(launch_app({"no_dropdown": False, "enable_manager": False}))
