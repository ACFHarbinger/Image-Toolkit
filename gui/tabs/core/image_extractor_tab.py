import os
import cv2
import datetime

from pathlib import Path
from typing import Optional, List, Set, Tuple, Any, Dict
from PySide6.QtWidgets import (
    QLabel, QComboBox, QStyle, 
    QSlider, QFileDialog, QGroupBox, 
    QWidget, QVBoxLayout, QHBoxLayout, 
    QMenu, QGraphicsView, QGraphicsScene,
    QScrollArea, QGridLayout, QMessageBox,
    QPushButton, QApplication, QLineEdit,
    QProgressDialog, QSpinBox, QCheckBox
)
from PySide6.QtGui import QPixmap, QResizeEvent, QAction, QImage
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import Qt, QUrl, Slot, QThreadPool, QPoint, QEvent
from ...windows import ImagePreviewWindow
from ...classes import AbstractClassSingleGallery
from ...components import ClickableLabel, MarqueeScrollArea
from ...helpers import VideoScannerWorker, GifCreationWorker, FrameExtractionWorker, VideoExtractionWorker
from backend.src.utils.definitions import LOCAL_SOURCE_PATH, SUPPORTED_VIDEO_FORMATS


class ImageExtractorTab(AbstractClassSingleGallery):
    def __init__(self):
        super().__init__()
        self.video_path: Optional[str] = None
        self.current_extracted_paths: List[str] = []
        self.selected_paths: Set[str] = set()
        self.duration_ms = 0
        self.extractor_worker: Optional[FrameExtractionWorker] = None
        self.open_image_preview_windows: List[QWidget] = [] 
        
        # Reference for the progress dialog
        self.progress_dialog: Optional[QProgressDialog] = None
        
        self.use_internal_player = True 
        
        # Cache for generated thumbnails (video frames)
        self._initial_pixmap_cache: Dict[str, QPixmap] = {}

        # Defined resolutions corresponding to the Combo Box items
        self.available_resolutions = [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]
        
        # Mapping for Extraction Resolutions
        self.extraction_res_map = {
            "Original": None,
            "480p": (854, 480),
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "1440p": (2560, 1440),
            "4K": (3840, 2160)
        }
        
        self.extraction_dir = Path(LOCAL_SOURCE_PATH) / "Frames"
        self.extraction_dir.mkdir(parents=True, exist_ok=True)
        self.last_browsed_extraction_dir = str(self.extraction_dir)

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
        self.line_edit_dir.setPlaceholderText("Select a folder containing videos or GIFs...")
        self.line_edit_dir.returnPressed.connect(lambda: self.scan_directory(self.line_edit_dir.text()))
        
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
        self.source_scroll.setStyleSheet("QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }")
        
        self.source_container = QWidget()
        self.source_container.setStyleSheet("QWidget { background-color: #2c2f33; }")

        self.source_grid = QGridLayout(self.source_container)
        self.source_grid.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignTop)
        self.source_scroll.setWidget(self.source_container)
        
        source_layout.addWidget(self.source_scroll)
        self.main_layout.addWidget(self.source_group)

        # 3. Video Player Section
        self.video_container_widget = QWidget() 
        video_container_layout = QVBoxLayout(self.video_container_widget)
        
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
        self.video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_view.setVisible(True) 
        self.video_view.installEventFilter(self)
        
        self.player_inner_layout.addWidget(self.video_view, 1, Qt.AlignmentFlag.AlignCenter)
        
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_item) 
        
        # Controls Row 1 (Top)
        controls_top_layout = QHBoxLayout()
        controls_top_layout.setContentsMargins(10, 5, 10, 0) 
        
        self.btn_toggle_mode = QPushButton("Switch to External Player")
        self.btn_toggle_mode.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
        self.btn_toggle_mode.clicked.connect(self.toggle_player_mode)
        controls_top_layout.addWidget(self.btn_toggle_mode)
        
        controls_top_layout.addWidget(QLabel("Player Size:"))
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["720p", "1080p", "1440p", "4K"])
        self.combo_resolution.setCurrentIndex(1)
        self.combo_resolution.currentIndexChanged.connect(lambda: self.change_resolution(self.combo_resolution.currentIndex()))
        controls_top_layout.addWidget(self.combo_resolution)
        
        # --- NEW: Vertical Checkbox for Player ---
        self.check_player_vertical = QCheckBox("Vertical")
        self.check_player_vertical.setToolTip("Swap width/height for vertical displays")
        self.check_player_vertical.toggled.connect(lambda: self.change_resolution(self.combo_resolution.currentIndex()))
        controls_top_layout.addWidget(self.check_player_vertical)
        # ----------------------------------------
        
        controls_top_layout.addStretch()
        self.player_inner_layout.addLayout(controls_top_layout)

        # Controls Row 2 (Bottom)
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(10, 0, 10, 10)
        
        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_play.setVisible(True)
        
        self.lbl_vol = QLabel("Vol:")
        self.lbl_vol.setVisible(True)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(60) 
        self.volume_slider.valueChanged.connect(lambda v: self.audio_output.setVolume(v / 100.0))
        self.volume_slider.setVisible(True)

        self.lbl_current_time = QLabel("00:00")
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        self.slider.sliderPressed.connect(self.media_player.pause)
        self.slider.sliderReleased.connect(self.set_position_on_release)
        
        self.lbl_total_time = QLabel("00:00")

        controls_layout.addWidget(self.lbl_vol)
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.lbl_current_time)
        controls_layout.addWidget(self.slider)
        controls_layout.addWidget(self.lbl_total_time)
        
        self.player_inner_layout.addLayout(controls_layout)
        
        self.info_label = QLabel("Video is playing externally. Use slider to select timestamps.")
        self.info_label.setStyleSheet("color: #aaa; font-style: italic; font-size: 11px;")
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
        
        # -- Row 1: Configuration --
        extract_config_layout = QHBoxLayout()
        
        extract_config_layout.addWidget(QLabel("Output Size:"))
        self.combo_extract_size = QComboBox()
        self.combo_extract_size.addItems(list(self.extraction_res_map.keys()))
        self.combo_extract_size.setCurrentText("Original") 
        extract_config_layout.addWidget(self.combo_extract_size)
        
        # --- NEW: Vertical Checkbox for Extraction ---
        self.check_extract_vertical = QCheckBox("Vertical Output")
        self.check_extract_vertical.setToolTip("Swap width/height for vertical output resolution")
        extract_config_layout.addWidget(self.check_extract_vertical)
        # ---------------------------------------------
        
        extract_config_layout.addSpacing(20)
        
        extract_config_layout.addWidget(QLabel("GIF FPS:"))
        self.spin_gif_fps = QSpinBox()
        self.spin_gif_fps.setRange(1, 60)
        self.spin_gif_fps.setValue(15)
        extract_config_layout.addWidget(self.spin_gif_fps)

        self.check_mute_audio = QCheckBox("Mute Audio in MP4/GIF")
        self.check_mute_audio.setChecked(False) 
        extract_config_layout.addWidget(self.check_mute_audio)
        
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
        self.btn_set_start = QPushButton("Set Start [00:00]")
        self.btn_set_start.clicked.connect(self.set_range_start)
        self.btn_set_start.setEnabled(False)
        self.btn_set_end = QPushButton("Set End [00:00]")
        self.btn_set_end.clicked.connect(self.set_range_end)
        self.btn_set_end.setEnabled(False)
        self.btn_extract_range = QPushButton("🎞️ Extract Range")
        self.btn_extract_range.clicked.connect(self.extract_range)
        self.btn_extract_range.setEnabled(False)

        self.btn_extract_video = QPushButton("MP4 Extract as Video")
        self.btn_extract_video.setStyleSheet("QPushButton { background-color: #2980b9; color: white; font-weight: bold; }")
        self.btn_extract_video.clicked.connect(self.extract_range_as_video)
        self.btn_extract_video.setEnabled(False)

        self.btn_extract_gif = QPushButton("GIF Extract as GIF")
        self.btn_extract_gif.setStyleSheet("QPushButton { background-color: #8e44ad; color: white; font-weight: bold; }")
        self.btn_extract_gif.clicked.connect(self.extract_range_as_gif)
        self.btn_extract_gif.setEnabled(False)

        extract_actions_layout.addWidget(self.btn_set_start)
        extract_actions_layout.addWidget(self.btn_set_end)
        extract_actions_layout.addWidget(self.btn_extract_range)
        extract_actions_layout.addWidget(self.btn_extract_video) 
        extract_actions_layout.addWidget(self.btn_extract_gif) 
        
        extract_main_layout.addLayout(extract_actions_layout)

        self.main_layout.addWidget(self.extract_group)
        self.extract_group.setVisible(False) 

        # 5. Results Gallery Section
        self.gallery_scroll_area = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True)
        self.gallery_scroll_area.setStyleSheet("""
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
        """)
        self.gallery_scroll_area.setMinimumHeight(600)
        
        self.gallery_container = QWidget()
        self.gallery_container.setStyleSheet("QWidget { background-color: #2c2f33; }")
        
        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.gallery_layout.setSpacing(3)
        self.gallery_scroll_area.setWidget(self.gallery_container)
        
        self.gallery_scroll_area.selection_changed.connect(self.handle_marquee_selection)

        self.main_layout.addWidget(self.gallery_scroll_area, 1)
        self.main_layout.addWidget(self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter)
        
        # --- Connections ---
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.errorOccurred.connect(self.handle_player_error)

        self._load_existing_output_images()

    def _load_existing_output_images(self):
        valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".mp4"}
        found_paths = []
        
        if self.extraction_dir.exists():
            for entry in self.extraction_dir.iterdir():
                if entry.is_file() and entry.suffix.lower() in valid_extensions:
                    full_path = str(entry.absolute())
                    found_paths.append(full_path)
        
        found_paths.sort()

        if found_paths:
            self.current_extracted_paths = found_paths
            self.start_loading_gallery(self.current_extracted_paths, pixmap_cache=self._initial_pixmap_cache)

    @Slot()
    def set_position_on_release(self):
        position = self.slider.value()
        self.media_player.setPosition(position)

    # --- Directory Browsing & Scanning ---
    @Slot()
    def browse_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Source Directory", self.last_browsed_scan_dir)
        if d:
            self.last_browsed_scan_dir = d
            self.scan_directory(d)

    def scan_directory(self, path: str):
        if not os.path.isdir(path):
            return
        
        self.line_edit_dir.setText(path)
        
        while self.source_grid.count():
            item = self.source_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        worker = VideoScannerWorker(path)
        worker.signals.thumbnail_ready.connect(self.add_source_thumbnail)
        worker.signals.finished.connect(lambda: self.scan_progress_complete())
        QThreadPool.globalInstance().start(worker)

    def scan_progress_complete(self):
        pass

    @Slot(str, QPixmap)
    def add_source_thumbnail(self, path: str, pixmap: QPixmap):
        if pixmap.isNull() and path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
             thumb = self._generate_video_thumbnail(path)
             if thumb: pixmap = thumb

        thumb_size = 120
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        
        clickable_label = ClickableLabel(file_path=path)
        clickable_label.setFixedSize(thumb_size, thumb_size)
        
        if not pixmap.isNull():
            scaled = pixmap.scaled(thumb_size, thumb_size, 
                                 Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
                                 Qt.TransformationMode.SmoothTransformation)
            diff_x = (scaled.width() - thumb_size) // 2
            diff_y = (scaled.height() - thumb_size) // 2
            cropped = scaled.copy(diff_x, diff_y, thumb_size, thumb_size)
            clickable_label.setPixmap(cropped)
        else:
            clickable_label.setText("No Preview")
            clickable_label.setStyleSheet("border: 1px dashed #666; color: #888;")
        
        if not pixmap.isNull():
            clickable_label.setStyleSheet("border: 2px solid #4f545c; border-radius: 4px;")
        
        clickable_label.path_clicked.connect(self.load_media)
        clickable_label.path_right_clicked.connect(self.show_source_context_menu)
        
        layout.addWidget(clickable_label)
        
        count = self.source_grid.count()
        row = count // 12 
        col = count % 12
        self.source_grid.addWidget(container, row, col)

    @Slot(QPoint, str)
    def show_source_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        view_action = QAction("View Preview", self)
        view_action.triggered.connect(lambda: self.handle_thumbnail_double_click(path))
        menu.addAction(view_action)
        menu.exec(global_pos)

    @Slot(str)
    def load_media(self, file_path: str):
        self.video_path = file_path
        ext = Path(file_path).suffix.lower()
        
        for i in range(self.source_grid.count()):
            container = self.source_grid.itemAt(i).widget()
            if container:
                label = container.findChild(ClickableLabel)
                if label:
                    if label.path == file_path:
                        label.setStyleSheet("border: 3px solid #3498db; border-radius: 4px;")
                    else:
                        label.setStyleSheet("border: 2px solid #4f545c; border-radius: 4px;")

        if ext == ".gif":
            self.video_container_widget.setVisible(False)
            self.extract_group.setVisible(False)
            self.media_player.stop()
            self.media_player.setSource(QUrl())
            
        else:
            self.video_container_widget.setVisible(True) 
            self.extract_group.setVisible(True)
            self.btn_snapshot.setEnabled(True)
            self.btn_set_start.setEnabled(True)
            self.btn_set_end.setEnabled(True)
            self._apply_player_mode()

    @Slot()
    def browse_extraction_directory(self):
        d = QFileDialog.getExistingDirectory(self, "Select Extraction Directory", self.last_browsed_extraction_dir)
        if d:
            new_path = Path(d)
            new_path.mkdir(parents=True, exist_ok=True)
            self.extraction_dir = new_path
            self.last_browsed_extraction_dir = str(new_path)
            self.line_edit_extract_dir.setText(str(self.extraction_dir))
            self._clear_gallery()
            self._load_existing_output_images()

    def _clear_gallery(self):
        self.current_extracted_paths.clear()
        self.selected_paths.clear()
        self.gallery_image_paths.clear()
        self._initial_pixmap_cache.clear() 
        self.clear_gallery_widgets()
        self.start_time_ms = 0
        self.end_time_ms = 0
        self.btn_set_start.setText("Set Start [00:00]")
        self.btn_set_end.setText("Set End [00:00]")
        self.btn_extract_range.setEnabled(False)
        self.btn_extract_gif.setEnabled(False)
        self.btn_extract_video.setEnabled(False)
        self.btn_extract_range.setText("🎞️ Extract Range")

    # --- Event Filters & Resizing ---
    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        if obj is self.video_view:
            if self.use_internal_player:
                if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                    self.toggle_playback()
                    return True
                if event.type() == QEvent.Type.MouseButtonDblClick:
                    self.toggle_fullscreen()
                    return True

        if obj is self.player_container:
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
        if not self.player_container.isFullScreen() and 0 <= index < len(self.available_resolutions):
            w, h = self.available_resolutions[index]
            # --- NEW: Swap dimensions if vertical checkbox is checked ---
            if self.check_player_vertical.isChecked():
                w, h = h, w
            # -----------------------------------------------------------
            self.video_view.setFixedSize(w, h)
            self.fit_video_in_view()

    # --- Gallery & Selection Logic (Extracted Frames) ---
    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)
        
        clickable_label = ClickableLabel(file_path=path)
        clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        clickable_label.setAlignment(Qt.AlignCenter)
        clickable_label.path = path 
        
        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))

        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(self.thumbnail_size, self.thumbnail_size, 
                                 Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            clickable_label.setPixmap(scaled)
            clickable_label.setText("") 
            
            if is_video:
                clickable_label.setStyleSheet("border: 2px solid #3498db;")
            else:
                clickable_label.setStyleSheet("border: 1px solid #4f545c;")
        else:
             if is_video:
                 clickable_label.setText("VIDEO")
                 clickable_label.setStyleSheet("border: 1px solid #2980b9; color: #2980b9; font-weight: bold;")
             else:
                 clickable_label.setText("Loading...")
                 clickable_label.setStyleSheet("border: 1px solid #4f545c; color: #888; font-size: 10px;")
        
        self._style_label(clickable_label, selected=(path in self.selected_paths))

        clickable_label.path_clicked.connect(self.handle_thumbnail_single_click)
        clickable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        clickable_label.path_right_clicked.connect(self.show_image_context_menu)
        
        layout.addWidget(clickable_label)
        return container

    def update_card_pixmap(self, widget: QWidget, pixmap: Optional[QPixmap]):
        clickable_label = widget.findChild(ClickableLabel)
        if clickable_label:
            is_video = clickable_label.path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
            
            if pixmap and not pixmap.isNull():
                scaled = pixmap.scaled(self.thumbnail_size, self.thumbnail_size, 
                                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                clickable_label.setPixmap(scaled)
                clickable_label.setText("")
                
                if is_video:
                    clickable_label.setStyleSheet("border: 2px solid #3498db;")
            else:
                if not is_video:
                    clickable_label.clear()
                    clickable_label.setText("Loading...")
            
            self._style_label(clickable_label, selected=(clickable_label.path in self.selected_paths))

    def _style_label(self, label: ClickableLabel, selected: bool):
        is_video = label.path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        
        if selected:
            label.setStyleSheet("border: 3px solid #5865f2; background-color: #36393f;")
        else:
            if is_video:
                if label.text() == "VIDEO":
                     label.setStyleSheet("border: 1px solid #2980b9; color: #2980b9; font-weight: bold;")
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
        if not self.gallery_container: return
        for label in self.gallery_container.findChildren(ClickableLabel):
            if hasattr(label, 'path'):
                is_selected = label.path in self.selected_paths
                self._style_label(label, is_selected)

    @Slot(str)
    def handle_thumbnail_double_click(self, image_path: str):
        if image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            try:
                if os.name == 'nt':
                    os.startfile(image_path)
                else:
                    import subprocess
                    subprocess.call(['xdg-open', image_path])
            except Exception as e:
                print(f"Error opening video: {e}")
            return

        for win in self.open_image_preview_windows:
            if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                win.activateWindow()
                return

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
            start_index=start_index
        )
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.closeEvent = lambda e: (self.open_image_preview_windows.remove(window) if window in self.open_image_preview_windows else None, e.accept())
        window.show()
        self.open_image_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        if path not in self.selected_paths:
            self.selected_paths = {path}
            self.update_visual_selection()

        count = len(self.selected_paths)
        menu = QMenu(self)
        if count == 1:
            if not path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                view_action = QAction("View Full Size", self)
                view_action.triggered.connect(lambda: self.handle_thumbnail_double_click(path))
                menu.addAction(view_action)
                menu.addSeparator()

        del_text = f"Delete {count} Items" if count > 1 else "Delete Item"
        delete_action = QAction(del_text, self)
        delete_action.triggered.connect(self.delete_selected_images)
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def delete_selected_images(self):
        if not self.selected_paths: return
        confirm = QMessageBox.question(
            self, "Confirm Deletion", 
            f"Are you sure you want to delete {len(self.selected_paths)} items?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            failed = []
            paths_to_delete = list(self.selected_paths)
            layout_changed = False
            
            widgets_to_delete = []

            for path in paths_to_delete:
                try:
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
            
                cols = self.common_calculate_columns(self.gallery_scroll_area, self.approx_item_width)
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
        if not self.video_path: return
        ext = Path(self.video_path).suffix.lower()
        if ext == ".gif": return
        self.media_player.setSource(QUrl.fromLocalFile(self.video_path))

        if self.use_internal_player:
            self.btn_toggle_mode.setText("Switch to External Player")
            self.btn_toggle_mode.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
            self.info_label.setVisible(False)
            self.combo_resolution.setEnabled(True)
            self.video_view.setVisible(True)
            self.btn_play.setVisible(True)
            self.lbl_vol.setVisible(True)
            self.volume_slider.setVisible(True)
            self.btn_play.setEnabled(True)
            self.media_player.setVideoOutput(self.video_item)
            self.media_player.setAudioOutput(self.audio_output)
            self.change_resolution(self.combo_resolution.currentIndex())
        else:
            self.btn_toggle_mode.setText("Switch to Internal Player")
            self.btn_toggle_mode.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
            self.info_label.setVisible(True)
            self.combo_resolution.setEnabled(False)
            self.video_view.setVisible(False)
            self.btn_play.setVisible(False)
            self.lbl_vol.setVisible(False)
            self.volume_slider.setVisible(False)
            self.media_player.setVideoOutput(None)
            self.media_player.setAudioOutput(None)
            self.media_player.pause()

    @Slot()
    def toggle_playback(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        else:
            self.media_player.play()
            self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))

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
            QMessageBox.critical(self, "Video Error", f"Media Player Error: {error_string}")

    # --- Extraction Logic ---
    @Slot()
    def set_range_start(self):
        self.start_time_ms = self.media_player.position()
        self.btn_set_start.setText(f"Start: {self._format_time(self.start_time_ms)}")
        self._validate_range()

    @Slot()
    def set_range_end(self):
        self.end_time_ms = self.media_player.position()
        self.btn_set_end.setText(f"End: {self._format_time(self.end_time_ms)}")
        self._validate_range()

    def _validate_range(self):
        if self.end_time_ms > self.start_time_ms:
            duration_str = self._format_time(self.end_time_ms - self.start_time_ms)
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

    # --- NEW HELPER: Resolution Swapping ---
    def _get_target_size(self) -> Optional[Tuple[int, int]]:
        selected_key = self.combo_extract_size.currentText()
        target_size = self.extraction_res_map.get(selected_key)
        # If vertical output is checked, flip dimensions
        if target_size and self.check_extract_vertical.isChecked():
            return (target_size[1], target_size[0])
        return target_size
    # ---------------------------------------

    @Slot()
    def extract_single_frame(self):
        if not self.video_path: return
        if self.use_internal_player and self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        current_ms = self.media_player.position()
        self._run_extraction(current_ms, -1, is_range=False)

    @Slot()
    def extract_range(self):
        if not self.video_path: return
        if self.use_internal_player:
             self.media_player.pause()
             self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._run_extraction(self.start_time_ms, self.end_time_ms, is_range=True)

    @Slot()
    def extract_range_as_gif(self):
        if not self.video_path: return
        if self.use_internal_player:
             self.media_player.pause()
             self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._run_gif_extraction(self.start_time_ms, self.end_time_ms)

    @Slot()
    def extract_range_as_video(self):
        if not self.video_path: return
        if self.use_internal_player:
            self.media_player.pause()
            self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self._run_video_extraction(self.start_time_ms, self.end_time_ms)

    def _run_extraction(self, start: int, end: int, is_range: bool):
        target_size = self._get_target_size()
        
        self.progress_dialog = QProgressDialog("Extracting and processing frames...", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Processing")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        self.extractor_worker = FrameExtractionWorker(
            video_path=self.video_path,
            output_dir=str(self.extraction_dir),
            start_ms=start,
            end_ms=end,
            is_range=is_range,
            target_resolution=target_size
        )
        self.extractor_worker.signals.finished.connect(self._on_extraction_finished)
        self.extractor_worker.signals.error.connect(lambda e: QMessageBox.warning(self, "Extraction Error", e))
        QThreadPool.globalInstance().start(self.extractor_worker)

    def _run_gif_extraction(self, start: int, end: int):
        target_size = self._get_target_size()
        fps = self.spin_gif_fps.value()

        self.progress_dialog = QProgressDialog("Generating GIF... This may take a moment.", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Processing GIF")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"GIF_{Path(self.video_path).stem}_{timestamp}.gif"
        output_path = str(self.extraction_dir / output_name)

        worker = GifCreationWorker(
            video_path=self.video_path, 
            start_ms=start, 
            end_ms=end, 
            output_path=output_path, 
            target_size=target_size, 
            fps=fps
        )
        worker.signals.finished.connect(self._on_export_finished)
        worker.signals.error.connect(self._on_export_error)
        QThreadPool.globalInstance().start(worker)

    def _run_video_extraction(self, start: int, end: int):
        target_size = self._get_target_size()
        mute_audio = self.check_mute_audio.isChecked()
        
        self.progress_dialog = QProgressDialog("Generating Video... This may take a moment.", "Cancel", 0, 0, self)
        self.progress_dialog.setWindowTitle("Processing Video")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.show()

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"CLIP_{Path(self.video_path).stem}_{timestamp}.mp4"
        output_path = str(self.extraction_dir / output_name)

        worker = VideoExtractionWorker(
            video_path=self.video_path, 
            start_ms=start, 
            end_ms=end, 
            output_path=output_path, 
            target_size=target_size,
            mute_audio=mute_audio 
        )
        worker.signals.finished.connect(self._on_export_finished)
        worker.signals.error.connect(self._on_export_error)
        QThreadPool.globalInstance().start(worker)

    @Slot(str)
    def _on_export_finished(self, new_path: str):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        
        if new_path and os.path.exists(new_path):
            if new_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                thumb = self._generate_video_thumbnail(new_path)
                if thumb:
                    self._initial_pixmap_cache[new_path] = thumb
            
            # Base class handles list management and loading
            self.start_loading_gallery([new_path], append=True, pixmap_cache=self._initial_pixmap_cache)
            
            # Keep local list synced
            self.current_extracted_paths = self.gallery_image_paths[:] 
            
            QMessageBox.information(self, "Success", f"Media created successfully:\n{Path(new_path).name}")

    @Slot(str)
    def _on_export_error(self, error_msg: str):
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        QMessageBox.warning(self, "Export Error", error_msg)

    @Slot(list)
    def _on_extraction_finished(self, new_paths: List[str]):
        if self.progress_dialog:
            self.progress_dialog.setLabelText(f"Loading {len(new_paths)} images...")
        if not new_paths:
            if self.progress_dialog: self.progress_dialog.close()
            QMessageBox.information(self, "Info", "No frames extracted.")
            return
        
        self.start_loading_gallery(new_paths, append=True)
        self.current_extracted_paths = self.gallery_image_paths[:] 
        
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None
        QMessageBox.information(self, "Success", f"Extracted {len(new_paths)} images. Total: {len(self.current_extracted_paths)}")

    def _format_time(self, ms: int) -> str:
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000) % 60
        return f"{minutes:02}:{seconds:02}"
    
    # --- Configuration Methods for SettingsWindow ---

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "source_directory": str(Path.home()),
            "extraction_directory": str(self.extraction_dir),
            "player_mode_internal": True,
            "player_resolution_index": 1,
            "player_vertical": False, # NEW
            "extract_vertical": False, # NEW
        }

    def collect(self) -> Dict[str, Any]:
        return {
            "source_directory": self.line_edit_dir.text(),
            "extraction_directory": self.line_edit_extract_dir.text(),
            "player_mode_internal": self.use_internal_player,
            "player_resolution_index": self.combo_resolution.currentIndex(),
            "player_vertical": self.check_player_vertical.isChecked(), # NEW
            "extract_vertical": self.check_extract_vertical.isChecked(), # NEW
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
            self.check_extract_vertical.setChecked(config.get("extract_vertical", False))
            
            res_index = config.get("player_resolution_index")
            if res_index is not None and 0 <= res_index < self.combo_resolution.count():
                self.combo_resolution.setCurrentIndex(res_index)
                self.change_resolution(res_index)
                
            mode = config.get("player_mode_internal")
            if mode is not None:
                if mode != self.use_internal_player:
                    self.toggle_player_mode()
                self._apply_player_mode() 
                
            QMessageBox.information(self, "Config Loaded", "Image Extractor configuration applied successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Config Error", f"Failed to apply configuration:\n{e}")