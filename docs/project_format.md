# Portable project and learning data format

Cel-Shaded-Generator projects are ordinary, movable directories. The source of
truth is `project.json`; artwork and redline files are relative assets beside
it. An application-managed index may make projects searchable later, but it
must always be rebuildable and is never authoritative.

The Krita alpha binds a newly created project directory as follows:

```text
my-head-practice/
├── project.json
├── artwork/
│   └── attempt-001.kra
└── .recovery/
    └── project.1.json
```

`document_asset` points to the active `artwork/attempt-001.kra` using a safe
project-relative path. This active document is not artwork *history* and does
not enable historical artwork retention. The creator refuses unrelated files
or an existing manifest rather than merging into an ambiguous directory.

Schema version 3 separates three concerns:

- project identity, user-selected autosave policy, and privacy consent;
- project-local exercises, attempts, feedback, and metrics, which travel with
  the artwork;
- an optional global learner profile stored outside project folders, containing
  only cross-project aggregates and contributing project identifiers.

Artwork paths in attempt history and feedback redlines are rejected unless the
project explicitly enables artwork-history retention. Contribution to the
global profile is independently opt-in and defaults off.
Project-local learning-progress retention is a visible user setting enabled by
default for learning projects. Disabling it requires the project to contain no
exercise history; an application must therefore offer an explicit purge before
turning retention off rather than claiming that retained data disappeared.

Each attempt may contain privacy-safe review records: stable review and method
versions, rubric identity/version, numeric measurements, explanations, and one
`pending`, `accepted`, or `rejected` suggestion decision. Redline geometry,
preview-layer metadata, and pixels are intentionally not copied into the
manifest. Decisions are final after acceptance/rejection and repeated identical
actions are idempotent. Review identifiers must be unique within an attempt.
Each review may also contain one final artist rating (`helpful`, `unhelpful`,
`incorrect`, or `not_applicable`) and an optional non-empty free-text note.
Ratings and notes stay in the portable project and an identical retry is
idempotent; replacing an existing report is refused so history cannot change
silently.
The local engine creates the manifest after Krita saves the initial document,
then atomically appends review records and decisions to the matching stable
attempt identifier; each changed save rotates the bounded recovery history.

Writes use a temporary file in the destination directory, flush it to disk,
then atomically replace the manifest. Autosave defaults to ten recoverable
manifest revisions under `.recovery/`; users may change the bound or disable
autosave. Binary asset versioning will be added with the drawing-document
integration and should use content-addressed or copy-on-write storage rather
than duplicating large files for every manifest snapshot.

Readers reject unknown schema versions. The pre-release version-0 manifest and
version-1 and version-2 project formats have explicit deterministic migrations
to version 3; they preserve existing progress, add empty review/feedback fields
where required, and enable project-local progress for manifests that already
contained it. Version-1 learner
profiles migrate without inventing aggregate data. Every future version must
likewise add a tested migration before it becomes writable; opening a newer
version with older software never rewrites or downgrades it.
