# Grok review — 2026-10-27

Read `.agent/bus/2026-10-26.md` and inspected the current shell, system, library, and settings deliveries with Bugbot. Shared-checkout integration is still pending; this is not a landing or native UI sign-off.

Fixed:

- Shared gallery, merge-board, and wallpaper-graph source URLs were denied by the desktop asset scope. Use bounded native PNG previews instead, reporting original dimensions for canvas fitting. The filesystem scope stays unchanged.
- Canvas placement used the source alpha as a second mask. A `(255,0,0,128)` pixel became `(128,0,0,64)`. Alpha composition preserves the original pixel.
- Canvas output could replace a source or truncate an existing destination on failed encoding. Reject source collisions and encode through an exclusive temporary sibling before replacement.
- Codec CRF zero was replaced with 28 by a truthiness default. Preserve zero.

Commits: `8a319c216`, `a544e6c66`, and the subsequent `fix(media): render scoped previews and preserve lossless quality` commit.

Validation: 4 merge-canvas Python tests, 4 media-subtab Python tests, 2 SourceImage frontend tests, and 10 merge/wallpaper frontend tests passed. TypeScript checking and Tauri security validation passed. No full suites, benchmarks, packaged builds, or live desktop checks ran.

Integration prerequisite: the shared checkout still has stale localStorage/logout behavior; `feat/redo-1-shell` already contains the live-session fixes. Bring the feature deliveries together before claiming the login/library lifecycle works in the combined shell. Other pre-existing working-tree changes remain uncommitted.
