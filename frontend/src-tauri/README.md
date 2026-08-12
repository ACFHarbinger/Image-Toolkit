# Tauri host boundary

This directory contains the native Tauri host for HIE’s standalone desktop
mode. The web UI in `../src/` is also designed to be mounted as a tab in
Image-Toolkit’s Tauri application.

```bash
cd frontend
npm install
npm run tauri dev
```

The Rust commands mirror `src/host.ts`: `open_media`, `export_document`, and
`notify`. They return a versioned `IpcResponse` envelope matching
`middleware/src/hie_middleware/ipc.py`; request IDs are supplied by the web
host and the current media/export responses intentionally report
`available: false` until a host-owned handler is connected.
