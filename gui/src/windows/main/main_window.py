"""``MainWindow`` -- composed from per-concern mixins."""

from __future__ import annotations

from backend.src._version import __version__
from backend.src.core.vault_manager import VaultManager
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QImageReader
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStatusBar,
    QSystemTrayIcon,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from gui.src.components.widgets.toast_widget import ToastManager
from gui.src.windows.settings.app_settings import AppSettings

from ...constants import NEW_LIMIT_MB
from ..cloud_compute import CloudComputeWindow
from ..settings import SettingsWindow
from ._global_search import _GlobalSearchMixin
from ._header_builder import _HeaderBuilderMixin
from ._lifecycle import _LifecycleMixin
from ._load_tab_config import _LoadTabConfigMixin
from ._notify import show_main_status, show_tray_notification
from ._save_tab_config import _SaveTabConfigMixin
from ._session_recovery import _SessionRecoveryMixin
from ._shortcuts import _ShortcutOverlayMixin
from ._startup_prefs import _StartupPrefsMixin
from ._tab_registry import _TabRegistryMixin
from ._tab_search import _TabSearchMixin
from ._theme import _ThemeMixin
from ._tray import _TrayMixin
from ._workflow_templates import _WorkflowTemplatesMixin
from ._zoom import _ZoomMixin


