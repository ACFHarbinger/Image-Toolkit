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
- **Scope: Global default + per-tab override** (Harbinger, round-1 Q&A): one
  app-wide background image by default; power users can pin a different image
  per tab on top of the global default.
- **Blur performance posture** (Harbinger, round-1 Q&A): blur **off by default**, opt-in
  per user, with two companion settings: *adaptive radius* (auto-reduce on low-end
  machines / FPS drops) and *cached blur layers* (blur once into a cached layer on
  resize, reuse it). Static background + opacity is the cheap default path.
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
  quantization to generate harmonious matching UI accents on the fly. **Off by
  default** (Harbinger, round-1 Q&A): a "derive accents from background" toggle in
  Theme Studio, so auto-extraction never fights a hand-picked palette.
- **Theme storage: JSON token pack AND raw QSS are both first-class** (Harbinger,
  round-1 Q&A): users can load/save either a semantic JSON theme pack or a raw
  QSS file as the active theme. JSON pack is the recommended portable format;
  QSS stays for power users who want direct stylesheet control.
- **QSS engine migration: hybrid** (Harbinger, round-1 Q&A): the existing
  $VAR-substitution QSS system (`gui/src/styles/qss/`) is kept; the new token
  pipeline generates the 5 core semantic slots now, and remaining QSS files
  migrate file-by-file onto generated tokens.
- **In-App Live QSS Stylesheet Editor**: Integrated code editor targeting
  `~/.image-toolkit/user_theme.qss` with live preview and a fail-safe "Reset to Default" button.

### C. Widget Styling, Curvature, & Typography
- **Corner Radius Curvature**: Selectable corner styles (Sharp $0\text{px}$ / Subtle $4\text{px}$ / Rounded $8\text{px}$ / Pill $16\text{px}$).
- **Elevation & Shadows**: Configurable UI card drop-shadow elevation.
- **Custom Typography**: Selectable application font family, scale ($80\%$–$150\%$), and font weight overrides.
- **Density as a theme axis** (Harbinger, round-1 Q&A): the existing
  compact_density.qss / spacious_density.qss controls fold into Theme Studio as
  a "Density" axis alongside Palette / Corners / Typography — one place to
  customize the whole look.

### D. Base Theme + Overrides Model (Harbinger, round-1 Q&A)
- User picks a **base theme** (Dark / Light, later a follow-system option that
  switches the base automatically), then **overrides individual tokens** on top.
  A saved theme = base + override deltas, not a full copy of every token.
- Follow-system is a base-switcher, not a theme-switcher: overrides stay applied
  when the OS light/dark setting changes the base.

---

## 2. Surface Integration Phasing

| Phase | Surface | Architecture & Mechanism | Status |
|:---|:---|:---|:---|
| **Phase 1** | **PySide6 Desktop (`gui/`)** | `_theme.py` + dynamic QSS generation + root `QPainter` background overlay + `user_theme.qss` live reload | In Design |
| **Phase 2** | **Docs Website (`docs/website/`)** | Shared JSON token schema → CSS custom properties (`tokens.css` + `theme.css`) + backdrop-filter glassmorphism | Next |
| **Phase 3** | **DevTool App (`dev/app/`)** | Migration from `index.css` to CSS custom property tokens matching the shared theme JSON schema | Next |

**Phase-1 scope decision** (Harbinger, round-1 Q&A): desktop first, but the shared
JSON token schema is designed up front so the docs website and devtool app adopt
the same theme-pack format later **without a schema redesign**. Do NOT ship the
three surfaces together in the first milestone; do NOT let the schema grow
organically without the cross-surface shape in mind.

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

---

## 4. Round-1 Q&A (deepseek → Harbinger, 2026-08-18)

Brainstorm round per the tracking issue's process: agent reads draft + the
surface's current styling code, asks Harbinger round-1 questions, proposals
follow after sign-off. Answers recorded here as design refinements.

| # | Question | Harbinger's answer |
|:--|:--|:--|
| 1 | Build on the existing $VAR QSS system or replace it? | **Hybrid** — keep the existing system; new token pipeline generates the 5 core slots now, migrate the rest file-by-file. |
| 2 | Background scope: global, per-tab, or both? | **Global default + per-tab override** (recommended option). |
| 3 | Theme storage format? | **Both first-class** — JSON token pack (portable) or raw QSS. |
| 4 | Dynamic palette extraction? | **Off by default**, toggle in Theme Studio ("derive accents from background"). |
| 5 | Fold density themes into Theme Studio? | **Yes — density becomes a theme axis** alongside palette/corners/typography. |
| 6 | Dark/Light selection model? | **Base theme + user overrides**; follow-system switches the base, overrides persist. |
| 7 | Blur performance posture? | **Off by default, opt-in**, with adaptive radius + cached blur layers as settings. |
| 8 | Phase-1 scope? | **Desktop first, schema designed for reuse** across all three surfaces. |

These refinements are folded into Sections 1 and 2 above; the work breakdown
(#437–#440) is unchanged. Next step per the process: team cross-review of this
roadmap, then proposals, then sign-off — implementation issues stay unfiled
until the design locks.
