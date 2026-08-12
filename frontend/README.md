# Hybrid Image Editor (HIE) — Tauri Frontend (`frontend/`)

This directory contains the web-native **Tauri UI frontend** for the Hybrid Image Editor (HIE).

## Multi-Hosting Architecture
- **Embedded Mode:** Integrated directly into Image-Toolkit's primary Tauri frontend as a dedicated workspace tab.
- **Standalone Mode:** The Vite shell runs independently today; the Tauri native wrapper is intentionally a follow-up bootstrap step (`npm run tauri dev`).

## Capabilities
- High-performance Canvas 2D / WebGL 2 rendering viewport.
- Real-time ML/DL inference controls and layer management.
- Non-destructive mathematical optimization parameter adjustment.
