# library.management

Create and remove groups, subgroups, and tags, plus tag merge, through `library_admin.mutate` on the injected store. Rename and tag category use the same method. Nothing opens `~/.image-toolkit/library.db` unless a session handle was already open.

PARITY-GAP library.management: vacuum, reindex, reset, embed backfill, JSON tag import, auto-populate from folders, statistics, and the legacy PostgreSQL connection form are absent.
