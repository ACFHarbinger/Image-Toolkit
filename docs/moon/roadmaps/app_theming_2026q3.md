# App Theming & Customization (2026Q3)

**Status: Phase 1 (desktop) shipped and stable as of 2026-08-19 end of
day.** #437-441 (schema, Theme Studio, palette extraction, background
canvas + glassmorphism, QSS editor/export) landed 2026-08-18. A follow-up
sweep landed 2026-08-19: glassmorphism defaulted off and its QSS selectors
didn't match the real widget tree (#449), ~45 tab files had inline
hardcoded panel/button colors overriding the theme entirely (#446,
#450-452, all closed), and making `OpaqueViewport` opaque for scroll
performance (#453) initially painted galleries solid black with no
background configured — landed, reverted, and correctly re-landed same
day once the fill color was sourced from the theme constants instead of
`QWidget.palette()` (which QSS never updates). Phases 2 (docs website) and
3 (devtool app) are still "Next," unstarted.

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
| **Phase 1** | **PySide6 Desktop (`gui/`)** | `_theme.py` + dynamic QSS generation + root `QPainter` background overlay + `user_theme.qss` live reload; host-owned tabs only | In Design |
| **Phase 2** | **Docs Website (`docs/website/`)** | Shared JSON token schema → CSS custom properties (`tokens.css` + `theme.css`) + backdrop-filter glassmorphism | Next |
| **Phase 3** | **DevTool App (`dev/app/`)** | Migration from `index.css` to CSS custom property tokens matching the shared theme JSON schema | Next |

**Phase-1 scope decision** (Harbinger, round-1 Q&A): desktop first, but the shared
JSON token schema is designed up front so the docs website and devtool app adopt
the same theme-pack format later **without a schema redesign**. Do NOT ship the
three surfaces together in the first milestone; do NOT let the schema grow
organically without the cross-surface shape in mind.

---

## 3. Work Breakdown & Issues (locked, filed)

- **#437 — shared JSON theme-token schema (foundational).** Blocks #438-441;
  must land first. 5 core semantic slots, base+override-delta model,
  `asset_ref` for backgrounds distinct from token values, designed for
  reuse across all 3 surfaces from day one. Assigned: **Claude**.
- **#438 — Theme Studio UI & Semantic Palette Customizer.** Settings
  "🎨 Appearance & Themes" tab: 5-slot color picker, WCAG contrast meter
  (advisory), corner curvature, typography, shadows, density-as-an-axis.
  Transactional preview. Assigned: **deepseek**.
- **#439 — Dynamic Palette Extraction.** $k$-means/median-cut color
  extractor from the active background image, off by default. Assigned:
  **opencode**.
- **#440 — Full-Window Background Canvas & Glassmorphic Layering.**
  Opacity/blur/fit-mode renderer, multi-image slideshow (one global
  clock), translucent panels. Assigned: **Gemini**.
- **#441 — In-App QSS Live Editor & Cross-Surface Theme Export/Import.**
  Advanced/expert QSS editor behind an explicit toggle, plus the
  portable theme-pack export/import format Phase 2/3 will later consume.
  Assigned: **deepseek**.

Sequencing: #437 first (everyone else depends on its schema contract).
#438-441 are independent of each other once #437 lands — parallelizable.

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

These refinements are folded into Sections 1 and 2 above.

## 5. Round-2 Q&A (opencode → Harbinger, 2026-08-18)

These answers narrow the implementation contract without locking the design:

| # | Question | Harbinger's answer |
|:--|:--|:--|
| 1 | Which surfaces participate in the first milestone? | **Host PySide6 GUI and its host-owned tabs only**; embedded HIE/CSG/ASP surfaces get adapters later. |
| 2 | How are background assets supplied and persisted? | **Both linked paths and explicit import**; users can choose portability without forcing every asset into managed storage. |
| 3 | What does a portable theme pack contain? | **Tokens plus background references**; the pack records paths/identifiers and reports missing assets rather than silently embedding large files. |
| 4 | What happens when a preview edit is invalid? | **Transactional preview**; apply temporarily and revert to the last valid theme on parse or application failure. |
| 5 | Which visual axes are Phase 1 controls? | **Palette, density, corners, typography, shadows, and motion**. |
| 6 | Are WCAG contrast checks hard gates? | **Warnings only**; the user may save an intentional low-contrast aesthetic, with the risk made visible. |
| 7 | How does a background playlist advance? | **One global clock** shared by the host window; per-tab overrides do not create independent timers in Phase 1. |
| 8 | How much authority does raw QSS receive? | **Separate expert toggle**: safe styling mode by default, unrestricted raw-QSS mode only after explicit opt-in. |

### Round-2 implications

- The shared JSON schema must distinguish `asset_ref` (linked path or imported
  asset id) from token values so packs remain portable without silently copying
  files.
- The background controller owns one timer and publishes the active image to
  the host; a tab override can replace the image but not create another clock.
- Preview application needs a transaction boundary around QSS generation,
  stylesheet installation, and background-pixmap loading. The previous valid
  snapshot remains the rollback source.
- Motion and shadow settings need reduced-motion and low-performance fallbacks;
  they must be runtime axes, not hardcoded animation assumptions.
- WCAG ratios remain diagnostics, not validators. The UI should name the
  affected token pair and provide a one-click return to a compliant suggestion.

## 6. Final Q&A (Claude → Harbinger, 2026-08-18) — closes the brainstorm

| # | Question | Harbinger's answer |
|:--|:--|:--|
| 1 | Schema sequencing: own foundational issue first, or fold into Theme Studio? | **Own foundational issue first** — #437, blocks #438-441. |
| 2 | Issue granularity: keep the 4 proposed feature issues, or split further? | **Keep as 4** (plus the foundational schema issue = 5 total). |
| 3 | Enumerate exactly which tabs are "host-owned" now, or leave to implementation judgment? | **Leave to implementation judgment.** |

Design locked. See §3 for the final issue numbers/assignments (shifted by
one from the §3/§4/§5 "proposed #437-440" numbering above once the real
foundational schema issue took #437 — read assignments from §3, not the
inline numbers in earlier sections' prose).
