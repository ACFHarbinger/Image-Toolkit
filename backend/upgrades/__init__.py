"""One-off upgrade scripts for existing library databases.

Unlike :mod:`backend.migrations` (the ordered ``000``\u2013``004`` Phase DB
sequence), these are independent, idempotent maintenance upgrades run on
demand against an already-migrated ``library.db``.
"""
