# Your checklist

## Tray (S-03)
Run each on KDE Wayland, GNOME Wayland, X11, Windows, macOS.
- [ ] Tray icon appears; left click restores the main window
- [ ] Close hides the main window and the cloud-jobs pop-out (both leave the taskbar)
- [ ] Close again, then Show Window: both come back
- [ ] Closing only the pop-out leaves the main window up
- [ ] Quit exits the app; the sidecar and slideshow daemon keep running
- [ ] Windows: a second launch focuses the running window
- [ ] GNOME/X11: note if the icon needs an extension / is XEmbed

## Wallpaper (S-07)
- [ ] KDE: one set gives each monitor a different image
- [ ] KDE: fill / fit / stretch change the look
- [ ] KDE: the slideshow presenter window opens, shows one monitor's queue, changes nothing
- [ ] KDE: slideshow advances each monitor; hiding the main window doesn't stop it
- [ ] GNOME: two monitors show different images (spanned image OK); dark theme matches
- [ ] Windows: different image per monitor; single-monitor style applies
- [ ] macOS: note what works

## Drag and drop (S-05), Linux / Windows / macOS
- [ ] Dropping image files onto the app works; bad paths are refused
- [ ] Dragging a preview out copies the file to the file manager

## Use each page once in the Tauri app
Then tell me, and I'll mark the row done.
- [ ] Convert
- [ ] Cloud Jobs window
- [ ] Library: Listings, Search, Preview, Scan, Management, Data Browser
- [ ] System: Merge, Similarity, Extractor
- [ ] Web: Crawler, Requests, Cloud Sync, Media Loader, Reverse Search, Entity Recon
- [ ] Deep Learning
- [ ] Wallpaper
- [ ] Stitching, Hybrid Editor, Manga (3 pages)
- [ ] Settings, Auth, Logs, Metadata, Cloud Compute setup

## Decide
- [ ] Tray/window and wallpaper: finish on Tauri, or keep on PySide6 as a recorded exception
- [ ] Approve deleting `gui/`, the Qt dependencies and `ImageToolkit.spec` (last step)
