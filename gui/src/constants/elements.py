"""Constants relocated from backend/src or gui/src modules under this subpackage (module-level ALL_CAPS assignments)."""

import re
from pathlib import Path
from typing import Dict

from PySide6.QtGui import QColor, QPen

# --- from gui/src/elements/web/media_loader_tab/_ui_builder.py ---
SOURCE_REDDIT = 0

# --- from gui/src/elements/core/image_extractor_subtab.py ---
SUPPORTED_IMAGE_FILTER = 'Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.tif);;All Files (*)'
_MIN_SCALE = 0.01
_MAX_SCALE = 80.0

# --- from gui/src/elements/core/wallpaper_tab/system_display_subtab/_video_duration.py ---
_VIDEO_DURATION_CACHE: Dict[str, float] = {}

# --- from gui/src/elements/core/wallpaper_tab/system_display_subtab/_ui_builder.py ---
_GROUP_BOX_STYLE = '\n    QGroupBox {\n        border: 1px solid #4f545c;\n        border-radius: 8px;\n        margin-top: 10px;\n    }\n    QGroupBox::title {\n        subcontrol-origin: margin;\n        subcontrol-position: top left;\n        padding: 4px 10px;\n        color: white;\n        border-radius: 4px;\n    }\n'

# --- from gui/src/elements/core/similarity_tab/_ui_builder.py ---
_SHARED_BUTTON_STYLE = '\n    QPushButton {\n        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #667eea, stop:1 #764ba2);\n        color: white; font-weight: bold; font-size: 14px;\n        padding: 14px 8px; border-radius: 10px; min-height: 44px;\n    }\n    QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #764ba2, stop:1 #667eea); }\n    QPushButton:disabled { background: #718096; }\n    QPushButton:pressed { background: #5a67d8; }\n'

# --- from gui/src/elements/database/series_listings_subtab/_gallery.py ---
_SORT_KEY_MAP = {'Sort by: Title': 'title', 'Sort by: Rating': 'rating', 'Sort by: Episodes': 'episodes', 'Sort by: Current Episode': 'current_episode', 'Sort by: Date': 'date', 'Sort by: Type': 'type', 'Sort by: Status': 'status', 'Sort by: Local Filename': 'local_file', 'Sort by: Tags': 'tags'}

# --- from gui/src/elements/database/database_tab/_connection_stats.py ---
EMBED_MODEL = 'openclip'

# --- from gui/src/elements/database/database_tab/_ui_groups.py ---
_TABLE_STYLE = '\n    QTableWidget {\n        background-color: #36393f;\n        border: 1px solid #4f545c;\n        alternate-background-color: #3b3e44;\n    }\n    QHeaderView::section {\n        background-color: #4f545c;\n        color: white;\n        padding: 4px;\n        border: 1px solid #36393f;\n    }\n'

# --- from gui/src/elements/database/entity_listings_subtab/_gallery.py ---
ENTITY_LISTINGS_SUBTAB__SORT_KEY_MAP = {'Sort by: Name': 'name', 'Sort by: Rating': 'rating', 'Sort by: Type': 'type', 'Sort by: Role': 'role', 'Sort by: Date Added': 'date_added', 'Sort by: Credits Count': 'credits_count'}

# --- from gui/src/elements/database/scan_metadata_tab/_auto_listings.py ---
_WORD_RE = re.compile('[a-z0-9]+')

# --- from gui/src/elements/database/search_tab/_ui_builder.py ---
_SEARCH_BUTTON_STYLE = '\n    QPushButton {\n        background: qlineargradient(x1:0, y1:0, x2:0, y2:1,\n            stop:0 #667eea, stop:1 #764ba2);\n        color: white; font-weight: bold; font-size: 16px;\n        padding: 14px; border-radius: 10px; min-height: 44px;\n    }\n    QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:0, y2:1,\n        stop:0 #764ba2, stop:1 #667eea); }\n    QPushButton:disabled { background: #4f545c; color: #a0a0a0; }\n    QPushButton:pressed { background: #5a67d8; }\n'

