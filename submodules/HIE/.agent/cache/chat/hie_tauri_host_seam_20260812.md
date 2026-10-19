# HIE Tauri Host Seam — Chat

Date: 2026-08-12

Added the typed `HieHost` interface in `frontend/src/host.ts` for media open,
document export, and host notifications. The frontend now uses this interface
instead of anonymous button callbacks. Tauri and Image-Toolkit can inject
native implementations through `window.__HIE_HOST__`, while standalone Vite
uses a browser-safe fallback.
