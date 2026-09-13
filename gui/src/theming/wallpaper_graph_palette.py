"""Paint palette for wallpaper sequence graph nodes and edges (#564)."""

from __future__ import annotations

from gui.src.theming.theme_api import color

# Default end-screen color persisted in graph JSON
GRAPH_END_COLOR_DEFAULT = color("window_bg")

# Node hover (drag-connect preview)
NODE_HOVER_ORANGE_BG = "#e67e22"
NODE_HOVER_ORANGE_BORDER = "#d35400"

# Role: basis (start node)
NODE_BASIS_BG_SEL = "#2d3b1e"
NODE_BASIS_BG = "#2a3520"
NODE_BASIS_BORDER_SEL = "#ffeaa7"
NODE_BASIS_BORDER = "#f1c40f"
NODE_BASIS_BADGE_BG = "#f1c40f"
NODE_BASIS_BADGE_TEXT = "#1a1a00"

# Role: sink (end node)
NODE_SINK_BG_SEL = "#3b1a2d"
NODE_SINK_BG = "#2e1a2b"
NODE_SINK_BORDER_SEL = "#ff7eb3"
NODE_SINK_BORDER = "#e056b8"
NODE_SINK_BADGE_BG = "#e056b8"
NODE_SINK_BADGE_TEXT = "#1a001a"

# Role: unreachable
NODE_UNREACHABLE_BG_SEL = "#3a2020"
NODE_UNREACHABLE_BG = "#2e2020"
NODE_UNREACHABLE_BORDER_SEL = "#ff7675"
NODE_UNREACHABLE_BORDER = "#7f4040"
NODE_UNREACHABLE_BADGE_BG = "#7f4040"
NODE_UNREACHABLE_BADGE_TEXT = "#ffcccc"

# Role: reachable (default step)
NODE_STEP_BG_SEL = "#1a2b3c"
NODE_STEP_BG = "#131c26"
NODE_STEP_BORDER_SEL = "#00ffff"
NODE_STEP_BORDER = color("accent")
NODE_STEP_BADGE_BG = color("accent")
NODE_STEP_BADGE_TEXT = "#001a33"

# Thumbnail placeholder
NODE_THUMB_PLACEHOLDER_BG = color("surface")
NODE_THUMB_PLACEHOLDER_ICON = color("accent")

# Edge colors
EDGE_ORANGE = "#f39c12"
EDGE_DEFAULT = color("accent")
EDGE_SELF_LOOP = "#6b2d2d"
EDGE_ARROW_BG = "#2c2f33"
EDGE_ARROW_SELF = "#1e1212"

# Scene background
GRAPH_SCENE_BG = color("surface")

# Highlight marker in scene
GRAPH_HIGHLIGHT = EDGE_ORANGE
