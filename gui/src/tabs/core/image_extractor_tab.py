import os
import cv2
import time
import json
import copy
import subprocess

from pathlib import Path
from typing import Optional, List, Set, Tuple, Any, Dict
from PySide6.QtWidgets import (
    QLabel,
    QComboBox,
    QStyle,
    QSlider,
    QFileDialog,
    QGroupBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMenu,
    QGraphicsView,
    QGraphicsScene,
    QScrollArea,
    QGridLayout,
    QMessageBox,
    QPushButton,
    QApplication,
    QLineEdit,
    QProgressDialog,
    QSpinBox,
    QCheckBox,
    QProgressBar,
    QInputDialog,
    QDialog,
    QTabBar,
    QListWidget,
)
from PySide6.QtGui import QPixmap, QResizeEvent, QAction, QImage
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import (
    Qt,
    QUrl,
    Slot,
    QThreadPool,
    QPoint,
    QEvent,
    Signal,
    QRunnable,
    QObject,
)
from ...windows import ImagePreviewWindow
from ...classes import AbstractClassSingleGallery
from ...components import ClickableLabel, MarqueeScrollArea
from ...components.frame_selection_dialog import FrameSelectionDialog
from ...utils.sort_utils import natural_sort_key
from ...helpers import (
    VideoScannerWorker,
    GifCreationWorker,
    FrameExtractionWorker,
    VideoExtractionWorker,
)
from ...helpers.video.video_scan_worker import VideoThumbnailer
from backend.src.constants import (
    LOCAL_SOURCE_PATH,
    SUPPORTED_VIDEO_FORMATS,
    IMAGE_TOOLKIT_DIR,
)


def run_extraction_in_process(config: dict) -> dict:
    import os
    import subprocess
    import time
    import re
    from pathlib import Path

    def natural_sort_key(s):
        return [
            int(text) if text.isdigit() else text.lower()
            for text in re.split(r"(\d+)", s)
        ]

    t_type = config.get("type")
    video_path = config.get("video_path")
    start_ms = config.get("start_ms")
    end_ms = config.get("end_ms")
    output_dir = config.get("output_dir")
    target_resolution = config.get("target_resolution")
    cuts_ms = config.get("cuts_ms", [])
    frame_interval = config.get("frame_interval", 1)
    smart_extract = config.get("smart_extract", False)
    smart_method = config.get("smart_method", "")
    fps = config.get("fps", 24)
    mute_audio = config.get("mute_audio", False)
    use_ffmpeg = config.get("use_ffmpeg", True)
    speed = float(config.get("speed", "1.0"))

    def get_keep_regions(t_start: float, t_end: float):
        if not cuts_ms:
            return [(0.0, t_end - t_start)]
        sorted_cuts = sorted(
            [(max(t_start, c[0] / 1000.0), min(t_end, c[1] / 1000.0)) for c in cuts_ms]
        )
        merged_cuts = []
        for c in sorted_cuts:
            if c[0] >= c[1]:
                continue
            if not merged_cuts:
                merged_cuts.append(c)
            else:
                last = merged_cuts[-1]
                if c[0] <= last[1]:
                    merged_cuts[-1] = (last[0], max(last[1], c[1]))
                else:
                    merged_cuts.append(c)
        keep = []
        current = t_start
        for c_start, c_end in merged_cuts:
            if c_start > current:
                keep.append((current - t_start, c_start - t_start))
            current = max(current, c_end)
        if current < t_end:
            keep.append((current - t_start, t_end - t_start))
        return keep

    def get_video_fps(path):
        import cv2

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return 23.976
        f = cap.get(cv2.CAP_PROP_FPS)
        cap.release()
        return f if f > 0 else 23.976

    try:
        if t_type in ("range", "single"):
            video_name = Path(video_path).stem
            t_start = start_ms / 1000.0
            detected_fps = get_video_fps(video_path)

            if smart_extract:
                t_end = end_ms / 1000.0
                duration = t_end - t_start
                cmd = ["ffmpeg", "-y", "-ss", str(t_start)]
                if t_type == "range" and end_ms != -1:
                    cmd.extend(["-t", str(duration)])
                cmd.extend(["-i", video_path])

                filters = []
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    select_expr = "+".join(
                        [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                    )
                    filters.append(f"select='{select_expr}'")
                if frame_interval > 1:
                    filters.append(f"select='not(mod(n,{frame_interval}))'")
                if "mpdecimate" in smart_method:
                    filters.append("mpdecimate")
                elif "scene" in smart_method:
                    match = re.search(r"\((.*?)\)", smart_method)
                    val = match.group(1) if match else "0.4"
                    filters.append(f"select='gt(scene,{val})'")
                if target_resolution:
                    w, h = target_resolution
                    filters.append(f"scale={w}:{h}:flags=lanczos")
                if filters:
                    cmd.extend(["-vf", ",".join(filters)])
                if t_type == "single":
                    cmd.extend(["-vframes", "1"])
                cmd.extend(
                    [
                        "-sws_flags",
                        "spline+accurate_rnd+full_chroma_int",
                        "-pix_fmt",
                        "rgb48be",
                        "-vsync",
                        "vfr",
                        "-frame_pts",
                        "1",
                    ]
                )

                temp_id = int(time.time() * 1000) % 100000
                out_pattern = os.path.join(
                    output_dir, f"{video_name}_smart_tmp_{temp_id}_%08d.png"
                )
                cmd.append(out_pattern)

                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                prefix = f"{video_name}_smart_tmp_{temp_id}_"
                tmp_files = sorted(
                    [
                        f
                        for f in os.listdir(output_dir)
                        if f.startswith(prefix) and f.endswith(".png")
                    ],
                    key=natural_sort_key,
                )

                saved_files = []
                for f in tmp_files:
                    match = re.search(r"_(\d+)\.png$", f)
                    if not match:
                        continue
                    pts = int(match.group(1))
                    current_ms = start_ms + int(pts * 1000.0 / detected_fps)
                    new_name = f"{video_name}_smart_{current_ms}ms.png"
                    final_path = os.path.join(output_dir, new_name)
                    if os.path.exists(final_path):
                        final_path = os.path.join(
                            output_dir,
                            f"{video_name}_smart_{current_ms}ms_{temp_id}.png",
                        )
                    os.rename(os.path.join(output_dir, f), final_path)
                    saved_files.append(final_path)
                return {"status": "success", "saved_files": saved_files}
            else:
                cmd = ["ffmpeg", "-y", "-ss", str(t_start)]
                if t_type == "range" and end_ms != -1:
                    duration = (end_ms - start_ms) / 1000.0
                    cmd.extend(["-t", str(duration)])
                cmd.extend(["-i", video_path])

                filters = []
                if cuts_ms:
                    keep_regions = get_keep_regions(
                        t_start, (end_ms / 1000.0 if end_ms != -1 else t_start + 1)
                    )
                    if keep_regions:
                        select_expr = "+".join(
                            [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                        )
                        filters.append(f"select='{select_expr}'")
                if frame_interval > 1:
                    filters.append(f"select='not(mod(n,{frame_interval}))'")
                if target_resolution:
                    w, h = target_resolution
                    filters.append(f"scale={w}:{h}:flags=lanczos")
                if filters:
                    cmd.extend(["-vf", ",".join(filters)])
                if t_type == "single":
                    cmd.extend(["-vframes", "1"])
                cmd.extend(
                    [
                        "-sws_flags",
                        "spline+accurate_rnd+full_chroma_int",
                        "-vsync",
                        "vfr",
                        "-q:v",
                        "2",
                    ]
                )

                out_pattern = os.path.join(output_dir, f"{video_name}_tmp_%05d.png")
                cmd.append(out_pattern)

                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )

                tmp_files = sorted(
                    [
                        f
                        for f in os.listdir(output_dir)
                        if f.startswith(f"{video_name}_tmp_") and f.endswith(".png")
                    ],
                    key=natural_sort_key,
                )
                saved_files = []
                for i, f in enumerate(tmp_files):
                    current_ms = start_ms + int(
                        i * frame_interval * (1000.0 / detected_fps)
                    )
                    new_name = f"{video_name}_{current_ms}ms.png"
                    final_path = os.path.join(output_dir, new_name)
                    if os.path.exists(final_path):
                        final_path = os.path.join(
                            output_dir, f"{video_name}_{current_ms}ms_{i}.png"
                        )
                    os.rename(os.path.join(output_dir, f), final_path)
                    saved_files.append(final_path)
                return {"status": "success", "saved_files": saved_files}

        elif t_type == "gif":
            t_start = start_ms / 1000.0
            t_end = end_ms / 1000.0
            output_path = os.path.join(
                output_dir,
                f"{Path(video_path).stem}_{int(start_ms)}ms_{int(end_ms)}ms.gif",
            )

            if use_ffmpeg:
                duration = t_end - t_start
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(t_start),
                    "-t",
                    str(duration),
                    "-i",
                    video_path,
                ]

                filter_chain = []
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    select_expr = "+".join(
                        [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                    )
                    filter_chain.append(f"select='{select_expr}'")
                    filter_chain.append("setpts=N/FRAME_RATE/TB")
                filter_chain.append(f"fps={fps}")
                if target_resolution:
                    w, h = target_resolution
                    filter_chain.append(f"scale={w}:{h}:flags=lanczos")
                if speed != 1.0:
                    pts_mult = 1.0 / speed
                    filter_chain.append(f"setpts={pts_mult}*PTS")

                base_filters = ",".join(filter_chain)
                complex_filter = (
                    f"{base_filters},split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
                )
                cmd.extend(["-vf", complex_filter])
                cmd.append(output_path)

                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                return {"status": "success", "output_path": output_path}
            else:
                from moviepy.editor import VideoFileClip, concatenate_videoclips

                base_clip = VideoFileClip(video_path).subclip(t_start, t_end)
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    clips = []
                    for start_sec, end_sec in keep_regions:
                        if end_sec > start_sec:
                            clips.append(base_clip.subclip(start_sec, end_sec))
                    clip = concatenate_videoclips(clips) if clips else base_clip
                else:
                    clip = base_clip
                if target_resolution:
                    clip = clip.resize(newsize=target_resolution)
                if speed != 1.0:
                    clip = clip.speedx(speed)
                clip.write_gif(output_path, fps=fps, logger=None)
                clip.close()
                base_clip.close()
                return {"status": "success", "output_path": output_path}

        elif t_type == "video":
            t_start = start_ms / 1000.0
            t_end = end_ms / 1000.0
            output_path = os.path.join(
                output_dir,
                f"{Path(video_path).stem}_{int(start_ms)}ms_{int(end_ms)}ms.mp4",
            )

            if use_ffmpeg:
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    kept_duration = sum(r[1] - r[0] for r in keep_regions)
                    if kept_duration <= 0:
                        kept_duration = t_end - t_start
                else:
                    kept_duration = t_end - t_start
                duration = kept_duration / speed

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    str(t_start),
                    "-t",
                    str(t_end - t_start),
                    "-i",
                    video_path,
                ]
                filters = []
                if cuts_ms and keep_regions:
                    select_expr = "+".join(
                        [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                    )
                    filters.append(f"select='{select_expr}'")
                    filters.append("setpts=N/FRAME_RATE/TB")
                if target_resolution:
                    w, h = target_resolution
                    filters.append(f"scale={w}:{h}")
                if speed != 1.0:
                    pts_mult = 1.0 / speed
                    filters.append(f"setpts={pts_mult}*PTS")
                if filters:
                    cmd.extend(["-vf", ",".join(filters)])

                cmd.extend(["-c:v", "libx264", "-movflags", "+faststart"])
                if mute_audio:
                    cmd.append("-an")
                else:
                    audio_filters = []
                    if cuts_ms and keep_regions:
                        aselect_expr = "+".join(
                            [f"between(t,{r[0]},{r[1]})" for r in keep_regions]
                        )
                        audio_filters.append(f"aselect='{aselect_expr}'")
                        audio_filters.append("asetpts=N/SR/TB")
                    if speed != 1.0:
                        s = speed
                        while s > 2.0:
                            audio_filters.append("atempo=2.0")
                            s /= 2.0
                        while s < 0.5:
                            audio_filters.append("atempo=0.5")
                            s /= 0.5
                        audio_filters.append(f"atempo={s}")
                    if audio_filters:
                        cmd.extend(["-af", ",".join(audio_filters)])
                    cmd.extend(["-c:a", "aac", "-b:a", "128k"])

                cmd.extend(["-t", str(duration), "-shortest", output_path])
                subprocess.run(
                    cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                return {"status": "success", "output_path": output_path}
            else:
                from moviepy.editor import VideoFileClip, concatenate_videoclips
                from moviepy.editor import AudioFileClip

                base_clip = VideoFileClip(video_path)
                original_audio_clip = None
                if mute_audio or base_clip.audio is None:
                    base_clip.audio = None
                    audio_codec = None
                else:
                    try:
                        original_audio_clip = AudioFileClip(video_path)
                        base_clip.audio = original_audio_clip
                    except:
                        pass
                    audio_codec = "aac"

                subclipped_base = base_clip.subclip(t_start, t_end)
                keep_regions = get_keep_regions(t_start, t_end)
                if cuts_ms and keep_regions:
                    clips = []
                    for start_sec, end_sec in keep_regions:
                        if end_sec > start_sec:
                            clips.append(subclipped_base.subclip(start_sec, end_sec))
                    clip = concatenate_videoclips(clips) if clips else subclipped_base
                else:
                    clip = subclipped_base

                if target_resolution:
                    clip = clip.resize(newsize=target_resolution)
                if speed != 1.0:
                    clip = clip.speedx(speed)
                if clip.duration is not None and clip.audio is not None:
                    clip.audio = clip.audio.set_duration(clip.duration)

                ffmpeg_params = ["-movflags", "faststart"]
                if audio_codec is not None:
                    ffmpeg_params.extend(["-b:a", "128k"])

                temp_audio_path = f"temp-audio-{int(time.time() * 1000)}.m4a"
                clip.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec=audio_codec,
                    temp_audiofile=temp_audio_path,
                    remove_temp=True,
                    ffmpeg_params=ffmpeg_params,
                    verbose=False,
                    logger=None,
                )
                if original_audio_clip:
                    original_audio_clip.close()
                clip.close()
                base_clip.close()
                if os.path.exists(temp_audio_path):
                    try:
                        os.remove(temp_audio_path)
                    except OSError:
                        pass
                return {"status": "success", "output_path": output_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}


class QueueWorkerSignals(QObject):
    started = Signal()
    progress = Signal(int)
    item_completed = Signal(int, dict)
    finished = Signal(list)
    error = Signal(str)


class QueueExecutionWorker(QRunnable):
    def __init__(self, queue_items: list, parallel: bool = False):
        super().__init__()
        self.queue_items = queue_items
        self.parallel = parallel
        self.signals = QueueWorkerSignals()
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        self.signals.started.emit()
        results = []

        if self.parallel:
            from multiprocessing import Pool
            import multiprocessing

            num_cores = min(multiprocessing.cpu_count(), len(self.queue_items))
            if num_cores < 1:
                num_cores = 1

            self.signals.progress.emit(10)

            try:
                with Pool(processes=num_cores) as pool:
                    async_results = [
                        pool.apply_async(run_extraction_in_process, (item,))
                        for item in self.queue_items
                    ]

                    completed = 0
                    total = len(self.queue_items)

                    while completed < total:
                        if self._is_cancelled:
                            pool.terminate()
                            self.signals.error.emit(
                                "Parallel queue extraction cancelled by user."
                            )
                            return

                        new_completed = 0
                        for r in async_results:
                            if r.ready():
                                new_completed += 1

                        if new_completed > completed:
                            completed = new_completed
                            progress_val = int(10 + (completed / total) * 90)
                            self.signals.progress.emit(min(99, progress_val))

                        time.sleep(0.5)

                    for i, r in enumerate(async_results):
                        res = r.get()
                        results.append(res)
                        self.signals.item_completed.emit(i, res)
            except Exception as e:
                self.signals.error.emit(f"Parallel processing error: {e}")
                return
        else:
            total = len(self.queue_items)
            for i, item in enumerate(self.queue_items):
                if self._is_cancelled:
                    self.signals.error.emit(
                        "Sequential queue extraction cancelled by user."
                    )
                    return

                self.signals.progress.emit(int((i / total) * 100))
                res = run_extraction_in_process(item)
                results.append(res)
                self.signals.item_completed.emit(i, res)

        self.signals.progress.emit(100)
        self.signals.finished.emit(results)


class CutLabel(QLabel):
    """A small interactive label for individual cuts that supports right-click."""

    right_clicked = Signal(QPoint, int)  # global_pos, index

    def __init__(self, text, index, parent=None):
        super().__init__(text, parent)
        self.index = index
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "color: #00BCD4; font-weight: bold; padding: 2px 6px; "
            "border: 1px solid #4f545c; border-radius: 4px; background-color: #1e1f22;"
        )
        self.setToolTip("Right-click to delete this cut")

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.right_clicked.emit(event.globalPos(), self.index)
        super().mousePressEvent(event)


