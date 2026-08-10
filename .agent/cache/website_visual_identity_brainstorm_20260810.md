# Image-Toolkit Website — Visual Identity Brainstorm

**Participants:** Chat/Codex + Gemini/Antigravity  
**Status:** Design workshop; no implementation decisions are final until Harbinger answers the questions at the end.

## Chat/Codex proposal — 2026-08-10

### What the reference sites have in common

- They each commit to one recognizable world rather than presenting a generic
  dashboard: PMF uses a historical game/art direction, VGP uses a living code
  graph, and Organization-Website uses a product-studio/network language.
- Their hero sections establish the product's promise visually within seconds:
  one strong asset or simulation, one memorable typographic statement, and a
  small number of purposeful actions.
- They repeat the same visual grammar below the fold: restrained navigation,
  dark layered surfaces, intentional accent colors, compact metadata labels,
  and narrative sections that explain why each capability exists.
- Their interactive elements are meaningful to the product. The graph and 3D
  elements are not decoration alone; they communicate structure, relationships,
  or the product's working model.

### Proposed Image-Toolkit identity: “The Visual Systems Laboratory”

Image-Toolkit should feel like a nocturnal imaging lab: precise, cinematic,
curious, and evidence-oriented. The core metaphor is **frames becoming
evidence**—raw images enter a controlled optical workspace, transformations
are measured, and the resulting visual artifact remains linked to its
provenance and quality signals.

Suggested identity primitives:

- **Palette:** near-black graphite foundation; cool cyan/sea-glass for active
  instrumentation; ultraviolet for analysis; warm amber for human review and
  warnings. Avoid using color to imply ASP success; amber should represent
  attention/review, not quality.
- **Typography:** a highly legible sans-serif for interface/body copy, a
  restrained editorial serif or display face for short hero phrases, and a
  monospaced face for measurements, file identifiers, and pipeline metadata.
- **Shapes:** thin optical reticles, crop marks, measured borders, image frames,
  calibration ticks, and occasional soft glass panels. Avoid making every
  surface a rounded card; the reference sites use hierarchy through whitespace
  and framing as much as cards.
- **Motion:** slow parallax/noise/particle drift in the background; deliberate
  transitions when a pipeline stage activates; no constant high-frequency
  animation. Respect reduced-motion and keep the first meaningful content
  available without waiting for a canvas or WebGL scene.
- **Voice:** concise, observational, and honest. Prefer “inspect the seam” or
  “compare the evidence” over inflated claims such as “perfect stitching.”

### Proposed page hierarchy

1. **Landing / Lab overview:** one distinctive hero artwork or interactive
   stitch viewport, promise, two CTAs, and a compact live-status strip.
2. **The workbench:** Capture → Understand → Compose, each with a small
   visual vignette and a link to the relevant documentation.
3. **Pipeline observatory:** a 2D interactive stage diagram. Selecting a stage
   reveals inputs, outputs, assumptions, and links to docs. This is the core
   VGP-inspired visualization and should be dependency-light SVG/canvas.
4. **Evidence / quality:** dashboard preview showing coverage, human ratings,
   automated metrics, defects, and disagreement. Human judgments must remain
   visually primary and explicitly distinct from proxies.
5. **Documentation portal:** a stable, searchable, deeply navigable docs
   surface using the same tokens but a calmer reading layout. The visual home
   page should lead into docs rather than treating `/docs` as an afterthought.
6. **Roadmap / research:** a timeline or constellation of active, deferred, and
   research items, with clear status labels and no misleading progress bars.

### Technical direction

- Keep React + Vite as the active surface now that the cutover builds.
- Establish tokens in one theme layer (`colors`, type scale, spacing, radii,
  shadows, motion durations) and use semantic classes rather than scattered
  page-specific colors.
- Use CSS/SVG/canvas for the signal field and 2D pipeline first. Reserve
  react-three-fiber for a product-relevant “stitch volume / seam inspection”
  view, lazy-loaded and optional, not as a prerequisite for navigation.
- Make the documentation route data-driven from the generated MkDocs nav and
  published Markdown assets instead of maintaining a short hand-written page
  list. Support nested paths and previous/next navigation.
- Treat visual assets as first-class source files: add provenance/license notes,
  responsive crops, alt text, and a lightweight fallback. The PMF asset should
  inspire composition, not be copied as Image-Toolkit branding.
- Add visual regression screenshots at desktop/mobile widths plus a reduced-
  motion/accessibility pass before calling the identity complete.

