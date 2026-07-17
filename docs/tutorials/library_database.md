# Library Database — Tab Tutorials

The **Library Database** category is everything that lives in the unified encrypted library (`~/.image-toolkit/library.db`, SQLCipher): your media/entity listings, the image search index, image tagging, and store maintenance. The library opens automatically with your vault session — the same login-time key derivation unlocks it, so there is no separate password.

---

## Listings

A personal catalogue of *content* (anime, movies, shows, books, manga, games…) and *entities* (people, studios, characters…), stored encrypted. Two subtabs: **Content Listings** and **Entity Listings**. Both show a searchable card gallery on the left and a detail panel for the selected entry on the right.

### Content Listings

Each entry holds a title, type, status, ratings, year, episode counts, genres, tags, associated entities, an optional local file, a web link, a summary, and your review.

- **⚡ Gen Thumbnail** — extracts a cover image *from the entry's associated Local File*. Point the entry's Local File at a video (or a file inside the series' folder), click the button, and a representative frame is grabbed and stored as the entry's thumbnail — no manual screenshotting. (The same button exists inside the episode editor to generate per-episode thumbnails.)
- **Auto-Fill from MAL** — fetches metadata from MyAnimeList and fills the form (title, ratings, year, episode count, genres, synopsis, and — where the fetch method provides them — characters/staff matched to your entities). Only enabled while **Type = Anime**. Three fetch methods are selectable in *Settings → System and Logging → MyAnimeList Auto-Fill*: **Jikan** (default; richest data, no key, but depends on the Jikan proxy's health), **official MAL API v2** (needs a free client ID; no character/staff data), and **direct scraping** (no key, full data). Transient gateway errors (429/502/503/504) are retried automatically with backoff.
- **Tags** (and **Genres**) — free comma-separated text fields on the entry. They power the gallery's tag/genre sorting, the Advanced Search include/exclude filters, and the Recommend engine's sparse features — consistent naming pays off.
- **Associated Entities** — links the entry to Entity Listings records via **🔗 Select Entities** (a picker dialog). Links are bidirectional: the entity's own detail panel lists the content back, and the read-only display box under the field shows the currently linked names.
- **Episodes / Chapters / Parts** section — a per-entry sub-list for tracking individual episodes, chapters, or parts. **＋ Add Episode Entry** opens an editor with *Number, Title, Date, Rating, Review, Local File, Web Link* (and its own Gen Thumbnail). Saved rows are listed with a star-rating display, quick open-file/open-link buttons, and per-row edit/delete.
- **Advanced Search** — a criteria dialog (reached from the search row) with three tabs — **Entities**, **Tags**, **Genres** — each providing *Include* and *Exclude* lists. **Match Mode (Inclusions)** decides whether an entry must match **ALL** positive criteria (AND) or **ANY** of them (OR); exclusions always remove matches. Use it for queries a plain text search can't express ("everything with entity X and tag Y but not genre Z").
- **🌟 Recommend** — ranks your *own* catalogue against a query using the local recommendation engine (BGE-M3 embeddings + hybrid retrieval; fully offline). The dialog takes an optional **Type** filter, comma-separated **Genres/Tags/Entities**, and a free-text **Natural Language Prompt**; results replace the gallery, sorted by relevance score. First run embeds new entries, so it can take a moment on a fresh catalogue.

### Entity Listings

Entries for people and organizations connected to your content.

- **Type vs. Role** — two different axes:
    - **Type** is *what the entity is*: `Person`, `Organization`, `Fictional Character`, or `Other`. It drives the card's color coding and top-level filtering.
    - **Role** is *what the entity does relative to your content*: `Actor / Seiyuu`, `Director`, `Producer`, `Writer`, `Studio`, `Publisher`, `Fictional Character`, `Other`. A Type=Person can have Role=Director; a Type=Organization is typically Role=Studio or Publisher.
- **Associated Content** — links the entity to Content Listings entries (the mirror of the content side's Associated Entities). The read-only box shows linked titles and scrolls when the list is long.
- **Associated Entities** — links entities *to each other* (a character to their voice actor, a person to their studio…). Same picker-dialog pattern.

### Both subtabs

- **📂 Import Dir** — a one-shot import wizard: pick a directory of video files → the wizard groups the files into detected series (each with a checkbox) → configure shared metadata (Type, Status, Year, Genres, Tags, Creator) → confirm. Each ticked series becomes a new entry with its local file already linked; existing titles are skipped.
- **🔄 Sync Backup / ⚡ Update Backup** — the encrypted-file backup pair:
    - **Update Backup** *writes* the backup: encrypts all current entries to a `.enc` file (using your vault key) and archives every referenced image (covers, episode thumbnails) into multi-part ZIPs.
    - **Sync Backup** *reads* it: decrypts the `.enc` file and upserts its entries into the library — the recovery path after data loss or when moving to a new machine. It refuses to run if no backup file exists yet ("Use 'Update Backup' first").
    - Rule of thumb: run **Update Backup** after significant editing sessions; touch **Sync Backup** only to restore.

---

## Image Search

Queries the image index of the unified library and shows matching thumbnails. Its power is that one query can mix **database metadata** with **file-system facts**:

- **Database criteria** — **Group name** and **Subgroup name** (editable dropdowns listing what exists in the DB) and the **Tags** checkbox list: check any number of tags and results must carry them. These match what was written by Scan and Tag / Maintenance.
- **File-system criteria** — the collapsible **Filename pattern** field (glob-style patterns like `*.png` or substrings like `img_001`) and **Input formats** (toggle buttons per supported image format, with Add All / Remove All) filter by the *file's* name and extension, independent of any DB metadata.
- **Combining them** — all filled-in criteria are ANDed. Example: Group `RWBY` + tag `Grimm` + Filename pattern `*_f0*` + format `png` returns only PNGs whose path is registered under the RWBY group, tagged Grimm, whose filename matches the pattern. Leave any criterion empty to not constrain on it; an empty form returns everything.
- **Refresh Tags** — rebuilds the tag checkbox list *from the database right now*. The list is populated when the tab loads, so tags created afterwards (in Maintenance's tag section, or by another tab) don't appear until you click this. It re-reads the tag vocabulary and rebuilds the checkboxes — check states start fresh, so set your tag filters *after* refreshing.

Results support marquee selection, Ctrl+A / Ctrl+D select/deselect-all, previews, and sending selections to other tabs.

---

## Scan and Tag

Registers image files into the library and batch-edits their metadata. Workflow: choose a **Scan Directory** → thumbnails appear in the scan gallery → click images to move them into the *Selected* gallery → apply batch metadata.

- **👁️ Show Only New (Not in DB)** vs. **💾 Show Only In DB** — two toggle filters on the scan gallery (mutually exclusive in practice):
    - **Show Only New** hides every file already registered, leaving exactly the files that still need to be imported — the "what's left to catalogue" view. After you add images while this is on, they disappear from the gallery immediately.
    - **Show Only In DB** is the inverse: only files already registered — the view for *re-tagging or auditing* existing records.
    - With neither active you see everything, with in-DB images visually marked.
- **Add/Update Selected Images** (the green button) — the upsert action. The *first* click reveals the **Batch Metadata** panel; the second actually writes. For **every selected image** it writes:
    - **Group Name** / **Subgroup Name** — set to the panel's values (empty fields are stored as "no group"/"no subgroup").
    - **Tags** — the set of *checked* tags in the panel's list replaces the image's tag set.
    - For images **not yet in the DB**, a new record is created with the image's path, pixel **width/height** (probed from the file), and the metadata above.
    - For images **already in the DB**, the existing record is updated with the panel's group/subgroup/tags — the panel applies to *all* selected images alike, so batch-select only images that should share the same metadata.
- **Delete Images Data from Database** removes the *records* of the selected images (never the files themselves).

---

## Maintenance

Administration of the unified library store itself (this tab was the old "Database" tab; since Phase DB it manages the encrypted SQLCipher library).

### Unified Library buttons

- **🔓 Open Library** — opens the encrypted store using the current vault session key. Normally the library auto-opens at login; this button exists for the locked-vault edge case. A statistics banner (image/group/subgroup/tag counts, dates) confirms a healthy connection.
- **⚠️ Reset Database (Drop All Data)** — wipes all data from the store. Deliberately gated: it refuses to run unless a *verified* backup manifest exists, and asks for confirmation. Use only when you truly want a fresh library.
- **🧹 Vacuum Database** — SQLite `VACUUM`: rewrites the database file to reclaim free space after large deletions and defragment pages. Safe any time; takes a moment on large stores.
- **🔍 Reindex Database** — rebuilds SQL indexes. Useful if searches have become slow or after bulk imports; also safe any time.

### Populate Database

- **Automatic Population** — **Auto-Sync Groups and Subgroups from Source** scans your configured source directory and mirrors its folder structure: *top-level folders become Groups, second-level folders become Subgroups*. The fastest way to bootstrap a group hierarchy that matches how your files are already organized.
- **Groups vs. Subgroups** — the two-level organizational hierarchy for images: a **Group** is the broad collection (a series, a trip, an artist), a **Subgroup** is a subdivision *belonging to one group* (an arc, a location, an album). Every subgroup has a parent group; images can then be filed under group alone or group+subgroup (see Scan and Tag). The *Create Group(s)* / *Create Subgroup(s)* forms accept comma-separated names for bulk creation (subgroups additionally need the parent group picked), and the *Existing …* lists support refresh/remove.
- **Tags** — the flat, typed labels that cut across groups (`Character`, `Artist`, `Series`, `General`, `Meta` types are offered, and the type combo is editable for custom types). *Create/Update Tag(s)* accepts comma-separated names with one **Tag Type** applied to all; the *Existing Tags* list supports refresh/remove. Tags are what the Image Search tab's checkbox list and Scan and Tag's batch panel draw from.

### Bulk Tag Import from JSON

Imports a whole tag vocabulary in one go. Select a JSON file, pick the **Tag Type** to apply to every imported tag, and click **Import Tags from JSON**. Two accepted file shapes:

```json
{ "tags": ["tag one", "tag two", "tag three"] }
```

or a bare array as a fallback:

```json
["tag one", "tag two", "tag three"]
```

Anything else (objects per tag, nested structures) is rejected with a format error. Duplicate tags are updated rather than duplicated (same upsert semantics as Create/Update Tag(s)).
