import os
import sys
import warnings

os.environ.setdefault("QT_FFMPEG_DECODING_HW_DEVICE_TYPES", "cuda")

import contextlib
import ctypes

with contextlib.suppress(OSError):
    ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libpulse.so.0")
with contextlib.suppress(OSError):
    ctypes.CDLL("/usr/lib/x86_64-linux-gnu/libfontconfig.so.1")

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)

from git.scripts._submodule_bootstrap import register_submodule_packages
register_submodule_packages(repo_root)

from backend.src.qt_runtime_env import pin_qt_media_backend
pin_qt_media_backend()

from backend.controllers.backend_dispatch import dispatch_command
from backend.controllers.cli.arg_parser import parse_params
from backend.src.app import launch_app, log_uncaught_exceptions
from gui.src.windows.settings.file_dialog_patch import apply_patch
apply_patch()

warnings.filterwarnings("ignore", message=".*urllib3.*doesn't match a supported version!.*")

# --- PROBE: dump Python stack when a cross-thread QObject warning fires ---
import threading
from PySide6.QtCore import qInstallMessageHandler, QtMsgType

def _probe_handler(mode, ctx, msg):
    import traceback
    if "another thread" in msg or "killTimer" in msg or "Socket notifier" in msg:
        print("\n[PROBE] QT-WARNING: " + msg, flush=True)
        print("[PROBE] thread=" + threading.current_thread().name + " ident=" + str(threading.get_ident()), flush=True)
        traceback.print_stack(limit=30)
        print("[PROBE] END-STACK\n", flush=True)
    else:
        print("[QT] " + msg, flush=True)

qInstallMessageHandler(_probe_handler)
# -------------------------------------------------------------------------

# --- PROBE: isolation patches (KT_PATCH=media|ffmpeg|both|none) ---
import os as _os
_kt_patch = _os.environ.get("KT_PATCH", "none")
if _kt_patch in ("media", "both"):
    from gui.src.elements.core.extractor_tab import _view_controls as _vc
    print(f"[PROBE] PATCH: noop update_playback_speed ({_kt_patch})", flush=True)
    _vc._ViewControlsMixin.update_playback_speed = lambda self, text: None
if _kt_patch in ("ffmpeg", "both"):
    from gui.src.helpers.video.video_thumbnailer import VideoThumbnailer
    print(f"[PROBE] PATCH: noop VideoThumbnailer.generate ({_kt_patch})", flush=True)
    VideoThumbnailer.generate = lambda self, *a, **k: None
print(f"[PROBE] KT_PATCH={_kt_patch}", flush=True)

if _os.environ.get("KT_TRACE_MEDIA", "") == "1":
    from PySide6.QtMultimedia import QAudioOutput as _QAO, QMediaPlayer as _QMP
    _orig_qao_init = _QAO.__init__
    _orig_qmp_init = _QMP.__init__
    def _traced_qao(self, *a, **k):
        import traceback as _tb, threading as _th
        print(f"[PROBE] QAudioOutput() constructed on {_th.current_thread().name} tid={_th.get_ident()}", flush=True)
        _tb.print_stack(limit=25)
        return _orig_qao_init(self, *a, **k)
    def _traced_qmp(self, *a, **k):
        import traceback as _tb, threading as _th
        print(f"[PROBE] QMediaPlayer() constructed on {_th.current_thread().name} tid={_th.get_ident()}", flush=True)
        _tb.print_stack(limit=25)
        return _orig_qmp_init(self, *a, **k)
    _QAO.__init__ = _traced_qao
    _QMP.__init__ = _traced_qmp
    print("[PROBE] media constructor tracing enabled", flush=True)

if _os.environ.get("KT_TRACE_TABS", "") == "1":
    from gui.src.elements.core.extractor_tab import _video_session_history as _vsh
    _orig_tab_changed = _vsh._VideoSessionHistoryMixin._on_active_video_tab_changed
    def _traced_tab_changed(self, index):
        print(f"[PROBE] TAB_CHANGED index={index} path={self.active_videos_tabbar.tabData(index)!r} video_path={getattr(self,'video_path',None)!r} switching={getattr(self,'_is_switching_tabs',None)} pending={getattr(self,'_media_load_pending',None)}", flush=True)
        return _orig_tab_changed(self, index)
    _vsh._VideoSessionHistoryMixin._on_active_video_tab_changed = _traced_tab_changed
    _orig_load_media = _vsh._VideoSessionHistoryMixin.load_media
    def _traced_load_media(self, file_path, force=False, defer_player=False):
        import traceback as _tb
        print(f"[PROBE] LOAD_MEDIA path={file_path!r} force={force} defer={defer_player} video_path={getattr(self,'video_path',None)!r} switching={getattr(self,'_is_switching_tabs',None)}", flush=True)
        return _orig_load_media(self, file_path, force=force, defer_player=defer_player)
    _vsh._VideoSessionHistoryMixin.load_media = _traced_load_media
    print("[PROBE] tab tracing enabled", flush=True)

if _os.environ.get("KT_ISO_AUDIO", "") == "1":
    from PySide6.QtCore import QTimer as _QTimer
    from PySide6.QtMultimedia import QAudioOutput as _QAO2
    def _iso_audio():
        import threading as _th
        print(f"[PROBE] ISO-AUDIO constructing QAudioOutput at t=5s on {_th.current_thread().name}", flush=True)
        ao = _QAO2()
        print(f"[PROBE] ISO-AUDIO QAudioOutput constructed OK: {ao}", flush=True)
    def _arm_iso(app):
        _QTimer.singleShot(5000, _iso_audio)
        print("[PROBE] ISO-AUDIO armed (construct QAudioOutput after 5s)", flush=True)
    from PySide6.QtWidgets import QApplication as _QApp
    _orig_app_init = _QApp.__init__
    def _traced_app_init(self, *a, **k):
        _r = _orig_app_init(self, *a, **k)
        _arm_iso(self)
        return _r
    _QApp.__init__ = _traced_app_init
    print("[PROBE] ISO-AUDIO will arm on QApplication creation", flush=True)
# -------------------------------------------------------------------------

if __name__ == "__main__":
    sys.excepthook = log_uncaught_exceptions
    if len(sys.argv) > 1:
        if sys.argv[1].startswith("-") and sys.argv[1] not in ["-h", "--help"]:
            sys.argv.insert(1, "gui")
        command, opts = parse_params()
        if command == "gui":
            sys.exit(launch_app(opts))
        else:
            assert command is not None
            dispatch_command(command, opts)
    else:
        sys.exit(launch_app({"no_dropdown": False, "enable_manager": False}))