# --- from gui/src/elements/database/data_browser_tab/_er_view.py ---
_CARD_WIDTH = 200
_ROW_HEIGHT = 18
_TITLE_HEIGHT = 26
_CARD_MARGIN_X = 60
_CARD_MARGIN_Y = 40
_BUCKET_ORDER = ('media', 'image', 'shared', 'search', 'other')
_BUCKET_LABELS = {'media': 'Media / Entity domain', 'image': 'Image domain', 'shared': 'Shared vocabulary', 'search': 'Search infrastructure', 'other': 'Other'}
_BUCKET_TABLES = {'media': {'media_items', 'episodes', 'entities', 'credits', 'media_entity', 'entity_entity'}, 'image': {'groups', 'subgroups', 'images'}, 'shared': {'tags', 'image_tags', 'media_tags', 'media_groups', 'entity_images'}, 'search': {'embeddings', 'vector_index', 'media_fts', 'entity_fts', 'image_fts'}}

# --- from gui/src/elements/database/data_browser_tab/_navigation.py ---
_FK_CELL_COLOR = QColor('#5dade2')

# --- from gui/src/elements/animation/stitch_tab/dialog/landmark_editor_dialog.py ---
_THUMB_W = 480
_THUMB_H = 360
_MARKER_R = 6
_COLORS = [QColor(255, 80, 80), QColor(80, 200, 80), QColor(80, 150, 255), QColor(255, 200, 50), QColor(230, 80, 230), QColor(80, 220, 220)]

# --- from gui/src/elements/animation/stitch_tab/dialog/mask_review_dialog.py ---
_OVERLAY_ALPHA = 0.4
_POSITIVE_COLOR = (0, 255, 0)
_NEGATIVE_COLOR = (0, 0, 255)
_CLICK_RADIUS = 6
_MAX_DISPLAY_H = 540

# --- from gui/src/elements/animation/stitch_tab/dialog/seam_painter_dialog.py ---
_MAX_PREVIEW_W = 520
_MAX_PREVIEW_H = 720
_PAINT_COLOR = QColor(255, 60, 60, 160)
_DEFAULT_BRUSH_PX = 18

# --- from gui/src/elements/animation/stitch_tab/dialog/final_output_review_dialog.py ---
_PREVIEW_MAX_PX = 640

# --- from gui/src/elements/animation/stitch_tab/dialog/hitl_session_viewer_dialog.py ---
_DEFAULT_SESSION_DIR = Path.home() / '.config' / 'image-toolkit' / 'hitl_sessions'
_CHECKPOINT_LABELS = {'frames': 'Frame selection', 'masks': 'Mask / segmentation', 'edges': 'Edge graph', 'canvas': 'Canvas layout', 'boundaries': 'Seam boundaries', 'composite': 'Post-composite paint', 'render': 'Render review', 'output': 'Final output RLHF', 'video': 'Video frame review'}

# --- from gui/src/elements/animation/stitch_tab/dialog/selection_review_dialog.py ---
_CARD_W = 160
_CARD_H = 120
_DIFF_BAR_H = 8
_DIFF_HIGH = 0.15

# --- from gui/src/elements/animation/stitch_tab/dialog/coverage_heatmap_dialog.py ---
DIALOG__MAX_PREVIEW_H = 600
_BAR_W = 200

# --- from gui/src/elements/animation/stitch_tab/dialog/boundary_editor_dialog.py ---
DIALOG__MAX_PREVIEW_W = 480
DIALOG_BOUNDARY_EDITOR_DIALOG__MAX_PREVIEW_H = 700
_LINE_COLOR = QColor(255, 80, 80)
_LABEL_COLOR = QColor(255, 220, 60)

# --- from gui/src/elements/animation/stitch_tab/dialog/canvas_inspector_dialog.py ---
_FRAME_COLORS = [QColor(100, 149, 237, 110), QColor(100, 220, 130, 110), QColor(255, 165, 0, 110), QColor(210, 100, 210, 110), QColor(255, 215, 0, 110), QColor(32, 178, 170, 110), QColor(255, 99, 71, 110), QColor(173, 216, 230, 110)]
_HIGHLIGHT_PEN = QPen(QColor(255, 220, 50), 3)
_NORMAL_PEN_ALPHA = 180

# --- from gui/src/elements/animation/stitch_tab/dialog/edge_review_dialog.py ---
_RADIUS = 200.0
_CENTRE = 230.0
_NODE_R = 18
_CONF_HIGH = QColor(80, 200, 80)
_CONF_MED = QColor(200, 200, 80)
_CONF_LOW = QColor(220, 80, 80)
_CONF_DIS = QColor(90, 90, 90)
_CONF_MANUAL = QColor(160, 100, 255)