class MainWindow(
    # Mixins MUST precede QWidget in MRO order (see gui/src/tabs/core/merge_tab/
    # manager.py for the bug this pattern fixes): several mixin methods here
    # (closeEvent, keyPressEvent, showEvent, wheelEvent) override same-named
    # methods QWidget itself defines, and would otherwise be silently shadowed.
    _HeaderBuilderMixin,
    _TabRegistryMixin,
    _ThemeMixin,
    _TrayMixin,
    _TabSearchMixin,
    _GlobalSearchMixin,
    _WorkflowTemplatesMixin,
    _ShortcutOverlayMixin,
    _SaveTabConfigMixin,
    _LoadTabConfigMixin,
    _StartupPrefsMixin,
    _SessionRecoveryMixin,
    _ZoomMixin,
    _LifecycleMixin,
    QWidget,
):
    def __init__(
        self,
        vault_manager: VaultManager,
        dropdown=True,
        app_icon=None,
        enable_manager=False,
    ):
        super().__init__()
        # MainWindow is itself the top-level widget (no separate central
        # widget/QStackedWidget) -- named so the glassmorphism QSS's
        # `QWidget#central_widget` selector actually matches something (#449).
        self.setObjectName("central_widget")

        # Store the authenticated vault manager instance
        self.vault_manager = vault_manager
        self.enable_manager = enable_manager
        self.toast_manager = ToastManager(self)

        self.setWindowTitle(f"Image Database and Edit Toolkit — v{__version__}")
        self.setMinimumWidth(800)
        self.setMinimumHeight(700)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        QImageReader.setAllocationLimit(NEW_LIMIT_MB)

        # --- LOAD THEME AND ACCOUNT INFO FROM VAULT (LOAD 1 OF 1) ---
        account_name = "Authenticated User"
        initial_theme = "dark"

        # Load credentials once to get theme and account name
        self.cached_creds = {}
        if self.vault_manager is not None:
            try:
                self.cached_creds = self.vault_manager.load_account_credentials()
                account_name = self.cached_creds.get("account_name", "Authenticated User")
                if getattr(self.vault_manager, "is_guest", False) is True:
                    account_name = f"{account_name} (Guest)"
                initial_theme = self.cached_creds.get("theme", "dark")
            except Exception as e:
                print(f"Warning: Failed to load account credentials or theme: {e}")

        # GUI/UX §2.8 — Option C: follow OS color scheme when no vault preference is stored.
        # cached_creds may be empty on first launch; fall back to OS preference in that case.
        if not self.cached_creds.get("theme"):
            try:
                os_scheme = QGuiApplication.styleHints().colorScheme()
                initial_theme = "light" if os_scheme == Qt.ColorScheme.Light else "dark"
            except Exception:
                pass

        self.current_theme = initial_theme
        # Prime the QPalette before building any tabs -- OptionalField and
        # friends read QApplication.palette() at construction time, and on a
        # frozen build with no platform-theme plugin it's still Qt's light
        # default until set_application_theme() runs (which happens after
        # _create_tabs() below). See _theme.py::prime_application_palette.
        self.prime_application_palette(self.current_theme)

        vbox = QVBoxLayout()
        self.settings_window = None
        # Must exist before startup preferences run: that path may construct a
        # tray icon. Resetting it afterward loses the reference while the
        # parented QSystemTrayIcon stays alive, so close-to-background creates
        # a second native tray/SNI surface.
        self._tray_icon: QSystemTrayIcon | None = None

        # --- Application Header ---
        header_widget = self._build_header(account_name, app_icon)
        vbox.addWidget(header_widget)

        # --- Tab Initialization / LINK TABS / all_tabs dict ---
        self._create_tabs(dropdown, enable_manager)

        # --- APPLY ACTIVE DEFAULT CONFIGURATIONS ---
        # Note: We wait to apply these configs until after startup preferences are applied

        # --- Command Selection (built after all_tabs so the list is always in sync) ---
        command_layout = QHBoxLayout()
        command_label = QLabel("Select Category:")
        command_label.setStyleSheet("font-weight: 600;")
        command_layout.addWidget(command_label)

        self.command_combo = QComboBox()
        self.command_combo.addItems(list(self.all_tabs.keys()))
        self.command_combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        command_layout.addWidget(self.command_combo)
        command_layout.addStretch()
        vbox.addLayout(command_layout)

        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        # §2.35 — background canvas update connections
        from gui.src.styles.background_canvas import BackgroundCanvasController
        BackgroundCanvasController.instance().background_changed.connect(self.update)
        self.tabs.currentChanged.connect(lambda _: self.update())

        # Connect after populating so the initial currentTextChanged fires correctly.
        self.command_combo.currentTextChanged.connect(self.on_command_changed)
        self.on_command_changed(self.command_combo.currentText())


        # Default before _apply_startup_preferences() so a saved
        # "minimize to tray" preference isn't stomped back to False by the
        # unconditional reset further down (that reset is only meant for
        # _tray_icon, see its comment) -- must exist here for guest/first
        # launch, where _apply_startup_preferences() has no saved prefs to
        # apply and returns early.
        self._minimize_to_tray: bool = False

        # GUI/UX §2.16 — wire vault preferences to runtime at startup
        self._apply_startup_preferences()

        # Apply tab configs after global preferences so profile settings take priority (deferred)
        # self._apply_active_tab_configs() is now called in the deferred do_restore function below to avoid layout race conditions.

        self.settings_button.clicked.connect(self.open_settings_window)
        if hasattr(self, "cloud_compute_button"):
            self.cloud_compute_button.clicked.connect(self.open_cloud_compute_window)

        # §2.10C — non-blocking status bar at the bottom of the main window
        self._status_bar = QStatusBar()
        self._status_bar.setSizeGripEnabled(False)
        self._status_bar.setMaximumHeight(24)
        vbox.addWidget(self._status_bar)

        self.setLayout(vbox)
        self.set_application_theme(self.current_theme)

        # GUI/UX §2.8 — live OS color-scheme changes (e.g. user toggles dark mode in KDE/Windows)
        try:

            def _on_os_scheme_changed(scheme):
                if not self.cached_creds.get("theme"):
                    new = "light" if scheme == Qt.ColorScheme.Light else "dark"
                    self.set_application_theme(new)

            QGuiApplication.styleHints().colorSchemeChanged.connect(_on_os_scheme_changed)
        except Exception:
            pass

        # §3.17 — restore saved window geometry (before showMaximized so it can override)
        _geom = AppSettings.mainwindow_geometry()
        if _geom:
            self.restoreGeometry(_geom)
        else:
            self.showMaximized()
        QTimer.singleShot(0, self._restore_session_recovery)

    def open_settings_window(self):
        if not self.settings_window:
            self.settings_window = SettingsWindow(self)
            self.settings_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.settings_window.destroyed.connect(lambda: self._reset_settings_window_ref())
        self.settings_window.show()
        self.settings_window.activateWindow()

    def _reset_settings_window_ref(self):
        self.settings_window = None

    def open_cloud_compute_window(self):
        if not self.cloud_compute_window:
            self.cloud_compute_window = CloudComputeWindow(self)
            self.cloud_compute_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self.cloud_compute_window.destroyed.connect(lambda: self._reset_cloud_compute_window_ref())
        self.cloud_compute_window.show()
        self.cloud_compute_window.activateWindow()

    def _reset_cloud_compute_window_ref(self):
        self.cloud_compute_window = None

    def show_toast(self, message: str, toast_type: str = "info", duration_ms: int = 2500):
        """Show a floating toast notification (GUI/UX §2.10A)."""
        self.toast_manager.show_toast(message, toast_type, duration_ms)

__all__ =  ["MainWindow", "show_main_status", "show_tray_notification"]
