# Image-Toolkit Docs Website: React Migration + 2D/3D Design

**Author:** Claude (Code) · **Date:** 2026-08-10
**Scope:** React migration architecture, dashboard data contract, 2D component
plan. Per Harbinger's scoping answers (recorded in `.agent/cache/AGENT_BUS.md`):
full rewrite (not staged), 2D-first with 3D only if it earns its place, static
JSON dashboard data, new Image-Toolkit-specific hero asset.

## 1. What already exists and should be carried forward, not redesigned

- **The dashboard's data contract is already decided by
  `RatingsDashboardView.vue`** (Vue scaffold, already in the tree, reads
  `public/data/asp_evaluations.json` + `public/data/benchmark_results.json`).
  Port its logic (histogram, mean, preference counts) into React — don't
  invent a new shape.
- `public/data/asp_evaluations.json` exists but is currently `{}` — populate
  it by pointing `just asp-benchmark-assess`'s `--out` at this path, or copy
  the dated output after a rating session (matches the Vue scaffold's own
  doc-comment instructions).
- `public/data/benchmark_results.json` **does not exist yet** — there is no
  aggregator. Raw per-run files exist at
  `submodules/ASP/backend/benchmark/output/anime_stitch_<timestamp>.json`
  (schema: `metadata` / `system` / `summary` / `datasets[]` /
  `performance_insights`). **Grok**: this is the missing half of your
  "dashboard metrics pipeline" — needs a small generator script that reads
  the latest (or all) `anime_stitch_*.json` runs and writes one
  `public/data/benchmark_results.json` with enough of `summary` +
  per-dataset `time`/`frames` to chart trends over time (i.e. an array of
  `{timestamp, summary, datasets}` objects, one per run, not just the latest).
  Happy to firm up the exact shape together before you build the script.
- `src/frameworks/react/ComponentGallery.tsx` is the only existing React
  file — Storybook-adjacent, not app-critical, can stay or go.

## 2. Target architecture (full rewrite, per Harbinger's decision)

Drop Vue entirely (`frameworks/vue/`, `vue`/`vue-router`/`vuex`/`vue-tsc`/
`@vitejs/plugin-vue` deps, `main.ts`→`main.tsx`, `router.ts`→`router.tsx`).
Keep everything else in the existing scaffold that isn't Vue-specific:

- **Router**: React Router (already a transitive convention across
  PMF/VGP — they use `src/libraries/router` + `router.tsx`, same
  `createAppRouter`-style wrapper). Reuse `nav.generated.ts` and
  `scripts/generate-nav.mjs` unchanged — they're framework-agnostic.
- **Astro islands**: keep as-is; Astro embeds React components natively, this
  isn't Vue-coupled.
- **Storybook**: already React-targeted (`@storybook/react-vite`) — no change
  needed, it was never actually wired to Vue components.
- **Styles**: `tailwind.css`/`theme.css`/`hub.css`/`markdown.css` carry over
  unchanged — these are the shared visual identity layer PMF/VGP/Image-Toolkit
  all use from the same lineage; only the component layer is Vue-specific.
- **Content**: `docs-content` generation, `useMarkdown`/`useDocs` hook
  patterns from PMF/VGP are directly portable (same hook signatures already
  present in Image-Toolkit's `src/hooks/`, just currently Vue-consumed via
  composables instead of hooks in a few places — check `src/composables/`
  for anything Vue-reactivity-specific that needs a React-hook rewrite).

### Route plan (parity checklist vs. PMF/VGP)

| Route | Current (Vue) | React target | Notes |
| --- | --- | --- | --- |
| `/` | `HomeView.vue` | `HomeView.tsx` | Hero asset (Gemini) + narrative/lore section (matches PMF's `simulations`/`stories` pattern — Image-Toolkit's equivalent would be pipeline/model showcases, not fortress lore) |
| `/dashboard/ratings` | `RatingsDashboardView.vue` (scaffold, real data contract) | `RatingsDashboardView.tsx` | Port directly — see §3 |
| `/:pathMatch(.*)*` (docs) | `DocPage.vue` | `DocPage.tsx` | Markdown rendering via existing `useMarkdown` hook |

## 3. Dashboard: React port plan

Direct port of the Vue scaffold's logic (`histogram`, `mean`, `prefCounts`,
`entries`/`reviewed` computeds) into React `useMemo`s — no behavior change,
same two JSON files, same stats. Additions once the 2D component pattern
(§4) exists:

- Score histogram (0–4 coherence scale) as bars — already computed in the
  Vue version, just needs a visual instead of (presumably) a table today.
- **Time-series view once `benchmark_results.json` is an array of runs**:
  sharpness/ghosting/coverage/SSIM trend lines across `anime_stitch_*`
  timestamps — this is the "over time" part of Harbinger's ask that the
  current single-snapshot Vue scaffold doesn't yet cover.
- Explicit "no human rating yet" / "missing data" states per the
  coordination file's rule: never imply a proxy metric (SSIM, sharpness)
  equals human coherence judgment — keep the two visually distinct, always
  labeled.

## 4. 2D component plan (dependency-free, VGP house style)

One canvas component, `StitchPipelineDiagram.tsx`, modeled directly on VGP's
`CodeGraphMorph.tsx` pattern (hand-rolled `<canvas>`, custom easing, palette
hook, `useReducedMotion` respect — reuse that hook as-is, it's already
framework-agnostic in `src/hooks/`):

- Visualizes the actual ASP pipeline stages from the benchmark JSON's own
  `time` breakdown (`birefnet` → `matching` → `bundle_adjust` → `ecc` →
  `render` → `composite`) as a morphing node graph — this makes it a real
  data visualization of this repo's own pipeline, not decoration, and reuses
  the exact field names already in `benchmark_results.json`.
- Ships on `/` (home) as the hero-adjacent interactive element, not buried in
  the dashboard.

**3D**: not committing to a concept yet, per Harbinger's "only if it earns
its place." If the 2D pipeline diagram above works well, the natural 3D
extension is a literal 3D stitch-seam visualization (source frames as
positioned planes, warp fields, composite seam) — genuinely specific to this
repo's subject matter, not generic. Proposing as a **follow-up**, not part of
this pass.

## 5. Handoffs

- **Grok**: `benchmark_results.json` generator script (§1) — let's confirm
  the array-of-runs shape before you build it.
- **Chat**: nav/content map should list `/dashboard/ratings` as an existing
  route to preserve, not a new page.
- **Gemini**: hero asset brief is §2's `/` route — new, Image-Toolkit-specific,
  inspired by PMF's treatment, sized/cropped for the same hero-banner slot
  pattern PMF uses (`public/assets/mobile_fortress_banner.jpg` equivalent).
- **Harbinger**: no action needed from you here beyond the rating pass
  already unblocked; will post again once the group has reacted to this plan
  or if there's disagreement to flag.
