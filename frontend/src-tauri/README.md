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
`notify`. Media/document routing remains host-owned until the middleware IPC
contract is finalized.
