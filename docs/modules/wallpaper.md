# Wallpaper (`wallpaper`)

| Field | Value |
|---|---|
| **Capability ID** | `wallpaper` |
| **Service Package** | `middleware/src/services/wallpaper/` |
| **Frontend View** | `frontend/src/views/system/WallpaperView.tsx` |
| **Contract Schema** | `contracts/schemas/capability/wallpaper.json` |
| **Contract SHA-256** | `131289910c5109ab28b470690a8e564ebf28be35ca6b06998ef95f6f2147f609` |

## Overview

`wallpaper` manages multi-monitor desktop backgrounds, slideshow presentation queues, and background slideshow daemon state.
It interfaces through a typed contract to `WallpaperService`, which wraps `WallpaperManager` in `middleware/src/core/wallpaper/manager.py`.
The implementation supports Linux (KDE Plasma scripting, GNOME `org.gnome.desktop.background`, XFCE `xfconf-query`, and generic feh/xwallpaper fallbacks) and Windows (`SystemParametersInfoW`).
Slideshow state is stored canonically at `~/.image-toolkit/.slideshow_config.json`, shared between the webview and daemon.

## Public Surface

- **Python Domain Service (`middleware/src/services/wallpaper/`):**
  - `WallpaperService`: implements `WallpaperServiceProtocol` (`get_monitors`, `set_wallpaper`, `get_slideshow_config`, `update_slideshow_config`, `toggle_slideshow`).
  - `commands.py`: typed command objects (`GetMonitorsCommand`, `SetWallpaperCommand`, `SlideshowConfigCommand`, `SlideshowToggleCommand`).
  - `handlers.py`: command dispatchers delegating to underlying wallpaper manager and config storage.
- **Sidecar (`middleware/src/sidecar/handlers/wallpaper.py`):**
  - `wallpaper.get_monitors`: returns connected monitor list and detected desktop environment.
  - `wallpaper.set`: applies wallpaper path mappings, scaling style, and background matte color.
  - `wallpaper.slideshow_config`: reads or updates slideshow interval, queues, and styling, and reports `running` only when the saved daemon pid is alive.
  - `wallpaper.slideshow_toggle`: starts or stops the background slideshow process.
- **Frontend (`frontend/src/views/system/WallpaperView.tsx`):**
  - Modular React component providing per-monitor path assignment, preview details, queue reordering, and daemon control.
  - `frontend/src/shell/SlideshowPresenterWindow.tsx`: Companion presentation window for role `slideshow` providing per-monitor queue inspection, queue item addition/removal, reordering, and background daemon toggle.
  - Client methods in `frontend/src/hostclient/client.ts`.

## Contract & Routing

- **JSON Schema:** `contracts/schemas/capability/wallpaper.json`
- **Methods:**
  - `wallpaper.get_monitors`
  - `wallpaper.set`
  - `wallpaper.slideshow_config`
  - `wallpaper.slideshow_toggle`
- **Events:** none

## Accessibility & Known Gaps

- **Keyboard parity:** All monitor inputs, style selection, queue order controls, and daemon toggle buttons participate in standard tab order with visible focus states.
- **Screen-reader notes & known gaps:** Dynamic status announcements use `role="status"` and `aria-live="polite"`.

## Verification

```bash
source .venv/bin/activate
pytest middleware/test/services/test_wallpaper_service.py -q
npm run test --workspace=frontend -- src/views/system/WallpaperView.test.tsx
python middleware/validation/check_docs_freshness.py
python middleware/validation/check_migration_ledger.py
python contracts/generate.py --check
```
