# App Theming & Customization (2026Q3)

**Status: DRAFT — Brainstorm Round 1 Decisions Consolidated.** Same process as the
Development Tool v2 and ASP wallpaper-mode pivots: brainstorm → team
cross-review → answers → proposals → sign-off. This document captures
Harbinger's design decisions from the brainstorming session.

**Origin:** Harbinger, 2026-08-18. "Make the app customizable — user-
defined theme (colors, styles, etc.) and background image(s)."

---

## 1. Core Architectural & Aesthetic Decisions (Harbinger's Answers)

### A. Background Image Canvas & Translucency Layering
- **Full-Window Canvas with Adjustable Opacity & Frosted Glass**: The background
  image renders behind the root application window with configurable opacity
  ($0.10$–$1.0$) and optional backdrop blur ($0$–$30\text{px}$). Content areas,
  toolbars, and cards use translucent glassmorphic surfaces (`rgba(..., alpha)`)
  so the image shows through subtly while maintaining text readability.
- **Dynamic Slideshow & Multi-Image Rotation**: Users can configure a background
  playlist with automatic timer-based slideshow rotation (1m, 5m, 15m, 1h) and
  smooth cross-fade transitions, integrating with the wallpaper daemon.
- **Fit & Scaling Modes**: Cover, Contain, Center, and Tile modes to cleanly adapt
  to ultrawide and multi-monitor setups.

### B. Color Token Customization & Stylesheet Control
- **Semantic Palette Editor**: Structured visual customizer exposing primary
  semantic color slots (Primary Accent, Surface/Card Background, Window Background,
  Primary/Muted Text, Border/Dividers).
- **WCAG 2.1 AA Auto-Contrast Validation**: Real-time contrast ratio indicator to
  prevent unreadable foreground/background combinations.
- **Dynamic Palette Extraction (Material You / PyWal Style)**: Automated color
  extraction from the active background image using $k$-means / median-cut
  quantization to generate harmonious matching UI accents on the fly.
- **In-App Live QSS Stylesheet Editor**: Integrated code editor targeting
  `~/.image-toolkit/user_theme.qss` with live preview and a fail-safe "Reset to Default" button.

### C. Widget Styling, Curvature, & Typography
- **Corner Radius Curvature**: Selectable corner styles (Sharp $0\text{px}$ / Subtle $4\text{px}$ / Rounded $8\text{px}$ / Pill $16\text{px}$).
- **Elevation & Shadows**: Configurable UI card drop-shadow elevation.
- **Custom Typography**: Selectable application font family, scale ($80\%$–$150\%$), and font weight overrides.

---

## 2. Surface Integration Phasing

| Phase | Surface | Architecture & Mechanism | Status |
|:---|:---|:---|:---|
| **Phase 1** | **PySide6 Desktop (`gui/`)** | `_theme.py` + dynamic QSS generation + root `QPainter` background overlay + `user_theme.qss` live reload | In Design |
| **Phase 2** | **Docs Website (`docs/website/`)** | Shared JSON token schema → CSS custom properties (`tokens.css` + `theme.css`) + backdrop-filter glassmorphism | Next |
| **Phase 3** | **DevTool App (`dev/app/`)** | Migration from `index.css` to CSS custom property tokens matching the shared theme JSON schema | Next |

---

## 3. Work Breakdown & Proposed Issues (#437–#440)

- **#437 (Theme Studio UI & Semantic Palette Customizer)**:
  - Settings "🎨 Appearance & Themes" tab with 5-slot color picker, WCAG contrast meter, corner curvature radio group, and font family selector.
- **#438 (Dynamic Palette Extraction & Wallpaper Daemon Integration)**:
  - Fast $k$-means/median-cut color extractor generating harmonious UI palettes from the active desktop/background image.
- **#439 (Full-Window Background Canvas & Glassmorphic Layering Engine)**:
  - Root window background renderer with opacity slider, backdrop blur, fit modes, and multi-image slideshow playlist.
- **#440 (In-App QSS Live Editor & Cross-Surface JSON Theme Export/Import)**:
  - In-app stylesheet editor with live reload, syntax validation, and portable JSON theme pack export/import.
