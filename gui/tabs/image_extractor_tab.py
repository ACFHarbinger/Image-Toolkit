import os

from pathlib import Path
from typing import Optional, List, Set
from PySide6.QtWidgets import (
    QSlider, QFileDialog, QGroupBox, 
    QMenu, QGraphicsView, QGraphicsScene,
    QScrollArea, QGridLayout, QMessageBox,
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QComboBox, QStyle, QPushButton, QApplication,
)
from PySide6.QtGui import QPixmap, QResizeEvent, QAction
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import Qt, QUrl, Slot, QThreadPool, QPoint, QEvent

from ..windows import ImagePreviewWindow
from ..helpers import FrameExtractorWorker
from ..classes import AbstractClassSingleGallery
from ..components import ClickableLabel, MarqueeScrollArea


class ImageExtractorTab(AbstractClassSingleGallery):
    def __init__(self):
        super().__init__()

        self.video_path: Optional[str] = None
        self.current_extracted_paths: List[str] = []
        self.selected_paths: Set[str] = set()
        self.duration_ms = 0
        self.extractor_worker: Optional[FrameExtractorWorker] = None
        self.open_image_preview_windows: List[QWidget] = [] 
        
        self.use_internal_player = True 
        
        self.extraction_dir = Path(os.getcwd()) / "data" / "Frames"
        self.extraction_dir.mkdir(parents=True, exist_ok=True)

        # --- UI Setup ---
        
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Main Tab Scroll Area
        self.tab_scroll_area = QScrollArea()
        self.tab_scroll_area.setWidgetResizable(True)
        self.tab_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.root_layout.addWidget(self.tab_scroll_area)
        
        self.content_widget = QWidget()
        self.main_layout = QVBoxLayout(self.content_widget)
        self.tab_scroll_area.setWidget(self.content_widget)
        
        # --- File Selection ---
        file_selection_layout = QHBoxLayout()
        self.btn_open = QPushButton("Open Video File")
        self.btn_open.clicked.connect(self.open_video_file)
        file_selection_layout.addWidget(self.btn_open)
        file_selection_layout.addStretch(1)
        self.main_layout.addLayout(file_selection_layout) 
        
        # --- Video Player ---
        self.video_container_widget = QWidget() 
        video_container_layout = QVBoxLayout(self.video_container_widget)
        
        player_group = QGroupBox("Video Player")
        player_layout = QVBoxLayout(player_group)
        
        self.video_item = QGraphicsVideoItem()
        self.graphics_scene = QGraphicsScene(self)
        self.graphics_scene.addItem(self.video_item)
        
        self.video_view = QGraphicsView(self.graphics_scene)
        self.video_view.setFixedSize(1920, 1080)
        self.video_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.video_view.setVisible(True) 
        self.video_view.installEventFilter(self)
        
        player_layout.addWidget(self.video_view, 0, Qt.AlignmentFlag.AlignCenter)
        
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_item) 
        
        # Player Controls
        controls_top_layout = QHBoxLayout()
        self.btn_toggle_mode = QPushButton("Switch to External Player")
        self.btn_toggle_mode.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DesktopIcon))
        self.btn_toggle_mode.clicked.connect(self.toggle_player_mode)
        controls_top_layout.addWidget(self.btn_toggle_mode)
        
        controls_top_layout.addWidget(QLabel("Player Size:"))
        self.combo_resolution = QComboBox()
        self.combo_resolution.addItems(["720p", "1080p", "1440p", "4K"])
        self.combo_resolution.setCurrentIndex(1)
        self.combo_resolution.currentIndexChanged.connect(self.change_resolution)
        controls_top_layout.addWidget(self.combo_resolution)
        controls_top_layout.addStretch()
        player_layout.addLayout(controls_top_layout)

        controls_layout = QHBoxLayout()
        self.btn_play = QPushButton()
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play.clicked.connect(self.toggle_playback)
        self.btn_play.setVisible(True)
        
        self.lbl_vol = QLabel("Vol:")
        self.lbl_vol.setVisible(True)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.valueChanged.connect(lambda v: self.audio_output.setVolume(v / 100.0))
        self.volume_slider.setVisible(True)

        self.lbl_current_time = QLabel("00:00")
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.set_position)
        self.slider.sliderPressed.connect(self.media_player.pause)
        self.lbl_total_time = QLabel("00:00")

        controls_layout.addWidget(self.lbl_vol)
        controls_layout.addWidget(self.volume_slider)
        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.lbl_current_time)
        controls_layout.addWidget(self.slider)
        controls_layout.addWidget(self.lbl_total_time)
        player_layout.addLayout(controls_layout)
        
        self.info_label = QLabel("Video is playing externally. Use slider to select timestamps.")
        self.info_label.setStyleSheet("color: #aaa; font-style: italic; font-size: 11px;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setVisible(False)
        player_layout.addWidget(self.info_label)

        video_container_layout.addWidget(player_group)
        self.main_layout.addWidget(self.video_container_widget)
        self.video_container_widget.setVisible(False) 

        # --- Extraction Controls ---
        self.extract_group = QGroupBox("Extraction Settings")
        extract_layout = QHBoxLayout(self.extract_group)

        self.btn_snapshot = QPushButton("📸 Snapshot Frame")
        self.btn_snapshot.clicked.connect(self.extract_single_frame)
        self.btn_snapshot.setEnabled(False)
        extract_layout.addWidget(self.btn_snapshot)
        extract_layout.addWidget(QLabel("|")) 
        
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

        extract_layout.addWidget(self.btn_set_start)
        extract_layout.addWidget(self.btn_set_end)
        extract_layout.addWidget(self.btn_extract_range)
        self.main_layout.addWidget(self.extract_group)
        self.extract_group.setVisible(False) 

        # --- Gallery Section ---
        self.gallery_scroll_area = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True)
        self.gallery_scroll_area.setMinimumHeight(600)
        
        self.gallery_container = QWidget()
        self.gallery_layout = QGridLayout(self.gallery_container)
        self.gallery_scroll_area.setWidget(self.gallery_container)
        
        self.gallery_scroll_area.selection_changed.connect(self.handle_marquee_selection)

        self.main_layout.addWidget(self.gallery_scroll_area)
        
        # --- Connections ---
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.errorOccurred.connect(self.handle_player_error)

    # --- Event Filters & Resizing ---
    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        if obj is self.video_view:
            if self.use_internal_player and event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.toggle_playback()
                return True
        return super().eventFilter(obj, event)

    @Slot(QResizeEvent)
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._resize_timer.start(150) 
        if self.video_view.isVisible():
            rect = self.video_view.viewport().rect()
            self.video_item.setSize(rect.size())
            self.video_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)

    @Slot(int)
    def change_resolution(self, index: int):
        resolutions = [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]
        if 0 <= index < len(resolutions):
            w, h = resolutions[index]
            self.video_view.setFixedSize(w, h)
            rect = self.video_view.viewport().rect()
            self.video_item.setSize(rect.size())
            self.video_view.fitInView(self.video_item, Qt.AspectRatioMode.KeepAspectRatio)

    # --- Gallery & Selection Logic ---

    def create_card_widget(self, path: str, pixmap: Optional[QPixmap]) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(5, 5, 5, 5)
        
        clickable_label = ClickableLabel(file_path=path)
        clickable_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        
        clickable_label.path = path 
        
        if pixmap and not pixmap.isNull():
            scaled = pixmap.scaled(self.thumbnail_size, self.thumbnail_size, 
                                 Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            clickable_label.setPixmap(scaled)
            clickable_label.setText("") 
        else:
             clickable_label.setText("Load Error")
        
        self._style_label(clickable_label, selected=(path in self.selected_paths))

        clickable_label.path_clicked.connect(self.handle_thumbnail_single_click)
        clickable_label.path_double_clicked.connect(self.handle_thumbnail_double_click)
        clickable_label.path_right_clicked.connect(self.show_image_context_menu)
        
        # --- REMOVED FILENAME LABEL START ---
        # Removed: lbl_name = QLabel(Path(path).name)
        # Removed: lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Removed: lbl_name.setStyleSheet("color: #ccc; font-size: 10px;")
        # Removed: lbl_name.setWordWrap(True)
        # --- REMOVED FILENAME LABEL END ---
        
        layout.addWidget(clickable_label)
        # Removed: layout.addWidget(lbl_name)
        
        return container

    def _style_label(self, label: ClickableLabel, selected: bool):
        if selected:
            label.setStyleSheet("border: 3px solid #3498db; background-color: #000;")
        else:
            if label.text() == "Load Error":
                label.setStyleSheet("border: 1px solid #e74c3c; background-color: #4f545c; color: white;")
            else:
                label.setStyleSheet("border: 1px solid #555; background-color: #000;")

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
            if hasattr(label, 'path'):
                is_selected = label.path in self.selected_paths
                self._style_label(label, is_selected)

    @Slot(str)
    def handle_thumbnail_double_click(self, image_path: str):
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
            view_action = QAction("View Full Size", self)
            view_action.triggered.connect(lambda: self.handle_thumbnail_double_click(path))
            menu.addAction(view_action)
            menu.addSeparator()

        del_text = f"Delete {count} Images" if count > 1 else "Delete Image"
        delete_action = QAction(del_text, self)
        delete_action.triggered.connect(self.delete_selected_images)
        menu.addAction(delete_action)
        
        menu.exec(global_pos)

    def delete_selected_images(self):
        if not self.selected_paths:
            return

        confirm = QMessageBox.question(
            self, "Confirm Deletion", 
            f"Are you sure you want to delete {len(self.selected_paths)} images?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            failed = []
            paths_to_delete = list(self.selected_paths)
            
            for path in paths_to_delete:
                try:
                    os.remove(path)
                    if path in self.current_extracted_paths:
                        self.current_extracted_paths.remove(path)
                except Exception as e:
                    failed.append(f"{Path(path).name}: {e}")
            
            self.selected_paths.clear()
            self.start_loading_gallery(self.current_extracted_paths)
            
            if failed:
                QMessageBox.warning(self, "Partial Deletion Failure", "\n".join(failed))

    def delete_image(self, path: str):
        if path not in self.selected_paths:
            self.selected_paths = {path}
        self.delete_selected_images()

    # --- Video & Player Logic ---
    @Slot()
    def open_video_file(self):
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilters(["Video files (*.mp4 *.avi *.mkv *.mov)"])
        if file_dialog.exec():
            files = file_dialog.selectedFiles()
            if files:
                self.video_path = files[0]
                self.btn_open.setText(f"Change Video File (Current: {Path(files[0]).name})")
                self.video_container_widget.setVisible(True) 
                self.extract_group.setVisible(True)
                self.btn_snapshot.setEnabled(True)
                self.btn_set_start.setEnabled(True)
                self.btn_set_end.setEnabled(True)
                self._apply_player_mode()

    @Slot()
    def toggle_player_mode(self):
        self.use_internal_player = not self.use_internal_player
        self._apply_player_mode()

    def _apply_player_mode(self):
        if not self.video_path: return
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
            self.launch_external_player()

    # ... (Rest of Video & Extraction Logic remains unchanged) ...
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
            self.btn_extract_range.setEnabled(True)
            self.btn_extract_range.setText(f"Extract Range ({self._format_time(self.end_time_ms - self.start_time_ms)})")
        else:
            self.btn_extract_range.setEnabled(False)
            self.btn_extract_range.setText("Extract Range")

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

    def _run_extraction(self, start: int, end: int, is_range: bool):
        self.extractor_worker = FrameExtractorWorker(
            video_path=self.video_path,
            output_dir=str(self.extraction_dir),
            start_ms=start,
            end_ms=end,
            is_range=is_range
        )
        self.extractor_worker.signals.finished.connect(self._on_extraction_finished)
        self.extractor_worker.signals.error.connect(lambda e: QMessageBox.warning(self, "Extraction Error", e))
        QThreadPool.globalInstance().start(self.extractor_worker)

    @Slot(list)
    def _on_extraction_finished(self, new_paths: List[str]):
        if not new_paths:
            QMessageBox.information(self, "Info", "No frames extracted.")
            return
        self.current_extracted_paths.extend(new_paths)
        unique_paths = list(dict.fromkeys(self.current_extracted_paths)) 
        self.current_extracted_paths = unique_paths
        self.start_loading_gallery(self.current_extracted_paths)
        QMessageBox.information(self, "Success", f"Extracted {len(new_paths)} images. Total: {len(self.current_extracted_paths)}")

    def _format_time(self, ms: int) -> str:
        seconds = (ms // 1000) % 60
        minutes = (ms // 60000) % 60
        return f"{minutes:02}:{seconds:02}"
