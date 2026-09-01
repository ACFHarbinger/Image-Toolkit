# Image Toolkit — Master Roadmap

> **Note (2026-08-06):** The Anime Stitch Pipeline (ASP) engine and the Manga
> Colorization & Animation feature have moved out of this repo into their own
> submodules — [ASP](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline)
> and [CSG](https://github.com/ACFHarbinger/Cel-Shaded-Generator)
> (`submodules/ASP`, `submodules/CSG`).
> Their roadmaps now live at `docs/moon/ROADMAP.md` inside each submodule;
> historical entries below that predate the move still
> reference the old in-repo paths as a record of what was true at the time.

**HIE submodule integration (S377, 2026-08-12):** The Hybrid Image Editor lives
in [`submodules/HIE`](https://github.com/ACFHarbinger/Hybrid-Image-Editor)
([roadmap](https://github.com/ACFHarbinger/Hybrid-Image-Editor/blob/main/docs/moon/ROADMAP.md)).
Image-Toolkit **re-exports** Hybrid Editor UI only — PySide6 via
`gui/src/tabs/editor/` → `hie_gui.HieEditorTab`, React via `hie-frontend`
(`file:../submodules/HIE/frontend`) → `frontend/src/embed/react/HieEditorTab.tsx`.
Host pipeline IPC (`PipelineSession`, capability/proposal/restoration methods)
is owned by HIE ([issue #8](https://github.com/ACFHarbinger/Hybrid-Image-Editor/issues/8)).
Do not fork editor UI in the parent; advance the submodule pointer after HIE commits.

**Current submodule integration (S313, 2026-08-06):** CSG
Phase 0 is complete. Its core and GUI are independently installable
distributions; the core exposes top-level domain packages directly from its
flattened `src/`, while the flattened GUI is loaded as `csg_gui`. Image
Toolkit consumes those public modules directly instead of manufacturing the
temporary `manga` and `manga_gui` aliases. Product planning and implementation
details remain owned by the [standalone roadmap](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/docs/moon/ROADMAP.md).
The first storage contract now uses portable project folders, bounded atomic
recovery history, project-local learning metrics, and a separate opt-in global
learner profile (S314).
Deterministic synthetic goldens and anonymized engine baselines now guard all
four existing compute areas; current measurements do not yet justify selecting
a C++ port target (S315).
Native-heavy work now has a spawned-process containment contract with adaptive
timeouts, cancellation, crash recovery, and privacy-safe local diagnostics;
host routing and overhead measurement remain in progress (S316).
Interactive ARAP now uses a restartable persistent isolated worker with
negligible measured warm overhead; batch Qt routing remains (S317).
All built-in CSG batch workers now use fresh isolated
processes, completing native-crash containment for current application paths
(S318).
CSG Phase 0 is complete: its authoritative documentation is
now product-specific and strict-build verified. The Krita anime head-and-face
learning alpha is the next phase (S319).
The alpha's adaptive-curriculum milestone now has a versioned nine-step
curriculum, deterministic explainable remediation, version-safe repeated-attempt
comparison, and a private non-ranking progress-summary core (S341). Krita
presentation and persistence remain in progress while drawing-dependent A2
checks stay in owner-deferred Review.
Portable schema v3 now persists one final structured advice rating and optional
note per review, with local learning retention enabled by default but
user-configurable; prerequisites recommend rather than lock content (S342).
The existing Krita tutor docker now has a headless-tested private project
progress section, default-visible normalized measurements, and explicit
keep/clear-disable/re-enable retention controls (S343); live host presentation
remains deferred.
Advice ratings and notes are now editable under per-project history and note
length settings, and the second lesson—head orientation—is fully authored with
theory, drills, diagnosed mistakes, and completion criteria (S344).
The existing tutor docker now offers unlocked selector and Previous/Next lesson
navigation, selectable offline SVG construction diagrams, and explicit
reversible checklist completion that review evidence cannot trigger (S345).
The orientation exercise now has a portable landscape five-view Krita template,
stable exercise identity, and correct next-lesson recommendation; its future
one-head-at-a-time critique is isolated from the front-view rubric (S346).
Profile and three-quarter selected-head critique now has active-layer detection,
explicit view confirmation, cropped specialized landmarks, six auditable rubric
dimensions, and version-safe retry comparisons (S347); tolerances await real
beginner calibration.
Orientation critique now produces cell-local preview redlines under the existing
Accept/Reject contract, and curriculum lesson three—cranial volume and jaw
variation—is fully authored with two original offline diagrams (S348).
Lesson three now also has a five-area Krita design sheet with one-active-layer
individual review and optional auditable front/turned consistency critique;
its provisional thresholds await beginner-drawing calibration (S349).
Lesson four—eye placement and perspective—is fully authored with two offline
diagrams, a four-stage front-to-turned Krita template, and dedicated active-layer
structure/style-expression critique. Its eye thresholds await calibration and
geometry-derived redlines remain open (S350).
Eye critique now includes conservative cell-local reversible previews, and
lesson five fully covers nose/muzzle, mouth, and equally weighted ear placement
with a six-area front-to-turned Krita matrix (S351).
Feature placement now has specialized per-layer and optional combined critique;
lesson six is fully authored around controlled asymmetry with a six-stage
control/cause/transfer Krita sheet (S352).
Feature critique now has reversible matrix-local previews; controlled asymmetry
has mandatory authored-intent evidence and control comparisons; lesson seven is
fully authored around undecorated variation and identity retention (S353).
Controlled asymmetry now has control-derived previews; portable schema v5 adds
editable mixed numeric/descriptive identity cards and identity comparisons; all
nine lessons are fully authored through cel values and capstone (S354).

*Last updated: 2026-08-31. Session S483: completed the frozen-bundle
path-assumption audit (#476) — confirmed every `_MEIPASS` resource read
resolves, moved the two remaining bundle-write hazards out of `ROOT_DIR`
(credential export → `~/.image-toolkit/backup`, crawler screenshots →
`~/.image-toolkit/screenshots` when frozen), and added clear guards to the
source-checkout-only subprocess features (wallpaper slideshow daemon ×2,
managed WebDriver, ComfyUI server launch, LyCORIS training, vault→assets
template sync). See `docs/moon/CHANGELOG.md` S483. Session S480: shipped Image-Toolkit v1.0.0 (Linux desktop — AppImage + .deb draft Release), fixed four frozen-bundle launch bugs, deferred native Windows to v1.1 (#471). See `docs/moon/CHANGELOG.md` S480. Previous update, 2026-08-06. Session S319: completed the CSG standalone foundation and moved the Krita learning alpha to Next. See `docs/moon/CHANGELOG.md` S319. Previous update, 2026-08-06. Session S318: completed CSG native crash containment across built-in Qt paths. See `docs/moon/CHANGELOG.md` S318. Previous update, 2026-08-06. Session S317: isolated interactive CSG ARAP work in a persistent recoverable process. See `docs/moon/CHANGELOG.md` S317. Previous update, 2026-08-06. Session S316: added CSG native-worker crash containment core. See `docs/moon/CHANGELOG.md` S316. Previous update, 2026-08-06. Session S315: established CSG correctness and performance baselines. See `docs/moon/CHANGELOG.md` S315. Previous update, 2026-08-06. Session S314: added CSG portable learning-project persistence and privacy-safe progress separation. See `docs/moon/CHANGELOG.md` S314. Previous update, 2026-08-06. Session S313: established CSG as an independently installable core + GUI package boundary and migrated Image Toolkit to its stable namespaces. See `docs/moon/CHANGELOG.md` S313. Previous update, 2026-08-06. Session S312: built docs/website/ (the same Vue site as Image-Toolkit's own, homogeneously styled) in all three submodules, moved their moon/reports/research into docs/, cross-linked all four sites via an embedded "Related Projects" sidebar (iframe + 404.html SPA fallback for GH Pages deep links), wired each submodule's own CI to deploy alongside its MkDocs portal, and brought CRE's repo scaffolding (.gitlab/.gitea/.forgejo/.devcontainer/etc.) up to parity with the other two. Also fixed pre-existing bugs in ASP/Manga's .gitlab-ci.yml, GitLab templates, and .devcontainer (still referenced removed template language dirs from S310) and broken relative links in Manga's/CRE's roadmaps (never updated for their own moon/research → docs/ moves). See `docs/moon/CHANGELOG.md` S312. Previous update, 2026-08-06. Session S311: moved the last two `research/*.md` reports into `docs/research/` and built `docs/website/` — a Vue 3 + Vite documentation site rendering every `docs/**/*.md`/`*.ipynb` directly (nav/search generated from `docs/mkdocs.yml`'s own `nav:` tree, so it never drifts from the Material portal), with instant search, live Mermaid, dark mode, and a notebook renderer; wired into `.github/workflows/docs.yml` (+ Forgejo/Gitea mirrors) to build and deploy alongside the MkDocs portal at `gh-pages`'s `/app/` path. See `docs/moon/CHANGELOG.md` S311. Previous update, 2026-08-06. Session S310: renamed the ASP submodule's `cpp/`→`base/`, `python/`→`backend/`, flattened both (and CSG's `src/`) to drop the redundant single-child `animation/`/`manga/` wrapper, split each submodule's PySide6 GUI into its own top-level `gui/` module, added `_submodule_bootstrap.py` package aliasing to keep imports collision-free, and scaffolded (unimplemented) `frontend/`+`app/ios`+`app/android` in both. See `docs/moon/CHANGELOG.md` S310. Previous update, 2026-08-05. Session S308: shipped MCA.12's remaining rigging-UI + real-time-GUI-wiring scope, fully closing issue #194 — `gui/src/elements/manga/mesh_overlay_editor.py::MeshOverlayEditor` (load an image, paint a binary mask, generate an ARAP mesh via `generate_mesh()`, drag any vertex to pose it in real time) and a new "Manga Puppeteering" tab (`gui/src/tabs/manga/puppeteering_tab.py`), a third "Manga" category tab alongside Colorization and Animation. Deliberately solves `arap_deform()` synchronously on the GUI thread during drags rather than via the usual QThread-worker pattern -- an async dispatch would let the pose lag behind the mouse, and empirical timing (~17ms mean for a ~64-vertex mesh) makes synchronous solving the pragmatic choice here. Found and mitigated a real intermittent native-crash hazard during development: this is the first manga module to call `np.linalg.svd` (every other solver only uses `scipy.sparse.linalg.splu`), and running its SVD-heavy tests under the full pytest collection (~140 native extension modules loaded in-process) intermittently (~40% of runs) segfaulted inside `numpy.linalg.svd` or threw bizarre downstream stdlib errors -- classic native heap-corruption symptoms, not a bug in the ARAP math itself (independently verified correct via the rigid-rotation-reproduction test). Mitigated by adding the same `MANGA_COLORIZE_LOCK` serialization every other manga solver already uses, plus reducing the heaviest tests' SVD call volume to a level that still validates the same properties -- 15/15 clean runs after, versus ~40% failure before; the underlying native co-loading fragility is not fully root-caused, a genuine documented residual risk. 30 new tests (18 `test_mesh_overlay_editor.py`, 12 `test_puppeteering_tab.py`; `test_arap.py`'s existing 14 had two tests' SVD call volume reduced, not newly added) -- 109 backend manga tests, 93 GUI manga tests total. See `docs/moon/CHANGELOG.md` S308. Previous update, 2026-08-05. Session S307: shipped MCA.12 partial (ARAP mesh puppeteering algorithmic core, `backend/src/manga/arap.py`), progressing issue #194 (the roadmap's own "highest-effort item") — `generate_mesh()` grid-samples + Delaunay-triangulates a caller-supplied binary mask into a 2D triangle mesh (dropping/reindexing unreferenced vertices to keep the solver's Laplacian non-singular); `arap_deform()` alternates a local step (per-triangle optimal rotation via 2D orthogonal Procrustes/SVD) and a global step (sparse graph-Laplacian solve over mesh edges, anchor vertices pinned via the same Dirichlet row-replacement trick `colorization.py` already uses, Laplacian factorized once via `splu` and reused across iterations). Verified correct: with every boundary vertex anchored to a rigidly-rotated target, free interior vertices converge to their own analytically-rotated positions to well under 1% of the mesh's scale — exactly the property a correct ARAP implementation must have. Pure Python/NumPy/SciPy, not the roadmap's originally-proposed C++ Eigen kernel (same established deviation as every other solver this milestone); no dependency on unbuilt issue #184 (character isolation) — accepts any caller-supplied mask, matching the roadmap's own "manual-mask MVP first" pattern. Marked "Partial": no rigging UI or real-time re-solve GUI wiring yet (issue #194's own ~2+ week scope includes both, on top of the algorithmic core). 14 new backend tests (109 backend manga tests total). See `docs/moon/CHANGELOG.md` S307. Previous update, 2026-08-05. Session S306: shipped MCA.9's remaining live-GUI-wiring scope, fully closing issue #191 — `MangaCanvasEditor` (§5.1) gained pixel-space stroke-bounding-box tracking (accumulated during a stroke, finalized on `mouseReleaseEvent`, padded by half the pen width, clipped to canvas bounds), and the Manga Colorization Tab (§6.1) gained a "Live Preview" checkbox (scribble-based modes only) that dispatches a new `IncrementalColorizeWorker` per completed stroke, seeding one ordinary full solve on the first stroke and re-solving only the touched quadtree window (via S305's `colorize_region_incremental()`) after that. A stroke completing while a solve is already in flight is silently skipped rather than queued -- documented as a deliberate best-effort trade-off for a HITL preview, not a correctness gap. Manually verified end-to-end with real threads and real cv2 outside pytest (documented cross-thread-signal-vs-`cv2`-mock hazard from issue #196 applies here too). 19 new tests (13 `gui/test/manga/test_colorization_tab.py` live-preview cases, 6 `gui/test/manga/test_canvas_editor.py` stroke-bbox cases) -- 95 backend manga tests, 63 GUI manga tests total. See `docs/moon/CHANGELOG.md` S306. Previous update, 2026-08-05. Session S305: shipped MCA.9 partial (Quadtree-accelerated interactive solve, `backend/src/manga/quadtree.py`), progressing issue #191 — `build_quadtree()` recursively partitions a grayscale image into flat-vs-detailed leaf regions by local intensity variance; `colorize_region_incremental()` re-solves only the quadtree-expanded window around a "dirty" bounding box (a stroke's extent) and composites it into a previously-solved full-canvas result, verified ~300x faster (~0.01s vs. ~3.5s) than a full-page re-solve for a stroke landing in a finely-partitioned detailed region. Marked "Partial" not "Done": no live per-stroke GUI dispatch loop was wired (both Manga tabs still solve on an explicit button click) — issue #191's own text explicitly allows this ("deferrable for an initial 'solve on demand' (non-live) MVP," this project's actual current state), so this is a legitimate scoped partial delivery. Found and documented, not fixed (out of scope): a dense high-contrast striped synthetic test pattern reproducibly triggered a pre-existing `RuntimeError: Factor is exactly singular` inside `colorize_scribble`'s SuperLU factorization for some sub-window crops — a real numerical edge case in the Levin solver's weight construction, worked around in this module's own tests via a sparse-dot pattern instead. 13 new backend tests (95 backend manga tests total). See `docs/moon/CHANGELOG.md` S305. Previous update, 2026-08-05. Session S304: shipped MCA.15 (GUI: Preference Review Dialog, `gui/src/components/manga_preference_dialog.py`), closing issue #197 — a side-by-side A/B candidate comparison dialog ("Prefer A" / "Tie / Skip" / "Prefer B") built as a stub ahead of the §4.1/§4.2 LocalDPO/LoRA alignment pipeline, per the roadmap's own "build early" rationale so preference data collection starts as soon as any generative colorization mode ships. Votes are appended to `backend/src/manga/preference_log.py::log_preference()`, a JSON-lines file at `~/.image-toolkit/manga_preferences.jsonl` (the same `~/.image-toolkit/` local-app-data convention `shortcut_manager.py`'s `keybindings.json` already uses) — chosen over SQLite (which the roadmap's own text allows) since an append-only vote log has no query/update/deletion needs SQLite's machinery would serve. Deliberately not wired into any existing tab (e.g. an automatic "Compare Modes" trigger) — issue #197's scope is the dialog + log file; it's a standalone component any future caller can drive directly. 16 new tests (`backend/test/manga/test_preference_log.py` 9, `gui/test/components/test_manga_preference_dialog.py` 7) — 82 backend manga tests, 55 GUI manga+components tests total. See `docs/moon/CHANGELOG.md` S304. Previous update, 2026-08-05. Session S303: shipped MCA.14 (GUI: Manga Animation Tab, `gui/src/tabs/manga/animation_tab.py`), closing issue #196 — a test/exercise harness for §3.1/§3.2's already-built animation solvers, per the issue's own title framing. Loads a line-art frame sequence via a multi-select file picker (sorted by filename); reuses MCA.8's `MangaCanvasEditor` as a single shared widget across frames, with a new per-frame-index scribble-overlay dict saving/restoring the canvas's scribble layer on every frame-slider move (reaching into the editor's private scribble-layer attributes rather than modifying `canvas_editor.py` itself, out of scope for this issue); "Colorize Sequence" dispatches a new `gui/src/helpers/manga/animation_worker.py::AnimationColorizeWorker` (`QThread` subclass, same pattern as `ColorizeWorker`) running `colorize_scribble_sequence()` (MCA.10) and, via a "Graph-cut refine" checkbox, optionally chaining `graph_cut_temporal_refine()` (MCA.11) as a second pass — both already-shipped backends wired, not just one; a second slider scrubs the solved result over a plain preview label, and "Export…" writes a `frame_%04d.png` sequence to a chosen directory. Deliberately dropped vs. the original brainstorm: no ARAP mesh puppeteering mode/mesh-vertex overlay, since MCA.12 (§3.3) has no backend yet to wire — the mode selector reduced to the graph-cut toggle accordingly, the natural consequence of "test the already-built solvers." Found and documented a real test-environment hazard during development: `gui/test/conftest.py` globally mocks `cv2`, and running either backend solver through that mock from a real background `QThread` reproducibly corrupted memory ("double free or corruption") — confirmed via a minimal repro; GUI tests therefore mock the worker/backend calls rather than letting a real thread run them, with the full load→scribble→solve→preview round trip manually verified against the *real* cv2 outside pytest instead. 46 GUI manga tests (18 new `test_animation_tab.py` + 5 new `test_animation_worker.py`, up from 25), 73 backend manga tests unaffected. See `docs/moon/CHANGELOG.md` S303. Previous update, 2026-08-05. Session S302: Content Gen §1.4 Phase A shipped (issue #35) — ControlNet (pose/depth/canny) + IP-Adapter (reference image) via curated ComfyUI workflow JSONs (`configs/comfy_workflows/{controlnet,ipadapter}_generate.json`), wired into a new "ControlNet / IP-Adapter Workflow" panel in `ComfyUITab` (`gui/src/tabs/models/gen/comfy_generate_tab.py`). The pre-existing `ComfyUIManager` only started/stopped the server and opened a browser tab — no in-app workflow-submission mechanism existed, so this added the smallest correct extension: `load_workflow()`/`apply_overrides()` (generic per-node input override dict) and `upload_image()`/`queue_workflow()` (ComfyUI's `/upload/image` and `/prompt` HTTP endpoints) on `ComfyUIManager`. 28 new tests (`backend/test/models/test_comfy_manager.py`, `gui/test/models/test_comfy_generate_tab.py`), no regressions in the existing 150-test `models` suites. Phase B (native diffusers ControlNet/IP-Adapter in `sd3_wrapper.py`/`SD3GenerateTab`) remains out of scope, tracked separately. See `docs/moon/CHANGELOG.md` S302. Previous update, 2026-08-05. Session S301: closed issues #97/#99 (extension.md §7.15B/D) — the GIF/animation frame extractor and video clip capture, the last two of the four items §53 split into #93/#94/#95/#97/#99. **§7.15B (issue #97):** `extension/src/frames/frames.{html,ts}`, a new "Extract frames…" image context-menu item opening a grid-preview tab (same `storage.local` hand-off pattern as #102's `galleryData`) that decodes GIF/APNG/animated-WebP with the WebCodecs `ImageDecoder` API — a big scrubbable/playable preview plus a per-frame grid, saving selected/all frames as a numbered PNG sequence. The roadmap's planned `omggif`/`upng` JS-decoder fallback was deliberately not bundled: `ImageDecoder` already covers every build target that matters (chrome/edge/brave); only Firefox lacks it and gets a clear unsupported-browser message instead, keeping the feature dependency-free. **§7.15D (issue #99):** two new video context-menu items — "Record 5s clip (WebM)" (`MediaRecorder` on a `canvas.captureStream()` fed by a `requestAnimationFrame` draw loop, the roadmap's literal MVP) and "Record 5s clip → Animated WebP" (`extension/src/videoClip.ts` samples the same draw loop at 10fps, encodes each frame with `canvas.toBlob("image/webp")`, then hand-muxes them into a real animated WebP container per the published RIFF/VP8X/ANIM/ANMF spec — new `extension/src/shared/webpMux.ts`, a few dozen lines of chunk-writing, not an image codec, so no new dependency). True GIF export and the app-side ffmpeg conversion path are out of scope — the roadmap's own text already framed ffmpeg conversion as optional/app-side, and new backend/bridge work is excluded from this pass; a fixed 5s duration is used, mirroring §7.15A's already-established fixed 5-frame burst rather than adding a config panel. `npm run typecheck` clean for every new/touched file (`background.ts`, `content.ts`, `videoCapture.ts`, `messages.ts`, new `frames/`, `videoClip.ts`, `shared/webpMux.ts`, `shared/webcodecs.d.ts`); the two pre-existing `shared/api.ts`/`shared/dupTabs.ts` `@types/chrome` overload errors reproduce identically on an unmodified checkout. `npm run build:chrome` bundles both new entries (`frames`, plus the touched `background`/`content`) cleanly against a locally pinned `typescript@5.6.3` (this checkout's pinned `typescript@7.0.2` still crashes `ts-loader` regardless of this change, confirmed pre-existing); `npm ci` restored the pinned toolchain afterward, `package.json`/`package-lock.json` untouched. No test framework is configured for this package (still true as of this session) — verification is typecheck + build only, matching #102/#93-95's precedent. See `docs/moon/CHANGELOG.md` S301. Previous update, 2026-08-05. Session S300: closed issues #93/#94/#95 (extension.md §7.14A/B/C) — three thin bridge endpoints wiring already-shipped app capabilities behind the extension's context menu. `POST /api/extension/cv/bg-remove` and `POST /api/extension/cv/upscale` (`extension_api/views.py`/`urls.py`) queue Celery jobs (`extension_api/tasks.py`, a new autodiscovered `tasks.py` module reusing the project's existing Celery queue rather than inventing a second async mechanism) running `BiRefNetWrapper.get_mask()`/`ESRGANWrapper.upscale()` and return a `job_id` the extension polls via `GET /api/extension/cv/status/<job_id>/`; `extension/src/shared/bridge.ts` gained `cvBgRemove()`/`cvUpscale()`/`pollCvJob()` (HTTP-only — job-id+poll doesn't map onto native messaging's single-request/response model without a second design pass, flagged as a deliberate scope line, not an oversight) and `background.ts` gained "Remove background"/"Upscale & save" context-menu items that pipe the result through the existing `downloadImage()` folder-profile/sidecar path. `POST /api/extension/ingest/` gained an `auto_tag: bool` flag (`bridge_handlers.handle_ingest`) calling `WDTaggerWrapper.tag_with_review()`; tags land in the provenance sidecar JSON and the response body — not the DB, since ingest doesn't do DB writes at all yet (§7.7's own "Remaining: embedding/DB indexing at ingest" note; tagging failure is caught and reported rather than losing the already-saved image). 53 `extension_api` tests (38 pre-existing + 15 new: `TestCvBgRemove`/`TestCvUpscale`/`TestCvJobStatus`, 3 new `TestIngest.test_auto_tag_*` cases) pass via `extension_api/test_settings.py`+`test_urls.py` (new, test-only) — needed because `manage.py test`'s system-check pass imports the *whole* `ROOT_URLCONF` graph, which includes `tasks.urls` → `tasks/tasks.py`'s pre-existing, unrelated `from backend.src.database import PgvectorImageDatabase` ImportError (an archived DB.6 symbol; confirmed via `git stash` that this breaks identically with zero extension changes present, not introduced by this session). `npm run typecheck` clean for both touched extension files (`bridge.ts`, `background.ts`); `npm run build:chrome` fails, but confirmed pre-existing (identical failure with this session's extension changes stashed) — a `ts-loader`/`typescript` version mismatch surfaced by a fresh `npm install` against no committed lockfile, unrelated to this change. Manual end-to-end smoke test (real Django test client, mocked model wrappers) confirmed the full happy path for all three: ping feature discovery, bg-remove queue→poll→transparent-PNG result, ingest+auto_tag. See `docs/moon/CHANGELOG.md` S300. Previous update, 2026-08-05. Session S299: closed issue #102, §7.9 Bulk Page Grabber's remaining "grid preview" scope (mode C) — `extension/src/gallery/gallery.{html,ts}`, a new tab page listing every image the content script detects on the active page (`shared/pageMedia.ts::collectImageDetails()`, a non-downloading sibling of the existing collector, now also reporting width/height), with client-side min-dimension/URL-contains/format-chip filters, a per-item download button with a progress/status badge (new `download_gallery_item` message; `background.ts::downloadImage()` now returns `{ok, error}` instead of `void`, kept backward-compatible with its existing fire-and-forget callers), and a "Check duplicates" action that reuses §7.16C's client pHash pre-check (`computePhashFromUrl()` + `snapshotBestMatch()`, unmodified) as a hint badge per item — no new dedup logic, exactly the integration §7.16C's own status note had flagged as its natural next step. `npm run typecheck` clean for all new/touched files; `npm run build:chrome` bundles the new `gallery` entry cleanly (verified against a locally pinned `typescript@5.6.3`, since this checkout's pinned `typescript@7.0.2` currently crashes `ts-loader` itself — confirmed pre-existing/unrelated by reproducing on an unmodified checkout). No test framework is configured for this package; verification is typecheck + build only, per this section's established precedent. See `docs/moon/CHANGELOG.md` S299. Previous update, 2026-08-05. Session S298: shipped MCA.11 (Graph-cut (Boykov-Kolmogorov) temporal coherence, `backend/src/manga/graph_cut.py`) — a second refinement pass over MCA.10's already-solved sequence output, using `PyMaxflow` (wraps the reference Boykov-Kolmogorov C++ implementation, not reimplemented) to decide, per pixel, whether to keep a frame's own solved chrominance or fall back to its temporal neighbors' blended chrominance, suppressing flicker introduced where MCA.10's intensity-correlation-based tracking breaks down under fast motion/occlusion. Deliberately narrowed the roadmap's general multi-label MRF formulation to a 2-label binary graph-cut per frame (OWN vs. BLEND) — a full alpha-expansion multi-label solve was scoped as real scope creep for a first pass; documented as a submodular-Potts-with-Gabor-affinity smoothness term (reusing MCA.3/§2.2's exact `exp(-||T(p)-T(q)||^2/(2*sigma^2))` weighting) over the standard 4-connected pixel grid, giving Boykov-Kolmogorov's binary min-cut an exact (not merely approximate) solution. `PyMaxflow` installed cleanly from a prebuilt manylinux wheel (added to `backend/pyproject.toml`), no C++ build toolchain needed, so the roadmap's SciPy-maxflow fallback plan wasn't required. Closed issue #193. 19 new backend tests (`backend/test/manga/test_graph_cut.py`, 73 backend manga tests total). See `docs/moon/CHANGELOG.md` S298. Previous update, 2026-08-05. Session S297: shipped MCA.10 (3D quadratic-cost temporal propagation, `backend/src/manga/temporal.py`) — a direct dimensional generalization of MCA.4's Levin scribble colorizer to a 3D `(t, y, x)` neighborhood, solved as one combined sparse system across a whole frame sequence so color diffuses along the temporal axis through unscribbled in-between frames, not just spatially per-frame. Found a real scaling issue during implementation: the 3D system's sparse-LU fill-in grows much faster than linearly with the temporal window (a 10-frame 400x400 sequence OOM'd at a proportionally-scaled `max_solve_dim=256`, but solved in ~36s/~4.4GB at 128), so `colorize_scribble_sequence()`'s default `max_solve_dim` is 128, documented as scoped for short in-between spans, not full-episode timelines. Closed issue #192. 14 new backend tests (54 backend + 25 GUI manga tests total). See `docs/moon/CHANGELOG.md` S297. Previous update, 2026-08-05. Session S296: shipped MCA.6 (Optimal-Transport / Sinkhorn reference colorizer, `backend/src/manga/optimal_transport.py`) — SLIC superpixel segmentation of both a reference image and target line art, Gabor-texture + normalized-position structural features (reusing MCA.3's `gabor_feature_bank`), a hand-written NumPy Sinkhorn solver (not `POT`/torch — see issue #188), and transport-plan-weighted color propagation onto the target's preserved luminance; same `max_solve_dim` downscale-for-solve pattern as MCA.4/MCA.5. Found and fixed a real bug during implementation: `sinkhorn()`'s early-stopping residual check was tautological (compared `u_new * kv` to `mu`, which is true by construction regardless of actual convergence) and broke after one iteration; fixed to track `|v_new - v|` iterate stability instead. Wired into the Manga Colorization Tab (MCA.13) as a third working mode, "Reference / Optimal-Transport", with a new "Load Reference…" button and `ReferenceColorizeWorker` (`gui/src/helpers/manga/colorize_worker.py`) — a separate `QThread` subclass rather than generalizing `ColorizeWorker`, since the two-image reference workflow doesn't share `ColorizeWorker`'s scribble-based signature. Closed issue #188. 13 new backend tests (`backend/test/manga/test_optimal_transport.py`), 6 new GUI tests (`gui/test/manga/test_colorization_tab.py`, 25 total). See `docs/moon/CHANGELOG.md` S296. Previous update, 2026-08-04. Session S295: increased the Meta+S Load Tab Configuration dialog's default size (360x~100 auto-sized -> 420x420) so more saved configs are visible without scrolling; continued the Manga Colorization & Animation feature -- shipped MCA.3 (Screentone Gabor feature extraction, `backend/src/manga/gabor.py`, pure Python/OpenCV rather than the roadmap's planned C++ kernel) and MCA.5 (screentone-aware propagation, `backend/src/manga/screentone.py`, reusing MCA.4's Levin solver with Gabor texture-affinity weights instead of a separate level-set PDE solver), wired as a second "Screentone-aware" mode in the Manga Colorization Tab via a new pluggable `colorize_fn` on `ColorizeWorker`. Closed issues #185, #187. Also added `telemetry.MANGA_COLORIZE_LOCK` serializing the two colorizers' OpenCV/scipy-heavy solve across concurrent `ColorizeWorker` threads (same established pattern as `NATIVE_IMAGE_BATCH_LOCK`). See `docs/moon/CHANGELOG.md` S295. Previous update, 2026-08-04. Session S294: started implementing the Manga Colorization & Animation feature (Milestone #6) — shipped MCA.4 (Levin quadratic-cost scribble colorizer, `backend/src/manga/colorization.py`, pure Python/SciPy rather than the roadmap's originally-proposed C++ kernel, documented as a deliberate pragmatic choice), MCA.8 (layered HITL canvas editor, `gui/src/elements/manga/canvas_editor.py`), and MCA.13 (Manga Colorization Tab, `gui/src/tabs/manga/colorization_tab.py`, new "Manga" category). Closed issues #186, #190, #195. See `docs/moon/CHANGELOG.md` S294. Previous update, 2026-08-04. Session S293: new `general.load_tab_config` shortcut (default `Meta+S`) — the missing load counterpart to Ctrl+S's save-current-tab-config (`gui/src/windows/main/_load_tab_config.py`, `_LoadTabConfigMixin`); opens a picker over the active tab's saved configs (same vault `tab_configurations` store Ctrl+S/Settings/workflow-templates already share) and applies the chosen one via `set_config()`. See `docs/moon/CHANGELOG.md` S293 and `roadmaps/gui_ux.md` (2026-08-04 update near §2.16H). Previous update, 2026-08-03. Session S292: fixed a SIGSEGV/heap-corruption crash on the first real Media Loader download (`QSocketNotifier`/JVM off-main-thread crash class) by dropping `asyncio`/`aiohttp`/`asyncpraw` from `RedditDownloader`/`NhentaiDownloader` in favor of synchronous `requests` (Reddit now via public `.json` endpoints, no OAuth); also fixed `NhentaiDownloader`'s gallery-page parsing for nhentai's current SvelteKit markup (with a legacy-markup fallback), added `telemetry.py` instrumentation, and 26 new tests (`backend/test/web/test_reddit_downloader.py`, `test_nhentai_downloader.py`, `gui/test/web/test_media_loader_worker.py`). Live-verified against the user's exact repro URL with zero crashes. Previous update, same day, Session S291: new "Media Loader" Web Integration tab (`roadmaps/new_features.md` §4.17, issue #182) — downloads media from the web, starting with `RedditDownloader` (images/galleries/video) and `NhentaiDownloader` (gallery-page scrape), both in `backend/src/web/downloaders/`; GUI at `gui/src/elements/web/media_loader_tab/`. Previous update, same day, Session S290: §5.5 Gradual Static Type Safety Migration — mypy `attr-defined` mixin cleanup via per-tab `Protocol` host classes (see `docs/moon/CHANGELOG.md` S290 and `roadmaps/architecture.md` §5.5), 4693 → 2987 project-wide errors (36%), 7 submodules fully clean (`cbir_train_tab`, both gallery base classes, `extractor_tab`, `wallpaper_tab` common/monitor/system), plus 2 real runtime bugs found/fixed along the way (missing `main_window.py` re-export, fontconfig SONAME-collision SIGSEGV). Previous update 2026-07-29: Phase Arch: A.22 shipped — the 3 deferred `gui/src/` giants (`stitch_tab.py` 5,035, `extractor_tab.py` 3,290, `settings_window.py` 2,505 code lines) split into package directories via public-API-preserving re-export, under a fresh issue #122 filed to pick up exactly what A.21 had scoped out. `settings_window.py` required decomposing its ~1,113-line `__init__` into `_build_*_section()` helpers first; `extractor_tab.py`'s crash-history-sensitive lazy `QMediaPlayer`/`QAudioOutput`/`QGraphicsVideoItem` construction moved verbatim per `.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`; `stitch_tab.py` decomposed cleanly along 8 pre-existing sub-tab features. §5.17 priority downgraded from High to Medium — Option B (splitting) is now fully closed across `backend/src/` and `gui/src/`; only Options A (CI-enforced gate) and D (LoC dashboard) remain open. Previous update 2026-07-30: Phase Arch: A.21 shipped — all 24 medium `gui/src/` files (515–1,355 LoC) split into package directories via public-API-preserving re-export, under a fresh issue #121 (superseding the `gui/src` portion of #116/#118, both closed on GitHub without that work landing). Discovered and documented a previously-unknown MRO-shadowing bug (a mixin's override is silently shadowed if the base class precedes the mixins in the class declaration) and applied the fix everywhere it applied. 3 giants (`stitch_tab.py` 5,032, `extractor_tab.py` 3,268, `settings_window.py` 2,505) remain explicitly out of scope, tracked for a dedicated follow-up. Previous update 2026-07-29: Phase Arch: A.18 (module dependency graph, §5.11C) + A.19 (unified `AppConfig`, §5.14C) shipped, closing out §5.11/§5.14's remaining DRY sub-items (both now ✅ Shipped A+B+C+D). A.20 shipped — all 8 oversized `backend/src/` files (§5.17, issue #117) split into package directories via public-API-preserving re-export, including `pipeline.py` and `compositing.py` (the two largest/most benchmark-sensitive files in the codebase); largest remaining file in `backend/src/` is 457 code lines. Previous update 2026-07-04: New Phase EXT (Browser Extension) added — webpack multi-browser manifest builds (chrome/firefox/edge/brave) in `extension/webpack/`, TypeScript migration, unified MV3, local app bridge (HTTP → native messaging), in-browser duplicate search against a configured directory tree (reuses `PhashDeduplicator` §4.6), send-to-app ingestion with provenance, visual similarity search, bulk page grabber, per-site folder rules + filename templating + metadata sidecar, full-resolution extraction, and turbo mode polish; full detail in [roadmaps/extension.md](roadmaps/extension.md). S206: thumbnail loading optimized (C++ reduced decode + disk cache + progressive gallery fill). Previous update 2026-06-18: Architecture roadmap updated: §5.5 (Gradual Static Type Safety), §5.8–§5.13 (model wrapper ABC, worker base class, gallery consolidation, circular imports, docs/diagrams, decorators), §5.14–§5.16 (settings facade, fault isolation, ML wrapper contract tests) added. Phase 4 updated to remove stale §4.1 Vault Manager link. New Phase Arch added for code-quality items. Session 131: §1.66 NCC structural coherence gate (Stage 11.4), §1.67 pre-BA frame canvas spread validation, §1.8C/D dump_asp_config with typed TOML schema comments (827 tests). Session 130: §1.60 fg pose-gap pre-escalation, §1.62 canvas aspect-ratio gate, §1.63 sort-frames-by-index, §1.64 exact-duplicate dHash guard, §1.65 fg seam erosion buffer, §1.10D MC-dropout uncertainty, §3.17 seam NCC coherence + §3.5A composite quality score in bench (822 tests). Session 78: §2.3 Canvas Layout Inspector read-only viewer (422 tests passing). Session 77: §2.2 Edge Graph Inspector read-only viewer (413 tests passing). Session 76: GNC-TLS BA (§1.32, 412 tests passing). GUI: §2.23A accessibility, §2.4B+C range-select + context menu, §2.25A shortcut overlay, §2.20A splitter persistence, §2.17D log window, §2.16C Ctrl+T tab search, §2.12A+B+C system tray, §2.11A+B+D preview enhancements, §2.21A+D dir history + MRU, §2.26B inline rename, §2.10C QStatusBar, §2.14A filename labels, §2.18 sort + search ops, §2.19 trash, §3.9 item range, §4.11 thumbnail slider, §3.15–3.17 shortcuts/QSS/geometry all shipped. §2.30 accent colour picker + font scale + UI density shipped. New roadmap sections added: §2.29 (configurable keyboard shortcuts), §2.30–2.32 (appearance customisation), §4.12–4.13 (appearance profiles + macros). Session 9: ToonCrafter seam synthesis wired (§3.6/ML.4, `ASP_TOONCRAFTER_SEAM=1`). Session 8: DINOv2 submodular frame selection (§3.3/ML.2), LSD collinearity in ARAP (§0.1/A3), Aligned-SSIM metric. Session 7: Stage 12.5 scroll-axis content trim (§2.6). Session 6: hold detection (§1.11/ML.1), GNC BA, SLIC SGM proxy (§3.1/ML.5). 107 tests passing. Session 5: alignment stability gate (+0.074 test08, +0.049 test25), fg pixel L1 pose metric (+0.010 test27 with pose-on), 90 unit tests. Session 4: ARAP Push (Sýkora 2009), 96-test run. Research: `research/Image_Stitching_Research.md`, `research/ASP_Comprehensive_Research_Report.md`.*

Completed items have been moved to [docs/moon/CHANGELOG.md](CHANGELOG.md).

---

## How to Use This Document

This document defines the **phased execution sequence** for all upcoming improvements. Each item links to the corresponding brainstorming section in the appropriate section-specific roadmap for full context, options, and trade-offs.

Section-specific roadmaps:
- [ASP — Anime Stitch Pipeline](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/docs/moon/ROADMAP.md)
- [Content Generation — Anime Image & Video](roadmaps/content_generation.md)
- [GUI/UX — Desktop Interface](roadmaps/gui_ux.md)
- [Performance — Compute, Memory, I/O](roadmaps/performance.md)
- [New Features — Capabilities & Integrations](roadmaps/new_features.md)
- [Architecture & Infrastructure](roadmaps/architecture.md)
- [Development Tool — telemetry, debug, benchmarks, plugins](roadmaps/development_tool.md)
- [Browser Extension — Capture, Build System & App Integration](roadmaps/extension.md)
- [Unified Database — Merging Listings Subtabs & Database Tabs](roadmaps/unified_database.md)
- [Cel-Shaded Generator — drawing education, coloring, animation, and game assets](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/docs/moon/ROADMAP.md)

Consolidated research reports (read before working on the respective pipeline):
- [Anime Stitching — Consolidated Research](reports/asp_research.md) — foreground-assembly paradigm, per-stage toolbox, 13-stage spec.
- [Anime Generation — Consolidated Research](research/Image_Generation_Research.md) — image + video models, fine-tuning, video→LoRA pipeline.
- [Anime Stitch Pipeline ML Research](reports/asp_research.md) — ML-driven solutions for aperture problem (AnimeInterp SGM), frame selection (DINOv2 submodular), camera estimation (CamFlow), generative composition (ToonCrafter, RDIStitcher), and reference-free metrics (SIQE, SI-FID, MLLM SIQS). Full roadmap entries in [the ASP submodule's roadmap §3.0](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/docs/moon/ROADMAP.md#30-ml-driven-pipeline-modernisation-research-phase--from-ml-research-report).
- Manga Colorization & Animation — Consolidated Research — HITL deep learning (diffusion reference colorization, DiT inbetweening, Diffusion-DPO) and mathematical optimization (Levin quadratic-cost scribbles, screentone level-sets, graph-correspondence QP, Optimal-Transport/Sinkhorn, Boykov-Kolmogorov graph cuts, ARAP mesh deformation). Full roadmap in [the CSG submodule's roadmap](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/docs/moon/ROADMAP.md).

Phases are ordered by impact-to-effort ratio and dependency order. Items within a phase are independent and can be parallelised.

---

## Phase 0/ML — ASP Pipeline (superseded pre-trim content — see the ASP submodule's moon/ROADMAP.md)

**⚠ Stale-content notice (added during a 2026-07-27 roadmap audit):** everything that used to live in this
slot ("Phase 0 — ASP Foreground Assembly" and "Phase ML — ASP ML-Driven Modernisation", the foreground-pose-registration/
ARAP/DINOv2/ToonCrafter/SLIC-SGM item lists) described the pre-trim pipeline architecture. The 2026-07-09
"S200 great trim" deleted ~3,596 lines of that ritual/failed work and `https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md` was rewritten
from scratch the same day — it is the current, actively-maintained ASP roadmap (through session S222 as of
2026-07-27) and uses an entirely different phase structure (Phase 0 Measurement Foundation, Phase 1 Targeted
Information Gathering, Phase 2 Coherence-First Core, Phase 2.6 Benchmark-Harness Host Freeze, Phase 3
Photometric & Seam Parity, Phase 4 Fallback-Class Conversion, Phase 5 Exceed/stretch). None of the old
`the ASP submodule's moon/ROADMAP.md#...` anchors below the old Phase 0/ML tables resolve any more, and several of the individual items
(ToonCrafter seam synthesis, SLIC SGM proxy, the RLHF quality-gate/reward-model loop referenced by old
ML.7/ML.10 and Phase 5/6 items below) were themselves removed in the trim rather than carried forward.

**Authoritative source: [the ASP submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md)** — read it directly for current status, ground rules, and
the 2026-07-09 baseline (27 asp_better / 41 comparable / 29 simple_better; aligned GT-SSIM 0.693 vs 0.718).
The retired pre-trim roadmap is archived at `archive/moon/asp.md` for historical reference only — treat it as
a catalogue of what was already tried, not as a plan.

---

## Phase CG — Content Generation (Anime Image & Video)

Builds on the existing generation stack (`LoRATuner` on Illustrious-XL, `SD3Wrapper`, ComfyUI integration, data pipeline). Full detail in [content_generation.md](roadmaps/content_generation.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| CG.1 | **[Gen] WD14 + Florence-2 anime captioning** (booru tags + trigger token; shared with auto-tagger) | ~2d | [content_generation.md §1.1](roadmaps/content_generation.md) |
| CG.2 | **[Gen] Shared anime upscaler** — Real-ESRGAN anime_6B module reused by gen tabs + ASP | ~1d | [content_generation.md §1.6](roadmaps/content_generation.md) |
| CG.3 | **[Gen] ComfyUI control workflows** — curated txt2img / pose / reference / upscale JSONs | ~2d | ✅ Done — `configs/comfy_workflows/{controlnet,ipadapter}_generate.json` + `backend/src/models/core/comfy_manager.py` + `gui/src/tabs/models/gen/comfy_generate_tab.py`. [content_generation.md §1.4](roadmaps/content_generation.md) |
| CG.4 | **[Gen] Video→Character-LoRA guided flow** — PySceneDetect + dedup + caption + per-GPU TOML | ~1–2w | [content_generation.md §3](roadmaps/content_generation.md) |
| CG.5 | **[Gen] LyCORIS variants** (LoCon/LoHa/LoKr) in `LoRATuner` | ~3d | [content_generation.md §1.3](roadmaps/content_generation.md) |
| CG.6 | **[Gen] AnimateDiff via ComfyUI** — short anime clips/GIFs with character LoRA | ~1w | [content_generation.md §2.1](roadmaps/content_generation.md) |
| CG.7 | **[Gen] v-prediction / zero-terminal-SNR** support in `LoRATuner` + samplers | [Research] | [content_generation.md §1.2](roadmaps/content_generation.md) |
| CG.8 | **[Gen] ToonCrafter inbetweening** (shared with ASP `animation/anim_fill.py` ghost-fill) | [Research] | [content_generation.md §2.2](roadmaps/content_generation.md) |
| CG.9 | **[Gen] FLUX.1 [dev] secondary support** (FP8/GGUF for 16 GB) | [Research] | [content_generation.md §1.5](roadmaps/content_generation.md) |
| CG.10 | **[Gen] Wan2.1 / SVD foundation video** (3090 Ti, VRAM-gated) | [Long-term] | [content_generation.md §2.3](roadmaps/content_generation.md) |

---

## Phase MCA — Manga Colorization & Animation (HITL Deep Learning + Mathematical Optimization)

Greenfield feature area tracked under GitHub Milestone #6 ("Manga Colorization and Animation"). Combines a deterministic, copyright-safe mathematical-optimization track (Levin scribble colorization, screentone-aware level sets, graph-correspondence QP / Optimal-Transport reference colorization, Boykov-Kolmogorov graph-cut temporal coherence, ARAP mesh puppeteering) with a [Research]-gated generative deep-learning track (diffusion reference colorization, DiT inbetweening, Diffusion-DPO/LoRA alignment), all exposed through a shared HITL layered-canvas editor. Full detail in [the CSG submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| MCA.1 | **[Manga] Text/speech-bubble detection + inpainting** (CRAFT/PaddleOCR + LaMa; manual-mask MVP first) | ~3–5d | [the CSG submodule's moon/ROADMAP.md §1.1](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#11-textspeech-bubble-detection--inpainting) |
| MCA.2 | **[Manga] Line art extraction** (PiDiNet / Informative-Drawing wrapper) | ~2–3d | [the CSG submodule's moon/ROADMAP.md §1.2](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#12-line-art-extraction) |
| MCA.3 | **[Manga] ✅ Screentone Gabor feature extraction** — `backend/src/manga/gabor.py`, pure Python/OpenCV (not the originally-planned C++ `base` kernel — see issue #185) | Done | [the CSG submodule's moon/ROADMAP.md §1.3](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#13-screentone-gabor-feature-extraction) |
| MCA.4 | **[Manga] ✅ Levin quadratic-cost scribble colorizer** — `backend/src/manga/colorization.py`, pure Python/SciPy sparse solve (not the originally-planned C++ `base::manga`/Eigen kernel — see issue #186 for rationale; native port remains an open follow-up) | Done | [the CSG submodule's moon/ROADMAP.md §2.1](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#21-levin-quadratic-cost-scribble-colorizer) |
| MCA.5 | **[Manga] ✅ Screentone-aware propagation** — `backend/src/manga/screentone.py`, Gabor texture-affinity reusing MCA.4's solver rather than a separate level-set PDE (see issue #187 for rationale) | Done | [the CSG submodule's moon/ROADMAP.md §2.2](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#22-screentone-aware-level-set-propagation) |
| MCA.6 | **[Manga] ✅ Optimal-Transport / Sinkhorn reference colorizer** — `backend/src/manga/optimal_transport.py`, hand-written NumPy Sinkhorn over SLIC superpixels + Gabor structural features (not `POT`/torch — see issue #188 for rationale) | Done | [the CSG submodule's moon/ROADMAP.md §2.4](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#24-optimal-transport--sinkhorn-reference-colorizer) |
| MCA.7 | **[Manga] Graph-correspondence QP reference colorizer** (fallback path) | ~2w+ | [the CSG submodule's moon/ROADMAP.md §2.3](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#23-graph-correspondence-qp-reference-colorizer) |
| MCA.8 | **[Manga] ✅ Layered HITL canvas editor** — `gui/src/elements/manga/canvas_editor.py` (`MangaCanvasEditor`) | Done | [the CSG submodule's moon/ROADMAP.md §5.1](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#51-layered-canvas-editor-multiply-blend-scribble--mask-layers) |
| MCA.9 | **[Manga] ✅ Quadtree-accelerated interactive solve** — `backend/src/manga/quadtree.py` (partitioning/windowed-resolve mechanism) + live "Live Preview" GUI wiring in the Manga Colorization Tab (`MangaCanvasEditor` stroke-bbox tracking + `IncrementalColorizeWorker`) | Done | [the CSG submodule's moon/ROADMAP.md §5.2](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#52-quadtree-accelerated-interactive-solve--done-2026-08-05-issue-191) |
| MCA.10 | **[Manga] ✅ 3D quadratic-cost temporal propagation** — `backend/src/manga/temporal.py`, direct (t,y,x) generalization of MCA.4's Levin solver (see issue #192 for the sparse-LU scaling caveat found during implementation) | Done | [the CSG submodule's moon/ROADMAP.md §3.1](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#31-3d-quadratic-cost-temporal-propagation) |
| MCA.11 | **[Manga] ✅ Graph-cut (Boykov-Kolmogorov) temporal coherence** — `backend/src/manga/graph_cut.py`, PyMaxflow-backed 2-label (OWN vs. neighbor-BLEND) per-frame binary graph-cut refinement over MCA.10's output (see issue #193 for the deliberate multi-label -> binary simplification) | Done | [the CSG submodule's moon/ROADMAP.md §3.2](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#32-graph-cut-boykov-kolmogorov-temporal-coherence--done-2026-08-05-issue-193) |
| MCA.12 | **[Manga] ✅ ARAP mesh puppeteering** (SVD local step + Poisson global solve) — `backend/src/manga/arap.py` algorithmic core + `gui/src/elements/manga/mesh_overlay_editor.py` (`MeshOverlayEditor`, real-time drag-to-pose rigging) + new "Puppeteering" tab (`gui/src/tabs/manga/puppeteering_tab.py`) | Done | [the CSG submodule's moon/ROADMAP.md §3.3](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#33-arap-mesh-puppeteering--done-2026-08-05-issue-194) |
| MCA.13 | **[Manga] ✅ GUI: Manga Colorization Tab** — `gui/src/tabs/manga/colorization_tab.py`, "Manga" category, Scribble/Levin + Screentone-aware + Reference/Optimal-Transport modes wired (Reference/QP mode gated pending MCA.7) | Done | [the CSG submodule's moon/ROADMAP.md §6.1](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#61-manga-colorization-tab) |
| MCA.14 | **[Manga] ✅ GUI: Manga Animation Tab** — `gui/src/tabs/manga/animation_tab.py`, frame-sequence loader + per-frame scribble store over MCA.8's shared canvas + `AnimationColorizeWorker` (§3.1 solve, optional §3.2 graph-cut refine) + result-preview scrubber + PNG-sequence export (ARAP/mesh-overlay mode deferred pending MCA.12's unbuilt backend — see issue #196) | Done | [the CSG submodule's moon/ROADMAP.md §6.2](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#62-manga-animation-tab--done-2026-08-05-issue-196) |
| MCA.15 | **[Manga] ✅ GUI: Preference Review Dialog** — `gui/src/components/manga_preference_dialog.py` (`MangaPreferenceDialog`) + `backend/src/manga/preference_log.py` (JSONL vote log at `~/.image-toolkit/manga_preferences.jsonl`, not SQLite — see issue #197 for rationale) | Done | [the CSG submodule's moon/ROADMAP.md §6.3](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#63-preference-review-dialog-dpo-capture--done-2026-08-05-issue-197) |
| MCA.16 | **[Manga] Diffusion reference colorizer** (MangaNinja/ColorFlow-style, ComfyUI spike first) | [Research] | [the CSG submodule's moon/ROADMAP.md §2.5](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#25-diffusion-reference-colorizer-manganinja-style-research) |
| MCA.17 | **[Manga] Diffusion inbetweening** (ToonCrafter-style, shared spike with ASP ghost-fill) | [Research] | [the CSG submodule's moon/ROADMAP.md §3.4](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#34-diffusion-inbetweening-tooncrafter-style-research) |
| MCA.18 | **[Manga] LocalDPO region preference fine-tuning + LoRA feedback loop** | [Research] | [the CSG submodule's moon/ROADMAP.md §4](https://github.com/ACFHarbinger/Cel-Shaded-Generator/blob/main/moon/ROADMAP.md#4-hitl-alignment-dpo--lora) |

---

## Phase 1 — Immediate Wins (Days, No New Dependencies)

These are one-line or near-trivial changes with immediate measurable benefit. Ship as a single batch.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 1.1 | **[ASP] ✅ Fallback path purity** — `scans_frames` snapshot taken before ML corrections at Stage 2; all fallback call-sites pass `scans_frames` | Done | [the ASP submodule's moon/ROADMAP.md §1.9](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#19-fallback-path-purity) |
| 1.2 | **[ASP] ✅ Dark scene gain clamp widening** — conditional `[0.80, 1.25]` when `ref_lum_scalar < 80`, `[0.88, 1.14]` otherwise | Done | [the ASP submodule's moon/ROADMAP.md §1.4](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#14-gain-clamp-widening-for-dark-scenes) |
| 1.3 | **[ASP] ✅ Static edge pre-bundle rejection** — `MIN_EXPECTED_STEP = 50` (defined in constants/animation.py) now correctly imported into pipeline.py; min-step guard at lines 278–298 is active | Done | [the ASP submodule's moon/ROADMAP.md §1.2](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#12-near-zero--zero-translation-edge-filter) |
| 1.4 | **[ASP] ✅ Content-aware minimal bounding crop** — `_crop_to_valid` uses `_largest_valid_rect` when valid_ratio < 0.80; SCANS fallback also uses `_largest_valid_rect` for diagonal panoramas | Done | [the ASP submodule's moon/ROADMAP.md §1.7](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#17-recdiffusion-border-rectangling) |
| 1.5 | **[ASP] ✅ Restrict seam search window** — `_seam_dp` gains `search_half` parameter; `de_seam` propagates it; callers pass `search_half=100` for small cross-axis displacement | Done | [the ASP submodule's moon/ROADMAP.md §1.5](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#15-stage-11-composite-performance) |
| 1.6 | **[Perf] ✅ WebDriver context manager** — all crawlers migrated to Rust (`base/src/web/`); Python wrappers call `base.run_*` and never hold a driver reference; Rust code calls `driver.quit().await` on all exit paths; Python-level orphaned-driver risk eliminated by architecture | Done | [performance.md §3.5](roadmaps/performance.md#35-webdriver-lifecycle-management) |
| 1.7 | **[Perf] ✅ Image move/copy semantics — moot post-C++ migration** — successors `base::core::apply_ar()` (`convert.cpp`) and `merge_images_horizontal/vertical/grid()` (`merger.cpp`) use `cv::Mat`, which is reference-counted/shallow-copy by default; no-op path (`convert.cpp:82`) already returns the shared-buffer image at O(1) cost, no `DynamicImage`-style deep clone exists to eliminate. Re-verified 2026-07-27 (#76) | Done | [performance.md §3.6](roadmaps/performance.md#36-dynamicimage-move-semantics-in-rust) |
| 1.8 | **[Perf] ✅ ML model unload after BiRefNet + LoFTR stages** — `unload()` added to all 7 model wrappers (BiRefNet, LoFTR, EfficientLoFTR, RoMa, ALIKED+LG, JamMa, BaSiC); pipeline calls `unload()` instead of `offload()` | Done | [performance.md §3.7](roadmaps/performance.md#37-python-ml-model-memory-lifecycle) |
| 1.9 | **[GUI] ✅ Session persistence** — `_save_last_dir` / `_load_last_dir` via `QSettings` in both gallery base classes | Done | [gui_ux.md §2.5](roadmaps/gui_ux.md#25-session-persistence) |
| 1.10 | **[GUI] ✅ OS dark mode follow** — `QGuiApplication.styleHints().colorScheme()` + `colorSchemeChanged` live signal in `MainWindow` | Done | [gui_ux.md §2.8](roadmaps/gui_ux.md#28-theme-support) |
| 1.11 | **[GUI] ✅ Ctrl+scroll thumbnail zoom** — `ctrl_wheel` signal on `MarqueeScrollArea`; auto-connected in `_on_layout_change`; reloads current page at new size | Done | [gui_ux.md §2.2](roadmaps/gui_ux.md#22-gallery-thumbnail-size-control) |
| 1.14 | **[GUI] ✅ Settings window — Gallery/Startup/Performance/Slideshow/Logging/Reset State sections** — implemented | Done | [gui_ux.md §2.9](roadmaps/gui_ux.md#29-settings-window-extensions) |
| 1.12 | **[Arch] ✅ `uv lock` + CI frozen install** — `uv.lock` committed; `.github/workflows/ci.yml` uses `uv sync --frozen --no-install-project`; `pip-audit` + `numpy` added to dev deps | Done | [architecture.md §5.7](roadmaps/architecture.md#57-dependency-audit-and-pinning) |
| 1.13 | **[Arch] ✅ Python `logging` module + rotating file handler** — `_setup_logging()` in `app.py` creates a 5 MB rotating file handler + console handler; `logger = logging.getLogger(__name__)` added to `pipeline.py`, `canvas.py`, `matching.py`, and all model wrappers; `print()` migrated to `logger.info/debug/warning/error` | Done | [architecture.md §5.4](roadmaps/architecture.md#54-logging-and-diagnostics) |

---

## Phase 2 — Core Quality-of-Service (Days to 1 Week, Minimal Dependencies)

Reliable improvements with a clear implementation path and direct impact on daily use.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 2.1 | **[ASP] ✅ TOML config file for pipeline constants** — `load_asp_config()` + `get_asp()` in `backend/src/animation/config.py`; `_CONFIG_SCHEMA` (14 keys); `validate_asp_config()` strict/warning modes; `asp_config.toml` loaded on startup (§1.8A/B, S27/S42) | Done | [the ASP submodule's moon/ROADMAP.md §1.8](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#18-asp-pipeline-configuration-file) |
| 2.2 | **[ASP] ✅ NumPy vectorised seam DP** — `_seam_cut()` forward pass uses `scipy.ndimage.minimum_filter1d(size=3, cval=np.inf)`; traceback uses slice-argmin; 5–10× speedup vs explicit loop (§1.5A, S10) | Done | [the ASP submodule's moon/ROADMAP.md §1.5](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#15-stage-11-composite-performance) |
| 2.3 | **[ASP] ✅ Near-duplicate frame deduplication** — `_near_dup_luma_filter()` + `_detect_hold_blocks_dhash()` (INTER_AREA + horizontal gradient hash, distance ≤ 4); wired in `smart_select_frames` step 1b; `ASP_HOLD_DHASH_THRESH=4` (§1.2B/§3.4A, S26/S43) | Done | [the ASP submodule's moon/ROADMAP.md §1.2](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#12-near-zero--zero-translation-edge-filter) |
| 2.4 | **[ASP] ✅ Increase foreground penalty in seam DP** — tiered cost map: fg-interior=1.0, fg-edge-buffer=0.5, bg=0.0; `sem_weight=200.0` in `_seam_cut()`; fg-dominated-column barrier cost=2.0 (§1.6A S19, §3.15A S33) | Done | [the ASP submodule's moon/ROADMAP.md §1.6](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#16-ghosting-reduction-in-composite-zone) |
| 2.5 | **[ASP] ⚠ Post-run RLHF quality gate — REMOVED, not done** — previously `_compute_rlhf_score()` + `_get_reward_model()` lazy singleton in `bench_anime_stitch.py` (§1.10A, S29); confirmed deleted in the 2026-07-09 S200 trim (`refactor(asp): trim benchmark to core metrics; prune dead-feature tests` / `refactor(asp): trim Python pipeline to its benchmarked core path`) — `bench_anime_stitch.py` has no reward-model or RLHF code left. Would need to be rescoped from scratch if wanted again; the current `the ASP submodule's moon/ROADMAP.md` roadmap has no equivalent item. | Not done (was Done, now removed) | [the ASP submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md) |
| 2.6 | **[ASP] ✅ Stage-level progress signals** — `_ProgressPipeline` in `stitch_worker.py` emits `sig_stage(idx, total, label)` at the start of all 13 stages via `_emit()`; `StitchWorker.sig_stage = Signal(int, int, str)` | Done | [gui_ux.md §2.7](roadmaps/gui_ux.md#27-progress-and-cancellation) |
| 2.7 | **[GUI] ✅ Cancellable QThread `_should_stop` flag** — `WallpaperWorker` and `TrainingWorker` now set `self._should_stop = True` in `stop()` (previously only `is_running` was set); both initialise `_should_stop = False` for uniform tooling | Done | [gui_ux.md §2.7](roadmaps/gui_ux.md#27-progress-and-cancellation) |
| 2.8 | **[GUI] ✅ Arrow key gallery navigation** — `keyPressEvent` in `AbstractClassTwoGalleries`: Left/Right/Up/Down move `_focused_found_idx`, Enter emits `path_double_clicked` on focused widget | Done | [gui_ux.md §2.3](roadmaps/gui_ux.md#23-keyboard-navigation) |
| 2.9 | **[GUI] ✅ Shift+click / Ctrl+click multi-select** — `handle_marquee_selection()` in `AbstractClassTwoGalleries` checks `Qt.ShiftModifier` (additive) and `Qt.ControlModifier` (subtractive); fully wired | Done | [gui_ux.md §2.4](roadmaps/gui_ux.md#24-bulk-selection-and-operations) |
| 2.26 | **[GUI] ✅ F2 Rename (§2.26B)** — `_rename_focused_file()` in `AbstractClassTwoGalleries` (triggered by F2, renames the file focused via arrow-key navigation) and `_rename_selected_file()` in `AbstractClassSingleGallery` (renames last selected item). Both sanitise the new name, guard against conflicts, and update `found_files`, `master_found_files`, `selected_files`, and `path_to_label_map` / `path_to_card_widget`. | Done | [gui_ux.md §2.26](roadmaps/gui_ux.md#226-inline-rename) |
| 2.19 | **[GUI] ✅ Export selection as paths list (§2.19A)** — `_export_selection_as_paths()` on both gallery base classes; Ctrl+E saves `selected_files` (or all found files if none selected) to a user-chosen `.txt`/`.csv`. Uses `DontUseNativeDialog` to avoid JVM RTTI conflict. | Done | [gui_ux.md §2.19](roadmaps/gui_ux.md#219-gallery-export-and-contact-sheet) |
| 2.10 | **[GUI] ✅ Recent directories MRU helpers** — `_add_recent_dir` / `_get_recent_dirs` on both gallery base classes; backed by `QSettings`; ready for concrete tabs to wire up a dropdown | Done | [gui_ux.md §2.5](roadmaps/gui_ux.md#25-session-persistence) |
| 2.16 | **[GUI] ✅ Wire settings A/B/C/D/E/F/G** — corrected 2026-07-27: verified against `main_window.py`'s `_apply_startup_preferences()`. §A+B+C+E are wired (thumbnail/page size, LRU cache resize, startup category, WallpaperTab slideshow spinboxes/combo — all tagged `§2.16A/B/C/E` in code); §D is wired (confirm_deletions, tagged separately in gui_ux.md §2.9). **Updated 2026-08-27: §F and §G have since been wired** — the "corrected 2026-07-27" text below described the pre-fix state and is kept for history. **§F (file_logging_enabled + log level) — wired (issue #64, S231):** `_setup_logging()` still runs pre-vault (file logging on, `--verbose` for console), but `backend/src/app.py::_reconfigure_logging(log_level_name, file_logging_enabled)` now applies the vault prefs after unlock, called from `gui/src/windows/main/_startup_prefs.py`. **§G (recent_dirs_count) — wired (issue #79, S232):** `gallery_base.py::_add_recent_dir` reads `self.recent_dirs_limit` (populated from the `recent_dirs_count` preference via `_startup_prefs.py`), not a hardcoded `10`. *(Pre-fix state: `_setup_logging()` only took `--verbose` and the log prefs were never applied; `recent_dirs_count` round-tripped through the dialog but every consumer hardcoded `max_entries=10`.)* | Done (all 7 wired) | [gui_ux.md §2.9](roadmaps/gui_ux.md#29-settings-window-extensions) |
| 2.11 | **[GUI] ✅ Toggle button + quality metrics overlay in StitchTab** — `_show_stitch_result()` loads result + first-frame pixmaps after stitch; "◀ Before / After ▶" toggle button switches between them; `_MetricsTask` (QRunnable) computes Laplacian sharpness + file size + dimensions off-thread; metrics label updates via `_MetricsSignals.ready`; result group hidden until first stitch | Done | [gui_ux.md §2.6](roadmaps/gui_ux.md#26-stitch-tab-ux--beforeafter-comparison) |
| 2.18 | **[GUI] ✅ Gallery sort toolbar + search operators** — Sort QComboBox (Name/Date/Size/Ext) + ↑↓ button in pagination bar; `_apply_sort()` / `_sort_key_fn()` in both gallery base classes; `_common_filter_string_list` upgraded to support `-exclude`, `"phrase"`, `a\|b` OR; placeholder text updated to hint syntax; sort applied on directory load too | Done | [gui_ux.md §2.13](roadmaps/gui_ux.md#213-gallery-filtering-and-sort-controls) |
| 2.19 | **[GUI] ✅ Move to Trash instead of permanent delete** — `send2trash` replaces `os.remove` in DeleteTab, WallpaperTab, SearchTab; confirmation dialogs updated; `send2trash>=1.8.3` added to `pyproject.toml` | Done | [gui_ux.md §2.15](roadmaps/gui_ux.md#215-undoredo-for-destructive-operations) |
| 2.17 | **[GUI] ✅ Accent colour picker + UI density + font scale** — `QColorDialog` swatches in settings "Display and Media" tab; `compute_accent_vars()` derives hover/pressed from base; `load_qss_with_overrides()` substitutes at runtime; density appends Compact/Spacious QSS; font scale via `QApplication.setFont`; all persisted in vault `preferences` | Done | [gui_ux.md §2.30](roadmaps/gui_ux.md#230-accent-color-and-ui-density-customization) |
| 2.12 | **[Perf] ✅ Rust two-pass streaming image merger** (Option A). All three `merge_images_{horizontal,vertical,grid}_core` functions refactored: Pass 1 reads image headers via `image::image_dimensions()` (no pixel decode) to compute canvas size; canvas allocated once; Pass 2 loads one image at a time, blits, drops immediately. Peak RAM = 1 image + output canvas instead of all-images-at-once. 6 Rust tests (2 original preserved, 4 new streaming-correctness tests). | Done | [performance.md §3.1](roadmaps/performance.md#31-rust-streaming-image-merger) |
| 2.13 | **[Arch] ✅ Pipeline execution trace JSON** — `_ProgressPipeline.run()` writes a per-run JSON to `~/.image-toolkit/traces/stitch_YYYYMMDD_HHMMSS.json` containing `started_at`, `finished_at`, `elapsed_seconds`, `frames_input`, `edges_found`, `canvas_size`, `fallback_used`, `success`, `error`, `stage_timings` | Done | [architecture.md §5.4](roadmaps/architecture.md#54-logging-and-diagnostics) |
| 2.14 | **[Arch] ✅ pgvector HNSW index tuning** — `schema.sql` index updated to `m=32, ef_construction=128`; `search_images()` sets `hnsw.ef_search = 80` via `SET LOCAL` before each vector query | Done | [performance.md §3.4](roadmaps/performance.md#34-database-query-optimisation) |
| 2.15 | **[Arch] ✅ `pip-audit` + `cargo audit` in CI** — `.github/workflows/security.yml`: weekly `pip-audit --requirement` scan of locked deps; `cargo audit` on `base/` crate; both upload JSON reports as CI artifacts; fails on any CVE (§5.7C/D) | Done | [architecture.md §5.7](roadmaps/architecture.md#57-dependency-audit-and-pinning) |

---

## Phase 3 — Feature Enrichment (1–2 Weeks per Item)

New capabilities that expand the app's core value proposition.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 3.1 | **[ASP] ✅ GNC robust loss in bundle adjustment** — GNC-TLS outer continuation loop shipped S76 (§1.32); Cauchy one-shot (§1.1C) available via `ASP_GNC_OUTER=0` | Done | [the ASP submodule's moon/ROADMAP.md §1.32](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#132-gnc-tls-bundle-adjustment-quick-win--shipped-s76) |
| 3.2 | **[ASP] ✅ OpenCV PANORAMA fallback** — `_panorama_stitch_fallback()` in `canvas.py`; uses `cv2.Stitcher_create(mode=0)` (PANORAMA); wired between Retry 3 and SCANS as last classical attempt (§1.3B, S31) | Done | [the ASP submodule's moon/ROADMAP.md §1.3](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#13-scale-and-rotation-handling) |
| 3.3 | **[ASP] ⚠ Poisson blending at seam zone — REMOVED, not done** — previously `_poisson_seam_blend()` in `compositing.py` (§1.6C, S21); confirmed no longer present — `compositing.py` now only implements multi-band Laplacian-pyramid blending (`_laplacian_blend`, whose own docstring notes it is "Superior to Poisson blending for cel-shaded anime"), and no `_poisson_seam_blend`/`seamlessClone` call-site remains anywhere in `backend/src/animation/`. Superseded by the Laplacian blend path, not a gap to refill. | Not done (was Done, now removed/replaced) | [the ASP submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md) |
| 3.4 | **[ASP] ⚠ SRStitcher diffusion border fill — REMOVED, not done** — previously gated on `self.sr_mode and _SRSTITCHER_OK` in `pipeline.py`, calling `border_diffusion_fill()` from `sr_stitcher.py`; confirmed no longer present anywhere in `backend/` (no `sr_stitcher`, `SRSTITCHER`, or `border_diffusion_fill` references remain). Would need to be reimplemented from scratch if wanted again. | Not done (was Done, now removed) | [the ASP submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md) |
| 3.5 | **[Feat] ✅ CLI batch stitching** — top-level `stitch` command: single-sequence (`-i frames/ -o out.png`) and `--batch-dir` mode (stitch each sub-dir); `--resume` skips sequences where output exists (Option C); `.stitch_progress.json` progress file tracks done/failed/skipped per sequence (Option E); `--renderer` passes `median`/`first`/`blend` to pipeline; `--output-suffix` for output naming | Done | [new_features.md §4.1](roadmaps/new_features.md#41-batch-stitching) |
| 3.6 | **[Feat] ✅ WD-1.4 auto-tagger via ONNX** with confidence thresholds (Options A + E). `WDTaggerWrapper(ModelWrapper)` in `backend/src/models/wd_tagger_wrapper.py`; HuggingFace download + ONNX session on first `load()`; NHWC BGR float32 preprocessing with white-bg RGBA composite + square-pad; `tag()` / `tag_batch()` / `tag_with_review()` public API; `tag_with_review()` splits auto-accepted vs review-queue tags (Option E); default threshold 0.35; `WD_TAGGER_MODEL_REPO` + `WD_TAGGER_CACHE_DIR` env overrides; 26 tests passing. | Done | [new_features.md §4.4](roadmaps/new_features.md#44-auto-tagger-integration) |
| 3.7 | **[Feat] ✅ Safetensors metadata viewer** — `read_metadata()` in `safetensors_metadata.py` (shape/dtype via `get_slice()` without loading tensors); `SafetensorsInspectorDialog` (`gui/src/components/`): file info, user metadata, tensor tree (sortable, 197+ rows fast); "Inspect" button in LoRA generate tab; "Inspect .safetensors..." in LoRA train tab (§4.9A) | Done | [new_features.md §4.9](roadmaps/new_features.md#49-safetensors-metadata-viewer) |
| 3.8 | **[Feat] ✅ Slideshow configuration** — timing, order, source-directory filter (Option A). Wallpaper tab gains `slideshow_filter_group` row (QLineEdit + Browse) below interval/order controls; stored as `filter_dir` in tab config. `_apply_vault_slideshow_defaults()` deferred-loads interval/order from vault preferences at init. `collect()`/`set_config()`/`get_default_config()` wired. Both `_sync_daemon_config()` and `toggle_daemon()` emit `filter_directories: [filter_dir]` in `.slideshow_config.json`. Rust daemon: `filter_directories: Vec<String>` field + `matches_filter()` helper; filtered queue falls back to full queue when no match (slideshow never stalls). 4 new Rust tests (6 total). | Done | [new_features.md §4.7](roadmaps/new_features.md#47-slideshow-improvements) |
| 3.9 | **[GUI] ✅ Increase page size + item range indicator** — default page size 100→150; "150" added to page-size combo; item range label "Items A–B of C" in every pagination bar (§3.9); updated in `_update_pagination_ui` for both gallery base classes | Done | [gui_ux.md §2.1](roadmaps/gui_ux.md#21-virtual-scroll-gallery) |
| 3.10 | **[GUI] ✅ QSS dark/light mode toggle** — ☀/🌙 toggle button in header; `_toggle_theme()` switches `current_theme` + calls `set_application_theme()` + saves `creds["theme"]` to vault; `set_application_theme` syncs button icon on every call; OS auto-follow (§1.10) backs off once vault preference is set | Done | [gui_ux.md §2.8](roadmaps/gui_ux.md#28-theme-support) |
| 3.15 | **[GUI] ✅ Configurable keyboard shortcuts** — `ShortcutRegistry` (21 actions) + `QKeySequenceEdit` table in Settings "⌨️ Shortcuts" tab; JSON persistence to `~/.image-toolkit/keybindings.json`; conflict detection; `keyPressEvent` in both gallery base classes and `ImagePreviewWindow` uses `reg.matches()`; PySide6 6.10 flag-type fix in `matches()` | Done | [gui_ux.md §2.29](roadmaps/gui_ux.md#229-configurable-keyboard-shortcuts) |
| 3.16 | **[GUI] ✅ QSS user override file** — `load_user_qss_override()` appends `~/.image-toolkit/user_theme.qss` as the final step in `set_application_theme()`; returns `""` silently if the file is absent | Done | [gui_ux.md §2.31](roadmaps/gui_ux.md#231-custom-qss-user-theme-override) |
| 3.17 | **[GUI] ✅ Auto-save/restore window geometry** — `QSettings("ImageToolkit","ImageToolkit")` saves `mainwindow/geometry` in `closeEvent()`, restored in `__init__` before `showMaximized()` | Done | [gui_ux.md §2.32](roadmaps/gui_ux.md#232-window-layout-and-state-profiles) |
| 3.11 | **[Perf] ✅ PyTorch GPU temporal median** — `_gpu_nanmedian()` in `rendering.py`; all 5 `np.nanmedian` calls (1 main + 2 vertical fade + 2 horizontal fade) replaced; `ASP_GPU_MEDIAN=1` env flag; lazy CUDA detection via `_cuda_available`; falls back to numpy on no-CUDA or any failure | Done | [performance.md §3.2](roadmaps/performance.md#32-asp-render-stage-gpu-acceleration) |
| 3.12 | **[Perf] ✅ Dynamic BiRefNet batching** — `get_mask_batch` now pre-transforms all frames, groups into VRAM-sized chunks via `_compute_batch_size()` (`torch.cuda.mem_get_info()` − 1 GB reserve, 32× raw-tensor estimate, cap=4); batched forward pass via `torch.stack`; falls back to batch=1 on CPU/failure | Done | [performance.md §3.3](roadmaps/performance.md#33-birefnet-inference-batching) |
| 3.13 | **[Arch] ✅ ASP unit tests for bundle_adjust, compositing, matching** — 675 unit tests in `backend/test/animation/` as of 2026-07-27 (count re-verified via `pytest --collect-only`; the 827 figure quoted here previously was pre-S200-trim and is now stale — the trim removed dead-feature tests along with the ritual pipeline code); covers `bundle_adjust.py`, `compositing.py`, `frame_selection.py`, `canvas.py`, `pipeline.py`, `matching.py`, `validation.py`, `config.py`, `fg_register.py` and more; each test <1 s, no GPU required | Done | [architecture.md §5.1](roadmaps/architecture.md#51-asp-pipeline-unit-test-coverage) |
| 3.14 | **[Arch] ✅ GitHub Actions benchmark regression CI** — `.github/workflows/benchmark.yml`: runs all ASP unit tests (675 as of 2026-07-27, was 827 pre-trim) on push to main; `uv sync --frozen --no-install-project`; artifacts retained 14 days; fails PR if any test regresses (§5.2A) | Done | [architecture.md §5.2](roadmaps/architecture.md#52-benchmark-regression-ci) |

---

## Phase 4 — Platform Hardening (2–4 Weeks, Some Architecture Change)

Items that improve reliability, architecture cleanliness, and long-term maintainability.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 4.1 | **[Arch] ✅ Abstract Matcher base class & MatcherRegistry** — formal `Matcher` interface + `MatcherRegistry` plugin system + concrete plugins (`TemplateMatcher`, `PhaseCorrelateMatcher`, `SegmentGuidedMatcher`) shipped in `backend/src/animation/alignment/matching/` (§5.3B, issue #125) | Done | [architecture.md §5.3](roadmaps/architecture.md#53-plugin-system-for-matchers-and-compositors) |
| 4.2 | **[Arch] ✅ `ModelWrapper` ABC + `@lazy_load` decorator + `ModelRegistry`** — `backend/src/models/base.py`; all 7 wrappers migrated; `loaded` property + `is_available()` classmethod; `@lazy_load` on public entry-points; `ModelRegistry.unload_all()` | Done | [architecture.md §5.8](roadmaps/architecture.md#58-model-wrapper-abstraction-layer-backendsrcmodels) |

| 4.3 | **[Arch] ✅ Weekly scheduled ASP benchmark CI** — `benchmark.yml` gains `schedule: cron: "0 6 * * 1"` (every Monday 06:00 UTC); catches dep-induced regressions that don't touch the codebase (e.g. scipy minor bump) | Done | [architecture.md §5.2](roadmaps/architecture.md#52-benchmark-regression-ci) |
| 4.4 | **[Arch] ✅ LogWindow upgraded (§2.17D)** — `QPlainTextEdit`, colour-coded levels, timestamps, Copy All / Save / Clear / Follow. Full collapsible global panel (Option C) remains. | Partial | [architecture.md §5.4](roadmaps/architecture.md#54-logging-and-diagnostics) |
| 4.5 | **[Feat] ✅ OpenAPI schema for existing REST endpoints** — `drf-spectacular>=0.27.2` added; `drf_spectacular` in `INSTALLED_APPS`; `SPECTACULAR_SETTINGS` (title/desc/version); `/api/schema/` (YAML), `/api/docs/` (Swagger UI), `/api/redoc/` (ReDoc) in `api/urls.py`; all 19 task views annotated with `@extend_schema` (tags, summary, request, 202/400 responses) | Done | [new_features.md §4.10](roadmaps/new_features.md#410-rest-api-layer-for-remote-control) |
| 4.6 | **[Feat] ✅ Cross-directory phash deduplication index** — `phash BIGINT` column + `idx_images_phash` index added to PostgreSQL `images` table via idempotent `ALTER TABLE … ADD COLUMN IF NOT EXISTS` in `schema.sql`; `update_phash(image_id, phash_int)` + `find_near_duplicates_by_phash(phash_int, threshold, limit)` on `PgvectorImageDatabase` (Hamming distance via `bit_count(phash::bit(64) # query::bit(64))`); `compute_phash(path)` + `PhashDeduplicator` (index_image/index_directory/find_duplicates_for/find_all_duplicate_groups) in `backend/src/core/phash_deduplicator.py`; 10 unit tests | Done | [new_features.md §4.6](roadmaps/new_features.md#46-image-deduplication-across-directories) |
| 4.7 | **[Feat] ✅ KDE per-monitor wallpaper via D-Bus** — `find_qdbus_binary()` auto-detects `qdbus6`/`qdbus-qt6`/`qdbus`/`qdbus-qt5`; `evaluate_kde_script_dbus_python()` pure-Python D-Bus fallback (bypasses CLI); `evaluate_kde_script_with_fallback(qdbus, script)` chain (CLI → dbus-python → clear error); all three KDE script call-sites in `WallpaperManager` migrated; `wallpaper_tab.py` uses `find_qdbus_binary()` instead of inline 2-name check; works on Wayland+KDE where `DESKTOP_SESSION` ≠ `plasma` | Done | [new_features.md §4.5](roadmaps/new_features.md#45-multi-monitor-wallpaper-support) |
| 4.8 | **[Perf] ✅ psycopg3 connection pool** — `PooledPgvectorDatabase` in `backend/src/database/pooled_image_database.py` uses `psycopg_pool.ConnectionPool` (psycopg3 sync pool, min=2, max=10). Drop-in replacement for `PgvectorImageDatabase`: identical public API, each method borrows a thread-safe connection from the pool, returns it automatically. Eliminates single-connection bottleneck where multiple QThread workers raced on `self.conn`. `psycopg[pool]>=3.2` added to `pyproject.toml`. Row access via `psycopg.rows.dict_row` row_factory; duplicate-column queries (`get_all_subgroups_detailed`, `get_statistics`) use per-cursor `tuple_row` override. `VACUUM`/`REINDEX` use a direct `autocommit=True` connection outside the pool. 22 unit tests using mocked pool/connection, no live DB required. | Done | [performance.md §3.4](roadmaps/performance.md#34-database-query-optimisation) |
| 4.9 | **[GUI] QListView + QAbstractItemModel virtual scrolling** — prototype against `AbstractClassTwoGalleries` (Option A) | ~1w | [gui_ux.md §2.1](roadmaps/gui_ux.md#21-virtual-scroll-gallery) |
| 4.10 | **[GUI] Global hotkey table in settings** — JSON-backed `QShortcut` (Option B) | ~1w | [gui_ux.md §2.3](roadmaps/gui_ux.md#23-keyboard-navigation) |
| 4.12 | **[GUI] ✅ Named layout profiles** — extend "System Preference Profiles" to bundle geometry + splitter state + appearance settings (§2.32B). `_get_current_ui_preferences()` now snapshots `saveGeometry()` as base64 + all `splitters/*` QSettings keys as a `layout_splitters` dict. New `_apply_layout_from_profile()` restores geometry to the main window immediately and writes splitter states to QSettings (active on next tab init). Both Load Profile and Use Profile call the helper. | Done | [gui_ux.md §2.32](roadmaps/gui_ux.md#232-window-layout-and-state-profiles) |
| 4.13 | **[Feat] ✅ Appearance profiles** — extend vault profiles to include accent colour, font scale, density (Option A). `_get_current_ui_preferences()` now bundles `accent_color_dark/light`, `font_scale`, `ui_density` alongside `theme`/`active_tab_configs`. New `_apply_appearance_from_profile()` helper updates swatches + spinbox + combo. Load/Use profile both call helper. Login profile selection merges appearance keys into `preferences`. | Done | [new_features.md §4.12](roadmaps/new_features.md#412-appearance-profiles) |
| 4.11 | **[GUI] ✅ Thumbnail slider + per-tab persistent size** — `QSlider` (64–512 px, step 16) in every pagination bar; `_save_thumbnail_size()` on slider release and after Ctrl+scroll; `_load_thumbnail_size()` at `__init__` time keyed by `{ClassName}/thumbnail_size`; `_sync_thumb_slider()` keeps all sliders in sync; both gallery base classes updated | Done | [gui_ux.md §2.2](roadmaps/gui_ux.md#22-gallery-thumbnail-size-control) |
| 4.14 | **[Feat] ✅ Media Loader web-download tab** — new Web Integration tab (issue #182) with `RedditDownloader` (public `.json` endpoints, images/galleries/video) and `NhentaiDownloader` (SvelteKit gallery-JSON scrape) in `backend/src/web/downloaders/`, both synchronous-`requests`-based after an asyncio/aiohttp crash fix; GUI at `gui/src/elements/web/media_loader_tab/` (manager.py + mixins) + `MediaLoaderWorker` QThread | Done | [new_features.md §4.17](roadmaps/new_features.md#417-media-loader--web-media-downloader) |

---

## Phase 5 — Advanced Features (1–3 Weeks per Item, Research Required)

Higher-complexity features that depend on Phase 3–4 infrastructure or require experimentation.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 5.1 | **[Feat] OpenCLIP semantic search** — dual embedding column in PostgreSQL (Options A + C) | ~2w | [new_features.md §4.3](roadmaps/new_features.md#43-clip-based-semantic-image-search) |
| 5.2 | **[Feat] GUI batch stitching** — directory-level batch mode with progress list (Option A) | ~1w | [new_features.md §4.1](roadmaps/new_features.md#41-batch-stitching) |
| 5.3 | **[Feat] FFmpeg scrolling video export** (Option B) | ~1w | [new_features.md §4.2](roadmaps/new_features.md#42-export-stitched-panorama-to-scrolling-video) |
| 5.4 | **[Feat] ComfyUI drag-and-drop gallery integration** (Option C) | ~1w | [new_features.md §4.8](roadmaps/new_features.md#48-comfyui-workflow-integration-for-post-processing) |
| 5.5 | **[Feat] WD tagging review queue** — PostgreSQL-backed human-in-the-loop (Option C) | ~1w | [new_features.md §4.4](roadmaps/new_features.md#44-auto-tagger-integration) |
| 5.6 | **[Feat] REST API trigger for desktop operations + WebSocket status** (Options B + C) | ~2w | [new_features.md §4.10](roadmaps/new_features.md#410-rest-api-layer-for-remote-control) |
| 5.7 | **[ASP] ⚠ RLHF Bayesian parameter search** — optuna over gain, feather, seam cost (Option B). **Note (2026-07-27):** the base reward-model/RLHF loop this item builds on (see 2.5) was removed in the S200 trim; this item is moot until that foundation is rebuilt, if ever wanted again. Not currently on the `the ASP submodule's moon/ROADMAP.md` roadmap. | ~1w | [the ASP submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md) |
| 5.8 | **[ASP] Similarity transform (scale+rotation+translation) matcher** — `estimateAffinePartial2D` (Option E) | ~1w | [the ASP submodule's moon/ROADMAP.md §1.3](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#13-scale-and-rotation-handling) |
| 5.9 | **[ASP] ⚠ Seam DP cache for RLHF iteration** — keyed by `(frame_ids, seam_cost_config)` (Option D). **Note (2026-07-27):** premise (iterative RLHF parameter search, see 5.7) no longer applies since the RLHF loop was removed in the S200 trim; a seam-DP cache could still be independently useful for benchmark-iteration speed, but not for the originally-stated RLHF reason. | ~1d | [the ASP submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md) |
| 5.10 | **[Arch] Compositor registry** — same pattern as Matcher (Option E) | ~1w | [architecture.md §5.3](roadmaps/architecture.md#53-plugin-system-for-matchers-and-compositors) |
| 5.11 | **[Perf] Rust memory-mapped output buffer** — `memmap2` for >10K px panoramas (Option C) | ~2d | [performance.md §3.1](roadmaps/performance.md#31-rust-streaming-image-merger) |
| 5.12 | **[GUI] Extractor tab `libmpv` playback engine spike** — swap `QMediaPlayer`/`QGraphicsVideoItem` for `python-mpv` (Option A), gated on an isolated JVM-coexistence smoke test per the project's prior JPype/native-lib SIGSEGV history; falls back to mpv's OpenGL render API (Option B) if X11 `wid` window embedding proves unreliable on Wayland | ~2w | [gui_ux.md §2.33](roadmaps/gui_ux.md#233-extractor-tab-playback-engine--libmpv-integration) |
| 5.13 | **[GUI] 🔄 Draft: host Theme Studio & semantic customization** — Phase 1 host PySide6 GUI only; shared JSON schema for later surfaces; palette, density, corners, typography, shadows, motion, opt-in image-derived palette, transactional preview, and expert-gated raw QSS | Design / ~1–2w after sign-off | [app_theming_2026q3.md](roadmaps/app_theming_2026q3.md) · [gui_ux.md §2.34](roadmaps/gui_ux.md#234-custom-theme-engine--semantic-color-system) |
| 5.14 | **[GUI] Draft: background canvas & playlist** — linked/imported assets, token-pack references, global playlist clock, per-tab static override, fit modes, opacity, and opt-in cached blur | Design / ~1–2w after sign-off | [app_theming_2026q3.md](roadmaps/app_theming_2026q3.md) · [gui_ux.md §2.35](roadmaps/gui_ux.md#235-full-window-background-canvas--glassmorphic-layering) |
| 5.14 | **[GUI] Full-Window Background Canvas & Glassmorphic Layering** — full-window layered background canvas with adjustable opacity/blur, glassmorphic card layering, multi-image slideshow playlist with cross-fade transitions, and fit/scaling modes (Options A + B + C) | ~1w | [gui_ux.md §2.35](roadmaps/gui_ux.md#235-full-window-background-canvas--glassmorphic-layering) |


---

## Phase DB — Unified Database (Merging Listings Subtabs & Database Tabs)

Merges the SQLCipher listings store (`base.secret`/`listings_secure.db`, Content/Entity Listings subtabs) and the PostgreSQL + pgvector image index (Configuration/Search/Metadata tabs) into one encrypted, serverless SQLCipher store (`~/.image-toolkit/library.db`) behind a new **`base.database`** C++ module (session-keyed handle — Argon2id runs once at login; `base.secret` untouched) and a Python DAL. PostgreSQL is dropped entirely. Full detail, schema, phasing, and risk register in [unified_database.md](roadmaps/unified_database.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| DB.1 | **[DB] Unified schema design** — normalized relational schema replacing the listings JSON blob and the pgvector schema; media/entity/episode/credit tables, M2M associations, shared typed-tag vocabulary, FK'd groups/subgroups, `embeddings` + FTS5 | ~2d | [unified_database.md DB.1](roadmaps/unified_database.md#db1-unified-schema-design) |
| DB.2 | **[DB] `base.database` native engine** — new C++ module (NOT `base.secret`): session-keyed SQLCipher handle (one KDF per session), WAL, generic parameterized query/execute, management ops, HNSW vector search + FTS5 | ~1w | [unified_database.md DB.2](roadmaps/unified_database.md#db2-basedatabase--the-native-storage-engine) |
| DB.3 | **[DB] Python DAL** — `backend/src/database/unified/` repositories (media/entity/image/tag/search/manager); single-transaction saves; both tab families consume it | ~4d | [unified_database.md DB.3](roadmaps/unified_database.md#db3-python-dal-backendsrcdatabaseunified) |
| DB.4 | **[DB] Backups + migration scripts** — `backend/migrations/` 000–004: mandatory full backup gate, DDL, listings migration, Postgres migration (skippable), verification report; idempotent resumable runner | ~4d | [unified_database.md DB.4](roadmaps/unified_database.md#db4-backups--migration-scripts-backendmigrations) |
| DB.5 | **[DB] Listings subtabs port** — repos replace fetch-all/diff/re-upsert association loops (~500 LOC deleted); FTS/SQL search; `.enc` backup format preserved | ~1w | [unified_database.md DB.5](roadmaps/unified_database.md#db5-listings-subtabs-on-the-unified-store) |
| DB.6 | **[DB] Image tabs port + Postgres retirement** — Search/Scan/Preview/Wallpaper onto the DAL; Configuration tab → Library Management; psycopg2/pgvector removed; unified "Library" tab category; upsert loop moved off the GUI thread | ~1.5w | [unified_database.md DB.6](roadmaps/unified_database.md#db6-image-tabs-on-the-unified-store-postgres-retirement) |
| DB.7 | **[DB] Semantic search & CBIR** — MetaCLIP image/text embeddings + BGE-M3 listings embeddings in one `embeddings` table; HNSW knn with SQL prefilter; text→image search + find-similar; pHash demoted to dedup-only; rec_engine.db absorbed | ~1.5w | [unified_database.md DB.7](roadmaps/unified_database.md#db7-semantic-search--cbir) |
| DB.8 | **[DB] Cross-domain features** — media↔image-group links, entity↔image links (Entity Recon bridge), unified tag vocabulary + merge tool, auto-create listings from scans | ~1w | [unified_database.md DB.8](roadmaps/unified_database.md#db8-cross-domain-features) |
| DB.9 | **[DB] Data Browser tab** — crow's-foot ER schema view auto-generated from PRAGMAs + raw-value table grid with FK navigation and reverse-reference panel | ~4d | [unified_database.md DB.9](roadmaps/unified_database.md#db9-data-browser-tab-raw-tables--er-view) |
| DB.10 | **[DB] Backup pipeline retarget + cleanup** — `.enc` exports from the unified store, full-library encrypted dump, dead-code removal, docs, tests | ~3d | [unified_database.md DB.10](roadmaps/unified_database.md#db10-backup-pipeline-retarget--final-cleanup) |
| DB.11 | **[DB] Danbooru-style tag category system** — `tag_categories` table (color, scope, extensible), entities now taggable (`entity_tags`), auto-tag-on-create, transitive entity↔series tag search, grouped-tags display component | ~1w | [unified_database.md DB.11](roadmaps/unified_database.md#db11-danbooru-style-tag-category-system--done-2026-08-02) |

**Dependency order:** DB.1 → DB.2 → DB.3 → DB.4 (foundation, strictly sequential); DB.4 → DB.5 → DB.6 (listings cut over before Postgres retires); DB.6 → DB.7 → DB.8; DB.9 anytime after DB.3; DB.10 → DB.11.

---

## Phase EXT — Browser Extension (Capture, Build System & App Integration)

Upgrades the `extension/` WebExtension from a minimal image saver into a first-class companion to the desktop app. Full detail, options, and dependency graph in [extension.md](roadmaps/extension.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| EXT.1 | **[Ext] ✅ Webpack multi-browser build system** — `extension/webpack/` generates per-browser `manifest.json` (chrome, firefox, edge, brave) from `manifest.base.json` + overlays; replaces the three hand-maintained manifests; per-browser dist zips | ~2d | [extension.md §7.1](roadmaps/extension.md#71-webpack-multi-browser-build-system) |
| EXT.2 | **[Ext] ✅ TypeScript migration + shared core** — typed message contract, single browser-API adapter, typed `storage.local` schema | ~2d | [extension.md §7.2](roadmaps/extension.md#72-typescript-migration--shared-core) |
| EXT.3 | **[Ext] ✅ Unified Manifest V3** — drop MV2 Firefox manifest; MV3 everywhere with per-browser overlays (Firefox 109+) | ~1d | [extension.md §7.3](roadmaps/extension.md#73-unified-manifest-v3) |
| EXT.4 | **[Ext] 🔄 Options page redesign** — popup (profile switcher, turbo, bridge status) + full options tab (profiles, site rules, app connection) | ~2–3d | [extension.md §7.4](roadmaps/extension.md#74-options-page-redesign) |
| EXT.5 | **[Ext] 🔄 Local app bridge** — Phase A: token-authenticated localhost Django endpoints (`/api/extension/…`); Phase B: native messaging host per browser | ~3d + ~1w | [extension.md §7.5](roadmaps/extension.md#75-local-app-bridge-http--native-messaging) |
| EXT.6 | **[Ext] ✅ In-browser duplicate search** — right-click image → pHash search (`PhashDeduplicator`, §4.6) of the user-configured directory + subdirectories; match list with thumbnails; optional auto-check on turbo downloads | ~4d | [extension.md §7.6](roadmaps/extension.md#76-in-browser-duplicate-search) |
| EXT.7 | **[Ext] 🔄 Send to Image Toolkit** — ingest with source URL/page metadata, immediate pHash + embedding indexing | ~3d | [extension.md §7.7](roadmaps/extension.md#77-send-to-image-toolkit) |
| EXT.8 | **[Ext] Visual similarity search from browser** — right-click → BGE-M3/CLIP vector search of local library (gated on §5.1 embedding index) | ~4d | [extension.md §7.8](roadmaps/extension.md#78-visual-similarity-search-from-browser) |
| EXT.9 | **[Ext] ✅ Bulk page grabber** — one-click download of all page images+videos; in-page click-to-select overlay with download/cancel bar; grid-preview page (`extension/src/gallery/`) with size/format/URL filters, per-item download progress, and §7.16C client-pHash dup-check badges | ~1w | [extension.md §7.9](roadmaps/extension.md#79-bulk-page-grabber) |
| EXT.10 | **[Ext] 🔄 Per-site folder rules + filename templating + metadata sidecar** — domain→profile rules, `{site}/{date}_{name}.{ext}` templates, optional provenance JSON sidecar | ~4d | [extension.md §7.10](roadmaps/extension.md#710-per-site-folder-rules-filename-templating--metadata-sidecar) |
| EXT.11 | **[Ext] 🔄 Full-resolution extraction** — srcset/`<picture>`/lazy-load/CSS-background/canvas candidates; per-site URL upgrade table | ~4d | [extension.md §7.11](roadmaps/extension.md#711-full-resolution-extraction) |
| EXT.12 | **[Ext] 🔄 Turbo mode polish** — capture flash + badge, modifier-key mode, per-site enable list, download history panel | ~3d | [extension.md §7.12](roadmaps/extension.md#712-turbo-mode-polish) |
| EXT.13 | **[Ext] ✅ Duplicate tab highlighter** — scan current window's tabs, group duplicates by normalized URL; colored tab groups on Chromium, badge + popup set list on Firefox; keep-first/close-rest actions | ~2d | [extension.md §7.13](roadmaps/extension.md#713-duplicate-tab-highlighter) |
| EXT.14 | **[Ext] 🔄 App-powered CV operations** — A/B/C ✅ shipped (issues #93/#94/#95): `POST /api/extension/cv/bg-remove` (BiRefNet, job-id+poll via Celery) + "Remove background" menu item (`extension_api/tasks.py`, `views.py`, `background.ts`); `POST /api/extension/cv/upscale` (Real-ESRGAN anime_6B, `scale: 2\|4`) + "Upscale & save" menu item; `auto_tag` flag on §7.7 ingest (`WDTaggerWrapper.tag_with_review()`, tags in sidecar JSON — DB storage still pending on §7.7's own "DB indexing at ingest" remaining item). D (OCR extraction + local translation) remains unbuilt — a new app-side capability, out of scope for this pass | ~1.5w | [extension.md §7.14](roadmaps/extension.md#714-app-powered-cv-operations) |
| EXT.15 | **[Ext] 🔄 Media capture suite** — A/B/D ✅ shipped: native-res video frame grabber+burst (`videoCapture.ts`); GIF/APNG/animated-WebP frame extractor via WebCodecs `ImageDecoder` (issue #97, `extension/src/frames/`); video clip capture → WebM (`MediaRecorder`) or hand-muxed animated WebP (issue #99, `extension/src/videoClip.ts`, `shared/webpMux.ts`). Remaining: C webtoon strip capture → ASP stitch, E video downloader with time-range cutting (both need new app-side/bridge endpoints) | ~2.5w | [extension.md §7.15](roadmaps/extension.md#715-media-capture-suite) |
| EXT.16 | **[Ext] 🔄 Image analysis utilities** — EXIF + embedded SD/ComfyUI prompt metadata inspector, reverse-search shortcuts (SauceNAO/trace.moe/Lens/IQDB), client-side pHash pre-check with app hash snapshot, local-ML reverse search (transformers.js fallback) | ~2w | [extension.md §7.16](roadmaps/extension.md#716-image-analysis-utilities) |

**Dependency order:** EXT.1 → EXT.2 → (EXT.3, EXT.4) foundation first; EXT.5A → EXT.6 → EXT.7 (bridge before integration features); EXT.11 → EXT.9 → EXT.12 (extractor before grabber/turbo); EXT.8 gated on §5.1; EXT.5B last.

---

## Phase Arch — Code Quality & Developer Experience (Days to 2 Weeks, No New Features)

Targeted refactors that reduce maintenance burden, improve onboarding, and prevent regressions. Items are ordered by ascending effort; all are independent and can be parallelised. Full detail in [architecture.md](roadmaps/architecture.md).

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| A.1 | **[Arch] ✅ Pyright `basic` mode** — `typeCheckingMode = "basic"` in `pyproject.toml` | Done | [architecture.md §5.5B](roadmaps/architecture.md#55-gradual-static-type-safety-migration) |
| A.2 | **[Arch] ✅ Eliminate silent `print()` errors** — `conversion_worker.py` (3×), `duplicate_scan_worker.py` (2×), `gan_wrapper.py` (1×), `lo_ra_tuner.py` (1×); all replaced with `logger.warning/error` | Done | [architecture.md §5.15C](roadmaps/architecture.md#515-fault-isolation--error-boundary-protocol) |
| A.3 | **[Arch] ✅ Remove `# --- Relocated Nested Imports ---` comment blocks** — single grep-and-edit pass across all model wrappers; consolidate into standard PEP 8 import order | Done | [architecture.md §5.8D](roadmaps/architecture.md#58-model-wrapper-abstraction-layer-backendsrcmodels) |
| A.4 | **[Arch] ✅ `__all__` hygiene pass** — 15 `__init__.py` files updated: `backend/src/{models,web,core,pipeline,utils,controller,__init__}` and `gui/src/{utils,styles,helpers/{image,video,web,core},tabs,tabs/core/common}`; empty files get `[]`; populated files get explicit `__all__` lists | Done | [architecture.md §5.11D](roadmaps/architecture.md#511-circular-import-prevention--module-boundary-documentation) |
| A.5 | **[Arch] ✅ QSettings key validation at startup** — `SETTINGS_SCHEMA` dict + `SETTINGS_PREFIX_TYPES` + `_validate_settings()` in `app.py`; called after `QApplication()` creation; logs warnings for type-mismatched keys and clears them; unknown keys logged at DEBUG | Done | [architecture.md §5.14D](roadmaps/architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.6 | **[Arch] ✅→🗑️ `@log_call` timing decorator** — `backend/src/utils/decorators/function_calls.py`; never applied to any function anywhere in the codebase; removed as dead code during the 2026-07-28 controllers/utils restructuring pass | Removed (unused) | [architecture.md §5.13C](roadmaps/architecture.md#513-decorator-library-for-cross-cutting-concerns-backendsrcutilsdecoratorspy) |
| A.7 | **[Arch] ✅ Metaclass docstring + `_load_thumbnail_size` extraction** — extended docstring in `meta_abstract_class_gallery.py` explaining Qt metaclass fusion + injection rationale; `save_thumbnail_size`/`load_thumbnail_size` extracted to `gui/src/utils/thumbnail_size.py`; both gallery base classes delegate to shared functions | Done | [architecture.md §5.10C](roadmaps/architecture.md#510-gallery-base-class-consolidation-guisrcclasses) |
| A.8 | **[Arch] ✅ TYPE_CHECKING guards for heavy GUI→backend imports** — `from __future__ import annotations` + `if TYPE_CHECKING:` for `AnimeStitchPipeline` and other PyTorch imports in GUI workers; reduces cold-start by ~2–4s | Done | [architecture.md §5.11B](roadmaps/architecture.md#511-circular-import-prevention--module-boundary-documentation) |
| A.9 | **[Arch] ✅ ML wrapper contract tests (mock-based)** — one `TestXxxWrapperContract` class per wrapper in `backend/test/models/`; verifies output shape/dtype, `unload()` idempotency, `loaded` property; no GPU required; <1s per test | Done | [architecture.md §5.16A](roadmaps/architecture.md#516-contract-testing-for-ml-model-wrappers-backendsrcmodels) |
| A.10 | **[Arch] ✅ mypy baseline config + TypedDict worker configs** — `[tool.mypy]` section in `pyproject.toml` (permissive baseline); `ConversionConfig`, `DeletionConfig`, `MergeConfig`, `StitchConfig` TypedDicts in `gui/src/helpers/core/config_types.py`; wired into `ConversionWorker`, `DeletionWorker`, `MergeWorker` | Done | [architecture.md §5.5A](roadmaps/architecture.md#55-gradual-static-type-safety-migration) |
| A.11 | **[Arch] ✅ `AppSettings` GUI facade** — `gui/src/utils/settings.py` singleton; replaces 20+ inline `QSettings("ImageToolkit","ImageToolkit")` constructor calls; typed properties per key; wired into both gallery base classes, `main_window.py`, `splitter_persistence.py`, `listings_common.py`, `thumbnail_size.py` | Done | [architecture.md §5.14A](roadmaps/architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.12 | **[Arch] ✅ `get_asp()` helper in `config.py`** — `get_asp(key, default="")` reads `os.environ[key]` with fallback; `ConfigError` raised in `validate_asp_config` strict mode; exported from `backend/src/animation/config.py` | Done | [architecture.md §5.14B](roadmaps/architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.13 | **[Arch] ✅ Custom exception hierarchy** — `backend/src/exceptions.py` with `ImageToolkitError` → `PipelineError`/`AlignmentFailedError`/`CanvasError`/`FallbackExhaustedError`/`ModelLoadError`/`ConfigError`; bare `RuntimeError`/`ValueError` replaced in `animation/pipeline.py`, `animation/canvas.py`, `animation/config.py`, `models/birefnet_wrapper.py`; `BaseQThreadWorker` three-tier handler routes `AlignmentFailed`/`Canvas` as WARNING, `Pipeline`/`Model`/`Config` as ERROR | Done | [architecture.md §5.15A](roadmaps/architecture.md#515-fault-isolation--error-boundary-protocol) |
| A.14 | **[Arch] ✅ `BaseQThreadWorker` + `BaseQRunnableWorker` + `_WorkerSignals`** — `gui/src/helpers/base.py`; uniform `cancel()`/`stop()`, exception routing; `SearchWorker` migrated to `BaseQRunnableWorker` | Done | [architecture.md §5.9](roadmaps/architecture.md#59-worker-thread-base-class--lifecycle-standardisation-guisrchelpers) |
| A.15 | **[Arch] ✅ Codebase documentation & Mermaid class diagrams** — Mermaid class hierarchy diagrams added to `backend/src/models/__init__.py` and `gui/src/classes/__init__.py` + NumPy-style docstrings across model and alignment modules (§5.12, issue #124) | Done | [architecture.md §5.12](roadmaps/architecture.md#512-codebase-documentation--diagrams) |
| A.16 | **[Arch] ✅ `AbstractGalleryBase` + real `common_*` methods** — `gallery_base.py` (574 lines); shared init state extracted; 9 injected `_common_*` functions → real inherited `common_*` methods; 10 duplicate helpers removed from both gallery files; `_on_layout_change`/`get_default_config`/`set_config` as `@abstractmethod`; metaclass 397→18 lines | Done | [architecture.md §5.10A](roadmaps/architecture.md#510-gallery-base-class-consolidation-guisrcclasses) |
| A.17 | **[Arch] ✅ `import-linter` contracts** — 3 contracts in `pyproject.toml`; enforces backend-core-no-GUI, gui.src.utils is leaf, gui.src.classes no-tabs; `import-linter>=2.0` added to dev deps; `PYTHONPATH=. lint-imports` runs clean; pydeps SVG deferred to a dedicated docs PR | Done | [architecture.md §5.11A](roadmaps/architecture.md#511-circular-import-prevention--module-boundary-documentation) |
| A.18 | **[Arch] ✅ Module dependency graph** — fixed pre-existing but broken `backend/validation/visualize_module_graph.py` (stale `"logic"` layer prefix, silently detecting zero Backend-layer modules) rather than adding `pydeps`; now scans `backend/src` + `gui/src` together with a shared repo-root-relative name space; `just validation::module-graph` wired to output `docs/module_graph.html` (committed, 475 modules/763 edges, 0 unexplained cross-layer violations, 1 allowlisted composition-root exception) | Done | [architecture.md §5.11C](roadmaps/architecture.md#511-circular-import-prevention--module-boundary-documentation) |
| A.19 | **[Arch] ✅ Unified `AppConfig` snapshot** — `gui/src/windows/settings/app_config.py`; frozen dataclass merging ASP env-var config (new `asp_schema()` export from `backend/src/animation/core/config.py`) with `AppSettings`'s known GUI keys + `gui_dynamic_keys`; `AppConfig.capture()` builds a fresh, read-only introspectable snapshot; placed under `windows/settings/` rather than `gui/src/utils/` to keep the `gui.src.utils`-is-a-leaf import-linter contract intact | Done | [architecture.md §5.14C](roadmaps/architecture.md#514-centralised-settings-facade-guisrcutilssettingspy--backendsrcanimconfigpy) |
| A.20 | **[Arch] ✅ Split all 8 oversized `backend/src/` files (<500 LoC)** — `wallpaper.py`, `matching.py`, `fg_register.py`, `image_merger.py`, `frame_selection.py`, `rendering.py`, `pipeline.py`, `compositing.py` → package directories via Option B (public-API-preserving re-export); includes `pipeline.py`/`compositing.py`, the two largest/most benchmark-sensitive files in the codebase; largest resulting file is 457 code lines (`animation/core/pipeline/run_stage.py`); closes issue #117 | Done | [architecture.md §5.17](roadmaps/architecture.md#517-file-size-limit-enforcement-500-loc) |
| A.21 | **[Arch] ✅ Split 24 medium `gui/src/` files (515–1,355 LoC) into packages** — `wallpaper_common_base.py`, `database_tab.py`, `merge_tab.py`, `monitor_display_subtab.py`, `scan_metadata_tab.py`, `system_display_subtab.py`, `abstract_class_two_galleries.py`, `similarity_tab.py`, `search_tab.py`, `main_window.py`, `format_subtab.py`, `stitch_worker.py`, `abstract_class_single_gallery.py`, `image_crawler_tab.py`, `series_listings_subtab.py`, `codec_subtab.py`, `drive_sync_tab.py`, `entity_listings_subtab.py`, `cbir_train_tab.py`, `display/detail_panel.py`, `sampler_subtab.py`, `metadata_editor_window.py`, `entity_recon_tab.py`, `monitor_drop_view.py` → package directories via Option B; discovered and documented an MRO-shadowing bug (mixins must precede the base class in the class declaration or their overrides are silently shadowed); one file (`stitch_worker/_progress_pipeline.py`, 689 LoC) deliberately left over-limit as a documented behavior-risk exception; the 3 remaining giants (`stitch_tab.py`, `extractor_tab.py`, `settings_window.py`) stay out of scope; closes issue #121 (superseding the `gui/src` portion of #116/#118) | Done | [architecture.md §5.17](roadmaps/architecture.md#517-file-size-limit-enforcement-500-loc) |
| A.22 | **[Arch] ✅ Split the 3 deferred `gui/src/` giants (2,505–5,035 LoC) into packages** — `settings_window.py` (11 files; required decomposing its ~1,113-line `__init__` into `_build_*_section()` helpers before a mixin split was possible), `extractor_tab.py` (16 files; crash-history-sensitive lazy `QMediaPlayer`/`QAudioOutput`/`QGraphicsVideoItem` construction and `cancel_loading()` teardown ordering moved verbatim per `.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`), `stitch_tab.py` (21 files; decomposed along its 8 pre-existing sub-tab features plus ~1,200 lines of standalone node-graph/match-editor/thumbnail-picker classes, with `_build_stitch_panel`/`_stats_build_recommendations` kept whole as documented over-limit exceptions) → package directories via Option B; extends the MRO-shadowing fix to `AbstractClassSingleGallery` and 13-mixin compositions; closes issue #122 | Done | [architecture.md §5.17](roadmaps/architecture.md#517-file-size-limit-enforcement-500-loc) |
| A.23 | **[Arch] ✅ CI-enforced LoC gate & auto-generated report** — `--max-code-lines 500 --fail-over` enforcement mode in `count_loc.py`, grandfathered exceptions list `docs/loc_exceptions.txt`, `--markdown-out docs/loc_report.md`, `just check-loc` / `just loc-report` recipes, and unit tests (§5.17 Options A+D, issue #126) | Done | [architecture.md §5.17](roadmaps/architecture.md#517-file-size-limit-enforcement-500-loc) |

**Dependency order:** A.1–A.7 are independent Quick Wins (batch in one PR each). A.8 depends on A.4 (`__all__` first). A.9 is independent. A.13 → A.14 (exception hierarchy makes error boundary meaningful). A.11 + A.12 can be done together (settings facade sprint). A.16 depends on A.7. A.18 + A.19 are independent DRY prerequisites; A.20 is independent of both but benefits from A.18's module graph for post-split verification. A.21 follows the same pattern as A.20, applied to `gui/src/`. A.22 follows the same pattern as A.21, applied to the 3 files A.21 explicitly deferred.

---

## Phase 6 — Long-term Research (Months, Exploratory)

Aspirational improvements requiring significant experimentation, external data, or architectural investment. No fixed timeline.

| # | Item | Effort | Roadmap Link |
|---|------|--------|--------------|
| 6.1 | **[ASP] ⚠ Online DRL agent for ECC/registration** — wire `rlhf_trainer.py` into Stage 8. **Note (2026-07-27):** `rlhf_trainer.py` no longer exists in the codebase — deleted in the S200 trim along with the rest of the reward-model/RLHF apparatus. This item would need a from-scratch RLHF foundation before it is actionable. Not on the current `the ASP submodule's moon/ROADMAP.md` roadmap. | [Long-term] | [the ASP submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md) |
| 6.2 | **[ASP] RANSAC/MAGSAC++ pre-filter for >40% outlier datasets** | [Research] | [the ASP submodule's moon/ROADMAP.md §1.1](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#11-bundle-adjustment-hardening) |
| 6.3 | **[ASP] ⚠ ToonCrafter fill for overlap ghost reduction** — final-quality mode. **Note (2026-07-27):** the ToonCrafter seam-synthesis wiring this item extends (previously shipped, formerly "ML.4") was itself removed in the S200 trim — no `anim_fill`/`ASP_TOONCRAFTER_SEAM`/`_generate_canonical_cel` code remains in `backend/src/animation/`. This item would need the wiring rebuilt first. Not on the current `the ASP submodule's moon/ROADMAP.md` roadmap. | [Research] | [the ASP submodule's moon/ROADMAP.md](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md) |
| 6.4 | **[ASP] Background histogram matching via CLAHE** for complex dark scenes | [Research] | [the ASP submodule's moon/ROADMAP.md §1.4](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#14-gain-clamp-widening-for-dark-scenes) |
| 6.5 | **[Feat] AnimeCLIP domain-specific CLIP fine-tune** — swap into §5.1 once validated | [Research] | [new_features.md §4.3](roadmaps/new_features.md#43-clip-based-semantic-image-search) |
| 6.6 | **[Feat] File system watcher auto-stitch** — `watchdog`/`inotify` triggered batch | [Research] | [new_features.md §4.1](roadmaps/new_features.md#41-batch-stitching) |
| 6.7 | **[Feat] Mobile remote wallpaper + push notifications** — depends on §5.6 REST API | [Exploratory] | [new_features.md §4.5](roadmaps/new_features.md#45-multi-monitor-wallpaper-support) |
| 6.8 | **[Arch] Hypothesis property-based tests for bundle_adjust and compositing** | [Research] | [architecture.md §5.1](roadmaps/architecture.md#51-asp-pipeline-unit-test-coverage) |
| 6.9 | **[Perf] CUDA seam DP via PyTorch scatter/gather** — GPU seam computation | [Research] | [the ASP submodule's moon/ROADMAP.md §1.5](https://github.com/ACFHarbinger/Anime-Stitch-Pipeline/blob/main/moon/ROADMAP.md#15-stage-11-composite-performance) |
| 6.10 | **[Arch] Full mypy strict coverage** — all modules under `disallow_untyped_defs = true`; end state of §5.5 gradual migration | [Long-term] | [architecture.md §5.5](roadmaps/architecture.md#55-gradual-static-type-safety-migration) |

---

## Master Effort × Impact Matrix

Cross-roadmap overview. Items are the top-priority pending work from each sub-roadmap, classified by effort and expected impact.

*Effort* — **Low**: < 1 day · **Medium**: 1 day – 1 week · **High**: 1 – 2 weeks · **Very High**: 2+ weeks, research, or data-gated
*Impact* — **Low**: marginal · **Medium**: noticeable targeted improvement · **High**: major capability or quality gain across multiple users/tests · **Very High**: architectural unlock or differentiating feature

| **Effort ↓ / Impact →** | Low | Medium | High | Very High |
|---|---|---|---|---|
| **Low (<1d)** | [GUI] ✅ §2.10 toast · ✅ §2.14 overlay | [GUI] §2.7A progress bar · [Feat] §4.11A inline RLHF rating | [GUI] §2.3A+C keyboard nav · [ASP] §2.5 coverage map · §2.6 crop assistant · §3.15A SemanticStitch column filter | [ASP] §10A2 click-based SAM-2 refinement |
| **Medium (1d–1w)** | [Arch] ✅ §5.4B pipeline trace JSON | [GUI] §2.8A dark/light theme | [ASP] §1.10B Bayesian param search · §2.9 BigWarp fallback · §3.3 DINOv2 submodular · §3.13 ProPainter · §3.15B OBJ-GSP mesh · §10A3 NL seam routing · §10B1 COCO serializer · [Arch] ✅ §5.8A ModelWrapper ABC · [Feat] §4.3A CLIP semantic search · [CG] §1.3 LyCORIS · §2.1A AnimateDiff | [ASP] §9A PyAV video ingestion · §10A1 Grounded SAM-2 |
| **High (1–2w)** | — | [ASP] §3.12 Overmix sub-pixel · §3.16A StabStitch++ | [ASP] §2.10 SAM2Flow · §3.2 ConvGRU flow · §3.6 ToonCrafter seam · §3.14B horizontal-strip composite · [Arch] §5.3B abstract Matcher interface · [Perf] §3.2A GPU CUDA median render · [CG] §1.4B native ControlNet/IP-Adapter | [ASP] §9C Hybrid 4K/1080p composite |
| **Very High (2w+ / data-gated)** | — | — | [ASP] §3.7 UDIS++ diffusion seam · [CG] §3.x video→LoRA full pipeline · [Arch] §5.5C Rust AES-256-GCM vault | [ASP] §10C1 SAM-2 anime fine-tune · §10C2 Pose contrastive · §10C3 PPO optimization · [CG] §2.3 Wan2.1/SVD foundation video |

---

## Dependency Graph Summary

```mermaid
flowchart TD
    %% ── TYPE classes (node fill = element type) ─────────────────────────────
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef fix         fill:#dc2626,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef perf        fill:#ea580c,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef security    fill:#7f1d1d,color:#fff
    classDef refactor    fill:#0f766e,color:#fff
    classDef migration   fill:#4338ca,color:#fff
    classDef testing     fill:#a16207,color:#fff
    classDef docs        fill:#15803d,color:#fff
    classDef integration fill:#9d174d,color:#fff
    %% ── STATUS classes (node border = implementation status) ─────────────────
    classDef done        stroke:#16a34a,stroke-width:4px
    classDef active      stroke:#d97706,stroke-width:4px
    classDef planned     stroke:#64748b,stroke-width:2px
    classDef blocked     stroke:#dc2626,stroke-width:3px
    classDef hold        stroke:#9333ea,stroke-width:3px

    P0["Phase 0/ML\nASP Pipeline\n(superseded — see the ASP submodule's moon/ROADMAP.md)"]:::fix:::done
    PML["the ASP submodule's moon/ROADMAP.md\nCurrent ASP Roadmap\n(active, S222)"]:::research:::active
    PCG["Phase CG\nContent Generation"]:::feature:::planned
    P1["Phase 1\nImmediate Wins"]:::augment:::active
    P2["Phase 2\nCore QoS"]:::augment:::planned
    P3["Phase 3\nFeature Enrichment"]:::feature:::planned
    P4["Phase 4\nPlatform Hardening"]:::infra:::planned
    PARCH["Phase Arch\nCode Quality"]:::refactor:::planned
    P5["Phase 5\nAdvanced Features"]:::feature:::planned
    P6["Phase 6\nLong-term Research"]:::research:::planned
    PEXT["Phase EXT\nBrowser Extension"]:::integration:::planned

    P0  ==>  PML
    P0  -->  P1
    P1  ==>  P2
    P2  -->  P3
    P2  -->  P4
    P2  -->  PARCH
    P3  -->  P5
    P4  -->  P5
    PARCH --- P3
    PARCH --- P4
    P5  -->  P6
    P1  -->  PCG
    PML -->  P3

    P4  -->|"4.5 OpenAPI + 4.6 phash\nunblock EXT.5/EXT.6"| PEXT
    PEXT -->|"EXT.8 similarity\nneeds 5.1 CLIP index"| P5

    %% key item-level dependencies
    P3 -->|"3.13 tests\nunblocks 3.14 CI"| P4
    P4 -->|"4.2 ModelWrapper\nunblocks A.9"| PARCH
    P2 -->|"2.5 quality gate\nunblocks 5.7 RLHF"| P5
```

---

## Advanced Feature Roadmap

### Overview

This roadmap defines the feature evolution and quality-of-life improvements for the Image-Toolkit ecosystem. It is grounded in a deep audit of the current codebase (May 2026) and covers every layer of the stack.

The application follows a **Tri-Interface Strategy**:
1. **PySide6 Desktop App** — The heavyweight native powerhouse for local ML inference, deep OS integration, and interactive image pipeline control.
2. **React / Tauri Web App** — The cross-platform, network-ready hub for library management, remote task dispatch, and device syncing.
3. **Android / iOS Mobile Apps** — Companion clients for remote monitoring, on-device preview, and library browsing.

Each item is tagged by priority: **[CRITICAL]**, **[HIGH]**, **[MEDIUM]**, or **[LOW]**.

---

### 1. PySide6 Desktop Application (The Pro Environment)

#### A. Advanced ML UI & Interactive Pipelines

##### [CRITICAL] SD3 ControlNet & IP-Adapter Support
`backend/src/models/sd3_wrapper.py:62` has a `TODO` for ControlNet. Switch the pipeline to `StableDiffusion3ControlNetPipeline` when a ControlNet model path is provided. In `DDMGenerateTab`, add a ControlNet image drop-zone, conditioning scale slider, and preprocessor selector (Canny, Depth, OpenPose). Separately, add IP-Adapter support via `diffusers`' `IPAdapterMixin` for reference-image conditioning — expose a reference image input and weight slider. Both unblock character-consistency and pose-guided workflows on the SD3 backbone.

##### [CRITICAL] Complete CLI Dispatcher Commands
`backend/dispatcher.py` has three disconnected dispatch paths: merge (line 56), database (line 91), and model (line 95) all either print a placeholder or are unreachable. Wire all three so the app is fully scriptable from the command line. The `--recursive` flag for batch conversion (line 46) also needs to be forwarded to `ImageFormatConverter.convert_batch()`.

##### [HIGH] Dynamic ComfyUI Dashboard
Build a native PySide6 dynamic form generator that parses `workflow_api.json` templates (like the 7-stage Illustrious XL pipeline in `backend/config/inference/sdxl_comfyui.yaml`) and auto-generates UI controls — sliders, dropdowns, seed spinboxes, and node-selection widgets — mapped to `parameters.json` keys. The `ComfyGenerateTab` currently requires hand-editing raw JSON; this replaces it with a generated form that calls the ComfyUI API transparently. Add a template browser to save, load, and share workflow presets.

##### [HIGH] Panorama Stitch UI (`StitchTab`)
Create a dedicated `StitchTab` using `QGraphicsView` to expose `stitch_net.py` and `loftr_wrapper.py` interactively. Users should be able to load two or more frames, preview LoFTR keypoint matches as an overlay, drag alignment anchors to correct stitching errors before rendering, preview the "Master-Cel" masking boundaries from `anime_stitch_pipeline.py`, and export stitched panoramas at up to 4× source resolution via `base.core.merge_images_*`. Queue batch stitch jobs and monitor them via the existing `QThreadPool` worker pattern.

##### [HIGH] Interactive Background Removal (BiRefNet Integration)
Integrate `birefnet_wrapper.py` into the `ConvertTab` as an optional post-processing step. After format conversion, a "Remove Background" toggle passes each output image through BiRefNet. Add an interactive mask-refinement widget using QPainter brush strokes to correct matting errors before saving. Output alpha channel as transparent PNG. Run as a `QRunnable` to keep the main thread free.

##### [HIGH] Full Fine-Tune UI Tab (`FullFTTrainTab`)
`backend/src/models/full_finetune.py` exists but has no dedicated GUI tab. Add a `FullFTTrainTab` with dataset path, gradient checkpointing toggle, batch size, mixed precision selector, and DeepSpeed ZeRO stage selector. The `LoRATrainTab` partially covers this; full fine-tuning of SDXL/Flux needs its own surface.

##### [HIGH] Flux Dev Generation Tab
`backend/config/model/flux_dev.yaml` is configured but there is no dedicated generation tab for `FLUX.1-dev`. Extend the `DDMGenerateTab` model selector to include Flux, routing to a `FluxPipeline` backend path. Expose its unique CFG-free distilled guidance scale and step count parameters as first-class controls, not buried in an advanced JSON field.

##### [MEDIUM] DreamBooth Prior Preservation Training
`backend/config/training/dreambooth.yaml` exists but prior preservation loss is not surfaced in `LoRATrainTab`. Add a "DreamBooth Mode" toggle that unlocks a class images directory selector, prior loss weight slider, and num-class-images field. Wire these into `DreamBoothTuner.train()`.

##### [MEDIUM] Multi-GPU Training via Accelerate
Current training runs on a single device. Add Accelerate config generation into training tabs. When multiple CUDA devices are detected, expose a device-selection multi-check and auto-write an `accelerate_config.yaml`. Pass `--multi_gpu` to the training pipeline. Essential for multi-stage LoRA training on the 3090 Ti alongside other CUDA workloads.

##### [MEDIUM] R3GAN Evaluate Tab — Live Loss Curve Visualization
`r3gan_evaluate_tab.py` only shows scalar metrics. Embed a `pyqtgraph` line chart that reads from `training_hooks.py` diagnostics and plots discriminator loss, generator loss, and FID over epochs in real time during training.

##### [MEDIUM] LyCORIS / DoRA Method Selector
`lora_diffusion.py` supports LoCon, LoHa, LoKr, DoRA, and rsLoRA via PEFT but the `LoRATrainTab` only exposes a fraction of these. Add a method selector dropdown that surfaces all available PEFT methods with a brief description tooltip. Show the relevant method-specific hyperparameters (e.g., LoCon convolution dimension) only when that method is active.

##### [LOW] Video Wallpaper with mpv
Expand `WallpaperTab` to support video wallpapers. On Linux, manage an `mpv` subprocess alongside the existing `qdbus-qt6` D-Bus wallpaper daemon. On Windows, use the existing COM pathway. Add seamless-loop detection and per-monitor assignment. Use subprocess-based mpv (not libmpv) to avoid native C++ library conflicts with the JPype JVM.

##### [LOW] Training Run History Browser
Add a training history panel to `TrainTab` that reads checkpoint directories and surfaces: model name, architecture, dataset path, epoch count, final loss values, and sample generation grid. Let users resume a past run, compare metrics across runs, or delete old checkpoints with a single click.

---

#### B. OS Integration & Media Handling

##### [HIGH] Hardware-Accelerated Frame Extraction
Replace `cv2.VideoCapture` in the `ImageExtractorTab` and `task_extract_frames()` with a C++ FFmpeg binding. Extend `base/src/core/convert.cpp` with `extract_frames()` using `libavcodec`/`libavformat` for hardware-decode support (NVDEC, VAAPI). Expose via pybind11 as `base.core.extract_frames(path, output_dir, start_ms, end_ms, fps_limit, hw_device)`. This will be dramatically faster than OpenCV for high-resolution H.264/H.265 sources.

##### [HIGH] Video Converter — Quality & Codec Controls
`base/src/core/convert.cpp`'s `convert_video()` uses a subprocess to ffmpeg. Build it out with CRF/bitrate selection, hardware encode (NVENC, VAAPI), audio track control (copy / re-encode / strip), and a full container format matrix (mp4, mkv, webm, mov). Surface all options in a `VideoConvertTab` alongside the existing image conversion workflow.

##### [MEDIUM] System Tray Integration & Daemon Mode
Add a `QSystemTrayIcon` so the desktop app runs in the background while the slideshow daemon and wallpaper rotation are active. The tray menu should expose: pause/resume slideshow, add wallpaper folder, open main window, and quit. The slideshow daemon (`base/src/utils/slideshow.cpp`) already runs as a background thread — the tray is the missing control surface.

##### [MEDIUM] Drag-and-Drop Desktop Integration
Enable OS-level drag-and-drop targets for all conversion, merge, and extraction tabs. Accept `text/uri-list` and `application/x-qabstractitemmodeldatalist` mime types so users can drag files directly from a file manager into gallery panels, bypassing the directory picker entirely.

##### [MEDIUM] Batch Rename with Pattern Templates
Add a `RenameTab` or toolbar action that applies pattern-based renames to selected files. Support tokens: `{index}`, `{date}`, `{resolution}`, `{group}`, `{tag}`, `{hash}`. Preview the rename mapping in a before/after table before committing. Support undo via the edit recipe system.

##### [LOW] macOS Wallpaper Support
Add a macOS variant for wallpaper setting using `NSWorkspace.setDesktopImageURL(_:for:options:)` via a small Swift helper binary. Guard it behind `sys.platform == "darwin"` in `backend/src/core/wallpaper.py`.

---

#### C. Gallery & Image Management QoL

##### [HIGH] Non-Destructive Edit Recipes
Implement an edit-history JSON format for color grade, crop, and resize. Rather than overwriting source pixels, store a `recipe.json` sidecar per image listing ordered operations with parameters. Apply the recipe chain in memory on open. "Bake" to disk only on explicit export (`Ctrl+E`). Support recipe sharing by exporting the JSON. Requires a `RecipeEngine` class in the backend and a `RecipeEditor` panel in `ConvertTab`.

##### [HIGH] Intelligent Duplicate Grouping with Visual Diff
Enhance `DuplicateFinder` to present near-duplicate collisions side-by-side:
- Pixel-level diff heatmap via OpenCV `absdiff()`.
- File metadata comparison (size, resolution, format, date) alongside the diff.
- Batch resolution actions: "Keep Largest", "Keep Newest", "Keep All Non-Watermarked" (using BiRefNet to detect watermark regions).
- Wire into the existing `PropertyComparisonDialog` component in `gui/src/components/`.

##### [HIGH] Global Keyboard Shortcuts & Command Palette
Add a command palette (`Ctrl+K`) with fuzzy-searchable access to all tab actions. Implement `QShortcut` bindings:
- `Ctrl+O` — Open directory picker in active tab.
- `Ctrl+Enter` — Run the active tab's primary action.
- `Ctrl+Z` / `Ctrl+Shift+Z` — Undo/Redo for edit recipes.
- `Space` — Toggle full-screen preview.
- `Delete` — Delete selected items with confirmation.
- `Ctrl+F` — Focus the search field.

##### [HIGH] Session State Persistence
Tab state (input paths, parameters, selected files) is lost on restart. Add a `SessionManager` that serializes all tab state to JSON on `QApplication.aboutToQuit` and restores it on launch. Include a configurable MRU list (last 10 paths) per tab.

##### [HIGH] Gallery Multi-Select with Batch Actions Toolbar
When multiple images are selected: show a floating action toolbar with Convert, Delete, Add to Group, and Export Captions actions. Add rubber-band marquee selection (click-drag), `Ctrl+A` to select all, `Ctrl+Shift+A` to invert selection.

##### [MEDIUM] Configurable Thumbnail Size Slider
Add a thumbnail size slider (64px → 512px) in the gallery toolbar that dynamically resizes thumbnails without reloading from disk. The `LRUImageCache` stores full `QImage` — use `QPixmap.fromImage().scaled()` at render time for instant resize.

##### [MEDIUM] Image Preview Enhancements
Expand `image_preview_window.py` to support pan and zoom (mouse wheel + drag), side-by-side A/B comparison mode (original vs. processed), EXIF/XMP metadata panel toggle, copy-to-clipboard shortcut, and "Open in external editor" action.

##### [MEDIUM] Unified Progress Overlay
Replace per-tab progress widgets with a unified bottom-anchored `ProgressOverlay` panel showing: a progress bar per active operation with label, ETA, and cancel button; a badge count on each tab's header showing pending/running operations; a notification bell for completions.

##### [MEDIUM] Dark/Light Theme Toggle
Add a theme toggle in `SettingsWindow`. Implement `dark.qss` and `light.qss` stylesheets applied via `QApplication.setStyleSheet()`. Persist the choice in the config file. Default to the system color scheme via `QGuiApplication.palette()`.

##### [LOW] LRU Cache Size Configurability
`gui/src/utils/lru_image_cache.py` hardcodes cache sizes (found=300, selected=200, single=300). Expose these in `SettingsWindow` with a memory usage readout in the status bar. Users with limited RAM can reduce; users with 32GB+ can increase for snappier gallery navigation.

##### [LOW] Onboarding & First-Launch Wizard
A `FirstLaunchWizard` dialog that guides new users through: setting the local source path, testing the PostgreSQL connection, unlocking VaultManager credentials, and selecting the default wallpaper folder.

---

### 2. React / Tauri Web Application (The Cross-Platform Hub)

#### A. Real-Time Network Architecture

##### [CRITICAL] Django Channels / WebSocket Live Progress
Upgrade the REST-only API to include WebSocket endpoints via Django Channels. Define a `TaskProgressConsumer` that forwards Celery progress events to the browser. Add a React `useTaskProgress(taskId)` hook that drives a live progress bar, ETA display, and stdout log stream for all long-running operations — batch conversion, crawling, training.

##### [HIGH] Virtualized Media Galleries
All gallery queries currently load entire result sets into the DOM. Implement `@tanstack/react-virtual` as the scroll engine for `WallpaperGallery` and every search result list. Fetch paginated slices from Django (page size 100), pre-fetch the next page on scroll, and dispose offscreen tiles. Essential for 100,000+ image libraries.

##### [HIGH] Missing API Endpoints
Several backend capabilities have no REST surface at all. Add:
- `GET /api/status/<task_id>/` — Celery task progress polling.
- `DELETE /api/tasks/<task_id>/` — Celery task cancellation.
- `GET /api/db/groups/` — List all groups and subgroups.
- `GET /api/db/search/` — Semantic vector search with query, filters, and pagination.
- `GET /api/db/stats/` — Image count, group count, vector coverage.
- `POST /api/db/embed/` — Trigger CLIP embedding for a given group or directory.
- `POST /api/train-lora/` — LoRA training task (only GAN training is wired today).
- `POST /api/run-birefnet/` — Batch background removal.
- `POST /api/stitch/` — Panorama stitching pipeline.

##### [HIGH] Saved Search Presets & History
Add a `SavedSearch` model and endpoints (`POST /api/search/presets/`, `GET /api/search/presets/`). In the React `SearchTab`, render a sidebar of saved searches that can be re-run or edited. Store the last 50 searches in `localStorage` as a quick-access history.

##### [MEDIUM] Batch Operation Pipeline Builder
Add a workflow-style drag-and-drop pipeline composer in the React frontend. Users build a sequence of operations (Crawl → Convert → Embed → Tag) into a named pipeline, then trigger it as a Celery `chain()`. Add a `POST /api/pipeline/` endpoint. The Celery primitive already supports chaining; the frontend just needs the composition UI.

##### [MEDIUM] LAN Remote Access Mode (mDNS)
Register the service as `_imagetoolkit._tcp.local` using the `zeroconf` Python library. Bind Django to `0.0.0.0` with token authentication. Display the LAN URL and QR code in the desktop app's `SettingsWindow` so mobile clients can connect without manual IP configuration.

##### [LOW] Progressive Web App (PWA) Manifest
Add a `manifest.json` and service worker to the React frontend so the web app can be installed as a PWA on desktop and Android Chrome. Cache the app shell and static assets, and implement a background-sync queue for offline task submission that drains when the connection restores.

---

#### B. UI & UX QoL

##### [HIGH] Dark Mode & Theme System
Add CSS custom properties (design tokens) for colors, spacing, and typography. Implement `prefers-color-scheme` auto-detection and a manual toggle stored in `localStorage`. All components should reference token variables rather than hardcoded hex values.

##### [HIGH] Virtual Album Browser
Add a "Virtual Albums" section to the `DatabaseTab` backed by live HNSW vector queries. Users type a natural language query (e.g., *"cyberpunk cityscapes at night with rain"*) and save it as a named album. The album auto-refreshes on a configurable schedule and shows a live image count badge. Render albums as a special group type distinct from manually curated groups.

##### [MEDIUM] Image Detail Panel (Slide-In)
When clicking any image in a gallery, slide in a detail panel (rather than a separate page) showing: full-size preview, EXIF metadata, tags, group membership, vector embedding visualization (a 2D UMAP projection of the image's neighbors), edit recipe history, and quick actions (Delete, Convert, Add to Group).

##### [MEDIUM] Keyboard Navigation Mode
Add a `useHotkeys` hook via `react-hotkeys-hook` replicating the desktop keyboard shortcuts in the web frontend. Arrow keys to navigate gallery, `Enter` to open detail panel, `Delete` to remove, `Space` to preview full-screen. Essential for power users managing large libraries from the browser.

##### [LOW] Localization (i18n) Foundation
Add `react-i18next` and extract all user-visible strings into `en.json` translation files. Structure the codebase so adding a new language requires only a new JSON file. Prioritize the Convert, Search, and Database tabs first.

---

### 3. Core Engine & AI Enhancements (C++ / Python Base)

#### A. Next-Generation AI Tagging & Search

##### [HIGH] VLM Auto-Tagging Pipeline
`backend/src/models/data/captioner.py` exists — build a full `VLMCaptioner` class on top of it backed by `Moondream2` or `LLaVA-1.5-7B-GGUF` (via `llama-cpp-python` for CPU / `transformers` for GPU). Run captioning as a background `QRunnable` after images are added to the database. Store captions in a new `captions` column. Surface captions as searchable metadata in `SearchTab` and as auto-populated tags in `DatabaseTab`. Add a "Re-caption All" batch task in `ScanMetadataTab`.

##### [HIGH] Smart Semantic Albums
Implement dynamic virtual albums backed by live `pgvector` HNSW queries. A `VirtualAlbum` table stores a natural-language query string, threshold, and cached member list. The `SearchTab` gains a "Save as Album" button. Albums auto-refresh on a configurable schedule (hourly or on new image ingestion). Pairs with the React Virtual Album Browser feature above.

##### [HIGH] HNSW Index Migration
Transition all `pgvector` `vector` columns from `ivfflat` to `hnsw` index type. This reduces similarity search latency from seconds to milliseconds at 100k+ image scale. Requires a new Django migration that drops the existing IVFFlat index and creates the HNSW index with `(m=16, ef_construction=64)`. Update `image_database.py` to set `hnsw.ef_search = 100` per query.

##### [MEDIUM] Perceptual Hash Completion
`task_scan_duplicates()` in `tasks/tasks.py` returns an empty `{}` placeholder for perceptual hash mode. Implement the full pipeline: compute pHash/dHash via `base.core.find_similar_images_phash()` (which already has exact hash support), build a hamming distance matrix, and cluster images with distance ≤ threshold. Return grouped clusters, not a flat list.

##### [MEDIUM] CLIP Ensemble Search
Support multiple CLIP variants (OpenAI ViT-L/14, MetaCLIP ViT-H/14, SigLIP) stored as separate `vector` columns. Let users select the embedding model at search time, or enable an ensemble mode that averages cosine distances across all available models. Store the model identifier per embedding row so the database supports heterogeneous embedding sources.

##### [LOW] Hybrid Text + Vector Search
Add a `tsvector` GIN index over the captions and tags columns. Extend `SearchTab` to support hybrid search: cosine similarity from the vector column merged with `ts_rank` full-text relevance. This covers keyword-based search for users who don't have an embedding query in mind.

---

#### B. Database Performance & Indexing

##### [HIGH] Asynchronous Bulk Ingestion
Refactor `image_database.py` batch insertion to use `psycopg2.extras.execute_values()` with a single round-trip instead of per-row inserts. For very large directories (50,000+ images), add a `COPY FROM STDIN` path using `psycopg2.copy_expert`. Current single-insert path takes ~0.3s per 100 images; bulk should achieve < 0.05s per 100.

##### [MEDIUM] Incremental Embedding — Skip Already-Embedded Images
Add an `is_embedded` boolean column to the images table. During embedding passes, `SELECT ... WHERE is_embedded = FALSE`, process in batches, and flip the flag on success. This makes repeated scans of large libraries O(new images) rather than O(all images).

##### [MEDIUM] SafeTensors Model Inspector
`backend/src/utils/safetensors_metadata.py:80` has a silent `pass` in its metadata parsing. Complete the implementation to read LoRA rank, alpha, target modules, and trigger words from safetensors headers. Surface this as a model inspector panel in `MetaCLIPInferenceTab` and `LoRAGenerateTab` — users should be able to inspect a trained model's metadata without loading it into VRAM.

---

#### C. C++ Base Core Optimizations

##### [HIGH] Streaming Image Processing
`base/src/core/merger.cpp` and `convert.cpp` load full OpenCV `cv::Mat` buffers before processing. The benchmark shows a 734MB peak for thumbnail generation. Refactor both to tile-based streaming: process output canvas rows in chunks using `cv::imencode` to write directly to disk. Target ≤ 200MB peak RAM for a 1,000-image batch at 1080p.

##### [HIGH] Async HTTP Crawler in C++
`base/src/web/image_crawler.cpp` is a stub (Selenium-dependent). Add thread-pool-based HTTP crawling using cpp-httplib with configurable concurrency for direct-URL jobs. Reserve Python Selenium only for JS-rendered pages. This should improve direct-URL crawl throughput by ~10× and reduce WebDriver resource usage significantly.

##### [MEDIUM] Additional Image Board Crawlers
Extend the `base/src/web/board_crawler.cpp` framework with new platform crawlers: Twitter/X media downloads, ArtStation gallery scraper, Pixiv (with OAuth), and Pinterest board downloader. Each should subclass the `Crawler` interface and be selectable from the `ImageCrawlerTab` board-type dropdown.

##### [MEDIUM] Parallel Web Crawler Progress Reporting
The current crawlers run as opaque blocking operations with no mid-crawl feedback. Add a progress callback using a `std::function<void(const std::string&, size_t, const std::string&)>` callback parameter in `base/src/web/board_crawler.cpp` that emits per-download events (URL, file size, local path) back to Python via pybind11, so the `ImageCrawlerTab` progress bar reflects real-time download count rather than a spinner.

---

### 4. Quality of Life & Utilities

##### [HIGH] Non-Destructive Edit Recipes *(Desktop)*
*(See Section 1C — full description there.)*

##### [HIGH] Intelligent Duplicate Grouping with Visual Diff *(Desktop + Web)*
*(See Section 1C — full description there.)*

##### [HIGH] Safetensors Model Inspector *(Desktop)*
Standalone tool accessible from any training or generation tab: drop a `.safetensors` file to inspect LoRA rank, alpha, trigger words, and base model compatibility. Show a preview generation using the loaded LoRA at 3 different strength values (0.5, 0.75, 1.0) side-by-side.

---

## Cross-Roadmap Overview

*Big-picture status and dependency graph across all 9 roadmaps. Node fill = roadmap type; node border = current implementation status. Edges show inter-roadmap dependencies and complementary relationships.*

```mermaid
flowchart TD
    %% ── TYPE classes (node fill = element type) ─────────────────────────────
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef fix         fill:#dc2626,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef perf        fill:#ea580c,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef security    fill:#7f1d1d,color:#fff
    classDef refactor    fill:#0f766e,color:#fff
    classDef migration   fill:#4338ca,color:#fff
    classDef testing     fill:#a16207,color:#fff
    classDef docs        fill:#15803d,color:#fff
    classDef integration fill:#9d174d,color:#fff
    %% ── STATUS classes (node border = implementation status) ─────────────────
    classDef done        stroke:#16a34a,stroke-width:4px
    classDef active      stroke:#d97706,stroke-width:4px
    classDef planned     stroke:#64748b,stroke-width:2px
    classDef blocked     stroke:#dc2626,stroke-width:3px
    classDef hold        stroke:#9333ea,stroke-width:3px

    %% ── CORE PIPELINE ────────────────────────────────────────────────────────
    subgraph CORE["Core Pipeline"]
        ASP["🎬 ASP Roadmap\n(§1–§4 shipped;\nrefinements active)"]:::feature:::active
        CPP["⚡ ASP C++ Migration\n(Phases 1–6 complete;\narchived)"]:::migration:::done
        PERF["🚀 Performance\n(§3.10–§3.15 done;\n§3.1–§3.7 planned)"]:::perf:::active
    end

    %% ── INTELLIGENCE ─────────────────────────────────────────────────────────
    subgraph INTEL["Intelligence"]
        ANALYTICS["📊 Analytics &\nInterpretability\n(in progress)"]:::research:::active
        CONTENT["🎨 Content Generation\n(planned)"]:::feature:::planned
    end

    %% ── PLATFORM ─────────────────────────────────────────────────────────────
    subgraph PLATFORM["Platform"]
        ARCH["🏗️ Architecture\n(§5.x planned;\nrefactors queued)"]:::refactor:::planned
        GUI["🖥️ GUI / UX\n(§2.1–§2.31 done;\n§2.29–§2.31 recent)"]:::feature:::done
        NEWF["✨ New Features\n(§4.1–§4.13 planned)"]:::feature:::planned
    end

    %% ── FOUNDATIONS ──────────────────────────────────────────────────────────
    subgraph FOUND["Foundations"]
        DOCS["📝 Documentation\n(§6.1–§6.14 done;\n§6.15 active)"]:::docs:::active
    end

    %% ── INTER-ROADMAP DEPENDENCIES ───────────────────────────────────────────
    ASP --> CPP
    CPP --> PERF
    ASP --> ANALYTICS
    ASP --> CONTENT
    PERF --> ASP
    ARCH --> GUI
    ARCH --> PERF
    NEWF --> ASP
    DOCS --- ASP
    DOCS --- ARCH
    DOCS --- GUI
    DOCS --- ANALYTICS
```

---

## Diagram Visual Language Reference

*Every `## Implementation Timeline` diagram in `docs/moon/roadmaps/` uses the visual encoding defined here. Read this section to interpret any diagram, and follow it when updating or adding nodes.*

---

### Node Fill — Element Type

The node's **body color** identifies the category of work.

| Fill | Class | Type | Description |
|---|---|---|---|
| Blue `#2563eb` | `feature` | **New Feature** | A capability that did not previously exist |
| Violet `#7c3aed` | `augment` | **Augmentation** | Extends or improves an existing feature without replacing it |
| Red `#dc2626` | `fix` | **Bug Fix** | Corrects incorrect or broken behaviour |
| Cyan `#0891b2` | `infra` | **Infrastructure** | Build system, CI/CD, tooling, or project foundations |
| Orange `#ea580c` | `perf` | **Performance** | Optimises speed, memory, throughput, or latency |
| Slate `#475569` | `research` | **Research** | Exploratory; outcome uncertain; may not ship |
| Dark red `#7f1d1d` | `security` | **Security** | Hardens against vulnerabilities, audits, or compliance |
| Teal `#0f766e` | `refactor` | **Refactor** | Restructures internals without changing external behaviour |
| Indigo `#4338ca` | `migration` | **Migration** | Moves from one technology, format, or system to another |
| Amber-dark `#a16207` | `testing` | **Testing** | Test coverage additions or test infrastructure improvements |
| Dark green `#15803d` | `docs` | **Documentation** | Documentation-only work (no code change) |
| Pink `#9d174d` | `integration` | **Integration** | Connects to an external system, API, or third-party service |

---

### Node Border — Implementation Status

The node's **border color and thickness** show where the item currently stands.

| Border | Class | Status | Meaning |
|---|---|---|---|
| Thick green `#16a34a, 4px` | `done` | **✅ Complete** | Shipped and merged; no further action needed |
| Thick amber `#d97706, 4px` | `active` | **🔄 In Progress** | Actively being worked on right now |
| Thin slate `#64748b, 2px` | `planned` | **⬜ Planned** | Scoped and intended, but not yet started |
| Thick red `#dc2626, 3px` | `blocked` | **🚫 Blocked** | Cannot proceed — waiting on an unresolved external dependency |
| Medium purple `#9333ea, 3px` | `hold` | **⏸ On Hold** | Paused intentionally; may resume but not actively scheduled |

To update a node when its status changes: replace the second class suffix —
`:::planned` → `:::active` → `:::done`  (or `:::blocked` / `:::hold` as needed).

---

### Edge Style — Relationship Type

| Style | Syntax | Relationship | When to use |
|---|---|---|---|
| Bold thick arrow | `==>` | **Critical dependency** | Blocking prerequisite on the critical path; B cannot start without A |
| Solid thin arrow | `-->` | **Depends on** | A must be done before B, but B is not on the critical path |
| Dashed arrow | `-.->` | **Alternative to** | A and B solve the same problem differently — only one should be chosen |
| No arrowhead | `---` | **Complements** | A and B work well together but neither requires the other |
| Circle end | `--o` | **Optional dependency** | B can optionally use A, but does not require it |
| Cross end | `--x` | **Conflicts with** | A and B are mutually exclusive or A blocks B from shipping |
| Bidirectional | `<-->` | **Tightly coupled** | A and B must evolve together; changes to one require changes to the other |

Labels can be added to any edge for additional specificity: `A -->|"reason"| B`.

---

### Standard classDef Block

Copy this block verbatim into every `flowchart` diagram. Do not rename the classes — consistency across roadmaps lets readers build a shared mental model.

```
    %% ── TYPE classes (node fill = element type) ─────────────────────────────
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef fix         fill:#dc2626,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef perf        fill:#ea580c,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef security    fill:#7f1d1d,color:#fff
    classDef refactor    fill:#0f766e,color:#fff
    classDef migration   fill:#4338ca,color:#fff
    classDef testing     fill:#a16207,color:#fff
    classDef docs        fill:#15803d,color:#fff
    classDef integration fill:#9d174d,color:#fff
    %% ── STATUS classes (node border = implementation status) ─────────────────
    classDef done        stroke:#16a34a,stroke-width:4px
    classDef active      stroke:#d97706,stroke-width:4px
    classDef planned     stroke:#64748b,stroke-width:2px
    classDef blocked     stroke:#dc2626,stroke-width:3px
    classDef hold        stroke:#9333ea,stroke-width:3px
```

Apply both classes to every node: `NodeID["Label"]:::typeClass:::statusClass`

---

### Example Diagram

The diagram below demonstrates every element type, every status, and every edge relationship in a single coherent graph representing a hypothetical auth-platform development sequence.

```mermaid
flowchart TD
    %% ── TYPE classes (node fill = element type) ─────────────────────────────
    classDef feature     fill:#2563eb,color:#fff
    classDef augment     fill:#7c3aed,color:#fff
    classDef fix         fill:#dc2626,color:#fff
    classDef infra       fill:#0891b2,color:#fff
    classDef perf        fill:#ea580c,color:#fff
    classDef research    fill:#475569,color:#fff
    classDef security    fill:#7f1d1d,color:#fff
    classDef refactor    fill:#0f766e,color:#fff
    classDef migration   fill:#4338ca,color:#fff
    classDef testing     fill:#a16207,color:#fff
    classDef docs        fill:#15803d,color:#fff
    classDef integration fill:#9d174d,color:#fff
    %% ── STATUS classes (node border = implementation status) ─────────────────
    classDef done        stroke:#16a34a,stroke-width:4px
    classDef active      stroke:#d97706,stroke-width:4px
    classDef planned     stroke:#64748b,stroke-width:2px
    classDef blocked     stroke:#dc2626,stroke-width:3px
    classDef hold        stroke:#9333ea,stroke-width:3px

    %% ── ✅ COMPLETE nodes (thick green border) ───────────────────────────────
    REQ["🔬 Requirements\nAnalysis"]:::research:::done
    THREAT["🔒 Threat Model\n& Audit"]:::security:::done
    DB["🏗 Database\nSchema v1"]:::infra:::done
    AUTH["✨ Auth Module\n(JWT / Session)"]:::feature:::done
    CACHE["⚡ Response\nCaching Layer"]:::perf:::done
    UNIT["🧪 Unit\nTest Suite"]:::testing:::done
    DOC1["📄 API Reference\nDocs"]:::docs:::done
    REFACT["♻ Auth Code\nRefactor"]:::refactor:::done

    %% ── 🔄 IN PROGRESS nodes (thick amber border) ────────────────────────────
    MIG["🔄 Schema v1→v2\nMigration"]:::migration:::active
    RATELIM["🔧 Rate\nLimiting"]:::augment:::active
    INTTEST["🧪 Integration\nTest Suite"]:::testing:::active

    %% ── 🚫 BLOCKED nodes (thick red border) ─────────────────────────────────
    GDPR["🔒 GDPR\nCompliance Audit"]:::security:::blocked

    %% ── ⏸ ON HOLD nodes (medium purple border) ──────────────────────────────
    SDK["🔌 Mobile\nSDK Client"]:::integration:::hold

    %% ── ⬜ PLANNED nodes (thin slate border) ─────────────────────────────────
    OAUTH2["✨ OAuth2\nProvider Support"]:::feature:::planned
    WEBHOOK["🔌 Webhook\nIntegration"]:::integration:::planned
    TOKENFIX["🐛 Token Refresh\nRace Condition"]:::fix:::planned
    GUIDE["📄 User Guide\n& Tutorials"]:::docs:::planned
    PERF2["⚡ Query\nOptimisation"]:::perf:::planned

    %% ── EDGES — all seven relationship types ─────────────────────────────────
    REQ    ==>         AUTH          %% ==>  critical dependency (research gates feature)
    THREAT ==>         AUTH          %% ==>  critical dependency (threat model gates auth)
    DB     ==>         AUTH          %% ==>  critical dependency (schema gates auth)
    AUTH    -->        OAUTH2         %% -->  depends on
    AUTH    -->        REFACT         %% -->  depends on
    REFACT  -->        UNIT           %% -->  depends on
    AUTH    -->        CACHE          %% -->  depends on
    AUTH    -->        DOC1           %% -->  depends on
    DB      -->        MIG            %% -->  depends on
    MIG     -->        PERF2          %% -->  depends on
    DOC1    -->        GUIDE          %% -->  depends on
    SDK     -->        WEBHOOK        %% -->  depends on
    CACHE   ---        RATELIM        %% ---  complements (both protect the API surface)
    UNIT   <-->        INTTEST        %% <--> tightly coupled (suites co-evolve)
    OAUTH2  -.->       WEBHOOK        %% -.-> alternative (OAuth push vs webhook pull)
    TOKENFIX --x       OAUTH2         %% --x  conflicts with (race condition blocks OAuth)
    GDPR    --o        OAUTH2         %% --o  optional dependency (GDPR may gate OAuth)

    %% ── LEGEND — status borders ──────────────────────────────────────────────
    subgraph SLEG["Status — Border Color + Width"]
        direction LR
        SL1["✅ Complete"]:::feature:::done
        SL2["🔄 In Progress"]:::feature:::active
        SL3["⬜ Planned"]:::feature:::planned
        SL4["🚫 Blocked"]:::feature:::blocked
        SL5["⏸ On Hold"]:::feature:::hold
    end

    %% ── LEGEND — element type fills ─────────────────────────────────────────
    subgraph TLEG["Type — Node Fill Color"]
        direction LR
        TL1["New Feature"]:::feature:::done
        TL2["Augmentation"]:::augment:::done
        TL3["Bug Fix"]:::fix:::done
        TL4["Infrastructure"]:::infra:::done
        TL5["Performance"]:::perf:::done
        TL6["Research"]:::research:::done
        TL7["Security"]:::security:::done
        TL8["Refactor"]:::refactor:::done
        TL9["Migration"]:::migration:::done
        TL10["Testing"]:::testing:::done
        TL11["Docs"]:::docs:::done
        TL12["Integration"]:::integration:::done
    end

    %% ── LEGEND — edge relationships ──────────────────────────────────────────
    subgraph ELEG["Edge — Relationship Type"]
        direction TB
        EA["A"]:::infra:::done ==>|"critical dep"| EB["B"]:::infra:::done
        EC["C"]:::infra:::done  -->|"depends on"|   ED["D"]:::infra:::done
        EE["E"]:::infra:::done -.->|"alternative"|  EF["F"]:::infra:::done
        EG["G"]:::infra:::done ---|"complements"|   EH["H"]:::infra:::done
        EI["I"]:::infra:::done --o|"optional dep"|  EJ["J"]:::infra:::done
        EK["K"]:::infra:::done --x|"conflicts"|     EL["L"]:::infra:::done
        EM["M"]:::infra:::done <-->|"bidirectional"| EN["N"]:::infra:::done
    end
```

*Created: 2026-06-23. Update the classDef block in any diagram by copying the Standard classDef Block above verbatim.*

##### [HIGH] Batch Rename with Pattern Templates
Add a rename tool (tab or toolbar action) that applies pattern-based renames to selected files. Support tokens: `{index}`, `{date}`, `{resolution}`, `{group}`, `{tag}`, `{hash}`. Preview the rename mapping in a before/after table before committing. Support undo via the edit recipe system.

##### [MEDIUM] Quick-Convert Context Menu in Gallery
Right-clicking any image in any gallery should show a context menu with "Quick Convert To…" sub-items (PNG, JPEG, WebP, AVIF). Each item immediately fires a single-file conversion without opening the `ConvertTab`. The output lands in the same directory with a user-configurable suffix.

##### [MEDIUM] Aspect Ratio Crop Assistant
Add a crop-to-ratio helper in `ConvertTab` that lets users specify a target aspect ratio (e.g., 16:9, 1:1, 3:4, SDXL 1024×1024) and shows a crop preview overlay on the source image. The crop anchor (top-center, center, face-detect) is selectable. Face-detection crop uses the existing Siamese network's face-embed pipeline.

##### [MEDIUM] Image Metadata Batch Editor
Add a metadata editor tab that can write EXIF/XMP fields (title, description, keywords, copyright, GPS) to a batch of selected images. Support "copy metadata from one image to many" for quick-tagging datasets. Wire into the `ScanMetadataTab` workflow.

##### [MEDIUM] Color Palette Extractor
Add a palette extraction feature accessible from image preview and `SearchTab`. Extract the N dominant colors from an image using k-means (backed by the C++ core, exposed as `base.core.extract_palette()`). Show swatches with hex values and copy-to-clipboard. Add "Search by Color" functionality that encodes the dominant palette into a query vector for pgvector similarity search.

##### [MEDIUM] Slideshow Queue Editor
The `SlideshowWindow` and `slideshow.cpp` daemon exist but queue management is basic. Add a queue editor panel with drag-to-reorder, per-image duration overrides, transition type selector (fade, cut, slide), and a "play from here" action on any item.

##### [LOW] Export Dataset Manifest
From `DatabaseTab`, add an "Export Dataset" action that writes a JSONL or CSV manifest of all images in a group or subgroup, including paths, tags, captions, and embedding norms. This feeds directly into `lora_dataset.py` and external training tools without manual file organization.

##### [LOW] Image Statistics Dashboard
A stats tab or panel showing library-wide metrics: total image count, format breakdown, resolution distribution histogram, tag frequency chart, last-crawled timestamps per source, and VRAM/RAM usage by the active model. Pull data from `GET /api/db/stats/` and render with `pyqtgraph` (desktop) or Recharts (web).
