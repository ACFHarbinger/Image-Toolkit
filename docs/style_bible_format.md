# Character style-bible format

The version-1 style bible is a standalone JSON document for deterministic,
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
- zero or more artist-labelled reference views using safe relative POSIX paths;
- a bounded recovery count, defaulting to ten.

The manifest stores no pixels, embeddings, inferred identity, segmentation,
confidence, or model output. Reference images remain ordinary adjacent assets.
This keeps the bible reviewable in Git and usable by deterministic region tools,
optional local models, Blender material exporters, and eventual C++ consumers.

Writes are temporary-file, flush, fsync, and atomic-replace operations. Before
replacement, the previous valid bible rotates into `.recovery/`. Readers reject
unknown schema versions, unknown root fields, malformed colors, ambiguous
aliases, duplicate identities, and unsafe reference paths rather than guessing.

Version 1 has no legacy migration because no earlier style-bible format was
released. Every future writable version must add a deterministic migration and
retain future-version refusal.
