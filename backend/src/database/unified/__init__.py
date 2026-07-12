"""Unified Library Database DAL (Phase DB, DB.3).

Repository layer over the ``base.database.Database`` session-keyed SQLCipher
engine. Both tab families (Listings subtabs and the image tabs) consume this
package; no GUI file touches SQL directly.

Usage::

    from backend.src.database.unified import session
    db = session.open_session(password, salt)      # at login, KDF runs once
    from backend.src.database.unified.media_repo import MediaRepo
    MediaRepo(db).save_media(entry_dict)

See moon/roadmaps/unified_database.md §DB.3 and
docs/database/unified_schema.md for the schema contract.
"""

from . import session  # noqa: F401
