"""Scale benchmark for SearchRepo.filter_media()/filter_entities() (roadmap
development_tool.md §12.4, issue #63 / unified_database.md §DB.5).

§12.4 was rescoped 2026-07-27 away from a pgvector HNSW/IVFFlat benchmark
(that system is retiring) toward this: the default listings gallery
filter/sort SQL methods have correctness tests
(``backend/test/database/test_unified_repos.py``) but no scale benchmark.
This file measures the real query latency of the search box, the
type/status/role combos, the Advanced Search criteria builder, and the
sort-combo ORDER BY at 10k and 100k media/entity rows, plus the FTS5 text
search path that backs ``search_media_text``/``search_entities_text``.

The filter methods evaluate the search box with ``LIKE ... COLLATE NOCASE``
plus per-row ``EXISTS`` subqueries (tags/associated entities/credits), so the
leading-wildcard search box cannot use the title/name indexes — it is a full
scan with correlated subqueries, which is exactly the scaling risk this
benchmark exists to quantify.

Data is deterministic (seeded) and bulk-inserted via ``base.database``
``executemany`` (the FTS5 external-content triggers keep the shadow tables
in sync), so the run is reproducible without a real library.

Run standalone:
    python backend/benchmark/bench_search_repo_scale.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure repo root on path so `base` C++ module and `backend` are importable.
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from backend.benchmark.managers import BenchmarkManager  # noqa: E402

try:
    import base as _base  # type: ignore[import]
    _CPP_AVAILABLE = True
except ImportError:
    _base = None  # type: ignore[assignment]
    _CPP_AVAILABLE = False

from backend.src.database.unified import session  # noqa: E402
from backend.src.database.unified.search_repo import SearchRepo  # noqa: E402

# ── Deterministic data shape ─────────────────────────────────────────────────

WORDS = ("Crimson", "Silent", "Iron", "Lunar", "Neon", "Cobalt", "Ember",
         "Frost", "Solar", "Violet")                          # 10
MEDIA_TYPES = ("Anime", "Manga", "Movie", "Book")             # 4
MEDIA_STATUS = ("Completed", "Watching", "Planned", "")       # 4
CREATORS = tuple(f"Studio {c}" for c in "ABCDEFGHIJ")         # 10
ENTITY_TYPES = ("Person", "Studio", "Organization")           # 3
ENTITY_ROLES = ("Director", "Producer", "Composer", "Actor")  # 4
GENRES = tuple(f"genre{i:03d}" for i in range(50))            # 50
TAGS = tuple(f"tag{i:03d}" for i in range(150))               # 150

SCALES = (10_000, 100_000)

# Each media item links to 2 genres + 3 tags (deduped) and 2 entities.
# Each entity carries (j % 5) credits so the credits_count sort key has
# variance. Selectivity of every benchmark case below follows deterministically
# from these cycles (e.g. "chronicle" -> 100% of titles; "anime" -> ~25%).

_TMP_DIR: tempfile.TemporaryDirectory | None = None
_REPOS: dict[int, SearchRepo] = {}
_COUNTS: dict[int, dict[str, int]] = {}


def _populate(n: int):
    """Bulk-insert a deterministic n-media / n//10-entity library."""
    db = _base.database.Database(str(Path(_TMP_DIR.name) / f"lib_{n}.db"), "pw", "salt")
    session.ensure_schema(db)

    m = max(n // 10, 1)
    genre_cat_id = db.query(
        "SELECT id FROM tag_categories WHERE name='Genre'", ()
    )[0][0]

    db.begin()
    try:
        db.executemany(
            "INSERT INTO tags (name, category_id) VALUES (?, ?)",
            [(g, genre_cat_id) for g in GENRES] + [(t, None) for t in TAGS],
        )
        tag_ids = {name: tid for tid, name in db.query("SELECT id, name FROM tags", ())}

        media_rows = []
        media_tag_rows = []
        media_entity_rows = []
        for i in range(n):
            mid = f"m{i:06d}"
            media_rows.append((
                mid,
                f"{WORDS[i % 10]} Chronicle {i:06d}",
                MEDIA_TYPES[i % 4],
                MEDIA_STATUS[i % 4],
                i % 10,                 # personal_rating
                (i % 100) / 10.0,       # community_rating
                1990 + (i % 35),        # year
                (i % 26) + 1,           # episodes_total
                i % 13,                 # current_episode
                CREATORS[i % 10],
                "", "", "", "",         # review, web_link, local_file, image_path
                "2026-07-01",
                f"2026-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                "{}",
            ))
            for name in {GENRES[i % 50], GENRES[(i // 7) % 50],
                         TAGS[i % 150], TAGS[(i // 3) % 150], TAGS[(i // 11) % 150]}:
                media_tag_rows.append((mid, tag_ids[name]))
            media_entity_rows.append((mid, f"e{i % m:06d}"))
            media_entity_rows.append((mid, f"e{(i * 7 + 3) % m:06d}"))

        db.executemany(
            "INSERT INTO media_items (id, title, type, status, personal_rating, "
            "community_rating, year, episodes_total, current_episode, creator, "
            "review, web_link, local_file, image_path, date_added, date_watched, "
            "extra) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            media_rows,
        )

        entity_rows = []
        credit_rows = []
        for j in range(m):
            eid = f"e{j:06d}"
            entity_rows.append((
                eid,
                f"{WORDS[j % 10]} {ENTITY_ROLES[j % 4]} {j:06d}",
                "", "",                    # first_name, last_name
                ENTITY_TYPES[j % 3],
                ENTITY_ROLES[j % 4],
                j % 10,                    # rating
                1960 + (j % 60),           # year
                "", "",                    # notes, image_path
                "2026-07-01",
                "{}",
            ))
            for k in range(j % 5):
                credit_rows.append((
                    f"c{j:06d}_{k}", eid,
                    f"{WORDS[(j + k) % 10]} Work",
                    ENTITY_ROLES[(j + k) % 4],
                    1980 + ((j + k) % 40),
                    (j + k) % 10,
                    "", "", "",
                ))

        db.executemany(
            "INSERT INTO entities (id, name, first_name, last_name, type, role, "
            "rating, year, notes, image_path, date_added, extra) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            entity_rows,
        )
        db.executemany(
            "INSERT INTO credits (id, entity_id, title, role, year, rating, "
            "notes, image_path, web_link) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            credit_rows,
        )
        db.executemany(
            "INSERT OR IGNORE INTO media_tags (media_item_id, tag_id) VALUES (?, ?)",
            media_tag_rows,
        )
        db.executemany(
            "INSERT OR IGNORE INTO media_entity (media_item_id, entity_id) "
            "VALUES (?, ?)",
            media_entity_rows,
        )
    except Exception:
        db.rollback()
        raise
    else:
        db.commit()

    return db


def _setup() -> None:
    global _TMP_DIR
    _TMP_DIR = tempfile.TemporaryDirectory(prefix="search_repo_bench_")
    for n in SCALES:
        db = _populate(n)
        _REPOS[n] = SearchRepo(db)
        _COUNTS[n] = {
            "media": db.query("SELECT count(*) FROM media_items", ())[0][0],
            "entities": db.query("SELECT count(*) FROM entities", ())[0][0],
            "media_tags": db.query("SELECT count(*) FROM media_tags", ())[0][0],
            "media_entity": db.query("SELECT count(*) FROM media_entity", ())[0][0],
            "credits": db.query("SELECT count(*) FROM credits", ())[0][0],
            "fts": "on" if session.fts_enabled(db) else "off",
        }


# ── Benchmark cases (search-box / combo / advanced-criteria / sort) ─────────

_MEDIA_CASES = (
    ("filter_media_no_filter", {}),
    ("filter_media_search_title", {"search_query": "chronicle"}),
    ("filter_media_search_creator", {"search_query": "studio a"}),
    ("filter_media_search_tag", {"search_query": "tag042"}),
    ("filter_media_search_entity", {"search_query": "director"}),
    ("filter_media_type", {"type_filter": "Anime"}),
    ("filter_media_status", {"status_filter": "Completed"}),
    ("filter_media_type_status", {"type_filter": "Anime", "status_filter": "Completed"}),
    ("filter_media_advanced_genres_and",
     {"advanced_criteria": {"include_genres": ["genre000", "genre001"],
                            "match_mode": "AND"}}),
    ("filter_media_advanced_exclude_entity",
     {"advanced_criteria": {"exclude_entities": ["e000000"]}}),
    ("filter_media_sort_rating_desc", {"sort_key": "rating", "descending": True}),
    ("filter_media_sort_tags", {"sort_key": "tags"}),
)

_ENTITY_CASES = (
    ("filter_entities_no_filter", {}),
    ("filter_entities_search_name", {"search_query": "director"}),
    ("filter_entities_search_content_title", {"search_query": "chronicle"}),
    ("filter_entities_type", {"type_filter": "Person"}),
    ("filter_entities_role", {"role_filter": "Director"}),
    ("filter_entities_sort_credits_count", {"sort_key": "credits_count"}),
    ("filter_entities_sort_name_desc", {"sort_key": "name", "descending": True}),
)

_FTS_CASES = (
    ("search_media_text", lambda repo: repo.search_media_text("crimson chronicle")),
    ("search_entities_text", lambda repo: repo.search_entities_text("director")),
)


def _register(name, fn):
    return runner.benchmark(name, iterations=2, warmup=1)(fn)


def _media_bench(scale, kwargs):
    def bench():
        return _REPOS[scale].filter_media(**kwargs)
    return bench


def _entity_bench(scale, kwargs):
    def bench():
        return _REPOS[scale].filter_entities(**kwargs)
    return bench


def _fts_bench(scale, fn):
    def bench():
        return fn(_REPOS[scale])
    return bench


runner = BenchmarkManager("SearchRepo filter_media / filter_entities scale")

for _scale in SCALES:
    for _label, _kwargs in _MEDIA_CASES:
        _register(f"{_label}@{_scale}", _media_bench(_scale, _kwargs))
    for _label, _kwargs in _ENTITY_CASES:
        _register(f"{_label}@{_scale}", _entity_bench(_scale, _kwargs))
    for _label, _fn in _FTS_CASES:
        _register(f"{_label}@{_scale}", _fts_bench(_scale, _fn))


def _print_data_summary() -> None:
    print("\n" + "=" * 60)
    print("Populated corpora")
    print("=" * 60)
    for n in SCALES:
        c = _COUNTS[n]
        print(
            f"  {n:>7} media  {n:>7} -> {c['media']:>7} media_items, "
            f"{c['entities']:>6} entities, {c['media_tags']:>7} media_tags, "
            f"{c['media_entity']:>7} media_entity, {c['credits']:>6} credits "
            f"(fts={c['fts']})"
        )


def _print_selectivity_check() -> None:
    print("\n" + "=" * 60)
    print("Selectivity check (expected non-zero, deterministic)")
    print("=" * 60)
    repo = _REPOS[SCALES[0]]
    print(f"  filter_media() -> {len(repo.filter_media())} rows")
    print(f"  filter_media(search_query='chronicle') -> "
          f"{len(repo.filter_media(search_query='chronicle'))} rows")
    print(f"  filter_media(search_query='tag042') -> "
          f"{len(repo.filter_media(search_query='tag042'))} rows")
    print(f"  filter_media(type_filter='Anime', status_filter='Completed') -> "
          f"{len(repo.filter_media(type_filter='Anime', status_filter='Completed'))} rows")
    print(f"  filter_media(advanced include_genres AND) -> "
          f"{len(repo.filter_media(advanced_criteria={'include_genres': ['genre000', 'genre001'], 'match_mode': 'AND'}))} rows")
    print(f"  filter_entities() -> {len(repo.filter_entities())} rows")
    print(f"  filter_entities(search_query='director') -> "
          f"{len(repo.filter_entities(search_query='director'))} rows")
    print(f"  search_media_text('crimson chronicle') -> "
          f"{len(repo.search_media_text('crimson chronicle'))} rows")


if __name__ == "__main__":
    if not _CPP_AVAILABLE:
        print("ERROR: C++ base module not available.")
        print("       Run the build_base.sh|build_base.bat C++ build script first.")
        sys.exit(1)

    _setup()
    _print_data_summary()
    _print_selectivity_check()
    try:
        runner.run()
        runner.print_results()
        runner.save_json()
    finally:
        if _TMP_DIR is not None:
            _TMP_DIR.cleanup()
