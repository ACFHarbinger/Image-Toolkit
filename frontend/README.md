# Hybrid Image Editor (HIE) — Tauri Frontend (`frontend/`)

This directory contains the web-native **Tauri UI frontend** for the Hybrid Image Editor (HIE), plus the **embeddable React tab** consumed by Image-Toolkit.

## Multi-Hosting Architecture

- **Embedded Mode (Image-Toolkit):** The parent React app depends on this package
  (`hie-frontend` via `file:../submodules/HIE/frontend`) and re-exports
  `HieEditorTab` from `src/embed/react/`. Editor UI changes land here first;
  Image-Toolkit only keeps a thin re-export under `frontend/src/tabs/editor/`.
- **Standalone Mode:** The Vite shell (`src/main.ts`) runs independently, or the
  Tauri wrapper can be launched with `npm run tauri dev`.

## Layout

| Path | Role |
| --- | --- |
| `src/main.ts` | Standalone Vite workspace shell |
| `src/host.ts` | Typed `HieHost` IPC seam (browser / Tauri / injected) |
| `src/embed/react/HieEditorTab.tsx` | React Hybrid Editor tab for Image-Toolkit |

## Capabilities

- High-performance Canvas 2D / WebGL 2 rendering viewport (standalone shell).
- Real-time ML/DL inference controls and layer management.
- Non-destructive mathematical optimization parameter adjustment.
- Versioned host IPC: `open_media`, `export_document`, `notify`,
  `list_capabilities`, `preview_policy`, `accept_proposal`, `submit_restoration`.

## Running standalone

```bash
npm install
npm run build
npm run dev
```

A Tauri or Image-Toolkit host can inject an implementation through
`window.__HIE_HOST__`; standalone Vite uses a safe browser fallback.
