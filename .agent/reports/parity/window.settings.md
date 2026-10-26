# PARITY-GAP window.settings

Qt source: `gui/src/windows/settings/` (read-only). The Tauri window ports account display, the master-password field (refused without an injected C++ vault session), startup category, startup tab, thumbnail size, page size, confirm deletions, recursive scan, log level, the file-logging flag, and one shortcut override. Ledger row `window.settings` stays `pyside-only`.

PARITY-GAP window.settings: vault credential import — Qt "Manage Loaded Credentials" (`_build_credentials_section`) export, import, edit, and delete of vault JSON credentials is not on the Tauri window.
PARITY-GAP window.settings: vault sync and load — `_build_login_vault_section` copies secrets between `~/.image-toolkit/secrets` and the repo templates. Not ported. No second vault is implemented.
PARITY-GAP window.settings: master password re-encrypt — the new-password field is collected and sent to `prefs.set`, but the sidecar injects no C++ session, so the change returns success false and reason "C++ vault session locked". Qt `update_account_password` is not called from the shell.
PARITY-GAP window.settings: QSS — Theme Studio, the expert raw QSS override, theme-pack export (`_build_theme_studio_tab`), and the `user_theme.qss` hint in the shortcuts tab are not ported.
PARITY-GAP window.settings: bulk update — "Bulk Find and Replace / Pattern Update" (`_build_bulk_update_tab`) is not ported.
PARITY-GAP window.settings: named preference profiles — Qt profile CRUD (load, use, update, delete, save current settings as a profile in `_build_profiles_section`) is not ported. Only startup category and startup tab strings persist.
PARITY-GAP window.settings: tab configurations — startup tab-config combos (`_build_prefs_section`) and tab default configuration management (`_build_tab_defaults_section`) are not ported.
PARITY-GAP window.settings: startup session extras — restore last directory, restore last tab, close to tray, experimental runtime shell, experimental Deep Learning workspace, recent-directory limit, session recovery level, and default browse directory (`_build_session_section`) are not ported.
PARITY-GAP window.settings: favourite directories — browse, paste, and remove (`_build_favourites_section`) are not ported.
PARITY-GAP window.settings: appearance — base theme, semantic palette, font scale, density, zoom, accents, corners, shadows (`_build_appearance_section`), and the background canvas (`_build_background_section`) are not ported.
PARITY-GAP window.settings: gallery trash — "Send deleted files to system trash" is not ported. Thumbnail size, page size, confirm deletions, and recursive scan are.
PARITY-GAP window.settings: media extractor — seek, recent extractions, extraction queue, parallel processors, time format, encoder threads, gif colors, and fps clamp (`_build_media_section`) are not ported.
PARITY-GAP window.settings: slideshow defaults — interval and playback order (`_build_slideshow_section`) are not ported.
PARITY-GAP window.settings: performance cache — found, selected, and initial cache sizes (`_build_perf_section`) are not ported.
PARITY-GAP window.settings: mal auto-fill — the Jikan / official API / scrape picker (`_build_mal_section`) is not ported.
PARITY-GAP window.settings: log viewers — "View App Logs", "View Daemon Logs", and opening the log directory are not ported. Level and the file-logging flag are stored only.
PARITY-GAP window.settings: reset state — clear thumbnail cache, reset slideshow daemon, reset extraction history, clear logs, and clear tab configs and profiles (`_build_reset_state_section`) are not ported.
PARITY-GAP window.settings: shortcut editor — the Qt per-scope default toggle and multiple custom chords (`_build_shortcuts_groupbox`) are not ported. The window lists registry actions and saves one override into the keybindings file.
PARITY-GAP window.settings: reset reload relaunch — "Reset to default", "Reload settings", "Refresh Application (Relaunch)", and the unsaved-changes exit prompt are not ported. Save writes the ported fields.
