#!/usr/bin/env python3
"""One-shot migrator for allowlisted gui/src/tabs styling (#564)."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
ALLOWLIST = REPO / "tools/dev/gui_audit/styling_allowlist.txt"


def tab_paths() -> list[str]:
    out: list[str] = []
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line.startswith("gui/src/tabs/"):
            out.append(line)
    return out


def theme_import(rel: str) -> str:
    parts = rel.split("/")
    depth = len(parts) - 3
    if depth <= 1:
        return "from gui.src.theming.theme_api import color, qss"
    return f"from {'.' * (depth + 1)}theming.theme_api import color, qss"


def palette_import(rel: str, module: str) -> str:
    parts = rel.split("/")
    depth = len(parts) - 3
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
    # shadow
    src = src.replace('color_hex="#000000"', 'color_hex=color("window_bg")')
    src = re.sub(
        r'apply_shadow_effect\(([^,)]+),\s*"#000000"',
        r'apply_shadow_effect(\1, color("window_bg")',
        src,
    )

    pairs = [
        ('setStyleSheet("QScrollArea { border: none; }")', 'setStyleSheet(qss("scroll_area_borderless"))'),
        ('setStyleSheet("QPushButton:hover {  }")', 'setStyleSheet(qss("btn_hover_empty"))'),
        ('setStyleSheet("background: transparent;")', 'setStyleSheet(qss("transparent_bg"))'),
        ('setStyleSheet("background-color: green; color: white;")', 'setStyleSheet(qss("btn_success_solid"))'),
        ('setStyleSheet("background-color: red; color: white;")', 'setStyleSheet(qss("btn_danger_solid"))'),
        ('setStyleSheet("color: #999; border: 1px dashed #4f545c; background: transparent;")', 'setStyleSheet(qss("entity_recon_clickable_label"))'),
        ('setStyleSheet("color: #99aab5; font-size: 11px;")', 'setStyleSheet(qss("entity_recon_hint"))'),
        ('setStyleSheet("font-size: 20px; font-weight: bold; color: #ffffff;")', 'setStyleSheet(qss("entity_recon_title"))'),
        ('setStyleSheet("color: #b9bbbe;")', 'setStyleSheet(qss("entity_recon_meta"))'),
        ('setStyleSheet("color: #aaa; font-style: italic;")', 'setStyleSheet(qss("muted_label"))'),
        ('setStyleSheet("padding: 5px; font-size: 10px; color: #aaa;")', 'setStyleSheet(qss("crawler_api_doc_link"))'),
        ('setStyleSheet("color: #aaaaaa;")', 'setStyleSheet(qss("comfy_status_label"))'),
        ('setStyleSheet("color: #aaaaaa; font-family: monospace;")', 'setStyleSheet(qss("comfy_url_label"))'),
        ('setStyleSheet("color: #00BCD4; font-style: italic; padding: 4px; font-weight: bold;")', 'setStyleSheet(qss("extractor_status_label"))'),
        ('setStyleSheet("color: #00bcd4; font-weight: bold;")', 'setStyleSheet(qss("accent_section_title"))'),
        ('setStyleSheet("font-weight: bold; color: #3498db;")', 'setStyleSheet(qss("drive_sync_label_local"))'),
        ('setStyleSheet("font-weight: bold; color: #2ecc71;")', 'setStyleSheet(qss("drive_sync_label_remote"))'),
        ('setStyleSheet("color: #e74c3c;")', 'setStyleSheet(qss("drive_sync_rb_delete"))'),
        ('setStyleSheet("color: #95a5a6;")', 'setStyleSheet(qss("drive_sync_rb_ignore"))'),
        ('setStyleSheet("font-weight: bold; color: #e67e22;")', 'setStyleSheet(qss("comfy_warning_label"))'),
        ('setStyleSheet("font-weight: bold; color: #f1c40f;")', 'setStyleSheet(qss("wallpaper_countdown_warning"))'),
        ('setStyleSheet("color: #2ecc71;")', 'setStyleSheet(qss("monitor_status_ok"))'),
        ('setStyleSheet("QGraphicsView { border: 1px solid #4f545c; background-color: #1e1f22; border-radius: 8px; }")', 'setStyleSheet(qss("merge_canvas_view"))'),
        ('label.setStyleSheet("border: 3px solid #3498db; border-radius: 4px;")', 'label.setStyleSheet(qss("source_label_selected"))'),
        ('label.setStyleSheet("border: 2px solid #9b59b6; border-radius: 4px;")', 'label.setStyleSheet(qss("source_label_other_open"))'),
    ]
    for old, new in pairs:
        src = src.replace(old, new)

    src = re.sub(
        r'setStyleSheet\(\s*"QListWidget \{ border: 1px solid #4f545c; border-radius: 4px; \}"\s*\)',
        'setStyleSheet(qss("bordered_list_widget"))',
        src,
    )
    src = re.sub(
        r'setStyleSheet\(\s*"color: #aaa; font-style: italic; padding: 8px;"\s*\)',
        'setStyleSheet(qss("status_label_padded"))',
        src,
    )
    src = re.sub(
        r'setStyleSheet\(\s*"color: #666; font-style: italic; padding: 8px;"\s*\)',
        'setStyleSheet(qss("status_label_padded"))',
        src,
    )
    src = re.sub(
        r'self\.multicore_checkbox\.setStyleSheet\(\s*""".*?"""\s*\)',
        'self.multicore_checkbox.setStyleSheet(qss("convert_checkbox"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'self\.convert_progress_bar\.setStyleSheet\(\s*"QProgressBar \{.*?"\s*\)',
        'self.convert_progress_bar.setStyleSheet(qss("convert_progress_bar"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'self\.extraction_progress_bar\.setStyleSheet\(\s*"QProgressBar \{.*?"\s*\)',
        'self.extraction_progress_bar.setStyleSheet(qss("extractor_progress_bar"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'button_to_cancel\.setStyleSheet\(\s*"QPushButton \{.*?background-color: red;.*?"\s*\)',
        'button_to_cancel.setStyleSheet(qss("btn_danger_solid"))',
        src,
        flags=re.DOTALL,
    )

    multiline_labels = [
        ('label.setStyleSheet(\n                    "border: 2px solid #9b59b6; color: #9b59b6; font-weight: bold;  border-radius: 4px;"\n                )', 'label.setStyleSheet(qss("source_label_other_open_video"))'),
        ('label.setStyleSheet(\n                    "border: 2px solid #9b59b6; color: #9b59b6; border-radius: 4px;"\n                )', 'label.setStyleSheet(qss("source_label_other_open_text"))'),
        ('label.setStyleSheet(\n                        "border: 2px solid #2ecc71; color: #2ecc71; font-weight: bold;  border-radius: 4px;"\n                    )', 'label.setStyleSheet(qss("source_label_video_extracted"))'),
        ('label.setStyleSheet(\n                        "border: 2px solid #3498db; color: #3498db; font-weight: bold;  border-radius: 4px;"\n                    )', 'label.setStyleSheet(qss("source_label_video_default"))'),
        ('label.setStyleSheet(\n                    "border: 1px dashed #666; color: #888; border-radius: 4px;"\n                )', 'label.setStyleSheet(qss("source_label_no_preview"))'),
        ('label.setStyleSheet(\n                    "border: 1px dashed #666; color: #888; font-size: 10px; border-radius: 4px;"\n                )', 'label.setStyleSheet(qss("source_label_loading"))'),
        ('label.setStyleSheet(\n                        "border: 2px solid #2ecc71; border-radius: 4px;"\n                    )', 'label.setStyleSheet(qss("source_label_extracted"))'),
        ('label.setStyleSheet(\n                        "border: 2px solid #4f545c; border-radius: 4px;"\n                    )', 'label.setStyleSheet(qss("source_label_default"))'),
        ('clickable_label.setStyleSheet(\n            "border: 1px dashed #666; color: #888; font-size: 10px;"\n        )', 'clickable_label.setStyleSheet(qss("source_label_loading"))'),
        ('name_label.setStyleSheet(\n            "color: #bbb; font-size: 10px; border: none; padding-top: 2px;"\n        )', 'name_label.setStyleSheet(qss("source_name_label"))'),
    ]
    for old, new in multiline_labels:
        src = src.replace(old, new)

    btn_files = {
        "self.btn_cancel_extraction.setStyleSheet(": "extractor_btn_cancel",
        "self.btn_extract_range.setStyleSheet(": "extractor_btn_range",
        "self.btn_extract_gif.setStyleSheet(": "extractor_btn_gif",
        "self.btn_extract_video.setStyleSheet(": "extractor_btn_video",
        "self.btn_run_on_gcd.setStyleSheet(": "extractor_btn_gcd",
    }
    for prefix, comp in btn_files.items():
        pat = re.escape(prefix) + r'\s*"QPushButton \{.*?"\s*\)'
        src = re.sub(pat, f'{prefix}qss("{comp}"))', src, flags=re.DOTALL)

    src = re.sub(
        r'self\.setStyleSheet\(\s*"color: #00BCD4; border: 1px solid #4f545c;[^"]*"\s*\)',
        'self.setStyleSheet(qss("extractor_cut_label"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'self\.setStyleSheet\(\s*"color: #FFC107; border: 1px solid #4f545c;[^"]*"\s*\)',
        'self.setStyleSheet(qss("extractor_tag_label"))',
        src,
        flags=re.DOTALL,
    )

    src = src.replace(
        'f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;"',
        'f"background-color: {self.solid_color_hex}; border: 1px solid {color(\'border\')};"',
    )

    if rel.endswith("data_schema.py"):
        src = src.replace("from dataclasses import dataclass", "from dataclasses import dataclass, field")
        src = src.replace('end_color: str = "#000000"', 'end_color: str = field(default_factory=lambda: color("window_bg"))')
        src = src.replace('g.end_color = d.get("end_color", "#000000")', 'g.end_color = d.get("end_color", color("window_bg"))')

    if "qss(" in src or "color(" in src:
        src = insert_import(src, theme_import(rel))

    return src


def main() -> int:
    changed = 0
    for rel in tab_paths():
        path = REPO / rel
        orig = path.read_text(encoding="utf-8")
        new = transform(rel, orig)
        if new != orig:
            path.write_text(new, encoding="utf-8")
            changed += 1
    print(f"updated {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
