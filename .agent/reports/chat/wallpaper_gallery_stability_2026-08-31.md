# Wallpaper gallery browse stability

The virtual gallery eagerly started thumbnail work for every path in both
linked wallpaper panels and left queued workers alive after a directory change.
That created blank placeholder rows and a native decoder burst during browse /
startup recovery.

The gallery still warms the whole directory, but the model uses at most two
decoders and a directory change stops active workers and clears queued work
before the new generation starts. The affected GIF directory decoded cleanly
in an isolated model check (65 cached, 0 failed).

Validation: `test_virtual_gallery.py`, `test_wallpaper_gallery.py`, and
`test_wallpaper_linked_panel_scan_race.py` — 42 passed.
