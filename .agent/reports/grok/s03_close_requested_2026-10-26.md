# S-03 CloseRequested hide, restore, and tray

— Grok, 2026-10-26. Issue #889 follow-up. The window was not launched. No OS checklist box is ticked.

## What the code does

`on_window_event` handles `WindowEvent::CloseRequested` through `close_action`:

- `main` is `HideAll`: `prevent_close`, then `hide_all` (every hide-on-close webview, skip the taskbar, merge visible labels into the saved set).
- `cloud.jobs` / `cloud-jobs` and `library.preview` / `library-preview` are `HideThis`: `prevent_close`, hide that window, skip the taskbar.
- `tray`, `slideshow`, and an unknown label are `Allow`. The close is not prevented.

`restore` shows the saved labels, adds `main` when it is missing, clears skip-taskbar, unminimizes, and focuses `main`. A second hide with nothing visible keeps the earlier labels (`merge_hidden_labels`).

Show Window and a left-button release are `TrayAction::Restore` and call `restore`. The menu is not shown on left click (`show_menu_on_left_click(false)`). Quit is `app.exit(0)`. Stop all cloud activity stays `StopCloud` and only logs that the daemon command is missing.

## Tests

`cargo test -p app --lib` was 17 passed, including `close_requested_hides_main_and_popouts_and_allows_the_rest`, `show_restores_and_quit_exits`, and `left_release_restores_and_other_clicks_do_not`. They do not open a compositor.

The crate did not compile on this main: `lib.rs` still registered `auth_commands` and `database_commands` after those modules were deleted. Those registrations are removed so the tray tests can build. `settings_commands` stays.

## This machine

`XDG_SESSION_TYPE=wayland`, `XDG_CURRENT_DESKTOP=KDE`, `WAYLAND_DISPLAY=wayland-0`, `DISPLAY=:0` (Xwayland). `loginctl` reports one KDE Wayland user session. `gnome-shell` is not installed. `org.kde.StatusNotifierWatcher.IsStatusNotifierHostRegistered` is `true`, so Plasma has a tray host. That is not a pass for the app icon, hide, or restore.

## Checklist for Harbinger

Leave every box unchecked until a live run. Linux first.

### KDE Wayland

- [ ] The tray icon appears and survives a plasmashell redraw.
- [ ] Left click restores `main` and focuses it. Show Window does the same. Left click does not open the menu.
- [ ] Closing `main` hides `main`, a visible `cloud-jobs` pop-out, and a visible `library-preview`, and they leave the taskbar.
- [ ] Closing `main` again while they are hidden, then Show Window, restores the same set.
- [ ] Closing only a pop-out hides that window and leaves `main` up.
- [ ] Quit exits the shell. A supervisor-owned sidecar and slideshow daemon, if they were running, keep running.
- [ ] Stop all cloud activity stays disabled and does not send a daemon command.
- [ ] The tray menu does not become a second taskbar entry.

### GNOME Wayland

- [ ] The same eight checks. Record whether the icon is an AppIndicator or missing.
- [ ] If GNOME shows no icon without an extension, record the extension. Close-to-hide still has to work.

### X11 (KDE and GNOME)

- [ ] The same eight checks with `XDG_SESSION_TYPE=x11`.
- [ ] Record whether the icon is StatusNotifierItem or XEmbed.

### Windows

- [ ] The notification-area icon restores `main` and a hidden pop-out on left click and on Show Window.
- [ ] Close hides both and skips the taskbar. A second close still restores both.
- [ ] Quit exits the shell and leaves a supervisor-started daemon running.

### macOS

- [ ] The menu-bar icon restores `main` and a hidden pop-out on left click and on Show Window.
- [ ] Close hides both. Quit exits the shell and leaves a supervisor-started daemon running.
- [ ] The menu does not become a second Dock icon.

PySide6 tray and window paths stay. This note does not retire them.
