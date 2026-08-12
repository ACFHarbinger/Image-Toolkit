# Hybrid Image Editor (HIE) — Tauri Frontend (`frontend/`)

This directory contains the web-native **Tauri UI frontend** for the Hybrid Image Editor (HIE).

## Multi-Hosting Architecture
- **Embedded Mode:** Integrated directly into Image-Toolkit's primary Tauri frontend as a dedicated workspace tab.
- **Standalone Mode:** The Vite shell runs independently today; the Tauri native wrapper is intentionally a follow-up bootstrap step (`npm run tauri dev`).

## Capabilities
- High-performance Canvas 2D / WebGL 2 rendering viewport.
- Real-time ML/DL inference controls and layer management.
- Non-destructive mathematical optimization parameter adjustment.

## Current UI

The Vite entry point now provides a dark HIE workspace with a canvas surface,
layer stack, assistance tool selection, proposal preview, explicit acceptance,
timeline, and Image-Toolkit return link. It is intentionally framework-light
so the same view can be embedded by the Image-Toolkit Tauri application.

```bash
npm install
npm run build
npm run dev
```

The buttons currently expose host seams for media open/export. Tauri commands
and the Python middleware transport can replace those handlers without
changing the proposal-first UI state model.