## Questions for Gemini/Antigravity

1. Which single metaphor and hero treatment do you think can own Image-Toolkit
   without making it look like a PMF/VGP imitation: optical laboratory,
   panoramic cartography, archival image observatory, or another direction?
2. Should the hero prioritize one generated/curated cinematic panorama image,
   a live 2D stitching canvas, or a hybrid image with an interactive overlay?
3. Which current assets/components are worth preserving, and which currently
   make the site feel visually incoherent or generic?
4. Do you recommend adding a true 3D scene now, and if so what user task should
   it make easier than a 2D visualization?
5. What should be the signature accent color and meaning of each secondary
   accent so quality states are not confused with decoration?
6. Which page should receive the next design pass after Home: the dashboard,
   the documentation reader, or the pipeline observatory?
7. What specific visual references or assets from PMF, VGP, and Organization-
   Website can be reused legally/provenance-wise, versus recreated in the
   Image-Toolkit design language?

## Questions for Harbinger

1. Which identity direction feels most like the Image-Toolkit you want to use:
   a cinematic imaging laboratory, a cartographic panorama studio, a forensic
   evidence console, or a blend?
2. Should the site feel more editorial/artistic like PMF, more technical like
   VGP, or more product-commercial like Organization-Website? Please rank them.
3. What should the first hero communicate—image stitching, the broader image
   database/toolkit, the ASP research effort, or the documentation itself?
4. Do you have a preferred hero asset, or should us generate a new
   Image-Toolkit-specific asset after you approve the art direction?
5. Should the landing page expose real benchmark numbers immediately, or keep
   those in the Quality/Dashboard surface with only a “review in progress” cue
   on the hero?
6. Which interaction matters most for you in the next milestone: exploring the
   pipeline, browsing docs, comparing ASP/SCANS outputs, or exploring the image
   processing modules?
7. Are there any colors, motifs, typefaces, or visual styles you definitely want
   avoided?
8. Do you want us to optimize first for desktop widescreen (matching the
   screenshot), or for a responsive desktop/mobile experience from the outset?
9. Should the docs reader remain a single-page in-app experience, or may it
   open/generated-link to a separate static documentation build when that gives
   us better search and deep-link behavior?
10. What is the acceptable performance budget for hero animation/3D on your
    M3 Mac and on Android remote viewing?

## Gemini/Antigravity response

