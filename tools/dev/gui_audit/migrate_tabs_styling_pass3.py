#!/usr/bin/env python3
"""Final pass: fix remaining tab styling violations."""
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


def transform(src: str) -> str:
    subs = [
        ('setStyleSheet("")', 'setStyleSheet(qss("transparent_bg"))'),
        ('setStyleSheet(_qss("shared_button"))', 'setStyleSheet(qss("shared_button"))'),
        ('none_label.setStyleSheet("color: #666; font-style: italic;")', 'none_label.setStyleSheet(qss("muted_label"))'),
        ('btn.setStyleSheet("QPushButton:checked {  color: white; }")', 'btn.setStyleSheet(qss("extension_btn_checked"))'),
        ('graph_lbl.setStyleSheet("font-weight: bold; padding: 4px;")', 'graph_lbl.setStyleSheet(qss("section_header"))'),
        ('self.selection_label.setStyleSheet("padding: 4px 0; font-weight: bold;")', 'self.selection_label.setStyleSheet(qss("selection_label"))'),
        ('gallery_header.setStyleSheet("font-weight: bold; padding: 4px;")', 'gallery_header.setStyleSheet(qss("section_header"))'),
        ('canvas_lbl.setStyleSheet("font-weight: bold; padding: 4px;")', 'canvas_lbl.setStyleSheet(qss("section_header"))'),
        ('self.queue_header_label.setStyleSheet("font-weight: bold; padding: 4px;")', 'self.queue_header_label.setStyleSheet(qss("section_header"))'),
        ('thumb_label.setStyleSheet(\n                " border-radius: 4px;"\n            )', 'thumb_label.setStyleSheet(qss("thumb_rounded"))'),
        ('zoom_hint.setStyleSheet("color: #888; font-size: 10px; font-style: italic;")', 'zoom_hint.setStyleSheet(qss("extractor_zoom_hint"))'),
        ('self.setStyleSheet("font-family: monospace; font-size: 11px;")', 'self.setStyleSheet(qss("monospace_small"))'),
        ('self._recall_label.setStyleSheet("font-family: monospace; font-size: 12px;")', 'self._recall_label.setStyleSheet(qss("monospace_medium"))'),
        ('self._log_box.setStyleSheet("font-family: monospace; font-size: 11px;")', 'self._log_box.setStyleSheet(qss("monospace_small"))'),
        ('self.lbl_preview.setStyleSheet("border: 2px dashed #aaa; padding: 10px;")', 'self.lbl_preview.setStyleSheet(qss("gan_preview_placeholder"))'),
        ('placeholder.setStyleSheet("color:#555;font-size:14px;")', 'placeholder.setStyleSheet(qss("listings_empty_placeholder"))'),
        ('msg.setStyleSheet("QLabel{min-width: 400px;}")', 'msg.setStyleSheet(qss("msgbox_label"))'),
        ('self._queue_position_label.setStyleSheet(\n            "color:#f1c40f; font-weight:bold; font-size:14px;"\n        )', 'self._queue_position_label.setStyleSheet(qss("wallpaper_queue_position"))'),
        ('self._queue_timer_label.setStyleSheet(\n            "color:#2ecc71; font-weight:bold; font-size:14px;"\n        )', 'self._queue_timer_label.setStyleSheet(qss("wallpaper_queue_timer"))'),
        ('self._status_label.setStyleSheet(f"color: {colour};")', 'self._status_label.setStyleSheet(qss("status_color_dynamic", STATUS_COLOR=colour))'),
        ('self._cb_style = (\n            "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid #555; "\n            "border-radius: 3px;  }"\n            "QCheckBox::indicator:checked {  border: 1px solid #4CAF50; }"\n        )', ''),
        ('self.multicore_cb.setStyleSheet(_cb_style)', 'self.multicore_cb.setStyleSheet(qss("convert_checkbox"))'),
        ('self.delete_cb.setStyleSheet(_cb_style)', 'self.delete_cb.setStyleSheet(qss("convert_checkbox"))'),
        ('"border:1px solid #555; border-radius:4px; padding:4px; min-width:90px;"', 'qss("cbir_metric_label")'),
    ]
    for old, new in subs:
        src = src.replace(old, new)

    src = re.sub(
        r'button_to_cancel\.setStyleSheet\(\s*"""\s*QPushButton \{  color: white; font-weight: bold; \}\s*"""\s*\)',
        'button_to_cancel.setStyleSheet(qss("btn_cancel_active"))',
        src,
    )
    src = re.sub(
        r'cancel_btn\.setStyleSheet\(\s*"QPushButton \{  color: white; font-weight: bold; \}"\s*\)',
        'cancel_btn.setStyleSheet(qss("btn_cancel_active"))',
        src,
    )
    src = re.sub(
        r'btn\.setStyleSheet\(\s*"""\s*QPushButton:checked \{  color: white; \}\s*QPushButton:hover \{  \}\s*"""\s*\)',
        'btn.setStyleSheet(qss("toggle_btn_checked"))',
        src,
    )
    src = re.sub(
        r'self\.btn_scan\.setStyleSheet\(\s*"QPushButton \{  color: white; font-weight: bold; "\s*"padding: 10px; border-radius: 8px; \} QPushButton:hover \{  \}"\s*\)',
        'self.btn_scan.setStyleSheet(qss("similarity_action_btn"))',
        src,
    )
    src = re.sub(
        r'self\.btn_reset\.setStyleSheet\(\s*"QPushButton \{  color: white; font-weight: bold; "\s*"padding: 10px; border-radius: 8px; \} QPushButton:hover \{  \}"\s*\)',
        'self.btn_reset.setStyleSheet(qss("similarity_action_btn"))',
        src,
    )
    src = re.sub(
        r'edit_current_time\.setStyleSheet\(\s*"QLineEdit \{  color: #00BCD4; border: 1px solid #4f545c; border-radius: 4px; font-family: monospace; \}"\s*\)',
        'edit_current_time.setStyleSheet(qss("extractor_line_edit"))',
        src,
    )
    src = re.sub(
        r'self\.info_label\.setStyleSheet\(\s*"color: #aaa; font-style: italic; font-size: 11px;"\s*\)',
        'self.info_label.setStyleSheet(qss("extractor_info_italic"))',
        src,
    )
    src = re.sub(
        r'self\.storyboard_progress_bar\.setStyleSheet\(\s*"QProgressBar \{  color: #aaa; border: 1px solid #4f545c;.*?"\s*\)',
        'self.storyboard_progress_bar.setStyleSheet(qss("storyboard_progress_bar"))',
        src,
        flags=re.DOTALL,
    )
    src = re.sub(
        r'self\.groups_list_widget\.setStyleSheet\(\s*"QListWidget::item \{ padding: 4px; \} "\s*"QListWidget \{ border: 1px solid #4f545c; border-radius: 8px; \}"\s*\)',
        'self.groups_list_widget.setStyleSheet(qss("bordered_list_widget_items"))',
        src,
    )
    src = re.sub(
        r'self\.subgroups_list_widget\.setStyleSheet\(\s*"QListWidget::item \{ padding: 4px; \} "\s*"QListWidget \{ border: 1px solid #4f545c; border-radius: 8px; \}"\s*\)',
        'self.subgroups_list_widget.setStyleSheet(qss("bordered_list_widget_items"))',
        src,
    )
    src = re.sub(
        r'self\.tag_types_list_widget\.setStyleSheet\(\s*"QListWidget::item \{ padding: 4px; \} "\s*"QListWidget \{ border: 1px solid #4f545c; border-radius: 8px; \}"\s*\)',
        'self.tag_types_list_widget.setStyleSheet(qss("bordered_list_widget_items"))',
        src,
    )
    src = re.sub(
        r'self\.tags_list_widget\.setStyleSheet\(\s*"QListWidget::item \{ padding: 4px; \} "\s*"QListWidget \{ border: 1px solid #4f545c; border-radius: 8px; \}"\s*\)',
        'self.tags_list_widget.setStyleSheet(qss("bordered_list_widget_items"))',
        src,
    )
    src = re.sub(
        r'self\.tags_list_widget\.setStyleSheet\(\s*"QListWidget::item \{ padding: 5px; \} "\s*"QListWidget \{ border: 1px solid #4f545c; border-radius: 8px; \}"\s*\)',
        'self.tags_list_widget.setStyleSheet(qss("bordered_list_widget_items_lg"))',
        src,
    )
    src = re.sub(
        r'self\._log_view\.setStyleSheet\(\s*"font-family: monospace; font-size: 9pt;"\s*\)',
        'self._log_view.setStyleSheet(qss("comfy_log_text"))',
        src,
    )
    src = re.sub(
        r'self\._log_view\.setStyleSheet\(\s*"QPlainTextEdit \{.*?"\s*\)',
        'self._log_view.setStyleSheet(qss("comfy_log_view"))',
        src,
        flags=re.DOTALL,
    )

    # dynamic color previews
    src = src.replace(
        'f"background-color:{self._end_color_current}; border:1px solid {color(\'border\')};"',
        'qss("dynamic_color_preview", BG_COLOR=self._end_color_current)',
    )
    src = src.replace(
        'self._end_color_preview.setStyleSheet(\n            f"background-color:{self._end_color_current}; border:1px solid {color(\'border\')};"\n        )',
        'self._end_color_preview.setStyleSheet(qss("dynamic_color_preview", BG_COLOR=self._end_color_current))',
    )
    src = src.replace(
        'f"background-color: {self.solid_color_hex}; border: 1px solid {color(\'border\')};"',
        'qss("dynamic_color_preview", BG_COLOR=self.solid_color_hex)',
    )
    for pat in [
        'self.solid_color_preview.setStyleSheet(\n            f"background-color: {self.solid_color_hex}; border: 1px solid {color(\'border\')};"\n        )',
        'self.solid_color_preview.setStyleSheet(\n                f"background-color: {self.solid_color_hex}; border: 1px solid {color(\'border\')};"\n            )',
    ]:
        src = src.replace(pat, 'self.solid_color_preview.setStyleSheet(qss("dynamic_color_preview", BG_COLOR=self.solid_color_hex))')

    # cbir metric label - fix setStyleSheet call
    src = src.replace(
        'w.setStyleSheet(\n            qss("cbir_metric_label")\n        )',
        'w.setStyleSheet(qss("cbir_metric_label"))',
    )
    src = src.replace(
        'w.setStyleSheet(\n            "border:1px solid #555; border-radius:4px; padding:4px; min-width:90px;"\n        )',
        'w.setStyleSheet(qss("cbir_metric_label"))',
    )

    return src


def main() -> int:
    n = 0
    for rel in tab_paths():
        path = REPO / rel
        orig = path.read_text(encoding="utf-8")
        new = transform(orig)
        if new != orig:
            path.write_text(new, encoding="utf-8")
            n += 1
    print(f"pass3 updated {n} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
