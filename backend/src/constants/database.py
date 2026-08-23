import re
from typing import Dict

COLLECTION_NAME = "listings"
DENSE_DIM = 1024  # BGE-M3 dense output dimension

# --- from backend/src/database/unified/entity_repo.py ---
_COLUMN_KEYS = {'id': 'id', 'name': 'name', 'first_name': 'first_name', 'last_name': 'last_name', 'type': 'type', 'role': 'role', 'rating': 'rating', 'year': 'year', 'notes': 'notes', 'image_path': 'image_path', 'date_added': 'date_added'}
_RELATION_KEYS = {'credit_list', 'associated_content', 'associated_entities'}
_CREDIT_FIELDS = ('title', 'role', 'year', 'rating', 'notes', 'image_path', 'web_link')
_SELECT_COLUMNS = ('id', 'name', 'first_name', 'last_name', 'type', 'role', 'rating', 'year', 'notes', 'image_path', 'date_added', 'extra')

# --- from backend/src/database/unified/search_repo.py ---
_IMAGE_SELECT = 'SELECT DISTINCT i.id, i.file_path, i.filename, i.file_size, i.width, i.height, i.phash, g.name AS group_name, s.name AS subgroup_name, i.date_added, i.date_modified FROM images i LEFT JOIN groups g ON g.id = i.group_id LEFT JOIN subgroups s ON s.id = i.subgroup_id '
_IMAGE_COLUMNS = ('id', 'file_path', 'filename', 'file_size', 'width', 'height', 'phash', 'group_name', 'subgroup_name', 'date_added', 'date_modified')
_ENTITY_SORT_SQL: Dict[str, str] = {'name': "LOWER(COALESCE(e.name, ''))", 'rating': 'COALESCE(e.rating, 0)', 'type': "LOWER(COALESCE(e.type, ''))", 'role': "LOWER(COALESCE(e.role, ''))", 'date_added': "COALESCE(e.date_added, '')", 'credits_count': '(SELECT COUNT(*) FROM credits c WHERE c.entity_id = e.id)'}

# --- from backend/src/database/unified/tag_categories.py ---
DEFAULT_TAG_CATEGORIES = [('General', '#95a5a6', 0, 'universal'), ('Artist', '#5865f2', 1, 'universal'), ('Copyright', '#f1c40f', 2, 'universal'), ('Character', '#2ecc71', 3, 'universal'), ('Meta', '#9b59b6', 4, 'universal'), ('Genre', '#e91e63', 5, 'listing'), ('Medium', '#3498db', 6, 'listing'), ('Studio', '#8e44ad', 7, 'listing'), ('Setting', '#16a085', 8, 'listing'), ('Content Warning', '#c0392b', 9, 'listing'), ('Release Status', '#7f8c8d', 10, 'listing'), ('Appearance', '#1abc9c', 11, 'entity'), ('Occupation', '#e67e22', 12, 'entity'), ('Biographical', '#d35400', 13, 'entity'), ('Organization', '#2980b9', 14, 'entity')]
LEGACY_CATEGORY_ALIASES = {'Series': 'Copyright'}

# --- from backend/src/database/unified/browser_repo.py ---
_BANNED_WHERE_PATTERN = re.compile(';|\\b(INSERT|UPDATE|DELETE|DROP|ALTER|ATTACH|PRAGMA|CREATE|REPLACE)\\b', re.IGNORECASE)

# --- from backend/src/database/unified/media_repo.py ---
UNIFIED__COLUMN_KEYS = {'id': 'id', 'title': 'title', 'type': 'type', 'status': 'status', 'personal_rating': 'personal_rating', 'community_rating': 'community_rating', 'year': 'year', 'episodes': 'episodes_total', 'current_episode': 'current_episode', 'creator': 'creator', 'review': 'review', 'web_link': 'web_link', 'local_file': 'local_file', 'image_path': 'image_path', 'date_added': 'date_added', 'date_watched': 'date_watched'}
UNIFIED__RELATION_KEYS = {'genres', 'tags', 'associated_entities', 'episode_list'}
_EPISODE_FIELDS = ('number', 'title', 'date_watched', 'rating', 'review', 'image_path', 'local_file', 'web_link')
UNIFIED__SELECT_COLUMNS = ('id', 'title', 'type', 'status', 'personal_rating', 'community_rating', 'year', 'episodes_total', 'current_episode', 'creator', 'review', 'web_link', 'local_file', 'image_path', 'date_added', 'date_watched', 'extra')

# --- from backend/src/database/unified/image_repo.py ---
UNIFIED__IMAGE_COLUMNS = ('id', 'file_path', 'filename', 'file_size', 'width', 'height', 'phash', 'group_id', 'subgroup_id', 'date_added', 'date_modified')
_SELECT_IMAGE = 'SELECT i.id, i.file_path, i.filename, i.file_size, i.width, i.height, i.phash, i.group_id, i.subgroup_id, i.date_added, i.date_modified, g.name AS group_name, s.name AS subgroup_name FROM images i LEFT JOIN groups g ON g.id = i.group_id LEFT JOIN subgroups s ON s.id = i.subgroup_id '

# --- from backend/src/database/unified/session.py ---
SCHEMA_VERSION = 1

# --- from backend/src/database/unified/_util.py ---
_TAG_BUCKET_CLAUSE = {'Genre': "c.name = 'Genre'", 'Tag': "(c.name IS NULL OR (c.name != 'Genre' AND c.name != 'Copyright'))"}
