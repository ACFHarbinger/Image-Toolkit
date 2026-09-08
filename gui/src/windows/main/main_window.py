"""``MainWindow`` -- composed controllers plus Qt-override mixins (F22 / #544)."""

from __future__ import annotations

import logging

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
from gui.src.preferences import PreferenceStore
from gui.src.windows.settings.app_settings import AppSettings

from ...constants import NEW_LIMIT_MB
from ..cloud import CloudComputeWindow
from ..settings import SettingsWindow
from ..window_manager import register_window
from ..window_service import WindowService
from ._global_search import MainGlobalSearchController
from ._header_builder import MainHeaderBuilderController
from ._lifecycle import _LifecycleMixin
from ._load_tab_config import MainLoadTabConfigController
from ._notify import show_main_status, show_tray_notification
from ._runtime_shell import MainRuntimeShellController
from ._save_tab_config import MainSaveTabConfigController
from ._session_recovery import MainSessionRecoveryController
from ._shortcuts import MainShortcutOverlayController
from ._startup_prefs import MainStartupPrefsController
from ._tab_registry import MainTabRegistryController
from ._tab_search import MainTabSearchController
from ._theme import MainThemeController
from ._tray import MainTrayController
from ._workflow_templates import MainWorkflowTemplatesController
from ._zoom import _ZoomMixin

logger = logging.getLogger(__name__)


