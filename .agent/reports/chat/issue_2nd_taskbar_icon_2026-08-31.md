# Exit-to-background duplicate taskbar icon

Root cause verified on the live KDE Plasma 6.6.6 / Wayland session:
`_apply_startup_preferences()` could create `self._tray_icon`, after which
`MainWindow.__init__` overwrote that reference with `None`. The original,
parented `QSystemTrayIcon` remained alive; the first close-to-background then
created another one.

The live `org.kde.StatusNotifierWatcher` listed two Image Toolkit notifier
registrations from the same `python backend/main.py` PID. This rules out the
previous KWin app-id theory as the primary defect.

The first reference-order correction exposed the pre-show tray construction
hazard documented in the lifecycle code: the app crashed after startup when
the saved preference kept that icon alive. The final fix initializes the
reference before preferences **and defers native tray creation to the first
background close**. Focused GUI regressions: 3 passed. No running app was
restarted or otherwise interrupted during diagnosis.
