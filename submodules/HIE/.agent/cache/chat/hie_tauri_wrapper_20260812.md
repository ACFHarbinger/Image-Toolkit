# HIE Tauri Wrapper — Chat

Date: 2026-08-12

Added a minimal Tauri 2 host under `frontend/src-tauri/` with matching
`open_media`, `export_document`, and `notify` commands. The web frontend calls
these through the typed `HieHost` bridge when running inside Tauri, while
standalone Vite keeps its browser fallback. Media and document routing remain
host-owned seams until the IPC contract is finalized.
