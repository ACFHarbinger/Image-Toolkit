from PySide6.QtCore import QObject, Signal, Property, Slot, QTimer

class SlideshowBackend(QObject):
    image_changed = Signal()
    playing_changed = Signal()
    interval_changed = Signal()
    navigation_info_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._images = []
        self._current_index = 0
        self._is_playing = False
        self._interval = 5000 # ms
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.next)

    # --- Properties ---

    @Property(str, notify=image_changed)
    def currentImagePath(self):
        if not self._images:
            return ""
        if 0 <= self._current_index < len(self._images):
            return self._images[self._current_index]
        return ""

    @Property(bool, notify=playing_changed)
    def isPlaying(self):
        return self._is_playing

    @Property(int, notify=interval_changed)
    def interval(self):
        return self._interval
    
    @interval.setter
    def interval(self, val):
        if self._interval != val:
            self._interval = val
            self.interval_changed.emit()
            if self._is_playing:
                self._timer.start(self._interval)

    @Property(str, notify=navigation_info_changed)
    def navigationInfo(self):
        if not self._images:
            return "0 / 0"
        return f"{self._current_index + 1} / {len(self._images)}"

    # --- Slots ---

    @Slot(list)
    def setImages(self, image_list):
        self._images = [str(p) for p in image_list if p]
        self._current_index = 0
        self.image_changed.emit()
        self.navigation_info_changed.emit()
        # Auto start? No.

    @Slot()
    def next(self):
        if not self._images:
            return
        self._current_index = (self._current_index + 1) % len(self._images)
        self.image_changed.emit()
        self.navigation_info_changed.emit()

    @Slot()
    def previous(self):
        if not self._images:
            return
        self._current_index = (self._current_index - 1 + len(self._images)) % len(self._images)
        self.image_changed.emit()
        self.navigation_info_changed.emit()

    @Slot(bool)
    def setPlaying(self, playing):
        if self._is_playing == playing:
            return
        self._is_playing = playing
        self.playing_changed.emit()
        if playing:
            self._timer.start(self._interval)
        else:
            self._timer.stop()

    @Slot(int)
    def updateInterval(self, ms):
        self.interval = ms
