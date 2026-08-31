# Exit-to-background duplicate taskbar icon

Root cause verified on the live KDE Plasma 6.6.6 / Wayland session:
`_apply_startup_preferences()` could create `self._tray_icon`, after which
`MainWindow.__init__` overwrote that reference with `None`. The original,
parented `QSystemTrayIcon` remained alive; the first close-to-background then
created another one.

The live `org.kde.StatusNotifierWatcher` listed two Image Toolkit notifier
registrations from the same `python backend/main.py` PID. This rules out the
previous KWin app-id theory as the primary defect.

Fixed by initializing `_tray_icon` before startup preferences. Focused GUI
regression: `test_startup_tray_icon_reference_is_not_lost` (1 passed). No
running app was restarted or otherwise interrupted during diagnosis.
