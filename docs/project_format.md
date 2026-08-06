# Portable project and learning data format

Cel-Shaded-Generator projects are ordinary, movable directories. The source of
truth is `project.json`; artwork and redline files are relative assets beside
it. An application-managed index may make projects searchable later, but it
must always be rebuildable and is never authoritative.

Schema version 1 separates three concerns:

- project identity, user-selected autosave policy, and privacy consent;
- project-local exercises, attempts, feedback, and metrics, which travel with
  the artwork;
- an optional global learner profile stored outside project folders, containing
  only cross-project aggregates and contributing project identifiers.

Artwork paths in attempt history and feedback redlines are rejected unless the
project explicitly enables artwork-history retention. Contribution to the
global profile is independently opt-in and defaults off.

Writes use a temporary file in the destination directory, flush it to disk,
then atomically replace the manifest. Autosave defaults to ten recoverable
manifest revisions under `.recovery/`; users may change the bound or disable
autosave. Binary asset versioning will be added with the drawing-document
integration and should use content-addressed or copy-on-write storage rather
than duplicating large files for every manifest snapshot.

Readers reject unknown schema versions. The pre-release version-0 manifest has
an explicit deterministic migration to version 1 whose defaults preserve
privacy. Every future version must likewise add a tested migration before it
becomes writable; opening a newer version with older software never rewrites or
downgrades it.