class TagLabel(QLabel):
    """A small interactive label for individual tags that supports clicking to jump and right-click to edit/delete."""

    clicked = Signal(int)  # position_ms
    double_clicked = Signal(int)  # position_ms
    right_clicked = Signal(QPoint, int)  # global_pos, index

    def __init__(self, text, ms, index, parent=None):
        super().__init__(text, parent)
        self.ms = ms
        self.index = index
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "color: #FFC107; font-weight: bold; padding: 2px 6px; "
            "border: 1px solid #4f545c; border-radius: 4px; background-color: #1e1f22;"
        )
        self.setToolTip(f"Jump to {text}\nRight-click to edit/delete")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.ms)
        elif event.button() == Qt.RightButton:
            self.right_clicked.emit(event.globalPos(), self.index)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_clicked.emit(self.ms)
        super().mouseDoubleClickEvent(event)


class ImageExtractorTab(AbstractClassSingleGallery):
    # Signals for QML
    qml_source_path_changed = Signal(str)
    qml_extraction_status = Signal(str)

    def __init__(self):
        super().__init__()
        self.video_path: Optional[str] = None
        self.current_extracted_paths: List[str] = []
        self.selected_paths: Set[str] = set()
        self.duration_ms = 0
        self.extractor_worker: Optional[FrameExtractionWorker] = None
        self.vid_scanner_worker: Optional[VideoScannerWorker] = None
        self.open_preview_windows: List[QWidget] = []

        # Reference for the progress dialog and active workers
        self.progress_dialog: Optional[QProgressDialog] = None
        self.active_extraction_worker: Optional[Any] = None
        self._active_metadata: Optional[dict] = None
        self.wheel_seek_ms = 100
        self.extraction_queue_enabled = False
        self.extraction_queue: List[dict] = []
        self.active_queue_worker: Optional[QueueExecutionWorker] = None
        self.time_display_format = "m:s:ms"

        self.use_internal_player = True
        self.video_view: Optional[QGraphicsView] = None
        self.player_container: Optional[QWidget] = None
        self.lbl_current_time: Optional[QLabel] = None
        self.edit_current_time: Optional[QLineEdit] = None

        # Map to track source widgets for alphabetical updates
        self.source_path_to_widget: Dict[str, QWidget] = {}
        self.active_videos_config: Dict[str, dict] = {}
        self._is_switching_tabs = False

        # Defined resolutions corresponding to the Combo Box items
        self.available_resolutions = [
            (1280, 720),
            (1920, 1080),
            (2560, 1440),
            (3840, 2160),
        ]

        # Mapping for Extraction Resolutions
        self.extraction_res_map = {
            "Native": "native",
            "Player": None,
            "480p": (854, 480),
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "1440p": (2560, 1440),
            "4K": (3840, 2160),
        }

        self.extraction_dir = Path(LOCAL_SOURCE_PATH) / "Frames"
        self.extraction_dir.mkdir(parents=True, exist_ok=True)
        self.last_browsed_extraction_dir = str(self.extraction_dir)

        # --- Extraction History ---
        self.recent_extractions_limit = 10
        self.recent_runs: List[Dict[str, Any]] = []
        self.extraction_metadata: Dict[str, Any] = {}
        self._extracted_stems_cache: Set[str] = set()
        self._recent_combo_connected = False
        self._load_extraction_history()

        # --- Initialize Pagination ---
        self.pagination_widget = self.create_pagination_controls()

        # --- UI Setup ---
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        # Main Tab Scroll Area
        self.tab_scroll_area = QScrollArea()
        self.tab_scroll_area.setWidgetResizable(True)
        self.tab_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root_layout.addWidget(self.tab_scroll_area)

        self.content_widget = QWidget()
        self.main_layout = QVBoxLayout(self.content_widget)
        self.tab_scroll_area.setWidget(self.content_widget)

        # 1. Directory Selection Section (Source Directory)
        dir_select_group = QGroupBox("Source Directory")
        dir_layout = QHBoxLayout(dir_select_group)

        self.line_edit_dir = QLineEdit()
        self.line_edit_dir.setPlaceholderText(
            "Select a folder containing videos or GIFs..."
        )
        self.line_edit_dir.returnPressed.connect(
            lambda: self.scan_directory(self.line_edit_dir.text())
        )

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self.browse_directory)

        dir_layout.addWidget(self.line_edit_dir)
        dir_layout.addWidget(self.btn_browse)

        self.main_layout.addWidget(dir_select_group)

        # 1.5. Extraction Target Directory Section
        dir_set_group = QGroupBox("Output Directory")
        dir_set_layout = QHBoxLayout(dir_set_group)

        self.line_edit_extract_dir = QLineEdit(str(self.extraction_dir))
        self.line_edit_extract_dir.setReadOnly(True)

        self.btn_browse_extract = QPushButton("Change...")
        self.btn_browse_extract.clicked.connect(self.browse_extraction_directory)

        dir_set_layout.addWidget(self.line_edit_extract_dir)
        dir_set_layout.addWidget(self.btn_browse_extract)

        self.main_layout.addWidget(dir_set_group)

        # 2. Source Gallery
        self.source_group = QGroupBox("Available Media")
        source_layout = QVBoxLayout(self.source_group)

        self.source_scroll = MarqueeScrollArea()
        self.source_scroll.setWidgetResizable(True)
        self.source_scroll.setMinimumHeight(300)
        self.source_scroll.setMaximumHeight(300)
        self.source_scroll.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )

        self.source_container = QWidget()
        self.source_container.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.source_grid = QGridLayout(self.source_container)
        self.source_grid.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop
        )
        self.source_scroll.setWidget(self.source_container)

        source_layout.addWidget(self.source_scroll)
        self.main_layout.addWidget(self.source_group)

        # 3. Video Player Section
        self.video_container_widget = QWidget()
        video_container_layout = QVBoxLayout(self.video_container_widget)

        self.active_videos_tabbar = QTabBar()
        self.active_videos_tabbar.setTabsClosable(True)
        self.active_videos_tabbar.currentChanged.connect(
            self._on_active_video_tab_changed
        )
        self.active_videos_tabbar.tabCloseRequested.connect(
            self._on_active_video_tab_closed
        )
        self.active_videos_tabbar.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.active_videos_tabbar.customContextMenuRequested.connect(
            self._show_tab_context_menu
        )
        self.active_videos_tabbar.setStyleSheet(
            "QTabBar::tab { background: #2c2f33; color: #9b59b6; padding: 8px 16px; border: 1px solid #4f545c; border-top-left-radius: 4px; border-top-right-radius: 4px; }"
            "QTabBar::tab:selected { background: #23272a; color: #00bcd4; border-bottom-color: #23272a; font-weight: bold; }"
            "QTabBar::close-button { image: url(close.png); }"
        )
        video_container_layout.addWidget(self.active_videos_tabbar)

        player_group = QGroupBox("Video Player")
        self.player_layout_container = QVBoxLayout(player_group)

        self.player_container = QWidget()
        self.player_container.setStyleSheet("background-color: #2b2d31;")
        self.player_inner_layout = QVBoxLayout(self.player_container)
        self.player_inner_layout.setContentsMargins(0, 0, 0, 0)

        self.video_item = QGraphicsVideoItem()
        self.graphics_scene = QGraphicsScene(self)
        self.graphics_scene.addItem(self.video_item)

        self.video_view = QGraphicsView(self.graphics_scene)
        self.video_view.setFixedSize(1920, 1080)
        self.video_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.video_view.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.video_view.setVisible(True)

        # Install event filters on the view AND its viewport for robust wheel capture
        self.video_view.installEventFilter(self)
        self.video_view.viewport().installEventFilter(self)
        self.video_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.video_view.customContextMenuRequested.connect(self.show_video_context_menu)

        self.player_inner_layout.addWidget(
            self.video_view, 1, Qt.AlignmentFlag.AlignCenter
        )

        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_item)

        # Controls Row 1 (Top)
        controls_top_layout = QHBoxLayout()
        controls_top_layout.setContentsMargins(10, 5, 10, 0)

        self.btn_toggle_mode = QPushButton("Switch to External Player")
        self.btn_toggle_mode.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
        )
        self.btn_toggle_mode.clicked.connect(self.toggle_player_mode)
        controls_top_layout.addWidget(self.btn_toggle_mode)

        controls_top_layout.addWidget(QLabel("Player Size:"))
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["720p", "1080p", "1440p", "4K"])
        self.combo_resolution.setCurrentIndex(0)
        self.combo_resolution.currentIndexChanged.connect(
            lambda: self.change_resolution(self.combo_resolution.currentIndex())
        )
        controls_top_layout.addWidget(self.combo_resolution)

        # --- NEW: Vertical Checkbox for Player ---
        self.check_player_vertical = QCheckBox("Vertical")
        self.check_player_vertical.setToolTip("Swap width/height for vertical displays")
        self.check_player_vertical.toggled.connect(
            lambda: self.change_resolution(self.combo_resolution.currentIndex())
        )
        controls_top_layout.addWidget(self.check_player_vertical)
        # ----------------------------------------

        controls_top_layout.addSpacing(20)
        controls_top_layout.addWidget(QLabel("Player Speed:"))
        self.combo_player_speed = QComboBox()
        self.combo_player_speed.addItems(["0.25x", "0.5x", "1x", "1.5x", "2x", "4x"])
        self.combo_player_speed.setCurrentText("1x")
        self.combo_player_speed.currentTextChanged.connect(self.update_playback_speed)
        controls_top_layout.addWidget(self.combo_player_speed)

        controls_top_layout.addStretch()
        self.player_inner_layout.addLayout(controls_top_layout)

        # Controls Row 2 (Bottom)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 0, 10, 10)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_play.setVisible(True)

        self.lbl_vol = QLabel("Vol:")
        self.lbl_vol.setVisible(True)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(60)
        self.volume_slider.valueChanged.connect(
            lambda v: self.audio_output.setVolume(v / 100.0)
        )
        self.volume_slider.setVisible(True)

        self.lbl_current_time = QLabel("00:00:000")
        self.lbl_current_time.setCursor(Qt.PointingHandCursor)
        self.lbl_current_time.setToolTip("Click to jump to time")
        self.lbl_current_time.installEventFilter(self)

        self.edit_current_time = QLineEdit()
        self.edit_current_time.setFixedWidth(85)
        self.edit_current_time.setVisible(False)
        self.edit_current_time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit_current_time.setStyleSheet(
            "QLineEdit { background-color: #1e1f22; color: #00BCD4; border: 1px solid #4f545c; border-radius: 4px; font-family: monospace; }"
        )
        self.edit_current_time.returnPressed.connect(self._jump_to_edited_time)
        self.edit_current_time.installEventFilter(self)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        self.slider.sliderPressed.connect(self.media_player.pause)
        self.slider.sliderReleased.connect(self.set_position_on_release)
        self.slider.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.slider.customContextMenuRequested.connect(self.show_video_context_menu)

        self.lbl_total_time = QLabel("00:00")

        self.btn_fullscreen = QPushButton()
        self.btn_fullscreen.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton)
        )
        self.btn_fullscreen.setToolTip("Toggle Fullscreen")
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        self.btn_fullscreen.setFixedWidth(30)

        controls_layout.addWidget(self.lbl_vol)
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.lbl_current_time)
        controls_layout.addWidget(self.edit_current_time)
        controls_layout.addWidget(self.slider)
        controls_layout.addWidget(self.lbl_total_time)
        controls_layout.addWidget(self.btn_fullscreen)

        self.player_inner_layout.addLayout(controls_layout)

        self.info_label = QLabel(
            "Video is playing externally. Use slider to select timestamps."
        )
        self.info_label.setStyleSheet(
            "color: #aaa; font-style: italic; font-size: 11px;"
        )
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setVisible(False)
        self.player_inner_layout.addWidget(self.info_label)

        self.player_layout_container.addWidget(self.player_container)
        self.player_container.installEventFilter(self)

        video_container_layout.addWidget(player_group)
        self.main_layout.addWidget(self.video_container_widget)
        self.video_container_widget.setVisible(False)

        # 4. Extraction Controls
        self.extract_group = QGroupBox("Extraction Settings")
        extract_main_layout = QVBoxLayout(self.extract_group)

        # -- Row 0: Recent Configurations --
        from PySide6.QtWidgets import QSizePolicy

        recent_layout = QHBoxLayout()
        recent_layout.addWidget(QLabel("Recent Extractions:"))
        self.combo_recent_extractions = QComboBox()
        self.combo_recent_extractions.setMinimumWidth(300)
        self.combo_recent_extractions.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )
        recent_layout.addWidget(self.combo_recent_extractions)

        self.btn_load_recent = QPushButton("Load Config")
        self.btn_load_recent.clicked.connect(self._load_selected_recent_extraction)
        self.btn_load_recent.setEnabled(False)
        recent_layout.addWidget(self.btn_load_recent)

        extract_main_layout.addLayout(recent_layout)

        # -- Row 1: Configuration --
        extract_config_layout = QHBoxLayout()

        extract_config_layout.addWidget(QLabel("Output Size:"))
        self.combo_extract_size = QComboBox()
        self.combo_extract_size.addItems(list(self.extraction_res_map.keys()))
        self.combo_extract_size.setCurrentText("Native")
        extract_config_layout.addWidget(self.combo_extract_size)

        # --- NEW: Vertical Checkbox for Extraction ---
        self.check_extract_vertical = QCheckBox("Vertical Output")
        self.check_extract_vertical.setToolTip(
            "Swap width/height for vertical output resolution"
        )
        extract_config_layout.addWidget(self.check_extract_vertical)
        # ---------------------------------------------

        extract_config_layout.addSpacing(20)

        extract_config_layout.addWidget(QLabel("GIF FPS:"))
        self.spin_gif_fps = QSpinBox()
        self.spin_gif_fps.setRange(1, 60)
        self.spin_gif_fps.setValue(24)
        extract_config_layout.addWidget(self.spin_gif_fps)

        self.check_mute_audio = QCheckBox("Mute Audio in MP4/GIF")
        self.check_mute_audio.setChecked(False)
        extract_config_layout.addWidget(self.check_mute_audio)

        extract_config_layout.addSpacing(20)
        extract_config_layout.addWidget(QLabel("Engine:"))
        self.combo_engine = QComboBox()
        self.combo_engine.addItems(["FFmpeg", "MoviePy"])
        extract_config_layout.addWidget(self.combo_engine)

        extract_config_layout.addSpacing(20)
        extract_config_layout.addWidget(QLabel("Extraction Speed:"))
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.25x", "0.5x", "1x", "1.5x", "2x", "4x"])
        self.combo_speed.setCurrentText("1x")
        # Decoupled from player speed
        extract_config_layout.addWidget(self.combo_speed)

        extract_config_layout.addStretch()
        extract_main_layout.addLayout(extract_config_layout)

        # -- Row 2: Actions --
        extract_actions_layout = QHBoxLayout()

        self.btn_snapshot = QPushButton("📸 Snapshot Frame")
        self.btn_snapshot.clicked.connect(self.extract_single_frame)
        self.btn_snapshot.setEnabled(False)
        extract_actions_layout.addWidget(self.btn_snapshot)
        extract_actions_layout.addWidget(QLabel("|"))

        self.start_time_ms = 0
        self.end_time_ms = 0
        self.cut_start_ms = 0
        self.cut_end_ms = 0
        self.cuts_ms: List[Tuple[int, int]] = []
        self.tags_ms: List[Tuple[int, str]] = []

        self.btn_cancel_extraction = QPushButton("🛑 Cancel Extraction")
        self.btn_cancel_extraction.setStyleSheet(
            "QPushButton { background-color: #f04747; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #d84040; }"
            "QPushButton:disabled { background-color: #4f545c; color: #888; }"
        )
        self.btn_cancel_extraction.clicked.connect(self.cancel_extraction)
        self.btn_cancel_extraction.hide()

        self.btn_set_start = QPushButton("Set Start [00:00]")
        self.btn_set_start.clicked.connect(self.set_range_start)
        self.btn_set_start.setEnabled(False)

        self.btn_jump_start = QPushButton("Go")
        self.btn_jump_start.setFixedWidth(40)
        self.btn_jump_start.clicked.connect(self.jump_to_range_start)
        self.btn_jump_start.setEnabled(False)

        self.btn_set_end = QPushButton("Set End [00:00]")
        self.btn_set_end.clicked.connect(self.set_range_end)
        self.btn_set_end.setEnabled(False)

        self.btn_jump_end = QPushButton("Go")
        self.btn_jump_end.setFixedWidth(40)
        self.btn_jump_end.clicked.connect(self.jump_to_range_end)
        self.btn_jump_end.setEnabled(False)
        self.btn_extract_range = QPushButton("🎞️ Extract Range")
        self.btn_extract_range.clicked.connect(self.extract_range)
        self.btn_extract_range.setEnabled(False)

        self.btn_extract_gif = QPushButton("GIF Extract as GIF")
        self.btn_extract_gif.setStyleSheet(
            "QPushButton { background-color: #8e44ad; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #4f545c; color: #888; }"
        )
        self.btn_extract_gif.clicked.connect(self.extract_range_as_gif)
        self.btn_extract_gif.setEnabled(False)

        self.btn_extract_video = QPushButton("MP4 Extract as Video")
        self.btn_extract_video.setStyleSheet(
            "QPushButton { background-color: #2980b9; color: white; font-weight: bold; }"
            "QPushButton:disabled { background-color: #4f545c; color: #888; }"
        )
        self.btn_extract_video.clicked.connect(self.extract_range_as_video)
        self.btn_extract_video.setEnabled(False)

        extract_actions_layout.addWidget(self.btn_set_start)
        extract_actions_layout.addWidget(self.btn_jump_start)
        extract_actions_layout.addWidget(self.btn_set_end)
        extract_actions_layout.addWidget(self.btn_jump_end)
        extract_actions_layout.addWidget(self.btn_extract_range)
        extract_actions_layout.addWidget(self.btn_extract_video)
        extract_actions_layout.addWidget(self.btn_extract_gif)
        extract_actions_layout.addWidget(self.btn_cancel_extraction)

        extract_main_layout.addLayout(extract_actions_layout)

        # -- Row 3: Cuts --
        extract_cuts_layout = QHBoxLayout()
        self.btn_set_cut_start = QPushButton("Set Cut Start [00:00]")
        self.btn_set_cut_start.clicked.connect(self.set_cut_start)
        self.btn_set_cut_start.setEnabled(False)

        self.btn_set_cut_end = QPushButton("Set Cut End [00:00]")
        self.btn_set_cut_end.clicked.connect(self.set_cut_end)
        self.btn_set_cut_end.setEnabled(False)

        self.btn_add_cut = QPushButton("Add Cut")
        self.btn_add_cut.clicked.connect(self.add_cut)
        self.btn_add_cut.setEnabled(False)

        # Scrollable container for individual cuts
        self.cuts_scroll = QScrollArea()
        self.cuts_scroll.setWidgetResizable(True)
        self.cuts_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.cuts_scroll.setMaximumHeight(45)
        self.cuts_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.cuts_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.cuts_scroll.setStyleSheet("background: transparent;")

        self.cuts_container = QWidget()
        self.cuts_container.setStyleSheet("background: transparent;")
        self.cuts_layout = QHBoxLayout(self.cuts_container)
        self.cuts_layout.setContentsMargins(0, 5, 0, 5)
        self.cuts_layout.setSpacing(8)
        self.cuts_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.cuts_scroll.setWidget(self.cuts_container)

        self.btn_clear_cuts = QPushButton("Clear Cuts")
        self.btn_clear_cuts.clicked.connect(self.clear_cuts)
        self.btn_clear_cuts.setEnabled(False)

        extract_cuts_layout.addWidget(self.btn_set_cut_start)
        extract_cuts_layout.addWidget(self.btn_set_cut_end)
        extract_cuts_layout.addWidget(self.btn_add_cut)
        extract_cuts_layout.addWidget(self.cuts_scroll, 1)  # Give it stretch
        extract_cuts_layout.addWidget(self.btn_clear_cuts)
        extract_cuts_layout.addStretch()

        extract_main_layout.addLayout(extract_cuts_layout)

        # -- Row 4: Advanced Extraction Options --
        extract_adv_layout = QHBoxLayout()
        extract_adv_layout.addWidget(QLabel("Frame Interval:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 1000)
        self.spin_interval.setValue(1)
        self.spin_interval.setSuffix(" frames")
        extract_adv_layout.addWidget(self.spin_interval)

        extract_adv_layout.addSpacing(20)
        self.check_smart_extract = QCheckBox("Smart Extract (FFmpeg)")
        self.check_smart_extract.setToolTip(
            "Use FFmpeg filters to only extract unique frames or scene changes"
        )
        extract_adv_layout.addWidget(self.check_smart_extract)

        self.combo_smart_method = QComboBox()
        self.combo_smart_method.addItems(
            [
                "mpdecimate (De-duplicate)",
                "scene (0.1)",
                "scene (0.2)",
                "scene (0.4)",
                "scene (0.6)",
            ]
        )
        self.combo_smart_method.setCurrentText("mpdecimate (De-duplicate)")
        self.combo_smart_method.setEnabled(False)
        self.check_smart_extract.toggled.connect(self.combo_smart_method.setEnabled)
        extract_adv_layout.addWidget(self.combo_smart_method)

        extract_adv_layout.addStretch()
        extract_main_layout.addLayout(extract_adv_layout)

        # -- Row 5: Tags --
        extract_tags_layout = QHBoxLayout()
        self.btn_add_tag = QPushButton("🏷️ Add Tag")
        self.btn_add_tag.clicked.connect(self.add_tag)
        self.btn_add_tag.setEnabled(False)

        # Scrollable container for tags
        self.tags_scroll = QScrollArea()
        self.tags_scroll.setWidgetResizable(True)
        self.tags_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.tags_scroll.setMaximumHeight(45)
        self.tags_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.tags_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.tags_scroll.setStyleSheet("background: transparent;")

        self.tags_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.tags_scroll.setStyleSheet("background: transparent;")

        self.tags_container = QWidget()
        self.tags_container.setStyleSheet("background: transparent;")
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(0, 5, 0, 5)
        self.tags_layout.setSpacing(8)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.tags_scroll.setWidget(self.tags_container)

        self.btn_clear_tags = QPushButton("Clear Tags")
        self.btn_clear_tags.clicked.connect(self.clear_tags)
        self.btn_clear_tags.setEnabled(False)

        extract_tags_layout.addWidget(self.btn_add_tag)
        extract_tags_layout.addWidget(self.tags_scroll, 1)
        extract_tags_layout.addWidget(self.btn_clear_tags)
        extract_tags_layout.addStretch()

        extract_main_layout.addLayout(extract_tags_layout)

        # -- Row 6: Progress --
        self.extraction_progress_bar = QProgressBar()
        self.extraction_progress_bar.setTextVisible(True)
        self.extraction_progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extraction_progress_bar.setStyleSheet(
            "QProgressBar { background-color: #36393f; color: white; border: 1px solid #4f545c; border-radius: 4px; padding: 2px; height: 20px; }"
            "QProgressBar::chunk { background-color: #00BCD4; border-radius: 4px; }"
        )
        self.extraction_progress_bar.setMinimum(0)
        self.extraction_progress_bar.setMaximum(100)
        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.hide()
        extract_main_layout.addWidget(self.extraction_progress_bar)

        self.extraction_status_label = QLabel("Ready.")
        self.extraction_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extraction_status_label.setStyleSheet(
            "color: #00BCD4; font-style: italic; padding: 4px; font-weight: bold;"
        )
        self.extraction_status_label.hide()
        extract_main_layout.addWidget(self.extraction_status_label)

        self.main_layout.addWidget(self.extract_group)
        self.extract_group.setVisible(False)

        # 5. Results Gallery Section
        self.gallery_scroll_area = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True)
        self.gallery_scroll_area.setStyleSheet(
            """
            QScrollArea { 
                border: 1px solid #4f545c; 
                background-color: #2c2f33; 
                border-radius: 8px; 
            }
            QScrollBar:vertical {
                border: none;
                background: #2c2f33;
                width: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #00BCD4; 
                min-height: 20px;
                border-radius: 6px;
                margin: 0 2px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                subcontrol-position: none;
            }
            QScrollBar:horizontal {
                border: none;
                background: #2c2f33; 
                height: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #00BCD4; 
                min-width: 20px;
                border-radius: 6px;
                margin: 2px 0;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                subcontrol-position: none;
            }
        """
        )
        self.gallery_scroll_area.setMinimumHeight(600)

        self.gallery_container = QWidget()
        self.gallery_container.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.gallery_layout.setSpacing(3)
        self.gallery_scroll_area.setWidget(self.gallery_container)

        self.gallery_scroll_area.selection_changed.connect(
            self.handle_marquee_selection
        )

        # Setup Queue UI Group Box
        self.queue_group = QGroupBox("Extraction Queue")
        queue_layout = QVBoxLayout(self.queue_group)
        queue_layout.setContentsMargins(10, 10, 10, 10)

        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(120)
        self.queue_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.queue_list.customContextMenuRequested.connect(self.show_queue_context_menu)
        queue_layout.addWidget(self.queue_list)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Execution Mode:"))
        self.combo_queue_mode = QComboBox()
        self.combo_queue_mode.addItems(["Sequentially", "Parallel (Multiprocessing)"])
        controls_layout.addWidget(self.combo_queue_mode)

        self.btn_process_queue = QPushButton("⚙️ Process Queue")
        self.btn_process_queue.clicked.connect(self.process_queue)
        self.btn_process_queue.setStyleSheet(
            "QPushButton { font-weight: bold; background-color: #2ecc71; color: white; padding: 4px 8px; }"
        )
        controls_layout.addWidget(self.btn_process_queue)

        self.btn_clear_queue = QPushButton("🗑️ Clear Queue")
        self.btn_clear_queue.clicked.connect(self.clear_queue)
        controls_layout.addWidget(self.btn_clear_queue)

        queue_layout.addLayout(controls_layout)

        self.main_layout.addWidget(self.queue_group)
        self.queue_group.setVisible(self.extraction_queue_enabled)

        # Add shared search input (Lazy Search)
        self.main_layout.addWidget(self.search_input)

        self.main_layout.addWidget(self.gallery_scroll_area, 1)
        self.main_layout.addWidget(
            self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
        )

        self.extraction_status_label = QLabel("Ready.")
        self.extraction_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.extraction_status_label.setStyleSheet(
            "color: #666; font-style: italic; padding: 8px;"
        )
        self.extraction_status_label.hide()
        self.main_layout.addWidget(self.extraction_status_label)

        # --- Connections ---
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.errorOccurred.connect(self.handle_player_error)

        self._load_existing_output_images()
        self._update_recent_extractions_ui()

    def cancel_loading(self):
        """Stops all active media players, timers, and background workers."""
        super().cancel_loading()

        if self.active_extraction_worker:
            self.active_extraction_worker.cancel()
            self.active_extraction_worker = None

        if self.vid_scanner_worker:
            self.vid_scanner_worker.stop()
            self.vid_scanner_worker = None

        # Close sub-windows
        for win in list(self.open_preview_windows):
            try:
                win.close()
            except Exception:
                pass
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        """Cleanup processes on close."""
        self.cancel_loading()
        super().closeEvent(event)

    def _load_existing_output_images(self):
        valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".mp4"}
        found_paths = []

        if self.extraction_dir.exists():
            for entry in self.extraction_dir.iterdir():
                if entry.is_file() and entry.suffix.lower() in valid_extensions:
                    full_path = str(entry.absolute())
                    found_paths.append(full_path)

        found_paths.sort(key=natural_sort_key)

        if found_paths:
            self.current_extracted_paths = found_paths
            self.start_loading_gallery(
                self.current_extracted_paths, pixmap_cache=self._initial_pixmap_cache
            )

    @Slot()
    def set_position_on_release(self):
        position = self.slider.value()
        self.media_player.setPosition(position)

    # --- Directory Browsing & Scanning ---
    @Slot()
    def browse_directory(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Source Directory", self.last_browsed_scan_dir
        )
        if d:
            self.last_browsed_scan_dir = d
            self.scan_directory(d)

    def scan_directory(self, path: str):
        if not os.path.isdir(path):
            return

        self.line_edit_dir.setText(path)

        # Clear grid and path tracking
        paths_to_remove = list(self.source_path_to_widget.keys())
        for p in paths_to_remove:
            widget = self.source_path_to_widget.pop(p)
            widget.deleteLater()

        while self.source_grid.count():
            item = self.source_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # 0. Refresh extracted stems cache
        self._refresh_extracted_stems_cache()

        # 1. Alphabetical Directory Read (Quickly get names for placeholders)
        try:
            entries = sorted(os.scandir(path), key=lambda e: natural_sort_key(e.name))
            video_paths = [
                e.path
                for e in entries
                if e.is_file()
                and Path(e.path).suffix.lower() in SUPPORTED_VIDEO_FORMATS
            ]
        except Exception:
            video_paths = []

        # 2. Pre-populate grid with "Loading..." items in alphabetical order
        # Limit to 1000 items to avoid OOM/crash if directory is massive
        from ...constants import MAX_PREVIEW_ITEMS

        video_paths_limited = video_paths[:MAX_PREVIEW_ITEMS]

        for i, v_path in enumerate(video_paths_limited):
            # Check in-memory and disk cache
            cached_image = self._initial_pixmap_cache.get(v_path)
            if cached_image is None:
                # Try disk cache
                disk_cache = self._get_disk_cache_path(v_path)
                if os.path.exists(disk_cache):
                    img = QImage(disk_cache)
                    if not img.isNull():
                        cached_image = img
                        self._initial_pixmap_cache[v_path] = img

            widget = self._create_source_placeholder_widget(v_path)
            self.source_path_to_widget[v_path] = widget
            row = i // 12
            col = i % 12
            self.source_grid.addWidget(widget, row, col)

            if cached_image:
                # Immediately update if we have a cached version
                self.add_source_thumbnail(v_path, cached_image)

        # 3. Start the intensive thumbnailing worker
        if self.vid_scanner_worker:
            self.vid_scanner_worker.stop()
            self.vid_scanner_worker = None

        self.vid_scanner_worker = VideoScannerWorker(path, crop_square=True)
        self.vid_scanner_worker.signals.thumbnail_ready.connect(
            self.add_source_thumbnail
        )
        self.vid_scanner_worker.signals.finished.connect(
            lambda: self.scan_progress_complete()
        )
        QThreadPool.globalInstance().start(self.vid_scanner_worker)

    def _create_source_placeholder_widget(self, path: str) -> QWidget:
        """Creates a placeholder widget with 'Loading...' state for the source gallery."""
        thumb_size = 120
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)

        clickable_label = ClickableLabel(file_path=path)
        clickable_label.setFixedSize(thumb_size, thumb_size)
        clickable_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clickable_label.setText("Loading...")
        clickable_label.setStyleSheet(
            "border: 1px dashed #666; color: #888; font-size: 10px;"
        )

        clickable_label.path_clicked.connect(self.load_media)
        clickable_label.path_right_clicked.connect(self.show_source_context_menu)

        layout.addWidget(clickable_label)

        # File Name Label (Alphabetical position preserved here)
        file_name = Path(path).name
        name_label = QLabel(file_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setFixedWidth(thumb_size)
        fm = name_label.fontMetrics()
        elided_text = fm.elidedText(
            file_name, Qt.TextElideMode.ElideMiddle, thumb_size - 8
        )
        name_label.setText(elided_text)
        name_label.setToolTip(file_name)
        name_label.setStyleSheet(
            "color: #bbb; font-size: 10px; border: none; padding-top: 2px;"
        )

        layout.addWidget(name_label)
        return container

    def scan_progress_complete(self):
        pass

    @Slot(str, object)
    def add_source_thumbnail(self, path: str, image_or_pixmap: Any):
        """Updates an existing alphabetical placeholder with the actual generated thumbnail."""
        # 1. Resolve to Pixmap
        if isinstance(image_or_pixmap, QPixmap):
            pixmap = image_or_pixmap
        elif isinstance(image_or_pixmap, QImage):
            pixmap = QPixmap.fromImage(image_or_pixmap)
        else:
            pixmap = QPixmap()

        if pixmap.isNull() and path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            if hasattr(self, "_generate_video_thumbnail"):
                thumb = self._generate_video_thumbnail(path)
                if thumb:
                    pixmap = thumb

        # 1.5. Cache to memory if successful
        if not pixmap.isNull() and path not in self._initial_pixmap_cache:
            if isinstance(image_or_pixmap, QImage):
                self._initial_pixmap_cache[path] = image_or_pixmap
            elif isinstance(image_or_pixmap, QPixmap):
                self._initial_pixmap_cache[path] = image_or_pixmap.toImage()
            else:
                # If we fell back to _generate_video_thumbnail, pixmap is updated
                self._initial_pixmap_cache[path] = pixmap.toImage()

        # 2. Find and update the existing widget
        container = self.source_path_to_widget.get(path)
        if not container:
            return

        clickable_label = container.findChild(ClickableLabel)
        if not clickable_label:
            return

        if not pixmap.isNull():
            # NOTE: Scaling/cropping is now handled in the background by VideoScannerWorker(crop_square=True)
            clickable_label.setPixmap(pixmap)
            clickable_label.setText("")  # Remove "Loading..." text
        else:
            # Fallback if processing totally fails
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                clickable_label.setText("VIDEO")
            else:
                clickable_label.setText("No Preview")

        self._update_source_label_style(
            path, clickable_label, getattr(self, "video_path", None) == path
        )

    @Slot(QPoint, str)
    def show_source_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        is_open = False
        tab_idx = -1
        for i in range(self.active_videos_tabbar.count()):
            if self.active_videos_tabbar.tabData(i) == path:
                is_open = True
                tab_idx = i
                break

        if is_open:
            close_action = QAction("Close Video", self)
            close_action.triggered.connect(
                lambda: self._on_active_video_tab_closed(tab_idx)
            )
            menu.addAction(close_action)
        else:
            open_action = QAction("Open Video", self)
            open_action.triggered.connect(lambda: self.load_media(path))
            menu.addAction(open_action)

        view_action = QAction("View Preview", self)
        view_action.triggered.connect(lambda: self.handle_thumbnail_double_click(path))
        menu.addAction(view_action)

        menu.exec(global_pos)

    @Slot(QPoint)
    def _show_tab_context_menu(self, pos: QPoint):
        idx = self.active_videos_tabbar.tabAt(pos)
        if idx >= 0:
            menu = QMenu(self)
            close_action = QAction("Close Video", self)
            close_action.triggered.connect(
                lambda: self._on_active_video_tab_closed(idx)
            )
            menu.addAction(close_action)
            menu.exec(self.active_videos_tabbar.mapToGlobal(pos))

    def _refresh_extracted_stems_cache(self):
        """Scans extraction_dir once and caches which video stems have files."""
        self._extracted_stems_cache.clear()
        if not self.extraction_dir.exists():
            return
        try:
            # We only care about the prefix before the first '_' or similar.
            # However, stems can contain underscores.
            # To be robust, we just store all filenames and check prefixes in _has_extracted_files
            # OR we can collect all strings before the LAST underscore.
            for entry in os.scandir(self.extraction_dir):
                if entry.is_file():
                    name = entry.name
                    # Extracted files: {stem}_{ms}ms.png or {stem}_smart_{ms}ms.png
                    # or {stem}_snap_{ms}ms.png
                    if "_" in name:
                        # Take everything before the last underscore that looks like a timestamp
                        idx = name.rfind("_")
                        if idx > 0:
                            self._extracted_stems_cache.add(name[:idx])
        except Exception as e:
            print(f"Error refreshing extracted stems cache: {e}")

    def _has_extracted_files(self, video_path: str) -> bool:
        """Check if the video has extracted files in the output directory using cache."""
        if not self._extracted_stems_cache:
            self._refresh_extracted_stems_cache()

        stem = Path(video_path).stem
        # Check direct stem match
        if stem in self._extracted_stems_cache:
            return True
        # Check with _smart or _snap suffixes which might be in the cache if we used rfind
        if f"{stem}_smart" in self._extracted_stems_cache:
            return True
        if f"{stem}_snap" in self._extracted_stems_cache:
            return True

        return False

    def _update_source_label_style(
        self, path: str, label: ClickableLabel, selected: bool
    ):
        has_extracted = self._has_extracted_files(path)
        is_other_open = (
            hasattr(self, "active_videos_config")
            and path in self.active_videos_config
            and path != self.video_path
        )

        if selected:
            label.setStyleSheet("border: 3px solid #3498db; border-radius: 4px;")
        elif is_other_open:
            if label.text() == "VIDEO":
                label.setStyleSheet(
                    "border: 2px solid #9b59b6; color: #9b59b6; font-weight: bold; background-color: #2c2f33; border-radius: 4px;"
                )
            elif label.text() == "No Preview" or label.text() == "Loading...":
                label.setStyleSheet(
                    "border: 2px solid #9b59b6; color: #9b59b6; border-radius: 4px;"
                )
            else:
                label.setStyleSheet("border: 2px solid #9b59b6; border-radius: 4px;")
        else:
            if label.text() == "VIDEO":
                if has_extracted:
                    label.setStyleSheet(
                        "border: 2px solid #2ecc71; color: #2ecc71; font-weight: bold; background-color: #2c2f33; border-radius: 4px;"
                    )
                else:
                    label.setStyleSheet(
                        "border: 2px solid #3498db; color: #3498db; font-weight: bold; background-color: #2c2f33; border-radius: 4px;"
                    )
            elif label.text() == "No Preview":
                label.setStyleSheet(
                    "border: 1px dashed #666; color: #888; border-radius: 4px;"
                )
            elif label.text() == "Loading...":
                label.setStyleSheet(
                    "border: 1px dashed #666; color: #888; font-size: 10px; border-radius: 4px;"
                )
            else:
                if has_extracted:
                    label.setStyleSheet(
                        "border: 2px solid #2ecc71; border-radius: 4px;"
                    )
                else:
                    label.setStyleSheet(
                        "border: 2px solid #4f545c; border-radius: 4px;"
                    )

    def _save_current_video_config(self):
        if not self.video_path:
            return

        config = {
            "start_time_ms": getattr(self, "start_time_ms", 0),
            "end_time_ms": getattr(self, "end_time_ms", 0),
            "cut_start_ms": getattr(self, "cut_start_ms", 0),
            "cut_end_ms": getattr(self, "cut_end_ms", 0),
            "cuts_ms": copy.deepcopy(getattr(self, "cuts_ms", [])),
            "tags_ms": copy.deepcopy(getattr(self, "tags_ms", [])),
            "check_mute_audio": self.check_mute_audio.isChecked(),
            "spin_gif_fps": self.spin_gif_fps.value(),
            "combo_extract_size": self.combo_extract_size.currentText(),
            "check_extract_vertical": self.check_extract_vertical.isChecked(),
            "spin_interval": self.spin_interval.value(),
            "check_smart_extract": self.check_smart_extract.isChecked(),
            "combo_smart_method": self.combo_smart_method.currentText(),
            "media_position": self.media_player.position() if self.media_player else 0,
        }
        self.active_videos_config[self.video_path] = config

    def _load_video_config(self, path: str):
        config = self.active_videos_config.get(path, {})
        if not config:
            self.clear_cuts()
            self.clear_tags()
            self.start_time_ms = 0
            self.end_time_ms = 0
            self.cut_start_ms = 0
            self.cut_end_ms = 0
            self.btn_set_start.setText("Set Start [00:00]")
            self.btn_set_end.setText("Set End [00:00]")
            self.btn_set_cut_start.setText("Set Cut Start [00:00]")
            self.btn_set_cut_end.setText("Set Cut End [00:00]")
            return

        self.start_time_ms = config.get("start_time_ms", 0)
        self.end_time_ms = config.get("end_time_ms", 0)
        self.cut_start_ms = config.get("cut_start_ms", 0)
        self.cut_end_ms = config.get("cut_end_ms", 0)

        self.btn_set_start.setText(
            f"Start [{self._format_time(self.start_time_ms)}]"
            if self.start_time_ms
            else "Set Start [00:00]"
        )
        self.btn_set_end.setText(
            f"End [{self._format_time(self.end_time_ms)}]"
            if self.end_time_ms
            else "Set End [00:00]"
        )
        self.btn_set_cut_start.setText(
            f"Cut Start [{self._format_time(self.cut_start_ms)}]"
            if self.cut_start_ms
            else "Set Cut Start [00:00]"
        )
        self.btn_set_cut_end.setText(
            f"Cut End [{self._format_time(self.cut_end_ms)}]"
            if self.cut_end_ms
            else "Set Cut End [00:00]"
        )

        self.cuts_ms = config.get("cuts_ms", [])
        self._update_cuts_label()

        self.tags_ms = config.get("tags_ms", [])
        self._update_tags_ui()

        self.check_mute_audio.setChecked(config.get("check_mute_audio", False))
        self.spin_gif_fps.setValue(config.get("spin_gif_fps", 24))
        if config.get("combo_extract_size"):
            self.combo_extract_size.setCurrentText(config.get("combo_extract_size"))
        self.check_extract_vertical.setChecked(
            config.get("check_extract_vertical", False)
        )
        self.spin_interval.setValue(config.get("spin_interval", 1))
        self.check_smart_extract.setChecked(config.get("check_smart_extract", False))
        if config.get("combo_smart_method"):
            self.combo_smart_method.setCurrentText(config.get("combo_smart_method"))

        pos = config.get("media_position", 0)
        if pos > 0 and self.media_player:
            self.media_player.setPosition(pos)
            self.slider.setValue(pos)
            self.lbl_current_time.setText(self._format_time(pos))

    @Slot(int)
    def _on_active_video_tab_changed(self, index: int):
        if self._is_switching_tabs or index < 0:
            return

        path = self.active_videos_tabbar.tabData(index)
        if path and path != self.video_path:
            self.load_media(path)

    @Slot(int)
    def _on_active_video_tab_closed(self, index: int):
        path = self.active_videos_tabbar.tabData(index)

        # Don't allow closing the last tab
        if self.active_videos_tabbar.count() <= 1:
            QMessageBox.information(
                self, "Cannot Close", "Cannot close the last active video."
            )
            return

        self.active_videos_tabbar.removeTab(index)
        if path in self.active_videos_config:
            del self.active_videos_config[path]

        # If we closed the currently active video, it will automatically switch tab and load the new one via currentChanged signal
        if path == self.video_path:
            new_idx = self.active_videos_tabbar.currentIndex()
            new_path = self.active_videos_tabbar.tabData(new_idx)
            if new_path:
                self.load_media(new_path)
        else:
            # We closed an inactive tab, just update its style in the source list
            if path in self.source_path_to_widget:
                widget = self.source_path_to_widget[path]
                label = widget.findChild(ClickableLabel)
                if label:
                    self._update_source_label_style(path, label, False)

    @Slot(str)
    def load_media(self, file_path: str):
        old_path = self.video_path

        if old_path == file_path:
            return

        if old_path:
            self._save_current_video_config()

        self.video_path = file_path

        ext = Path(file_path).suffix.lower()
        if ext == ".gif":
            self.video_container_widget.setVisible(False)
            self.extract_group.setVisible(False)
            self.media_player.stop()
            self.media_player.setSource(QUrl())
            # Update style
            for path in [old_path, file_path]:
                if path and path in self.source_path_to_widget:
                    widget = self.source_path_to_widget[path]
                    label = widget.findChild(ClickableLabel)
                    if label:
                        self._update_source_label_style(path, label, path == file_path)
            return

        # Check if tab exists
        tab_idx = -1
        for i in range(self.active_videos_tabbar.count()):
            if self.active_videos_tabbar.tabData(i) == file_path:
                tab_idx = i
                break

        self._is_switching_tabs = True
        if tab_idx == -1:
            # Add new tab
            name = Path(file_path).name
            idx = self.active_videos_tabbar.addTab(name)
            self.active_videos_tabbar.setTabData(idx, file_path)
            self.active_videos_tabbar.setCurrentIndex(idx)
        else:
            self.active_videos_tabbar.setCurrentIndex(tab_idx)
        self._is_switching_tabs = False

        self._load_video_config(file_path)

        # Update styles only for the affected widgets (old and new selection)
        for path in [old_path, file_path]:
            if path and path in self.source_path_to_widget:
                widget = self.source_path_to_widget[path]
                label = widget.findChild(ClickableLabel)
                if label:
                    self._update_source_label_style(path, label, path == file_path)

        self.video_container_widget.setVisible(True)
        self.extract_group.setVisible(True)

        self.btn_snapshot.setEnabled(
            True if getattr(self, "start_time_ms", 0) else False
        )
        if not getattr(self, "start_time_ms", 0):
            self.btn_snapshot.setText("📸 Snapshot (Set Start First)")
        else:
            self.btn_snapshot.setText("📸 Snapshot Frame")

        self.btn_set_start.setEnabled(True)
        self.btn_set_end.setEnabled(True)
        self.btn_set_cut_start.setEnabled(True)
        self.btn_set_cut_end.setEnabled(True)
        self.btn_add_tag.setEnabled(True)

        self._apply_player_mode()

    @Slot()
    def browse_extraction_directory(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Extraction Directory", self.last_browsed_extraction_dir
        )
        if d:
            new_path = Path(d)
            new_path.mkdir(parents=True, exist_ok=True)
            self.extraction_dir = new_path
            self.last_browsed_extraction_dir = str(new_path)
            self.line_edit_extract_dir.setText(str(self.extraction_dir))
            self._clear_gallery()
            self._refresh_extracted_stems_cache()
            self._load_extraction_history()
            self._load_existing_output_images()

            for path, widget in self.source_path_to_widget.items():
                label = widget.findChild(ClickableLabel)
                if label:
                    self._update_source_label_style(
                        path, label, path == getattr(self, "video_path", None)
                    )

    def _load_extraction_history(self):
        """Loads metadata for extracted frames from a central hidden JSON file."""
        history_file = IMAGE_TOOLKIT_DIR / ".extraction_history.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "recent_runs" in data:
                        self.recent_runs = data.get("recent_runs", [])
                        self.extraction_metadata = data.get("file_map", {})
                    else:
                        # Legacy format where the whole json was extraction_metadata
                        self.extraction_metadata = data
                        # Reconstruct recent_runs from unique metadata in extraction_metadata
                        unique_runs = {}
                        for meta in self.extraction_metadata.values():
                            ts = meta.get("timestamp", 0)
                            unique_runs[ts] = meta
                        self.recent_runs = sorted(
                            unique_runs.values(),
                            key=lambda x: x.get("timestamp", 0),
                            reverse=True,
                        )
            except Exception as e:
                print(f"Error loading extraction history: {e}")
                self.extraction_metadata = {}
                self.recent_runs = []
        else:
            self.extraction_metadata = {}
            self.recent_runs = []

        if (
            hasattr(self, "combo_recent_extractions")
            and self.combo_recent_extractions is not None
        ):
            self._update_recent_extractions_ui()

    def _save_extraction_history(self):
        """Saves metadata for extracted frames to a central hidden JSON file."""
        history_file = IMAGE_TOOLKIT_DIR / ".extraction_history.json"
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "recent_runs": self.recent_runs,
                "file_map": self.extraction_metadata,
            }
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving extraction history: {e}")

    def _record_extraction(self, file_paths: List[str], metadata: dict):
        """Records metadata for a set of extracted files using absolute paths as keys."""
        metadata = copy.deepcopy(metadata)
        # 1. Update file_map for the new files
        for path in file_paths:
            abs_path = str(Path(path).absolute())
            self.extraction_metadata[abs_path] = metadata

        # 2. Add to recent runs (avoid duplicate additions based on timestamp)
        run_ts = metadata.get("timestamp")
        if not any(run.get("timestamp") == run_ts for run in self.recent_runs):
            self.recent_runs.append(metadata)

        # 3. Sort recent runs and limit to N
        self.recent_runs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        self.recent_runs = self.recent_runs[: self.recent_extractions_limit]

        # 4. Prune file_map to only contain files from the N most recent runs
        recent_timestamps = {
            run.get("timestamp") for run in self.recent_runs if run.get("timestamp")
        }
        keys_to_delete = [
            path
            for path, meta in self.extraction_metadata.items()
            if meta.get("timestamp") not in recent_timestamps
        ]
        for key in keys_to_delete:
            del self.extraction_metadata[key]

        self._save_extraction_history()
        self._update_recent_extractions_ui()

    def _apply_new_extractions_limit(self):
        """Called when the settings window updates recent_extractions_limit."""
        if hasattr(self, "recent_runs") and self.recent_runs:
            self.recent_runs = self.recent_runs[: self.recent_extractions_limit]

            # Prune file_map too
            recent_timestamps = {
                run.get("timestamp") for run in self.recent_runs if run.get("timestamp")
            }
            keys_to_delete = [
                path
                for path, meta in self.extraction_metadata.items()
                if meta.get("timestamp") not in recent_timestamps
            ]
            for key in keys_to_delete:
                del self.extraction_metadata[key]

            self._save_extraction_history()
            self._update_recent_extractions_ui()

    def _update_recent_extractions_ui(self):
        """Updates the dropdown of recent extractions in the Extract tab."""
        if self._recent_combo_connected:
            try:
                self.combo_recent_extractions.currentIndexChanged.disconnect(
                    self._on_recent_extraction_selected
                )
            except (RuntimeError, TypeError):
                pass
            self._recent_combo_connected = False

        self.combo_recent_extractions.clear()
        self.combo_recent_extractions.addItem("Select a previous configuration...")

        for run in self.recent_runs:
            video_path = run.get("video_path", "")
            video_name = Path(video_path).name if video_path else "Unknown Video"
            start_ms = run.get("start_ms", 0)
            end_ms = run.get("end_ms", 0)
            engine = run.get("engine", "FFmpeg")

            # Format timestamp nicely
            ts = run.get("timestamp", 0)
            ts_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "N/A"
            )

            start_str = self._format_time(start_ms)
            end_str = self._format_time(end_ms)

            label = f"[{ts_str}] {video_name} ({start_str} - {end_str}) [{engine}]"
            # Set the metadata dictionary as the item data!
            self.combo_recent_extractions.addItem(label, run)

        if hasattr(self, "btn_load_recent") and self.btn_load_recent is not None:
            self.btn_load_recent.setEnabled(
                self.combo_recent_extractions.currentIndex() > 0
            )

        self.combo_recent_extractions.currentIndexChanged.connect(
            self._on_recent_extraction_selected
        )
        self._recent_combo_connected = True

    def _on_recent_extraction_selected(self, index: int):
        """Enables/disables the load button based on selection."""
        if hasattr(self, "btn_load_recent") and self.btn_load_recent is not None:
            self.btn_load_recent.setEnabled(index > 0)

    def _load_selected_recent_extraction(self):
        """Loads the selected recent extraction configuration into the UI."""
        index = self.combo_recent_extractions.currentIndex()
        if index <= 0:
            QMessageBox.warning(
                self, "Error", "Please select a valid configuration from the list."
            )
            return

        run_data = self.combo_recent_extractions.itemData(index)
        if run_data:
            self._reload_extraction(run_data)
            QMessageBox.information(
                self, "Success", "Extraction configuration loaded successfully."
            )

    def _clear_gallery(self):
        self.current_extracted_paths.clear()
        self.selected_paths.clear()
        self.gallery_image_paths.clear()
        self._initial_pixmap_cache.clear()
        self.clear_gallery_widgets()
        self.start_time_ms = 0
        self.end_time_ms = 0

        # --- MODIFIED: Reset Snapshot button ---
        self.btn_snapshot.setEnabled(False)
        self.btn_snapshot.setText("📸 Snapshot Frame")
        # ---------------------------------------

        self.btn_set_start.setText("Set Start [00:00:000]")
        self.btn_set_end.setText("Set End [00:00:000]")

        self.btn_set_cut_start.setText("Set Cut Start [00:00]")
        self.btn_set_cut_end.setText("Set Cut End [00:00]")
        self.btn_add_cut.setEnabled(False)
        self.cuts_ms.clear()
        self._update_cuts_label()

        self.btn_add_tag.setEnabled(False)
        self.tags_ms.clear()
        self._update_tags_ui()
        self.btn_extract_range.setEnabled(False)
        self.btn_extract_gif.setEnabled(False)
        self.btn_extract_gif.setEnabled(False)
        self.btn_extract_video.setEnabled(False)
        self.btn_extract_range.setText("🎞️ Extract Range")

        self.btn_jump_start.setEnabled(False)
        self.btn_jump_end.setEnabled(False)

    # --- Event Filters & Resizing ---
    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        if self.lbl_current_time and obj is self.lbl_current_time:
            if event.type() == QEvent.Type.MouseButtonPress:
                self.lbl_current_time.hide()
                self.edit_current_time.setText(self.lbl_current_time.text())
                self.edit_current_time.show()
                self.edit_current_time.setFocus()
                self.edit_current_time.selectAll()
                return True

        if self.edit_current_time and obj is self.edit_current_time:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self._cancel_time_edit()
                    return True
            elif event.type() == QEvent.Type.FocusOut:
                # Only cancel if it's not a return press (which also triggers focus out in some cases)
                self._cancel_time_edit()
                return True

        # MANDATORY: Intercept mouse wheel events over any player-related object
        # This performs seeking AND locks the page position by consuming the event.
        if event.type() == QEvent.Type.Wheel:
            is_view = self.video_view and obj is self.video_view
            is_viewport = (
                self.video_view
                and hasattr(self.video_view, "viewport")
                and obj is self.video_view.viewport()
            )
            is_container = self.player_container and obj is self.player_container

            if is_view or is_viewport or is_container:
                # Only perform seek logic if the video is loaded and we are in internal player mode
                if self.use_internal_player and self.media_player.duration() > 0:
                    delta = event.angleDelta().y()
                    # Jump by configured ms per scroll tick
                    step = self.wheel_seek_ms if delta > 0 else -self.wheel_seek_ms
                    current_pos = self.media_player.position()
                    new_pos = max(
                        0, min(current_pos + step, self.media_player.duration())
                    )
                    self.media_player.setPosition(new_pos)

                # ALWAYS accept the event and return True.
                # This explicitly blocks the parent QScrollArea from shifting the player's alignment.
                event.accept()
                return True

        if self.video_view and obj is self.video_view:
            if self.use_internal_player:
                # toggle play on click
                if (
                    event.type() == QEvent.Type.MouseButtonPress
                    and event.button() == Qt.MouseButton.LeftButton
                ):
                    self.toggle_playback()
                    return True

                # --- Arrow Keys for Video Seeking (When video has focus) ---
                if event.type() == QEvent.Type.KeyPress:
                    if event.key() == Qt.Key.Key_Right:
                        # Seek forward
                        pos = self.media_player.position()
                        duration = self.media_player.duration()
                        new_pos = min(pos + self.wheel_seek_ms, duration)
                        self.media_player.setPosition(new_pos)
                        return True
                    elif event.key() == Qt.Key.Key_Left:
                        # Seek backward
                        pos = self.media_player.position()
                        new_pos = max(0, pos - self.wheel_seek_ms)
                        self.media_player.setPosition(new_pos)
                        return True
                    elif event.key() == Qt.Key.Key_Escape:
                        if (
                            self.player_container
                            and self.player_container.isFullScreen()
                        ):
                            self.toggle_fullscreen()
                            return True

        if self.player_container and obj is self.player_container:
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    if self.player_container.isFullScreen():
                        self.toggle_fullscreen()
                        return True
            if event.type() == QEvent.Type.Resize:
                if self.video_view.isVisible():
                    self.fit_video_in_view()

        return super().eventFilter(obj, event)

    def fit_video_in_view(self):
        rect = self.video_view.viewport().rect()
        self.video_item.setSize(rect.size())
        self.video_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)

    def toggle_fullscreen(self):
        if self.player_container.isFullScreen():
            self.player_container.setWindowFlags(Qt.Widget)
            self.player_container.showNormal()
            self.player_layout_container.addWidget(self.player_container)
            self.change_resolution(self.combo_resolution.currentIndex())
        else:
            self.player_container.setWindowFlags(Qt.WindowType.Window)
            self.player_container.showFullScreen()
            self.video_view.setFixedSize(16777215, 16777215)
            self.video_view.setMinimumSize(0, 0)
            self.video_view.setMaximumSize(16777215, 16777215)
            self.player_container.setFocus()

    @Slot(QResizeEvent)
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        if self.video_view.isVisible():
            self.fit_video_in_view()

    @Slot(int)
    def change_resolution(self, index: int):
        if not self.player_container.isFullScreen() and 0 <= index < len(
            self.available_resolutions
        ):
            w, h = self.available_resolutions[index]
            # --- NEW: Swap dimensions if vertical checkbox is checked ---
            if self.check_player_vertical.isChecked():
                w, h = h, w
            # -----------------------------------------------------------
            self.video_view.setFixedSize(w, h)
            self.fit_video_in_view()

    def is_path_selected(self, path: str) -> bool:
        return path in self.selected_paths

    # --- Gallery & Selection Logic (Extracted Frames) ---
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # Assign custom styling method for the Base class to call
        container.set_selected_style = lambda selected: self._style_label(
            clickable_label, selected
        )

        clickable_label = ClickableLabel(file_path=path)
        clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        clickable_label.setAlignment(Qt.AlignCenter)
        clickable_label.path = path

        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            clickable_label.setPixmap(scaled)
            clickable_label.setText("")

            if is_video:
                clickable_label.setStyleSheet("border: 2px solid #3498db;")
            else:
                clickable_label.setStyleSheet("border: 1px solid #4f545c;")
        else:
            if is_video:
                clickable_label.setText("VIDEO")
                clickable_label.setStyleSheet(
                    "border: 1px solid #2980b9; color: #2980b9; font-weight: bold;"
                )
            else:
                clickable_label.setText("Loading...")
                clickable_label.setStyleSheet(
                    "border: 1px solid #4f545c; color: #888; font-size: 10px;"
                )

        self._style_label(clickable_label, selected=(path in self.selected_paths))

        clickable_label.path_clicked.connect(self.handle_thumbnail_single_click)
        clickable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        clickable_label.path_right_clicked.connect(self.show_image_context_menu)

        layout.addWidget(clickable_label)
        return container

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        clickable_label = widget.findChild(ClickableLabel)
        if clickable_label:
            is_video = clickable_label.path.lower().endswith(
                tuple(SUPPORTED_VIDEO_FORMATS)
            )

            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.thumbnail_size,
                    self.thumbnail_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                clickable_label.setPixmap(scaled)
                clickable_label.setText("")

                if is_video:
                    clickable_label.setStyleSheet("border: 2px solid #3498db;")
            else:
                if not is_video:
                    clickable_label.clear()
                    clickable_label.setText("Loading...")

            self._style_label(
                clickable_label, selected=(clickable_label.path in self.selected_paths)
            )

    def _style_label(self, label: ClickableLabel, selected: bool):
        is_video = label.path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        if selected:
            label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            if is_video:
                if label.text() == "VIDEO":
                    label.setStyleSheet(
                        "border: 1px solid #2980b9; color: #2980b9; font-weight: bold;"
                    )
                else:
                    label.setStyleSheet("border: 2px solid #3498db;")
            elif label.text() in ["Load Error", "Loading..."]:
                pass
            else:
                label.setStyleSheet("border: 1px solid #4f545c;")

    @Slot(str)
    def handle_thumbnail_single_click(self, image_path: str):
        mods = QApplication.keyboardModifiers()
        is_ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        if is_ctrl:
            if image_path in self.selected_paths:
                self.selected_paths.remove(image_path)
            else:
                self.selected_paths.add(image_path)
        else:
            self.selected_paths.clear()
            self.selected_paths.add(image_path)
        self.update_visual_selection()

    @Slot(set, bool)
    def handle_marquee_selection(self, marquee_selection: Set[str], is_ctrl: bool):
        if is_ctrl:
            self.selected_paths.update(marquee_selection)
        else:
            self.selected_paths = marquee_selection
        self.update_visual_selection()

    def update_visual_selection(self):
        if not self.gallery_container:
            return
        for label in self.gallery_container.findChildren(ClickableLabel):
            if hasattr(label, "path"):
                is_selected = label.path in self.selected_paths
                self._style_label(label, is_selected)

    @Slot(str)
    def handle_thumbnail_double_click(self, image_path: str):
        if image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            try:
                if os.name == "nt":
                    os.startfile(image_path)
                else:
                    subprocess.Popen(
                        ["xdg-open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                print(f"Error opening video: {e}")
            return

        for win in list(self.open_preview_windows):
            try:
                if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                    win.activateWindow()
                    return
            except RuntimeError:
                if win in self.open_preview_windows:
                    self.open_preview_windows.remove(win)

        all_paths_list = self.current_extracted_paths
        try:
            start_index = all_paths_list.index(image_path)
        except ValueError:
            all_paths_list = [image_path]
            start_index = 0

        window = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=all_paths_list,
            start_index=start_index,
        )
        window.path_changed.connect(self.update_preview_highlight)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.show()
        self.open_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        if path not in self.selected_paths:
            self.selected_paths = {path}
            self.update_visual_selection()

        count = len(self.selected_paths)
        menu = QMenu(self)

        # Extraction History Actions
        abs_path = str(Path(path).absolute())
        metadata = self.extraction_metadata.get(abs_path)
        if metadata:
            menu.addSection("🎬 Extraction Source")

            jump_start_act = QAction("Jump to Start", self)
            jump_start_act.triggered.connect(
                lambda: self._jump_to_extraction_start(metadata)
            )
            menu.addAction(jump_start_act)

            jump_end_act = QAction("Jump to End", self)
            jump_end_act.triggered.connect(
                lambda: self._jump_to_extraction_end(metadata)
            )
            menu.addAction(jump_end_act)

            reload_act = QAction("♻️ Reload Extraction Params", self)
            reload_act.setToolTip(
                "Sets player time, cuts, and engine configs to match this run."
            )
            reload_act.triggered.connect(lambda: self._reload_extraction(metadata))
            menu.addAction(reload_act)

            menu.addSeparator()

        if count == 1:
            if not path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                view_action = QAction("View Full Size", self)
                view_action.triggered.connect(
                    lambda: self.handle_thumbnail_double_click(path)
                )
                menu.addAction(view_action)
                menu.addSeparator()

        del_text = f"Delete {count} Items" if count > 1 else "Delete Item"
        delete_action = QAction(del_text, self)
        delete_action.triggered.connect(self.delete_selected_images)
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def _jump_to_extraction_start(self, metadata: dict):
        video_path = metadata.get("video_path")
        if video_path and os.path.exists(video_path):
            if video_path != self.video_path:
                self.load_media(video_path)
            self.media_player.setPosition(metadata.get("start_ms", 0))
            self.media_player.pause()

    def _jump_to_extraction_end(self, metadata: dict):
        video_path = metadata.get("video_path")
        if video_path and os.path.exists(video_path):
            if video_path != self.video_path:
                self.load_media(video_path)
            self.media_player.setPosition(metadata.get("end_ms", 0))
            self.media_player.pause()

    def _reload_extraction(self, metadata: dict):
        video_path = metadata.get("video_path")
        if video_path and os.path.exists(video_path):
            if video_path != self.video_path:
                self.load_media(video_path)

        # Reload Times
        self.start_time_ms = metadata.get("start_ms", 0)
        self.end_time_ms = metadata.get("end_ms", 0)
        self._update_range_labels()

        # Reload Cuts
        self.cuts_ms = metadata.get("cuts_ms", [])
        self._update_cuts_label()

        # Reload Tags
        self.tags_ms = metadata.get("tags_ms", [])
        self._update_tags_ui()

        # Reload Configs
        self.combo_extract_size.setCurrentText(metadata.get("output_size", "Native"))
        self.check_extract_vertical.setChecked(metadata.get("extract_vertical", False))
        self.spin_gif_fps.setValue(metadata.get("gif_fps", 24))
        self.check_mute_audio.setChecked(metadata.get("mute_audio", False))
        self.combo_engine.setCurrentText(metadata.get("engine", "FFmpeg"))
        self.spin_interval.setValue(metadata.get("frame_interval", 1))
        self.check_smart_extract.setChecked(metadata.get("smart_extract", False))
        self.combo_smart_method.setCurrentText(
            metadata.get("smart_method", "mpdecimate (De-duplicate)")
        )
        if "speed" in metadata:
            self.combo_speed.setCurrentText(str(metadata["speed"]))

        self.media_player.setPosition(self.start_time_ms)
        self.media_player.pause()
        self.extraction_status_label.setText("Reloaded extraction parameters.")
        self.extraction_status_label.show()

    def delete_selected_images(self):
        if not self.selected_paths:
            return

        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        confirm = QMessageBox.question(
            self,
            f"Confirm {action_name}",
            f"Are you sure you want to move {len(self.selected_paths)} items to {action_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            failed = []
            paths_to_delete = list(self.selected_paths)
            layout_changed = False

            widgets_to_delete = []

            for path in paths_to_delete:
                try:
                    if send_to_trash_enabled:
                        from send2trash import send2trash

                        send2trash(path)
                    else:
                        import os

                        os.remove(path)
                    if path in self.current_extracted_paths:
                        self.current_extracted_paths.remove(path)
                    if path in self.gallery_image_paths:
                        self.gallery_image_paths.remove(path)

                    if path in self.path_to_card_widget:
                        widget = self.path_to_card_widget.pop(path)
                        if widget:
                            widgets_to_delete.append(widget)
                            layout_changed = True

                except Exception as e:
                    failed.append(f"{Path(path).name}: {e}")

            self.selected_paths.clear()

            if layout_changed:
                for widget in widgets_to_delete:
                    self.gallery_layout.removeWidget(widget)
                    widget.deleteLater()

                cols = self.common_calculate_columns(
                    self.gallery_scroll_area, self.approx_item_width
                )
                self.common_reflow_layout(self.gallery_layout, cols)
                self._update_pagination_ui()

            if failed:
                QMessageBox.warning(self, "Partial Deletion Failure", "\n".join(failed))

    def delete_image(self, path: str):
        if path not in self.selected_paths:
            self.selected_paths = {path}
        self.delete_selected_images()

    @Slot()
    def toggle_player_mode(self):
        self.use_internal_player = not self.use_internal_player
        self._apply_player_mode()

    def _apply_player_mode(self):
        if not self.video_path:
            return
        ext = Path(self.video_path).suffix.lower()
        if ext == ".gif":
            return
        self.media_player.setSource(QUrl.fromLocalFile(self.video_path))

        if self.use_internal_player:
            self.btn_toggle_mode.setText("Switch to External Player")
            self.btn_toggle_mode.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon)
            )
            self.info_label.setVisible(False)
            self.combo_resolution.setEnabled(True)
            self.video_view.setVisible(True)
            self.btn_play.setVisible(True)
            self.btn_fullscreen.setVisible(True)
            self.lbl_vol.setVisible(True)
            self.volume_slider.setVisible(True)
            self.btn_play.setEnabled(True)
            self.media_player.setVideoOutput(self.video_item)
            self.media_player.setAudioOutput(self.audio_output)
            self.change_resolution(self.combo_resolution.currentIndex())
        else:
            self.btn_toggle_mode.setText("Switch to Internal Player")
            self.btn_toggle_mode.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
            )
            self.info_label.setVisible(True)
            self.combo_resolution.setEnabled(False)
            self.video_view.setVisible(False)
            self.btn_play.setVisible(False)
            self.btn_fullscreen.setVisible(False)
            self.lbl_vol.setVisible(False)
            self.volume_slider.setVisible(False)
            self.media_player.setVideoOutput(None)
            self.media_player.setAudioOutput(None)
            self.media_player.setAudioOutput(None)
            self.media_player.pause()

        # Apply current speed locally
        self.update_playback_speed(self.combo_player_speed.currentText())

    @Slot(str)
    def update_playback_speed(self, text: str):
        speed_str = text.replace("x", "")
        try:
            speed = float(speed_str)
        except ValueError:
            speed = 1.0

        # QMediaPlayer.setPlaybackRate introduced in Qt6
        self.media_player.setPlaybackRate(speed)

    @Slot()
    def toggle_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
        else:
            self.media_player.play()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
            )

    @Slot(int)
    def position_changed(self, position: int):
        self.slider.setValue(position)
        self.lbl_current_time.setText(self._format_time(position))

    @Slot(int)
    def duration_changed(self, duration: int):
        self.duration_ms = duration
        self.slider.setRange(0, duration)
        self.lbl_total_time.setText(self._format_time(duration))

    @Slot(int)
    def set_position(self, position: int):
        self.media_player.setPosition(position)

    @Slot(QMediaPlayer.Error, str)
    def handle_player_error(self, error: QMediaPlayer.Error, error_string: str):
        if self.use_internal_player:
            self.btn_play.setEnabled(False)
            QMessageBox.critical(
                self, "Video Error", f"Media Player Error: {error_string}"
            )

    # --- Extraction Logic ---
    def _update_range_labels(self):
        """Updates the text and enabled state of range-related buttons."""
        start_str = self._format_time(self.start_time_ms)
        end_str = self._format_time(self.end_time_ms)

        self.btn_set_start.setText(f"Start: {start_str}")
        self.btn_set_end.setText(f"End: {end_str}")

        self.btn_snapshot.setText(f"📸 Snapshot at {start_str}")
        self.btn_snapshot.setEnabled(True)
        self.btn_jump_start.setEnabled(True)
        self.btn_jump_end.setEnabled(True)

        self._validate_range()

    @Slot()
    def set_range_start(self):
        self.start_time_ms = self.media_player.position()
        self._update_range_labels()

    @Slot()
    def set_range_end(self):
        self.end_time_ms = self.media_player.position()
        self._update_range_labels()

    @Slot()
    def set_cut_start(self):
        self.cut_start_ms = self.media_player.position()
        time_str = self._format_time(self.cut_start_ms)
        self.btn_set_cut_start.setText(f"Cut Start: {time_str}")
        self._validate_cut_range()

    @Slot()
    def set_cut_end(self):
        self.cut_end_ms = self.media_player.position()
        time_str = self._format_time(self.cut_end_ms)
        self.btn_set_cut_end.setText(f"Cut End: {time_str}")
        self._validate_cut_range()

    def _validate_cut_range(self):
        if self.cut_end_ms > self.cut_start_ms:
            self.btn_add_cut.setEnabled(True)
        else:
            self.btn_add_cut.setEnabled(False)

    @Slot()
    def add_cut(self):
        if self.cut_end_ms > self.cut_start_ms:
            self.cuts_ms.append((self.cut_start_ms, self.cut_end_ms))
            self.cut_start_ms = 0
            self.cut_end_ms = 0
            self.btn_set_cut_start.setText("Set Cut Start [00:00]")
            self.btn_set_cut_end.setText("Set Cut End [00:00]")
            self.btn_add_cut.setEnabled(False)
            self._update_cuts_label()

    @Slot()
    def clear_cuts(self):
        self.cuts_ms.clear()
        self._update_cuts_label()

    def _update_cuts_label(self):
        # Clear existing cut labels
        while self.cuts_layout.count():
            item = self.cuts_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.cuts_ms:
            none_label = QLabel("Cuts: None")
            none_label.setStyleSheet("color: #666; font-style: italic;")
            self.cuts_layout.addWidget(none_label)
            self.btn_clear_cuts.setEnabled(False)
        else:
            self.btn_clear_cuts.setEnabled(True)
            self.cuts_layout.addWidget(QLabel("Cuts:"))
            for i, (s, e) in enumerate(self.cuts_ms):
                cut_text = f"[{self._format_time(s)}-{self._format_time(e)}]"
                label = CutLabel(cut_text, i)
                label.right_clicked.connect(self.show_cut_context_menu)
                self.cuts_layout.addWidget(label)

        self.cuts_layout.addStretch()
        self._validate_range()

    @Slot(QPoint, int)
    def show_cut_context_menu(self, global_pos: QPoint, index: int):
        menu = QMenu(self)

        edit_start_action = QAction("Edit Start Timestamp", self)
        edit_start_action.triggered.connect(
            lambda: self.edit_cut_timestamp(index, is_start=True)
        )
        menu.addAction(edit_start_action)

        edit_end_action = QAction("Edit End Timestamp", self)
        edit_end_action.triggered.connect(
            lambda: self.edit_cut_timestamp(index, is_start=False)
        )
        menu.addAction(edit_end_action)

        menu.addSeparator()

        jump_start_action = QAction("Jump to Start", self)
        jump_start_action.triggered.connect(
            lambda: self.jump_to_cut_time(index, is_start=True)
        )
        menu.addAction(jump_start_action)

        jump_end_action = QAction("Jump to End", self)
        jump_end_action.triggered.connect(
            lambda: self.jump_to_cut_time(index, is_start=False)
        )
        menu.addAction(jump_end_action)

        menu.addSeparator()

        delete_action = QAction("Delete Cut", self)
        delete_action.triggered.connect(lambda: self.delete_cut(index))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def edit_cut_timestamp(self, index: int, is_start: bool):
        if 0 <= index < len(self.cuts_ms):
            current_start, current_end = self.cuts_ms[index]
            current_val = current_start if is_start else current_end
            formatted = self._format_time(current_val)

            label_text = (
                "New Start Time (MM:SS:mmm):"
                if is_start
                else "New End Time (MM:SS:mmm):"
            )
            new_time_str, ok = QInputDialog.getText(
                self, "Edit Cut", label_text, text=formatted
            )

            if ok and new_time_str:
                new_ms = self._parse_time(new_time_str)
                if new_ms is not None:
                    if is_start:
                        if new_ms < current_end:
                            self.cuts_ms[index] = (new_ms, current_end)
                        else:
                            QMessageBox.warning(
                                self,
                                "Invalid Time",
                                "Start time must be before end time.",
                            )
                    else:
                        if new_ms > current_start:
                            self.cuts_ms[index] = (current_start, new_ms)
                        else:
                            QMessageBox.warning(
                                self,
                                "Invalid Time",
                                "End time must be after start time.",
                            )
                    self._update_cuts_label()
                else:
                    QMessageBox.warning(
                        self,
                        "Invalid Format",
                        "Please use MM:SS:mmm, MM:SS, or SS formats.",
                    )

    def jump_to_cut_time(self, index: int, is_start: bool):
        if 0 <= index < len(self.cuts_ms):
            ms = self.cuts_ms[index][0] if is_start else self.cuts_ms[index][1]
            self.media_player.setPosition(ms)

    def delete_cut(self, index: int):
        if 0 <= index < len(self.cuts_ms):
            self.cuts_ms.pop(index)
            self._update_cuts_label()

    # --- Tags Logic ---
    @Slot()
    def add_tag(self):
        current_ms = self.media_player.position()
        formatted = self._format_time(current_ms)

        proposed_name = f"Tag {len(self.tags_ms) + 1}"
        label, ok = QInputDialog.getText(
            self, "Add Tag", f"Enter label for tag at {formatted}:", text=proposed_name
        )
        if ok and label:
            self.tags_ms.append((current_ms, label))
            self.tags_ms.sort(key=lambda x: x[0])  # Keep sorted by time
            self._update_tags_ui()

    @Slot()
    def clear_tags(self):
        self.tags_ms.clear()
        self._update_tags_ui()

    def _update_tags_ui(self):
        # Clear existing tag labels
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self.tags_ms:
            none_label = QLabel("Tags: None")
            none_label.setStyleSheet("color: #666; font-style: italic;")
            self.tags_layout.addWidget(none_label)
            self.btn_clear_tags.setEnabled(False)
        else:
            self.btn_clear_tags.setEnabled(True)
            self.tags_layout.addWidget(QLabel("Tags:"))
            for i, (ms, label_text) in enumerate(self.tags_ms):
                tag_display = f"{label_text} ({self._format_time(ms)})"
                label = TagLabel(tag_display, ms, i)
                label.clicked.connect(self.jump_to_tag_time)
                label.double_clicked.connect(self.jump_to_tag_time)
                label.right_clicked.connect(self.show_tag_context_menu)
                self.tags_layout.addWidget(label)

        self.tags_layout.addStretch()

        has_tags = len(self.tags_ms) > 0
        self.btn_clear_tags.setEnabled(has_tags)

    @Slot(QPoint)
    def show_video_context_menu(self, pos: QPoint):
        """Show a context menu on the video player or slider with tag jumping and other options."""
        sender = self.sender()
        if not sender:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1e1f22; color: white; border: 1px solid #4f545c; }"
        )

        # 1. Jump to Tag Submenu
        if self.tags_ms:
            jump_menu = menu.addMenu("📍 Jump to Tag")
            jump_menu.setStyleSheet(
                "QMenu { background-color: #1e1f22; color: #FFC107; }"
            )
            for ms, label in self.tags_ms:
                action = QAction(f"{label} ({self._format_time(ms)})", self)
                action.triggered.connect(lambda _, m=ms: self.jump_to_tag_time(m))
                jump_menu.addAction(action)
            menu.addSeparator()

        # 2. Add Tag at current pos
        add_tag_action = QAction("🏷️ Add Tag Here", self)
        add_tag_action.triggered.connect(self.add_tag)
        menu.addAction(add_tag_action)

        # 3. Range actions
        set_start_action = QAction("🎞️ Set Range Start", self)
        set_start_action.triggered.connect(self.set_range_start)
        menu.addAction(set_start_action)

        set_end_action = QAction("🎞️ Set Range End", self)
        set_end_action.triggered.connect(self.set_range_end)
        menu.addAction(set_end_action)

        menu.addSeparator()

        # 4. Extraction triggers (convenience)
        if self.end_time_ms > self.start_time_ms:
            extract_vid_action = QAction("🎬 Extract Video Range", self)
            extract_vid_action.triggered.connect(self.extract_range_as_video)
            menu.addAction(extract_vid_action)

        # Show at global position
        global_pos = sender.mapToGlobal(pos)
        menu.exec(global_pos)

    @Slot(int)
    def jump_to_tag_time(self, ms: int):
        self.media_player.setPosition(ms)
        self.media_player.pause()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )

    @Slot(QPoint, int)
    def show_tag_context_menu(self, global_pos: QPoint, index: int):
        menu = QMenu(self)

        jump_action = QAction("📍 Jump to Tag", self)
        jump_action.triggered.connect(
            lambda: self.jump_to_tag_time(self.tags_ms[index][0])
        )
        menu.addAction(jump_action)
        menu.addSeparator()

        edit_action = QAction("Edit Tag", self)
        edit_action.triggered.connect(lambda: self.edit_tag(index))
        menu.addAction(edit_action)

        delete_action = QAction("Delete Tag", self)
        delete_action.triggered.connect(lambda: self.delete_tag(index))
        menu.addAction(delete_action)

        menu.exec(global_pos)

    def edit_tag(self, index: int):
        if 0 <= index < len(self.tags_ms):
            ms, label = self.tags_ms[index]
            formatted_time = self._format_time(ms)

            new_label, ok = QInputDialog.getText(
                self, "Edit Tag", f"Label for tag at {formatted_time}:", text=label
            )
            if ok and new_label:
                # Also allow editing time? Let's just do label for now as it's easier.
                # Actually, editing time would be good too.
                new_time_str, ok_time = QInputDialog.getText(
                    self,
                    "Edit Tag Time",
                    f"Time for '{new_label}':",
                    text=formatted_time,
                )
                if ok_time and new_time_str:
                    new_ms = self._parse_time(new_time_str)
                    if new_ms is not None:
                        self.tags_ms[index] = (new_ms, new_label)
                        self.tags_ms.sort(key=lambda x: x[0])
                        self._update_tags_ui()
                    else:
                        QMessageBox.warning(
                            self, "Invalid Format", "Invalid time format."
                        )

    def delete_tag(self, index: int):
        if 0 <= index < len(self.tags_ms):
            self.tags_ms.pop(index)
            self._update_tags_ui()

    def _validate_range(self):
        if self.end_time_ms > self.start_time_ms:
            total_duration_ms = self.end_time_ms - self.start_time_ms

            # Subtract cut durations
            cut_duration_ms = 0
            for c_start, c_end in self.cuts_ms:
                overlap_start = max(self.start_time_ms, c_start)
                overlap_end = min(self.end_time_ms, c_end)
                if overlap_end > overlap_start:
                    cut_duration_ms += overlap_end - overlap_start

            actual_duration_ms = max(0, total_duration_ms - cut_duration_ms)
            duration_str = self._format_time(actual_duration_ms)

            self.btn_extract_range.setEnabled(True)
            self.btn_extract_range.setText(f"Extract Range ({duration_str})")
            self.btn_extract_gif.setEnabled(True)
            self.btn_extract_gif.setText(f"GIF Extract as GIF ({duration_str})")
            self.btn_extract_video.setEnabled(True)
            self.btn_extract_video.setText(f"MP4 Extract as Video ({duration_str})")
        else:
            self.btn_extract_range.setEnabled(False)
            self.btn_extract_range.setText("🎞️ Extract Range")
            self.btn_extract_gif.setEnabled(False)
            self.btn_extract_gif.setText("GIF Extract as GIF")
            self.btn_extract_video.setEnabled(False)
            self.btn_extract_video.setText("MP4 Extract as Video")

    @Slot()
    def jump_to_range_start(self):
        self.media_player.setPosition(self.start_time_ms)
        # Pause to let user see exactly where they are? Or keep playing?
        # Usually pausing is better when jumping to specific frame.
        self.media_player.pause()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )

    @Slot()
    def jump_to_range_end(self):
        self.media_player.setPosition(self.end_time_ms)
        self.media_player.pause()
        self.btn_play.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )

    # --- NEW HELPER: Resolution Swapping ---
    def _get_target_size(self) -> Optional[Tuple[int, int]]:
        selected_key = self.combo_extract_size.currentText()
        target_size = self.extraction_res_map.get(selected_key)
        if selected_key == "Native":
            if self.video_path and os.path.exists(self.video_path):
                cap = cv2.VideoCapture(self.video_path)
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cap.release()
                if w > 0 and h > 0:
                    target_size = (w, h)
                else:
                    target_size = None
            else:
                target_size = None
        # If vertical output is checked, flip dimensions
        if target_size and self.check_extract_vertical.isChecked():
            return (target_size[1], target_size[0])
        return target_size

    # ---------------------------------------

    @Slot()
    def extract_single_frame(self):
        if not self.video_path:
            return

        # Pause player if running
        if (
            self.use_internal_player
            and self.media_player.playbackState()
            == QMediaPlayer.PlaybackState.PlayingState
        ):
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )

        # Use current player position as starting point if possible
        start_ms = (
            self.media_player.position()
            if self.use_internal_player
            else self.start_time_ms
        )

        dlg = FrameSelectionDialog(self.video_path, start_ms=start_ms, parent=self)
        if dlg.exec() == QDialog.Accepted:
            timestamp_ms = int(dlg.selected_frame_idx / dlg.fps * 1000)
            if self.extraction_queue_enabled:
                config = {
                    "type": "single",
                    "video_path": self.video_path,
                    "start_ms": timestamp_ms,
                    "end_ms": timestamp_ms,
                    "output_dir": str(self.extraction_dir),
                    "target_resolution": self._get_target_size(),
                    "cuts_ms": [],
                    "frame_interval": 1,
                    "smart_extract": False,
                    "smart_method": "",
                    "fps": getattr(dlg, "fps", 23.976),
                    "mute_audio": False,
                    "use_ffmpeg": True,
                    "speed": "1.0",
                }
                self.extraction_queue.append(config)
                self._update_queue_ui()
                self.extraction_status_label.setText(
                    f"Added snapshot to queue. Queue size: {len(self.extraction_queue)}"
                )
                self.extraction_status_label.show()
                return

            if dlg.selected_image:
                self.extraction_status_label.setText("Saving snapshot...")
                self.extraction_status_label.show()
                self.qml_extraction_status.emit("Saving snapshot...")

                # Use target size logic if not "Native"
                target_size = self._get_target_size()
                img = dlg.selected_image
                if target_size:
                    img = img.scaled(
                        target_size[0],
                        target_size[1],
                        Qt.IgnoreAspectRatio,
                        Qt.SmoothTransformation,
                    )

                filename = f"{Path(self.video_path).stem}_snap_{timestamp_ms}ms.png"
                out_path = self.extraction_dir / filename

                if img.save(str(out_path)):
                    self.extraction_status_label.setText(f"Snapshot saved: {filename}")
                    self.extraction_status_label.show()

                    # Record metadata
                    metadata = self._get_current_extraction_metadata()
                    metadata["mode"] = "snapshot"
                    metadata["start_ms"] = timestamp_ms
                    metadata["end_ms"] = timestamp_ms
                    metadata["fps"] = getattr(dlg, "fps", 23.976)
                    self._record_extraction([str(out_path)], metadata)

                    # Update cache and refresh the source label style
                    self._refresh_extracted_stems_cache()
                    if self.video_path in self.source_path_to_widget:
                        widget = self.source_path_to_widget[self.video_path]
                        label = widget.findChild(ClickableLabel)
                        if label:
                            self._update_source_label_style(
                                self.video_path, label, True
                            )

                    # Auto-refresh gallery if needed
                    self.scan_directory(str(self.extraction_dir))
                else:
                    QMessageBox.critical(self, "Error", "Failed to save snapshot.")

    def _set_extraction_buttons_enabled(self, enabled: bool):
        """Helper to enable/disable all extraction-related buttons."""
        self.btn_snapshot.setEnabled(enabled and self.video_path is not None)
        self.btn_set_start.setEnabled(enabled and self.video_path is not None)
        self.btn_set_end.setEnabled(enabled and self.video_path is not None)
        self.btn_set_cut_start.setEnabled(enabled and self.video_path is not None)
        self.btn_set_cut_end.setEnabled(enabled and self.video_path is not None)

        # We handle btn_add_cut and btn_clear_cuts logic independently based on internal states
        # but if we disable extraction entirely, disable those too
        if not enabled:
            self.btn_add_cut.setEnabled(False)
            self.btn_clear_cuts.setEnabled(False)
        else:
            self._validate_cut_range()
            self._update_cuts_label()

        self.btn_extract_range.setEnabled(
            enabled and self.end_time_ms > self.start_time_ms
        )
        self.btn_extract_gif.setEnabled(
            enabled and self.end_time_ms > self.start_time_ms
        )
        self.btn_extract_video.setEnabled(
            enabled and self.end_time_ms > self.start_time_ms
        )

        # Also disable browsing while extracting to avoid path changes
        self.btn_browse.setEnabled(enabled)
        self.btn_browse_extract.setEnabled(enabled)

        # Show/hide action buttons vs cancel button
        self.btn_extract_range.setVisible(enabled)
        self.btn_extract_video.setVisible(enabled)
        self.btn_extract_gif.setVisible(enabled)

        self.btn_cancel_extraction.setVisible(not enabled)
        if not enabled:
            self.btn_cancel_extraction.setEnabled(True)

    @Slot()
    def cancel_extraction(self, enabled: bool = True):
        if self.active_extraction_worker:
            self.active_extraction_worker.cancel()
            self.active_extraction_worker = None

        # The worker returns without emitting finished/error on cancellation, so
        # re-enable the UI here rather than waiting for a signal that never arrives.
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()
        self.line_edit_dir.setEnabled(True)
        self.btn_add_tag.setEnabled(self.video_path is not None)
        self.btn_clear_tags.setEnabled(len(self.tags_ms) > 0)

    @Slot()
    def extract_range(self):
        if not self.video_path:
            return
        if self.use_internal_player:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
        self._run_extraction(self.start_time_ms, self.end_time_ms, is_range=True)

    @Slot()
    def extract_range_as_gif(self):
        if not self.video_path:
            return
        if self.use_internal_player:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
        self._run_gif_extraction(self.start_time_ms, self.end_time_ms)

    @Slot()
    def extract_range_as_video(self):
        if not self.video_path:
            return
        if self.use_internal_player:
            self.media_player.pause()
            self.btn_play.setIcon(
                self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
            )
        self._run_video_extraction(self.start_time_ms, self.end_time_ms)

    def _run_extraction(self, start: int, end: int, is_range: bool):
        target_size = self._get_target_size()

        if self.extraction_queue_enabled:
            config = {
                "type": "range" if is_range else "single",
                "video_path": self.video_path,
                "start_ms": start,
                "end_ms": end,
                "output_dir": str(self.extraction_dir),
                "target_resolution": target_size,
                "cuts_ms": self.cuts_ms[:],
                "frame_interval": self.spin_interval.value(),
                "smart_extract": self.check_smart_extract.isChecked(),
                "smart_method": self.combo_smart_method.currentText(),
                "fps": 23.976,
                "mute_audio": False,
                "use_ffmpeg": True,
                "speed": 1.0,
            }
            self.extraction_queue.append(config)
            self._update_queue_ui()
            self.extraction_status_label.setText(
                f"Added frame range to queue. Queue size: {len(self.extraction_queue)}"
            )
            self.extraction_status_label.show()
            return

        self._set_extraction_buttons_enabled(False)
        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText("Extracting frames...")
        self.extraction_status_label.show()

        self._active_metadata = self._get_current_extraction_metadata()
        self._active_metadata["mode"] = "range" if is_range else "single"

        self.active_extraction_worker = FrameExtractionWorker(
            video_path=self.video_path,
            output_dir=str(self.extraction_dir),
            start_ms=start,
            end_ms=end,
            is_range=is_range,
            target_resolution=target_size,
            cuts_ms=self.cuts_ms,
            frame_interval=self.spin_interval.value(),
            smart_extract=self.check_smart_extract.isChecked(),
            smart_method=self.combo_smart_method.currentText(),
        )
        self.active_extraction_worker.signals.progress.connect(
            self.extraction_progress_bar.setValue
        )
        self.active_extraction_worker.signals.finished.connect(
            self._on_extraction_finished
        )
        self.active_extraction_worker.signals.error.connect(
            lambda e: self._on_extraction_error(e)
        )
        QThreadPool.globalInstance().start(self.active_extraction_worker)

    def _on_extraction_error(self, error_msg: str):
        self.active_extraction_worker = None
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()
        self._active_metadata = None
        if "cancelled" not in error_msg.lower():
            QMessageBox.warning(self, "Extraction Error", error_msg)

    def _run_gif_extraction(self, start: int, end: int):
        target_size = self._get_target_size()
        fps = self.spin_gif_fps.value()

        # Speed
        speed_str = self.combo_speed.currentText().replace("x", "")
        try:
            speed = float(speed_str)
        except ValueError:
            speed = 1.0

        if self.extraction_queue_enabled:
            config = {
                "type": "gif",
                "video_path": self.video_path,
                "start_ms": start,
                "end_ms": end,
                "output_dir": str(self.extraction_dir),
                "target_resolution": target_size,
                "cuts_ms": self.cuts_ms[:],
                "frame_interval": 1,
                "smart_extract": False,
                "smart_method": "",
                "fps": fps,
                "mute_audio": False,
                "use_ffmpeg": (self.combo_engine.currentText() == "FFmpeg"),
                "speed": speed,
            }
            self.extraction_queue.append(config)
            self._update_queue_ui()
            self.extraction_status_label.setText(
                f"Added GIF extract to queue. Queue size: {len(self.extraction_queue)}"
            )
            self.extraction_status_label.show()
            return

        self._set_extraction_buttons_enabled(False)
        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText(
            "Generating GIF... This may take a moment."
        )
        self.extraction_status_label.show()

        self._active_metadata = self._get_current_extraction_metadata()
        self._active_metadata["mode"] = "gif"

        output_name = f"{Path(self.video_path).stem}_{int(start)}ms_{int(end)}ms.gif"
        output_path = str(self.extraction_dir / output_name)

        self.active_extraction_worker = GifCreationWorker(
            video_path=self.video_path,
            start_ms=start,
            end_ms=end,
            output_path=output_path,
            target_size=target_size,
            fps=fps,
            use_ffmpeg=(self.combo_engine.currentText() == "FFmpeg"),
            speed=speed,
            cuts_ms=self.cuts_ms,
        )
        self.active_extraction_worker.signals.progress.connect(
            self.extraction_progress_bar.setValue
        )
        self.active_extraction_worker.signals.finished.connect(self._on_export_finished)
        self.active_extraction_worker.signals.error.connect(self._on_export_error)
        QThreadPool.globalInstance().start(self.active_extraction_worker)

    def _run_video_extraction(self, start: int, end: int):
        target_size = self._get_target_size()
        mute_audio = self.check_mute_audio.isChecked()

        # Speed
        speed_str = self.combo_speed.currentText().replace("x", "")
        try:
            speed = float(speed_str)
        except ValueError:
            speed = 1.0

        if self.extraction_queue_enabled:
            config = {
                "type": "video",
                "video_path": self.video_path,
                "start_ms": start,
                "end_ms": end,
                "output_dir": str(self.extraction_dir),
                "target_resolution": target_size,
                "cuts_ms": self.cuts_ms[:],
                "frame_interval": 1,
                "smart_extract": False,
                "smart_method": "",
                "fps": 23.976,
                "mute_audio": mute_audio,
                "use_ffmpeg": (self.combo_engine.currentText() == "FFmpeg"),
                "speed": speed,
            }
            self.extraction_queue.append(config)
            self._update_queue_ui()
            self.extraction_status_label.setText(
                f"Added video extract to queue. Queue size: {len(self.extraction_queue)}"
            )
            self.extraction_status_label.show()
            return

        self._set_extraction_buttons_enabled(False)
        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText(
            "Extracting video clip... This may take a moment."
        )
        self.extraction_status_label.show()

        self._active_metadata = self._get_current_extraction_metadata()
        self._active_metadata["mode"] = "video"

        output_name = f"{Path(self.video_path).stem}_{int(start)}ms_{int(end)}ms.mp4"
        output_path = str(self.extraction_dir / output_name)

        self.active_extraction_worker = VideoExtractionWorker(
            video_path=self.video_path,
            start_ms=start,
            end_ms=end,
            output_path=output_path,
            target_size=target_size,
            mute_audio=mute_audio,
            use_ffmpeg=(self.combo_engine.currentText() == "FFmpeg"),
            speed=speed,
            cuts_ms=self.cuts_ms,
        )
        self.active_extraction_worker.signals.progress.connect(
            self.extraction_progress_bar.setValue
        )
        self.active_extraction_worker.signals.finished.connect(self._on_export_finished)
        self.active_extraction_worker.signals.error.connect(self._on_export_error)
        QThreadPool.globalInstance().start(self.active_extraction_worker)

    @Slot(str)
    def _on_export_finished(self, new_path: str):
        self.active_extraction_worker = None
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        if new_path and os.path.exists(new_path):
            if new_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                thumb = self._generate_video_thumbnail(new_path)
                if thumb:
                    self._initial_pixmap_cache[new_path] = thumb.toImage()

            # Base class handles list management and loading
            self.start_loading_gallery([new_path], append=True)

            # Keep local list synced
            self.current_extracted_paths = self.gallery_image_paths[:]

            if self._active_metadata:
                self._record_extraction([new_path], self._active_metadata)
            self._active_metadata = None

            QMessageBox.information(
                self, "Success", f"Media created successfully:\n{Path(new_path).name}"
            )

    @Slot(str)
    def _on_export_error(self, error_msg: str):
        self.active_extraction_worker = None
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()
        self._active_metadata = None
        if "cancelled" not in error_msg.lower():
            QMessageBox.warning(self, "Export Error", error_msg)

    def _generate_video_thumbnail(self, path: str) -> Optional[QPixmap]:
        """Generate a thumbnail for a single video file."""
        thumbnailer = VideoThumbnailer()
        q_image = thumbnailer.generate(path, self.thumbnail_size)

        if q_image and not q_image.isNull():
            return QPixmap.fromImage(q_image)
        return None

    @Slot(list)
    def _on_extraction_finished(self, new_paths: List[str]):
        if self._active_metadata and new_paths:
            if self.active_extraction_worker and hasattr(
                self.active_extraction_worker, "fps"
            ):
                self._active_metadata["fps"] = self.active_extraction_worker.fps
            self._record_extraction(new_paths, self._active_metadata)

            # Update cache and refresh the source label style
            self._refresh_extracted_stems_cache()
            if self.video_path in self.source_path_to_widget:
                widget = self.source_path_to_widget[self.video_path]
                label = widget.findChild(ClickableLabel)
                if label:
                    self._update_source_label_style(self.video_path, label, True)

        self._active_metadata = None

        self.active_extraction_worker = None
        self._set_extraction_buttons_enabled(True)
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        if not new_paths:
            QMessageBox.information(self, "Info", "No frames extracted.")
            return

        self.start_loading_gallery(new_paths, append=True)
        self.current_extracted_paths = self.gallery_image_paths[:]

        for path, widget in self.source_path_to_widget.items():
            label = widget.findChild(ClickableLabel)
            if label:
                self._update_source_label_style(
                    path, label, path == getattr(self, "video_path", None)
                )

        QMessageBox.information(
            self,
            "Success",
            f"Extracted {len(new_paths)} images. Total: {len(self.current_extracted_paths)}",
        )

    def _get_current_extraction_metadata(self) -> dict:
        """Collects current UI state as metadata for an extraction run."""
        return {
            "video_path": str(self.video_path),
            "start_ms": self.start_time_ms,
            "end_ms": self.end_time_ms,
            "cuts_ms": self.cuts_ms[:],
            "tags_ms": self.tags_ms[:],
            "output_size": self.combo_extract_size.currentText(),
            "extract_vertical": self.check_extract_vertical.isChecked(),
            "gif_fps": self.spin_gif_fps.value(),
            "mute_audio": self.check_mute_audio.isChecked(),
            "engine": self.combo_engine.currentText(),
            "frame_interval": self.spin_interval.value(),
            "smart_extract": self.check_smart_extract.isChecked(),
            "smart_method": self.combo_smart_method.currentText(),
            "speed": self.combo_speed.currentText(),
            "timestamp": time.time(),
        }

    def _format_time(self, ms: int) -> str:
        fmt = getattr(self, "time_display_format", "m:s:ms")
        if fmt == "h:m:s":
            hours = ms // 3600000
            minutes = (ms // 60000) % 60
            seconds = (ms // 1000) % 60
            return f"{hours:02}:{minutes:02}:{seconds:02}"
        elif fmt == "microseconds":
            return f"{ms * 1000}"
        elif fmt == "milliseconds":
            return f"{ms}"
        else:  # default "m:s:ms"
            seconds = (ms // 1000) % 60
            minutes = (ms // 60000) % 60
            milliseconds = ms % 1000
            return f"{minutes:02}:{seconds:02}:{milliseconds:03}"

    def _parse_time(self, time_str: str) -> Optional[int]:
        """Parses various formats (MM:SS:mmm, HH:MM:SS, pure milliseconds, or microseconds) into milliseconds."""
        try:
            time_str = time_str.strip()
            # If digit only, parse as number of units based on current format
            if time_str.isdigit():
                val = int(time_str)
                fmt = getattr(self, "time_display_format", "m:s:ms")
                if fmt == "microseconds":
                    return val // 1000
                elif fmt == "milliseconds":
                    return val
                else:
                    if val > 100000000:
                        return val // 1000
                    return val

            parts = time_str.replace(",", ".").split(":")
            fmt = getattr(self, "time_display_format", "m:s:ms")
            if len(parts) == 3:
                if fmt == "h:m:s":
                    h, m, s = parts
                    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000
                else:
                    m, s, ms = parts
                    return int(m) * 60000 + int(s) * 1000 + int(ms)
            elif len(parts) == 2:
                # MM:SS or SS.mmm
                if "." in parts[1]:
                    m, s_ms = parts
                    s, ms = s_ms.split(".")
                    return int(m) * 60000 + int(s) * 1000 + int(ms.ljust(3, "0")[:3])
                else:
                    m, s = parts
                    return int(m) * 60000 + int(s) * 1000
            elif len(parts) == 1:
                # SS or SS.mmm
                if "." in parts[0]:
                    s, ms = parts[0].split(".")
                    return int(s) * 1000 + int(ms.ljust(3, "0")[:3])
                else:
                    return int(parts[0]) * 1000
        except Exception:
            pass
        return None

    def refresh_time_display(self):
        if self.media_player:
            pos = self.media_player.position()
            dur = self.media_player.duration()
            if self.lbl_current_time:
                self.lbl_current_time.setText(self._format_time(pos))
            if self.lbl_total_time:
                self.lbl_total_time.setText(self._format_time(dur))

        # Update start, end, cut_start, and cut_end buttons
        if hasattr(self, "btn_set_start") and self.btn_set_start:
            self.btn_set_start.setText(
                f"Start [{self._format_time(self.start_time_ms)}]"
                if self.start_time_ms
                else "Set Start [00:00]"
            )
        if hasattr(self, "btn_set_end") and self.btn_set_end:
            self.btn_set_end.setText(
                f"End [{self._format_time(self.end_time_ms)}]"
                if self.end_time_ms
                else "Set End [00:00]"
            )
        if hasattr(self, "btn_set_cut_start") and self.btn_set_cut_start:
            self.btn_set_cut_start.setText(
                f"Cut Start [{self._format_time(self.cut_start_ms)}]"
                if self.cut_start_ms
                else "Set Cut Start [00:00]"
            )
        if hasattr(self, "btn_set_cut_end") and self.btn_set_cut_end:
            self.btn_set_cut_end.setText(
                f"Cut End [{self._format_time(self.cut_end_ms)}]"
                if self.cut_end_ms
                else "Set Cut End [00:00]"
            )

        # Update cuts and tags UI list
        if hasattr(self, "_update_cuts_label"):
            self._update_cuts_label()
        if hasattr(self, "_update_tags_ui"):
            self._update_tags_ui()

    @Slot()
    def _jump_to_edited_time(self):
        time_str = self.edit_current_time.text()
        ms = self._parse_time(time_str)
        if ms is not None:
            # Clamp to duration
            ms = max(0, min(ms, self.media_player.duration()))
            self.media_player.setPosition(ms)
        self._cancel_time_edit()

    def _cancel_time_edit(self):
        self.edit_current_time.hide()
        self.lbl_current_time.show()

    # --- Configuration Methods for SettingsWindow ---

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "source_directory": str(Path.home()),
            "extraction_directory": str(self.extraction_dir),
            "player_mode_internal": True,
            "player_resolution_index": 1,
            "player_speed_index": 2,  # NEW: Default to 1x (index 2)
            "player_vertical": False,  # NEW
            "extract_vertical": False,  # NEW
            "extraction_engine": "MoviePy",
        }

    def collect(self) -> Dict[str, Any]:
        if self.video_path:
            self._save_current_video_config()
        return {
            "source_directory": self.line_edit_dir.text(),
            "extraction_directory": self.line_edit_extract_dir.text(),
            "player_mode_internal": self.use_internal_player,
            "player_resolution_index": self.combo_resolution.currentIndex(),
            "player_speed_index": self.combo_player_speed.currentIndex(),  # NEW
            "player_vertical": self.check_player_vertical.isChecked(),  # NEW
            "extract_vertical": self.check_extract_vertical.isChecked(),  # NEW
            "extraction_engine": self.combo_engine.currentText(),
            "active_videos_config": copy.deepcopy(self.active_videos_config),
            "video_path": self.video_path,
        }

    def set_config(self, config: Dict[str, Any]):
        try:
            source_dir = config.get("source_directory", "")
            self.line_edit_dir.setText(source_dir)
            if os.path.isdir(source_dir):
                self.scan_directory(source_dir)

            extract_dir_str = config.get("extraction_directory")
            if extract_dir_str and os.path.isdir(extract_dir_str):
                new_path = Path(extract_dir_str)
                self.extraction_dir = new_path
                self.last_browsed_extraction_dir = str(new_path)
                self.line_edit_extract_dir.setText(str(new_path))
                self._load_existing_output_images()

            # --- Restore Checkboxes ---
            self.check_player_vertical.setChecked(config.get("player_vertical", False))
            self.check_extract_vertical.setChecked(
                config.get("extract_vertical", False)
            )

            res_index = config.get("player_resolution_index")
            if res_index is not None and 0 <= res_index < self.combo_resolution.count():
                self.combo_resolution.setCurrentIndex(res_index)
                self.change_resolution(res_index)

            speed_index = config.get("player_speed_index")
            if (
                speed_index is not None
                and 0 <= speed_index < self.combo_player_speed.count()
            ):
                self.combo_player_speed.setCurrentIndex(speed_index)

            mode = config.get("player_mode_internal")
            if mode is not None:
                if mode != self.use_internal_player:
                    self.toggle_player_mode()
                self._apply_player_mode()

            engine = config.get("extraction_engine")
            if engine in ["MoviePy", "FFmpeg"]:
                self.combo_engine.setCurrentText(engine)

            # Restore active videos tab state
            active_configs = config.get("active_videos_config", {})
            if active_configs:
                self.active_videos_config = copy.deepcopy(active_configs)
                
                # Clear tabbar and repopulate under switching guard
                self._is_switching_tabs = True
                while self.active_videos_tabbar.count() > 0:
                    self.active_videos_tabbar.removeTab(0)
                for path in self.active_videos_config.keys():
                    if os.path.exists(path):
                        name = Path(path).name
                        idx = self.active_videos_tabbar.addTab(name)
                        self.active_videos_tabbar.setTabData(idx, path)
                self._is_switching_tabs = False

            # Load the current video path
            curr_video = config.get("video_path", "")
            if curr_video and os.path.exists(curr_video):
                self.load_media(curr_video)

            QMessageBox.information(
                self,
                "Config Loaded",
                "Image Extractor configuration applied successfully.",
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Config Error",
                f"Failed to apply image extractor configuration:\n{e}",
            )

    # --- QML HANDLERS ---
    @Slot(str)
    def browse_source_qml(self, current_path=""):
        starting_dir = (
            current_path if os.path.isdir(current_path) else self.last_browsed_scan_dir
        )
        d = QFileDialog.getExistingDirectory(
            self, "Select Source Directory", starting_dir
        )
        if d:
            self.line_edit_dir.setText(d)  # Sync widget
            self.last_browsed_scan_dir = d
            self.qml_source_path_changed.emit(d)
            self.scan_directory(d)  # Triggers scanner
            # Note: The scanner populates self.source_grid (QWidget).
            # For QML, we might need to expose the file list via a model or JSON signal.
            # For now, we assume the QML side will use a FolderListModel or similar if it wants to show the list,
            # or we rely on the backend to just handle the logic.
            # Ideally, we should emit a list of found videos.
            return d
        return ""

    @Slot(str, int)
    def extract_single_frame_qml(self, video_path, timestamp_ms):
        """Extracts a single frame at the given timestamp (ms)."""
        if not video_path or not os.path.exists(video_path):
            self.qml_extraction_status.emit("Error: Video not found")
            return

        # Use backend logic
        self.video_path = video_path  # Set current context
        # We need a worker or direct extraction. The existing extract_single_frame uses self.media_player position.
        # QML player is separate. We should use ffmpeg/cv2 to extract specific frame.

        # Re-using FrameExtractionWorker logic but we need to pass time explicitly
        # Existing FrameExtractionWorker takes (video_path, output_dir, start_time, end_time, fps, etc)
        # For single frame, strict start/end or just snapshot?

        # Simplified: Use cv2 for instant snapshot if possible, or trigger worker?
        # Let's use a quick CV2 cap for responsiveness, similar to how ImageScannerWorker does it maybe?
        # Or just spawn a quick ffmpeg command.

        output_dir = self.extraction_dir
        filename = f"{Path(video_path).stem}_{timestamp_ms}ms.png"
        out_path = output_dir / filename

        # Run in thread to not block UI
        QThreadPool.globalInstance().start(
            lambda: self._quick_extract(video_path, timestamp_ms, str(out_path))
        )

    def _quick_extract(self, vid_path, ms, out_path):
        try:
            t_start = ms / 1000.0

            # Use FFmpeg for robustness against codec issues (like AV1 headers)
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(t_start),
                "-i",
                vid_path,
                "-vframes",
                "1",
                "-q:v",
                "2",
                out_path,
            ]

            # Hide console on windows if needed (usually handled by subprocess)
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(out_path):
                self.qml_extraction_status.emit(f"Saved: {os.path.basename(out_path)}")
            else:
                error = (
                    result.stderr if result.stderr else "FFmpeg failed to extract frame"
                )
                self.qml_extraction_status.emit(f"Error: {error}")

        except Exception as e:
            self.qml_extraction_status.emit(f"Error: {e}")

    @Slot(str, int, int, int)
    def extract_range_qml(self, video_path, start_ms, end_ms, fps):
        """Extracts frames in range."""
        if not video_path or not os.path.exists(video_path):
            self.qml_extraction_status.emit("Error: Invalid video")
            return

        self.video_path = video_path
        # Setup worker
        config = {
            "mode": "range",
            "start_time": start_ms / 1000.0,
            "end_time": end_ms / 1000.0,
            "fps": fps,
            "output_format": "png",  # default
            "output_dir": str(self.extraction_dir),
            "resize_dim": None,
        }

        # We need to adapt this to use FrameExtractionWorker if compatible,
        # or just make a new one. FrameExtractionWorker seems designed for this.
        # It takes (video_path, output_dir, config...)

        worker = FrameExtractionWorker(video_path, str(self.extraction_dir), config)
        self.active_extraction_worker = worker

        # Signals
        worker.signals.finished.connect(
            lambda: self.qml_extraction_status.emit("Extraction Finished")
        )
        worker.signals.error.connect(
            lambda e: self.qml_extraction_status.emit(f"Error: {e}")
        )
        worker.signals.progress.connect(
            lambda val, msg: self.qml_extraction_status.emit(f"Progress: {val}%")
        )

        QThreadPool.globalInstance().start(worker)

    @Slot()
    def clear_queue(self):
        self.extraction_queue.clear()
        self._update_queue_ui()
        self.extraction_status_label.setText("Queue cleared.")
        self.extraction_status_label.show()

    @Slot(QPoint)
    def show_queue_context_menu(self, pos: QPoint):
        item = self.queue_list.itemAt(pos)
        if not item:
            return
        idx = self.queue_list.row(item)
        if idx < 0 or idx >= len(self.extraction_queue):
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background-color: #1e1f22; color: white; border: 1px solid #4f545c; }"
        )
        load_action = menu.addAction("✏️ Load Configurations")
        remove_action = menu.addAction("❌ Remove")

        action = menu.exec(self.queue_list.mapToGlobal(pos))
        if action == load_action:
            self.load_extraction_config(idx)
        elif action == remove_action:
            self.remove_queue_item(idx)

    def remove_queue_item(self, idx: int):
        if 0 <= idx < len(self.extraction_queue):
            self.extraction_queue.pop(idx)
            self._update_queue_ui()
            self.extraction_status_label.setText("Removed item from queue.")
            self.extraction_status_label.show()

    def load_extraction_config(self, idx: int):
        if idx < 0 or idx >= len(self.extraction_queue):
            return
        item = self.extraction_queue[idx]
        v_path = item.get("video_path")
        if not v_path or not os.path.exists(v_path):
            QMessageBox.warning(self, "File Not Found", f"The video file '{v_path}' no longer exists.")
            return

        # Load video if not already open
        if self.video_path != v_path:
            self.load_media(v_path)

        # Set start and end time from config
        self.start_time_ms = item.get("start_ms", 0)
        self.end_time_ms = item.get("end_ms", 0)
        self.btn_set_start.setText(
            f"Start [{self._format_time(self.start_time_ms)}]"
            if self.start_time_ms
            else "Set Start [00:00]"
        )
        self.btn_set_end.setText(
            f"End [{self._format_time(self.end_time_ms)}]"
            if self.end_time_ms
            else "Set End [00:00]"
        )

        # Load cuts
        self.cuts_ms = copy.deepcopy(item.get("cuts_ms", []))
        self._update_cuts_label()

        # Load interval/smart extract
        self.spin_interval.setValue(item.get("frame_interval", 1))
        self.check_smart_extract.setChecked(item.get("smart_extract", False))
        if item.get("smart_method"):
            self.combo_smart_method.setCurrentText(item.get("smart_method"))

        # Target resolution
        target_res = item.get("target_resolution")
        if target_res:
            res_str = f"{target_res[0]}x{target_res[1]}"
            for i in range(self.combo_extract_size.count()):
                if self.combo_extract_size.itemText(i) == res_str:
                    self.combo_extract_size.setCurrentIndex(i)
                    break
        else:
            self.combo_extract_size.setCurrentText("Native")

        # Load engine
        use_ffmpeg = item.get("use_ffmpeg", True)
        self.combo_engine.setCurrentText("FFmpeg" if use_ffmpeg else "MoviePy")

        # Load speed
        speed = item.get("speed", 1.0)
        if isinstance(speed, float):
            if speed == 1.0:
                speed_str = "1x"
            elif speed == 0.5:
                speed_str = "0.5x"
            elif speed == 0.25:
                speed_str = "0.25x"
            elif speed == 1.5:
                speed_str = "1.5x"
            elif speed == 2.0:
                speed_str = "2x"
            elif speed == 4.0:
                speed_str = "4x"
            else:
                speed_str = f"{speed:g}x"
        else:
            speed_str = str(speed)
            if not speed_str.endswith("x"):
                speed_str += "x"
        self.combo_speed.setCurrentText(speed_str)

        # Load mute audio
        self.check_mute_audio.setChecked(item.get("mute_audio", False))

        # Load fps (for gif or others)
        self.spin_gif_fps.setValue(item.get("fps", 24))

        # Jump to start_ms in media player
        if self.start_time_ms > 0 and self.media_player:
            self.media_player.setPosition(self.start_time_ms)
            self.slider.setValue(self.start_time_ms)
            self.lbl_current_time.setText(self._format_time(self.start_time_ms))

        # Update active video config dictionary so switching tabs doesn't lose it
        config = self.active_videos_config.get(v_path, {})
        config["start_time_ms"] = self.start_time_ms
        config["end_time_ms"] = self.end_time_ms
        config["cuts_ms"] = copy.deepcopy(self.cuts_ms)
        config["spin_interval"] = item.get("frame_interval", 1)
        config["check_smart_extract"] = item.get("smart_extract", False)
        config["combo_smart_method"] = item.get("smart_method", "")
        config["check_mute_audio"] = item.get("mute_audio", False)
        config["spin_gif_fps"] = item.get("fps", 24)
        config["combo_extract_size"] = self.combo_extract_size.currentText()
        config["media_position"] = self.start_time_ms
        self.active_videos_config[v_path] = config

        self.extraction_status_label.setText(f"Loaded configurations from queue item #{idx + 1}.")
        self.extraction_status_label.show()

    def _update_queue_ui(self):
        self.queue_list.clear()
        for idx, item in enumerate(self.extraction_queue):
            v_name = Path(item["video_path"]).name
            t_type = item["type"].upper()
            start_fmt = time.strftime("%M:%S", time.gmtime(item["start_ms"] / 1000.0))
            end_fmt = (
                time.strftime("%M:%S", time.gmtime(item["end_ms"] / 1000.0))
                if item["end_ms"] != -1
                else "End"
            )
            self.queue_list.addItem(
                f"{idx + 1}. [{t_type}] {v_name} ({start_fmt} - {end_fmt})"
            )

        enabled = len(self.extraction_queue) > 0
        self.btn_process_queue.setEnabled(enabled)
        self.btn_clear_queue.setEnabled(enabled)

    def _on_queue_toggle_changed(self):
        if hasattr(self, "queue_group"):
            self.queue_group.setVisible(self.extraction_queue_enabled)

    @Slot()
    def process_queue(self):
        if not self.extraction_queue:
            return

        mode = self.combo_queue_mode.currentText()
        is_parallel = "Parallel" in mode

        self.btn_process_queue.setEnabled(False)
        self.btn_clear_queue.setEnabled(False)
        self.combo_queue_mode.setEnabled(False)

        self.extraction_progress_bar.setValue(0)
        self.extraction_progress_bar.show()
        self.extraction_status_label.setText(f"Processing queue ({mode})...")
        self.extraction_status_label.show()

        self.active_queue_worker = QueueExecutionWorker(
            self.extraction_queue, parallel=is_parallel
        )
        self.active_queue_worker.signals.progress.connect(
            self.extraction_progress_bar.setValue
        )
        self.active_queue_worker.signals.finished.connect(
            self._on_queue_processing_finished
        )
        self.active_queue_worker.signals.error.connect(self._on_queue_processing_error)

        QThreadPool.globalInstance().start(self.active_queue_worker)

    def _on_queue_processing_finished(self, results):
        self.active_queue_worker = None
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        self.btn_process_queue.setEnabled(True)
        self.btn_clear_queue.setEnabled(True)
        self.combo_queue_mode.setEnabled(True)

        self.extraction_queue.clear()
        self._update_queue_ui()

        new_paths = []
        errors = []
        for res in results:
            if res.get("status") == "success":
                if "saved_files" in res:
                    new_paths.extend(res["saved_files"])
                elif "output_path" in res:
                    new_paths.append(res["output_path"])
            else:
                errors.append(res.get("message", "Unknown error"))

        if new_paths:
            self._refresh_extracted_stems_cache()
            self.start_loading_gallery(new_paths, append=True)
            self.current_extracted_paths = self.gallery_image_paths[:]

            for path, widget in self.source_path_to_widget.items():
                label = widget.findChild(ClickableLabel)
                if label:
                    self._update_source_label_style(
                        path, label, path == getattr(self, "video_path", None)
                    )

        if errors:
            QMessageBox.warning(
                self,
                "Queue Extraction Completed with Errors",
                f"Processed queue items. Errors encountered:\n" + "\n".join(errors),
            )
        else:
            QMessageBox.information(
                self,
                "Success",
                f"Queue execution complete! Processed all items. Extracted {len(new_paths)} items.",
            )

    def _on_queue_processing_error(self, error_msg):
        self.active_queue_worker = None
        self.extraction_progress_bar.hide()
        self.extraction_status_label.hide()

        self.btn_process_queue.setEnabled(True)
        self.btn_clear_queue.setEnabled(True)
        self.combo_queue_mode.setEnabled(True)

        if "cancelled" not in error_msg.lower():
            QMessageBox.warning(self, "Queue Processing Error", error_msg)
