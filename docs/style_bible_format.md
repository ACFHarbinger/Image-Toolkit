# Character style-bible format

The version-2 style bible is a standalone JSON document for deterministic,
offline character-color consistency. It is intentionally independent of Krita,
the current Python solvers, and any future C++ or ML engine.

```text
project/
├── style-bibles/
│   └── aiko-tv.json
├── references/
│   └── aiko-front.png
└── .recovery/
```

Each bible contains:

- a lowercase kebab-case identity plus human character/style names;
- one or more canonical semantic materials;
- unique human aliases resolving to exactly one canonical material;
- uppercase `#RRGGBB` sRGB local, light, and shadow colors plus an optional
  accent;
- zero or more artist-labelled reference views using safe relative POSIX paths
  and a controlled `front`, `profile`, `three-quarter`, `expression`,
  `costume-detail`, or `other` view type;
- a bounded recovery count, defaulting to ten.

The manifest stores no pixels, embeddings, inferred identity, segmentation,
confidence, or model output. Reference images remain ordinary adjacent assets.
This keeps the bible reviewable in Git and usable by deterministic region tools,
optional local models, Blender material exporters, and eventual C++ consumers.

Writes are temporary-file, flush, fsync, and atomic-replace operations. Before
replacement, the previous valid bible rotates into `.recovery/`. Readers reject
unknown schema versions, unknown root fields, malformed colors, ambiguous
aliases, duplicate identities, and unsafe reference paths rather than guessing.

Version 2 deterministically migrates version-1 references to the conservative
`other` view type; it does not infer metadata from filenames. Every future
writable version must add a deterministic migration and retain future-version
refusal.

Portable project schema v9 binds bibles through an ordered safe-relative asset
list. Binding validates the bible and referenced views in place; it does not copy
or embed them. Detaching removes only the manifest reference. This makes moving
the whole project directory sufficient to preserve the relationship.

The Character Colors Krita adapter copies external references into
`references/<sanitized-stem>-<sha256-prefix>.<ext>` using an atomic write. An
identical source is idempotent. Semantic masks live under `Material Masks` and
use `Material — <canonical-id>` names; alpha is the region definition. Palette
previews are locked layers under `Character Colors`. Preview is blocked when the
active mask overlaps another semantic mask, with conflict pixel counts shown to
the artist instead of silently resolving ambiguity by layer order. Accepting
renames the preview to `Color — <canonical-id> — <role>` and unlocks that
separate editable layer; rejecting removes it. Neither action recolors the mask
or source artwork.
