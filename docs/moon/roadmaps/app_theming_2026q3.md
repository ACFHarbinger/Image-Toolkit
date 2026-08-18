# App Theming & Customization (2026Q3)

**Status: DRAFT — brainstorm stage, not locked.** Same process as the
Development Tool v2 and ASP wallpaper-mode pivots: brainstorm → team
cross-review (each agent asks Harbinger their own questions
independently) → answers → proposals → sign-off. This document captures
round 1 (Harbinger's initial framing) so the team has real context to
brainstorm against — it is not a spec to implement yet.

**Origin:** Harbinger, 2026-08-18. "Make the app customizable — user-
defined theme (colors, styles, etc.) and background image(s)."

## Scope, per Harbinger's round-1 answers

1. **Customization depth: full custom palette.** Not just tinting an
   accent color on top of dark/light — every semantic color token
   (background, panel, text, accent, borders, hover states, etc.)
   user-definable. Dark/light become two of possibly several shipped
   presets, not the only two options. (Extends, doesn't replace, the
   existing accent-color-override mechanism — see §2.8 in `gui_ux.md`.)
2. **Background image: whole app window, translucent panels on top.**
   One background image behind the entire main window; content panels/
   cards get semi-transparent backgrounds so the image shows through —
   game-launcher / Discord-style theming, not a small confined region.
3. **Surface scope: all three UI surfaces.** PySide6 desktop app
   (`gui/`), the devtool Tauri/React app (`dev/app/`), and the docs
   website (`docs/website/`). One (conceptually) unified theming system,
   not three independent ones built separately.
4. **Editor UX: visual editor primary, config file secondary.** A
   dedicated settings panel — color pickers per token, background-image
   picker, live preview — as the main experience. Raw config-file
   editing (extending the existing `load_user_qss_override` hook for
   PySide6) stays available underneath for power users.

## What already exists per surface (read before proposing anything)

- **PySide6 (`gui/`):** `gui/src/windows/main/_theme.py` — dark/light
  QSS toggle, per-theme accent-color override (`compute_accent_vars`),
  UI density (`Comfortable`/`Compact`/`Spacious`), font scale,
  `load_user_qss_override` (a user QSS file hook already exists — not
  starting from zero). Stylesheets live in `gui/src/styles/qss/`.
- **devtool-app (`dev/app/`):** React app (Vite), single
  `dev/app/src/index.css`, no token/theme system yet — a straight port
  of the original vanilla-JS app's styling, never designed for
  user customization.
- **docs website (`docs/website/`):** most mature token infrastructure
  of the three already — `docs/website/src/styles/tokens.css` +
  `theme.css` (real CSS custom properties), separate from
  `tailwind.css`/`hub.css`/per-page CSS files.

The three surfaces are at very different maturity levels for this. A
"unified" system most likely means a shared *theme definition format*
(color tokens + background image reference, some serializable spec)
that each surface's own renderer consumes differently — a QSS
generator for PySide6, CSS custom properties for React/docs-website —
not literally shared runtime code across a Python/Qt app and two web
apps.

## Open questions for the team (round 1 — ask Harbinger your own, don't just answer these)

These are the ones visible from round 1 alone; expect more once each
agent looks at their own surface's actual styling code.

1. **Theme definition format.** A single portable spec (JSON/YAML/TOML)
   that all three surfaces read, with a per-surface adapter/generator?
   Or three separate but visually-matching implementations? Affects
   whether this is one shared-format project or three coordinated ones.
2. **Token set.** What's the actual semantic token list — same set
   across all three surfaces, or does each surface get its own set
   mapped from a smaller shared "core" (accent, background, text,
   border) plus surface-specific extras?
3. **Background image scope on devtool-app/docs-website.** Harbinger's
   "whole window, translucent panels" answer was likely framed around
   the PySide6 app. Does it apply identically to the other two, or do
   web surfaces need their own treatment (a website background image
   raises very different performance/accessibility questions than a
   native app window)?
4. **Preset gallery / sharing.** Ship a few curated built-in themes?
   Let users export/import a theme file to share? Not asked in round 1,
   worth raising.
5. **Accessibility.** Full custom palettes risk bad-contrast
   combinations. Any minimum contrast-ratio enforcement, or fully
   trust the user?
6. **Rollout order.** Which surface first? PySide6 has the most
   existing infra to extend (lowest risk, fastest to a real result);
   docs-website has the best token foundation already (fastest to
   retrofit); devtool-app has neither (greenfield, most freedom but
   most work). Team should propose a sequencing, not do all three at
   once.

## Process

Each agent: read this doc + your own surface's actual current styling
code, then ask Harbinger your own round-1 questions on the bus (same
format as the ASP pivot thread) — don't just answer the six above,
find what's actually unclear once you're looking at real code. After
Harbinger answers, proposals, then sign-off, then this doc gets
rewritten from DRAFT to a locked design (same treatment
`asp_wallpaper_mode_roadmap_2026q3.md` got).
