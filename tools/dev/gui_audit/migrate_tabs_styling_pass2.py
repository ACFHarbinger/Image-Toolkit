#!/usr/bin/env python3
"""Second-pass migrator for remaining tab styling violations."""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def tab_paths() -> list[str]:
    out: list[str] = []
    for line in (REPO / "tools/dev/gui_audit/styling_allowlist.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line.startswith("gui/src/tabs/"):
            out.append(line)
    return out


def theme_import(rel: str) -> str:
    depth = len(rel.split("/")) - 3
    if depth <= 1:
        return "from gui.src.theming.theme_api import color, qss"
    return f"from {'.' * (depth + 1)}theming.theme_api import color, qss"


def palette_import(rel: str, module: str) -> str:
    depth = len(rel.split("/")) - 3
    return f"from {'.' * (depth + 1)}theming.{module} import *"


def insert_import(src: str, imp: str) -> str:
    if imp in src:
        return src
    lines = src.splitlines(keepends=True)
    idx = 0
    paren = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith(("from ", "import ")) or (paren > 0 and s):
            paren += line.count("(") - line.count(")")
            idx = i + 1
        elif idx and s and not s.startswith("#") and paren <= 0:
            break
    lines.insert(idx, imp + "\n")
    return "".join(lines)


def transform(rel: str, src: str) -> str:
    subs = [
        ('setStyleSheet(_TABLE_STYLE)', 'setStyleSheet(qss("table_widget"))'),
        ('setStyleSheet(_SEARCH_BUTTON_STYLE)', 'setStyleSheet(qss("search_button"))'),
        ('setStyleSheet(STYLE_START_ACTION)', 'setStyleSheet(qss("start_action_btn"))'),
        ('setStyleSheet(STYLE_STOP_ACTION)', 'setStyleSheet(qss("stop_action_btn"))'),
        ('setStyleSheet(self.multicore_checkbox.styleSheet())', 'setStyleSheet(qss("convert_checkbox"))'),
        ('setStyleSheet(tab.groups_table.styleSheet())', 'setStyleSheet(qss("table_widget"))'),
        ('setStyleSheet("font-size:18px;font-weight:bold;color:#00bcd4;")', 'setStyleSheet(qss("listings_title"))'),
        ('setStyleSheet("color:#888;font-size:11px;")', 'setStyleSheet(qss("listings_stats"))'),
        ('setStyleSheet("QScrollArea{border:1px solid #4f545c;border-radius:8px;}")', 'setStyleSheet(qss("bordered_scroll_area"))'),
        ('setStyleSheet("color: #aaa; font-style: italic; font-size: 12px;")', 'setStyleSheet(qss("registry_info"))'),
        ('setStyleSheet("font-weight: bold;")', 'setStyleSheet(qss("font_bold"))'),
        ('setStyleSheet("font-weight: bold; font-size: 14px;")', 'setStyleSheet(qss("results_title"))'),
        ('setStyleSheet("QComboBox { font-weight: bold; }")', 'setStyleSheet(qss("combo_bold"))'),
        ('setStyleSheet("QCheckBox { color: #f1c40f; }")', 'setStyleSheet(qss("drive_sync_dry_run"))'),
        ('setStyleSheet("QCheckBox { color: #f1c40f; font-weight: bold; }")', 'setStyleSheet(qss("drive_sync_dry_run_bold"))'),
        ('setStyleSheet("color: #e67e22; font-weight: bold;")', 'setStyleSheet(qss("drive_sync_section_warning"))'),
        ('setStyleSheet("color:#b9bbbe;")', 'setStyleSheet(qss("wallpaper_props_hint"))'),
        ('setStyleSheet("color:#b9bbbe; font-size:11px; padding:2px;")', 'setStyleSheet(qss("wallpaper_seq_label"))'),
        ('setStyleSheet("color:#b9bbbe; font-size:10px;")', 'setStyleSheet(qss("wallpaper_edges_hint"))'),
        ('setStyleSheet("color: #00BCD4; font-weight: bold;")', 'setStyleSheet(qss("extractor_info_label"))'),
        ('setStyleSheet("border: 1px solid #4f545c; border-radius: 4px;")', 'setStyleSheet(qss("extractor_scene_border"))'),
        ('self.solid_color_hex = "#000000"', 'self.solid_color_hex = color("window_bg")'),
        ('self._end_color_current = "#000000"', 'self._end_color_current = color("window_bg")'),
        ('getattr(target, "solid_color_hex", "#000000")', 'getattr(target, "solid_color_hex", color("window_bg"))'),
        ('config.get("solid_color_hex", "#000000")', 'config.get("solid_color_hex", color("window_bg"))'),
        ('"solid_color_hex": "#000000"', '"solid_color_hex": color("window_bg")'),
        ('color_map.get(tag_category, "#95a5a6")', 'color_map.get(tag_category, color("muted_text"))'),
        ('color_map.get(t, "#95a5a6")', 'color_map.get(t, color("muted_text"))'),
        ('tag_data.get("color") or "#95a5a6"', 'tag_data.get("color") or color("muted_text")'),
    ]
    for old, new in subs:
        src = src.replace(old, new)

    src = re.sub(
        r'from gui\.src\.constants\.elements import _TABLE_STYLE\n',
        '',
        src,
    )
    src = re.sub(
        r'from gui\.src\.constants\.elements import _SEARCH_BUTTON_STYLE\n',
        '',
        src,
    )
    src = re.sub(
        r'from \.+styles import STYLE_START_ACTION, apply_shadow_effect, set_button_role',
        'from .....styles import apply_shadow_effect, set_button_role',
        src,
    )
    src = re.sub(
        r'from \.+styles import STYLE_START_ACTION, STYLE_STOP_ACTION',
        '',
        src,
    )
    src = re.sub(
        r'from \.+styles import STYLE_START_ACTION\n',
        '',
        src,
    )

    src = re.sub(
        r'setStyleSheet\(\s*"QListWidget \{ border: 1px solid #4f545c; border-radius: 8px; \}"\s*\)',
        'setStyleSheet(qss("bordered_list_widget_lg"))',
        src,
    )
    src = re.sub(
        r'setStyleSheet\(\s*"QMenu \{ background:#2c2f33; color:white; border:1px solid #4f545c; \}"\s*"QMenu::item:selected \{ background:#00bcd4; color:black; \}"\s*\)',
        'setStyleSheet(qss("context_menu_dark"))',
        src,
    )
    src = re.sub(
        r'setStyleSheet\(\s*"QMenu \{  color: white; border: 1px solid #4f545c; \}"\s*\)',
        'setStyleSheet(qss("extractor_menu"))',
        src,
    )
    src = re.sub(
        r'setStyleSheet\(\s*"QMenu \{  color: #FFC107; \}"\s*\)',
        'setStyleSheet(qss("extractor_menu_highlight"))',
        src,
    )
    src = re.sub(
        r'label\.setStyleSheet\("border: 3px solid #2ecc71; background-color: rgba\(88, 101, 242, 0\.4\);"\)',
        'label.setStyleSheet(qss("monitor_label_ok_active"))',
        src,
    )
    src = re.sub(
        r'label\.setStyleSheet\("border: 3px solid #2ecc71; background-color: rgba\(46, 204, 113, 0\.15\);"\)',
        'label.setStyleSheet(qss("monitor_label_ok"))',
        src,
    )
    src = re.sub(
        r'self\.countdown_label\.setStyleSheet\(\s*"color: #2ecc71; font-weight: bold; font-size: 14px;"\s*\)',
        'self.countdown_label.setStyleSheet(qss("wallpaper_countdown_ok_lg"))',
        src,
    )
    src = re.sub(
        r'self\._seq_label\.setStyleSheet\(\s*"color:#f1c40f; font-weight:bold; font-size:14px;"\s*\)',
        'self._seq_label.setStyleSheet(qss("wallpaper_end_countdown"))',
        src,
    )
    src = re.sub(
        r'self\._countdown_label\.setStyleSheet\(\s*"color:#2ecc71; font-weight:bold; font-size:14px;"\s*\)',
        'self._countdown_label.setStyleSheet(qss("wallpaper_countdown_ok_lg"))',
        src,
    )
    src = re.sub(
        r'setStyleSheet\(\s*"color: #b9bbbe; font-style: italic; padding: 10px;"\s*\)',
        'setStyleSheet(qss("merge_canvas_hint"))',
        src,
    )
    src = re.sub(
        r'self\.setStyleSheet\(\s*"color: #FFC107; font-weight: bold; padding: 2px 6px; "\s*"border: 1px solid #4f545c; border-radius: 4px; "\s*\)',
        'self.setStyleSheet(qss("extractor_tag_label"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'self\.setStyleSheet\(\s*"color: #00BCD4; font-weight: bold; padding: 2px 6px; "\s*"border: 1px solid #4f545c; border-radius: 4px; "\s*\)',
        'self.setStyleSheet(qss("extractor_cut_label"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'self\.extraction_status_label\.setStyleSheet\(\s*"color: #00BCD4; font-style: italic; padding: 4px; font-weight: bold;"\s*\)',
        'self.extraction_status_label.setStyleSheet(qss("extractor_status_label"))',
        src,
    )
    src = re.sub(
        r'self\._time_edit\.setStyleSheet\(\s*"QLineEdit \{  color: #00BCD4; border: 1px solid #4f545c; border-radius: 4px; font-family: monospace; \}"\s*\)',
        'self._time_edit.setStyleSheet(qss("extractor_line_edit"))',
        src,
    )
    src = re.sub(
        r'self\.seek_progress\.setStyleSheet\(\s*"QProgressBar \{  color: #aaa; border: 1px solid #4f545c;.*?"\s*\)',
        'self.seek_progress.setStyleSheet(qss("extractor_progress_muted"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'self\._chk_multicore\.setStyleSheet\(\s*"QCheckBox::indicator \{.*?"\s*\)',
        'self._chk_multicore.setStyleSheet(qss("convert_checkbox"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'self\.resample_progress_bar\.setStyleSheet\(\s*"QProgressBar \{  color: white; border: 1px solid #4f545c;.*?"\s*\)',
        'self.resample_progress_bar.setStyleSheet(qss("convert_progress_bar"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'f"background-color:\{self\._end_color_current\}; border:1px solid #4f545c;"',
        'f"background-color:{self._end_color_current}; border:1px solid {color(\'border\')};"',
        src,
    )

    # comfy_generate_tab dynamic colors
    if rel.endswith("comfy_generate_tab.py"):
        src = src.replace('self._status_signal.emit("Starting…", "#f0ad4e")', 'self._status_signal.emit("Starting…", color("accent_hover"))')
        src = src.replace('self._status_signal.emit("Server: stopped", "#aaaaaa")', 'self._status_signal.emit("Server: stopped", color("muted_text"))')
        src = src.replace('"Timed out — check the log for errors", "#d9534f"', '"Timed out — check the log for errors", color("danger")')
        src = src.replace('self._status_signal.emit(f"Error: {exc}", "#d9534f")', 'self._status_signal.emit(f"Error: {exc}", color("danger"))')
        src = src.replace('self._status_signal.emit(f"Running at {url}", "#5cb85c")', 'self._status_signal.emit(f"Running at {url}", color("success"))')
        src = re.sub(
            r'self\._url_label\.setStyleSheet\(\s*"color: #5cb85c; font-family: monospace; font-weight: bold;"\s*\)',
            'self._url_label.setStyleSheet(qss("comfy_url_label"))',
            src,
        )
        src = re.sub(
            r'self\._log_view\.setStyleSheet\(\s*"QPlainTextEdit \{.*?"\s*\)',
            'self._log_view.setStyleSheet(qss("transparent_bg"))',
            src,
            flags=re.DOTALL,
        )

    # image_extractor_subtab scene colors
    if rel.endswith("image_extractor_subtab.py"):
        src = src.replace('self.setBackgroundBrush(QColor("#1e1f22"))', 'self.setBackgroundBrush(QColor(color("window_bg")))')
        src = src.replace('colors = (QColor("#00e5ff"), QColor("#ff4dff"))', 'colors = (QColor(color("accent")), QColor(color("accent_hover")))')
        src = src.replace('leftover_pen = QPen(QColor("#ffc107"))', 'leftover_pen = QPen(QColor(color("accent_hover")))')

    # graph palette migration
    if rel.endswith(("node_item.py", "edge_item.py", "wallpaper_graph_scene.py", "wallpaper_graph_view.py")):
        imp = palette_import(rel, "wallpaper_graph_palette")
        ti = theme_import(rel)
        if ti in src:
            src = src.replace(ti + "\n", imp + "\n")
        elif imp not in src:
            src = insert_import(src, imp)
        # node_item replacements
        node_repl = {
            'QColor("#e67e22")': 'QColor(NODE_HOVER_ORANGE_BG)',
            'QColor("#d35400")': 'QColor(NODE_HOVER_ORANGE_BORDER)',
            'QColor("#2d3b1e")': 'QColor(NODE_BASIS_BG_SEL)',
            'QColor("#2a3520")': 'QColor(NODE_BASIS_BG)',
            'QColor("#ffeaa7")': 'QColor(NODE_BASIS_BORDER_SEL)',
            'QColor("#f1c40f")': 'QColor(NODE_BASIS_BORDER)',
            'QColor("#3b1a2d")': 'QColor(NODE_SINK_BG_SEL)',
            'QColor("#2e1a2b")': 'QColor(NODE_SINK_BG)',
            'QColor("#ff7eb3")': 'QColor(NODE_SINK_BORDER_SEL)',
            'QColor("#e056b8")': 'QColor(NODE_SINK_BORDER)',
            'QColor("#3a2020")': 'QColor(NODE_UNREACHABLE_BG_SEL)',
            'QColor("#2e2020")': 'QColor(NODE_UNREACHABLE_BG)',
            'QColor("#ff7675")': 'QColor(NODE_UNREACHABLE_BORDER_SEL)',
            'QColor("#7f4040")': 'QColor(NODE_UNREACHABLE_BORDER)',
            'QColor("#1a2b3c")': 'QColor(NODE_STEP_BG_SEL)',
            'QColor("#131c26")': 'QColor(NODE_STEP_BG)',
            'QColor("#00ffff")': 'QColor(NODE_STEP_BORDER_SEL)',
            'QColor("#3498db")': 'QColor(NODE_STEP_BORDER)',
            'QColor("#1a1a00")': 'QColor(NODE_BASIS_BADGE_TEXT)',
            'QColor("#1a001a")': 'QColor(NODE_SINK_BADGE_TEXT)',
            'QColor("#ffcccc")': 'QColor(NODE_UNREACHABLE_BADGE_TEXT)',
            'QColor("#001a33")': 'QColor(NODE_STEP_BADGE_TEXT)',
            'QColor("#23272a")': 'QColor(NODE_THUMB_PLACEHOLDER_BG)',
            'QColor("#7289da")': 'QColor(NODE_THUMB_PLACEHOLDER_ICON)',
            'QColor("#ffffff")': 'QColor(color("text"))',
            'QColor("#b9bbbe")': 'QColor(color("muted_text"))',
        }
        for old, new in node_repl.items():
            src = src.replace(old, new)
        if rel.endswith("edge_item.py"):
            edge_repl = {
                'QColor("#f39c12")': 'QColor(EDGE_ORANGE)',
                'QColor("#7289da")': 'QColor(EDGE_DEFAULT)',
                'QColor("#6b2d2d")': 'QColor(EDGE_SELF_LOOP)',
                'QColor("#2c2f33")': 'QColor(EDGE_ARROW_BG)',
                'QColor("#1e1212")': 'QColor(EDGE_ARROW_SELF)',
            }
            for old, new in edge_repl.items():
                src = src.replace(old, new)
        if rel.endswith("wallpaper_graph_scene.py"):
            src = src.replace('QColor("#f39c12")', 'QColor(GRAPH_HIGHLIGHT)')
        if rel.endswith("wallpaper_graph_view.py"):
            src = src.replace('QColor("#23272a")', 'QColor(GRAPH_SCENE_BG)')

    if rel.endswith("_er_view.py"):
        imp = palette_import(rel, "er_view_palette")
        ti = theme_import(rel)
        if ti in src:
            src = src.replace(ti + "\n", imp + "\n")
        elif imp not in src:
            src = insert_import(src, imp)
        er_repl = {
            'QColor("#2c2f33")': 'QColor(CARD_BG)',
            'QColor("#4f545c")': 'QColor(CARD_BORDER)',
            'QColor("#ffffff")': 'QColor(CARD_TITLE)',
            'QColor("#f2b900" if col.get("pk") else "#dcddde")': 'QColor(CARD_PK if col.get("pk") else CARD_ROW)',
            'QColor("#23272a")': 'QColor(SCENE_BG)',
            'QColor("#7289da")': 'QColor(RELATIONSHIP_LINE)',
        }
        for old, new in er_repl.items():
            src = src.replace(old, new)

    if "qss(" in src or "color(" in src:
        src = insert_import(src, theme_import(rel))

    return src


def main() -> int:
    n = 0
    for rel in tab_paths():
        path = REPO / rel
        orig = path.read_text(encoding="utf-8")
        new = transform(rel, orig)
        if new != orig:
            path.write_text(new, encoding="utf-8")
            n += 1
    print(f"pass2 updated {n} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