_(Gemini/Antigravity: please append your independent proposal and answers to
the Chat questions here. Do not edit Chat's section.)_

## Harbinger's decisions — 2026-08-10

- Primary identity: anime art and video-game asset development, expressed
  through an imaging-toolkit lens.
- Style balance: PMF artistic/editorial character first, VGP technical
  precision second, with Organization-Website's product clarity as a lesser
  influence.
- Homepage promise: the broader toolkit, not ASP or documentation alone.
- Hero: cinematic asset plus interactive 2D canvas.
- Benchmark numbers: dashboard only; the homepage may indicate activity but
  must not turn incomplete ratings into marketing claims.
- Interaction priority: module exploration first, pipeline exploration second.
- 3D: include one lightweight beautiful demo placeholder now; defer a full
  seam/stitch inspection scene until its product use case is specified.
- Primary target: widescreen desktop. Mobile remains a later optimization.
- Theme: dark-mode-first. The homepage should primarily use **Optic Lab**;
  the docs reader and dashboard should blend Optic Lab with **Engineer’s
  Blueprint**.
- Preferred 3D direction: beautiful abstract optical visualization first,
  with literal pipeline representation as a later layer.

## Agreed implementation plan and task split

### Phase 1 — Shared visual foundation

Create one semantic theme contract before more page-specific styling:

- graphite/obsidian surfaces and atmospheric gradients;
- silver/neutral text hierarchy;
- cyan and magenta chromatic light accents for the Optic Lab homepage;
- blueprint blue plus a restrained technical yellow/green accent for
  diagnostics, documentation metadata, and active instrumentation;
- typography, spacing, border, shadow, z-index, motion, and responsive tokens;
- accessibility states, reduced motion, focus rings, and contrast checks.

**Owner: Chat/Codex**, with Gemini reviewing visual decisions before broad
component work. The tokens must avoid copying PMF/VGP class names or layouts.

### Phase 2 — Homepage / Optic Lab

Rework the landing page around anime/game-asset creation rather than generic
image processing:

1. cinematic hero composition with a new Image-Toolkit-specific asset;
2. interactive lightweight 2D optical/light-field overlay;
3. one lazy-loaded abstract 3D prism/aperture/lens demo placeholder;
4. module exploration as the first major interaction, with modules framed as
   asset workflows (capture/import, inspect/understand, compose/export);
5. toolkit capability sections and restrained documentation/dashboard CTAs;
6. no benchmark score rail on the homepage.

**Owner: Gemini/Antigravity** for hero art direction, optical 3D treatment,
and visual motion. **Chat/Codex** owns module information architecture,
content accuracy, route integration, and performance/accessibility review.

### Phase 3 — Blueprint documentation and quality surfaces

Apply the shared foundation without turning every page into a hero:

- documentation reader: calm reading column, blueprint grid/reticle details,
  generated navigation, search, breadcrumbs, previous/next links, and robust
  nested-document routing;
- quality dashboard: blueprint instrumentation treatment, explicit human vs
  automated sections, charts, defect tags, and missing-data states;
- pipeline observatory: module/pipeline exploration with the same stage data
  used by the dashboard and links into relevant documentation.

**Owner: Chat/Codex** for routing, docs navigation, dashboard semantics, and
pipeline/module information architecture. **Gemini/Antigravity** reviews the
visual composition, chart language, and blueprint treatment.

### Phase 4 — Validation and refinement

- desktop-first visual QA at 1440px and ultrawide layouts;
- verify the app remains usable at narrower widths even before a mobile pass;
- test reduced-motion mode and keyboard navigation;
- lazy-load the 3D scene and measure initial page load/render cost;
- add provenance/license notes for every new visual asset;
- confirm all benchmark claims remain truthful and human ratings remain
  distinct from proxy metrics;
- compare before/after screenshots against the approved identity checklist.

**Joint review**, with Chat responsible for the final build/accessibility/data
check and Gemini responsible for the final visual coherence check.

### Deliberately deferred

- full seam/stitch 3D inspection;
- mobile-specific art direction and performance tuning;
- aggressive 3D usage across multiple pages;
- putting live ASP/SCANS scores in the marketing hero;
- duplicating PMF/VGP/Organization-Website assets or copying their layouts.

## Immediate ownership summary

| Work item | Chat/Codex | Gemini/Antigravity |
|---|---:|---:|
| Theme token contract | Lead | Visual review |
| Hero art direction and asset | Support/provenance | Lead |
| 2D optical overlay | Integration/perf | Lead |
| 3D placeholder | Integration/lazy loading | Lead |
| Module exploration content/UX | Lead | Visual review |
| Documentation routing/navigation | Lead | Review |
| Dashboard/pipeline semantics | Lead | Visual review |
| Desktop visual QA | Lead/build | Lead/aesthetic |

This is the implementation plan to execute after both agents confirm the split.

## Chat/Codex implementation update — 2026-08-10

- Added the shared semantic token layer at `src/styles/tokens.css` and loaded
  it from the React entrypoint.
- Added keyboard-accessible module selection with contextual descriptions and
  module-specific links; the workbench is now the first meaningful homepage
  interaction.
- Added the pipeline observatory section using the dependency-light canvas
  diagram. Its copy explicitly distinguishes pipeline visualization from human
  quality judgment.
- Lazy-loaded `Hero3D` so the homepage's initial JavaScript bundle does not
  include the WebGL scene. The production build now emits a separate 3D chunk.
- Kept benchmark numbers off the homepage in accordance with Harbinger's
  decision; the dashboard remains the quality evidence surface.
- Build passes. Remaining joint visual QA should inspect Gemini's latest hero,
  `Viewfinder2D`, and the dashboard against the agreed Optic Lab/Blueprint
  identity.

## Chat/Codex follow-up — 2026-08-10

- Split navigation into distinct `/` Home and `/pipeline` Pipeline pages;
  Pipeline now has its own observatory, stage cards, and documentation links.
- Added `anime_lab_hero.png`, a new generated widescreen anime/game-art
  production atelier asset. The prior hero assets remain recoverable.
- Fixed Mermaid fences in the React docs reader by converting Mermaid fences to
  renderable containers, running Mermaid after Markdown mounts, respecting the
  deployment base path, and adding responsive SVG sizing.
- Production build passes. Vite still reports a chunk-size warning caused by
  the Mermaid/visualization bundle; this is non-blocking and is a future
  code-splitting optimization candidate.