class MainWindow(
    # F22: Qt virtuals stay on mixins still in the MRO. Follow-up PRs move
    # one override each. Mixins MUST precede QWidget so closeEvent /
    # keyPressEvent / showEvent / wheelEvent / paintEvent are not shadowed.
    _LifecycleMixin,
    _ZoomMixin,
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
        register_window(self, role="main")
        self.window_service = WindowService(self)

        # Store the authenticated vault manager instance
        self.vault_manager = vault_manager
        self.enable_manager = enable_manager
        self.toast_manager = ToastManager(self)

        # Composed controllers (ui-arch-23, #544). ``tab`` on each is this
        # MainWindow (a QWidget) — same TabBoundController API as Search/Scan.
        self.header_builder = MainHeaderBuilderController(self)
        self.runtime_shell = MainRuntimeShellController(self)
        self.tab_registry = MainTabRegistryController(self)
        self.theme_controller = MainThemeController(self)
        self.tray_controller = MainTrayController(self)
        self.tab_search = MainTabSearchController(self)
        self.global_search = MainGlobalSearchController(self)
        self.workflow_templates = MainWorkflowTemplatesController(self)
        self.shortcut_overlay = MainShortcutOverlayController(self)
        self.save_tab_config = MainSaveTabConfigController(self)
        self.load_tab_config = MainLoadTabConfigController(self)
        self.startup_prefs = MainStartupPrefsController(self)
        self.session_recovery = MainSessionRecoveryController(self)

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
                self._refresh_account_credentials(
                    self.vault_manager.load_account_credentials()
                )
                account_name = self.cached_creds.get("account_name", "Authenticated User")
                if getattr(self.vault_manager, "is_guest", False) is True:
                    account_name = f"{account_name} (Guest)"
                initial_theme = self.cached_creds.get("theme", "dark")
                # #525's attach_vault_credentials() wiring now lives inside
                # _refresh_account_credentials() (see below), called just
                # above (line ~105) -- this used to be a separate inline
                # call here, now redundant with that centralized helper.
            except Exception as e:
                print(f"Warning: Failed to load account credentials or theme: {e}")

        # GUI/UX §2.8 — Option C: follow OS color scheme when no vault preference is stored.
        # cached_creds may be empty on first launch; fall back to OS preference in that case.
        if not self.cached_creds.get("theme"):
            try:
                os_scheme = QGuiApplication.styleHints().colorScheme()
                initial_theme = "light" if os_scheme == Qt.ColorScheme.Light else "dark"
            except Exception:
                logger.debug("Suppressed Exception in MainWindow.__init__", exc_info=True)

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

        self._using_runtime_shell = self._runtime_shell_enabled()
        if self._using_runtime_shell:
            # No legacy tabs on this path — PreferenceStore flag is the rollback.
            self.all_tabs = {}
            self.command_combo = None
            self.tabs = None
            vbox.addWidget(self._create_runtime_shell(dropdown=dropdown, enable_manager=enable_manager))
        else:
            # --- Tab Initialization / LINK TABS / all_tabs dict ---
            self._create_tabs(dropdown, enable_manager)

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
        if not self._using_runtime_shell:
            self._apply_startup_preferences()
        else:
            # #516: _apply_startup_preferences() is gated off entirely on the
            # runtime shell path (classic tab/category wiring is N/A there),
            # but that meant the device-owned tray preference -- read from
            # PreferenceStore via AppSettings, not tab-coupled at all -- was
            # never applied either, leaving _minimize_to_tray stuck at its
            # hardcoded False default regardless of what the user configured.
            self._apply_tray_preference()

        # Apply tab configs after global preferences so profile settings take priority (deferred)
        # self._apply_active_tab_configs() is now called in the deferred do_restore function below to avoid layout race conditions.

        self.settings_button.clicked.connect(self.open_settings_window)
        if hasattr(self, "cloud_compute_button"):
            self.cloud_compute_button.clicked.connect(self.open_cloud_compute_window)

        # §2.10C / §2.39 — status bar at the bottom of the main window
        if self._using_runtime_shell:
            from gui.src.components.widgets.telemetry_status_bar import TelemetryStatusBar

            self._status_bar = TelemetryStatusBar(
                parent=self,
                event_hub=self.module_event_hub,
                context=self.module_context,
            )
            if hasattr(self, "shell_layout_manager"):
                self._status_bar.layout_toggle_requested.connect(
                    self.shell_layout_manager.toggle_nav_mode
                )
        else:
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
            logger.debug("Suppressed Exception in MainWindow.__init__", exc_info=True)

        # §3.17 — restore saved window geometry (before showMaximized so it can override)
        _geom = AppSettings.mainwindow_geometry()
        if _geom:
            self.restoreGeometry(_geom)
        else:
            self.showMaximized()
        QTimer.singleShot(0, self._restore_session_recovery)

    def _refresh_account_credentials(self, credentials: dict) -> None:
        """Install one committed account snapshot for UI and preferences."""
        self.cached_creds = credentials
        PreferenceStore.instance().attach_vault_credentials(
            credentials,
            self.vault_manager,
            credentials.get("account_name", "Authenticated User"),
        )

    def open_settings_window(self):
        if not self.settings_window:
            self.settings_window = SettingsWindow(window_service=self.window_service)
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

    # --- Facade delegation (composed controllers) ---
    def _build_header(self, account_name: str, app_icon) -> QWidget:
        return self.header_builder._build_header(account_name, app_icon)

    def _runtime_shell_enabled(self) -> bool:
        return self.runtime_shell._runtime_shell_enabled()

    def _create_runtime_shell(self, *, dropdown: bool, enable_manager: bool) -> QWidget:
        return self.runtime_shell._create_runtime_shell(
            dropdown=dropdown, enable_manager=enable_manager
        )

    def _activate_initial_runtime_module(self) -> None:
        self.runtime_shell._activate_initial_runtime_module()

    def _dispose_runtime_shell(self) -> None:
        self.runtime_shell._dispose_runtime_shell()

    def _toggle_context_inspector(self) -> None:
        self.runtime_shell._toggle_context_inspector()

    def _create_tabs(self, dropdown: bool, enable_manager: bool) -> None:
        self.tab_registry._create_tabs(dropdown, enable_manager)

    def _activate_legacy_module(self, intent) -> None:
        self.tab_registry._activate_legacy_module(intent)

    def _handle_legacy_path_import(self, intent) -> None:
        self.tab_registry._handle_legacy_path_import(intent)

    def prime_application_palette(self, theme_name: str) -> None:
        self.theme_controller.prime_application_palette(theme_name)

    def set_application_theme(self, theme_name, *, preferences: dict | None = None):
        self.theme_controller.set_application_theme(theme_name, preferences=preferences)

    def apply_theme_pack(self, pack) -> None:
        self.theme_controller.apply_theme_pack(pack)

    def _toggle_theme(self) -> None:
        self.theme_controller._toggle_theme()

    def _setup_tray_icon(self, app_icon=None) -> None:
        self.tray_controller._setup_tray_icon(app_icon)

    def _tray_show_window(self) -> None:
        self.tray_controller._tray_show_window()

    def _tray_toggle_daemon(self) -> None:
        self.tray_controller._tray_toggle_daemon()

    def _tray_next_wallpaper(self) -> None:
        self.tray_controller._tray_next_wallpaper()

    def _on_tray_activated(self, reason) -> None:
        self.tray_controller._on_tray_activated(reason)

    def tray_notify(self, title: str, message: str, timeout_ms: int = 4000) -> None:
        self.tray_controller.tray_notify(title, message, timeout_ms)

    def set_minimize_to_tray(self, enabled: bool) -> None:
        self.tray_controller.set_minimize_to_tray(enabled)

    def _open_tab_search(self) -> None:
        self.tab_search._open_tab_search()

    def _open_runtime_module_search(self) -> None:
        self.tab_search._open_runtime_module_search()

    def _select_tab_by_name(self, tab_name: str) -> None:
        self.tab_search._select_tab_by_name(tab_name)

    def _iter_gallery_tabs(self):
        return self.global_search._iter_gallery_tabs()

    def _open_global_search(self) -> None:
        self.global_search._open_global_search()

    def _load_workflow_templates(self) -> dict:
        return self.workflow_templates._load_workflow_templates()

    def _save_workflow_templates(self, templates: dict) -> bool:
        return self.workflow_templates._save_workflow_templates(templates)

    def _open_workflow_templates_dialog(self) -> None:
        self.workflow_templates._open_workflow_templates_dialog()

    def _run_workflow_template(self, name: str) -> None:
        self.workflow_templates._run_workflow_template(name)

    def _open_workflow_template_builder(self) -> None:
        self.workflow_templates._open_workflow_template_builder()

    def _open_shortcut_overlay(self) -> None:
        self.shortcut_overlay._open_shortcut_overlay()

    def _open_save_tab_config_dialog(self) -> None:
        self.save_tab_config._open_save_tab_config_dialog()

    def _save_tab_config_to_vault(self, tab_instance, config_name: str) -> None:
        self.save_tab_config._save_tab_config_to_vault(tab_instance, config_name)

    def _open_load_tab_config_dialog(self) -> None:
        self.load_tab_config._open_load_tab_config_dialog()

    def _load_tab_config_into(self, tab_instance, config_data: dict, config_name: str) -> None:
        self.load_tab_config._load_tab_config_into(tab_instance, config_data, config_name)

    def _apply_tray_preference(self) -> None:
        self.startup_prefs._apply_tray_preference()

    def _sanitize_config_if_needed(self, config_data: dict) -> dict:
        return self.startup_prefs._sanitize_config_if_needed(config_data)

    def _apply_active_tab_configs(self, previous_configs: dict | None = None) -> None:
        self.startup_prefs._apply_active_tab_configs(previous_configs=previous_configs)

    def _apply_startup_preferences(self) -> None:
        self.startup_prefs._apply_startup_preferences()

    def _load_recovery_data(self) -> dict:
        return self.session_recovery._load_recovery_data()

    def _runtime_shell_startup_module_id(self, category_name: str, tab_name: str):
        return self.session_recovery._runtime_shell_startup_module_id(category_name, tab_name)

    def _restore_runtime_shell_session_recovery(self) -> None:
        self.session_recovery._restore_runtime_shell_session_recovery()

    def _restore_session_recovery(self) -> None:
        self.session_recovery._restore_session_recovery()

    def _restore_tab_config_instance(self, tab_instance, tab_configs, error_context: str) -> None:
        self.session_recovery._restore_tab_config_instance(tab_instance, tab_configs, error_context)

    def _do_restore_configs(self, recovery_level, active_category, active_tab_name, tab_configs) -> None:
        self.session_recovery._do_restore_configs(
            recovery_level, active_category, active_tab_name, tab_configs
        )

    def _save_runtime_shell_session_recovery(self) -> None:
        self.session_recovery._save_runtime_shell_session_recovery()

    def _save_session_recovery(self) -> None:
        self.session_recovery._save_session_recovery()


__all__ = ["MainWindow", "show_main_status", "show_tray_notification"]
