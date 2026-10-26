# Cross-check: classic (PySide6) vs the Tauri pages mounted in `frontend/src/shell/views.tsx`

Four read-only passes compared `CLASSIC_TAB_ROUTES` and the widgets those factories build with the pages `views.tsx` actually mounts. Source: Harbinger, 2026-10-27.

| Area | Parity | Partial | Missing |
|---|---|---|---|
| Convert, merge, similarity, extractor, wallpaper | 0 | 5 | 0 |
| Library, preview, settings, login, logs, metadata | 0 | 11 | 0 |
| Crawler, requests, drive sync, media loader, reverse search, entity recon, cloud jobs, cloud compute | 0 | 8 | 0 |
| Eight stitch routes, hybrid editor, three manga routes, deep learning, ComfyUI | 0 | 20 | 1 (`ml.comfyui` has no webview) |

"Partial" means a route exists and a few fields submit. The classic task is still absent: galleries, batch jobs, canvases, a library session, and the live engines.

- Convert is one file. Qt scans a directory, converts the selection, and can delete originals.
- Similarity is an average-hash of pasted paths. Qt scans two trees and deletes duplicates.
- Video extractor only runs ffprobe. The player, range extract, GIF, MP4 and queue are absent.
- Monitor wallpaper is a path list. Qt's node graph is absent.
- Listings in Tauri is a filename list, and the sidecar's library store is unset, so search, management and the data browser do not open `library.db`. Scan can walk a folder, then save fails closed.
- Settings is six section titles. Login checks the vault and then shuts that process down, so the library stays disconnected.
- All eight stitch routes share one status panel. `stitch.status` returns "stitch pipeline is not started".
- Deep learning is one "inspect a run directory" form. ComfyUI has no page.
- Drive sync and media loader only record a plan (`submitted: false`, `downloaded: false`). The crawler reports success with zero downloads. Cloud submit stays refused because `cloud_service` is never set.

Benchmarks is the one Tauri page with no classic tab. It reads existing JSON reports.
