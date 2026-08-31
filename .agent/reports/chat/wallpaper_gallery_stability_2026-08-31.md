# Wallpaper gallery browse stability

The virtual gallery eagerly started thumbnail work for every path in both
linked wallpaper panels and left queued workers alive after a directory change.
That created blank placeholder rows and a native decoder burst during browse /
startup recovery.

The gallery still warms the whole directory, but the model uses at most two
decoders and a directory change stops active workers and clears queued work
before the new generation starts. The source panel now emits its linked-panel
mirror only after image/video enumeration and its virtual-gallery pool have
settled; the peer reuses the shared bounded thumbnail cache instead of
decoding the directory concurrently. The affected GIF directory decoded
cleanly in an isolated model check (65 cached, 0 failed).

Native thumbnail drags mark the active DnD loop for Wallpaper's application
event filter, so wheel scrolling remains available over a monitor target.

Validation: `test_wallpaper_event_filter.py`,
`test_wallpaper_linked_panel_scan_race.py`, `test_gallery_crash_stress.py`,
and `test_wallpaper_gallery.py` — 25 passed.
