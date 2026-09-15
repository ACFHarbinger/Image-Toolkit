"""Extraction-history JSON (recent extractions) and requeue into the queue.

Split from ``_video_session_history`` (§5.17 Option B, #629) — pure code
motion, no logic change. Composed into
:class:`ExtractorVideoSessionHistoryController` together with
:mod:`_video_session_config`; cross-module calls resolve via ``self`` on
the leaf class at runtime.
"""

from __future__ import annotations

import contextlib
import copy
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, List

from backend.src.constants import IMAGE_TOOLKIT_DIR
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from ._tab_bound import TabBoundController

if TYPE_CHECKING:
    from ..protos.extractor_tab import VideoExtractorSubTabHostProtocol


class ExtractorExtractionHistoryController(TabBoundController):
    """Extraction-history JSON, recents dropdown, and requeue-to-queue."""

    def _load_extraction_history(self: "VideoExtractorSubTabHostProtocol"):
        """Loads metadata for extracted frames from a central hidden JSON file."""
        history_file = IMAGE_TOOLKIT_DIR / ".extraction_history.json"
        if history_file.exists():
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "recent_runs" in data:
                        self.recent_runs = data.get("recent_runs", [])
                        self.extraction_metadata = data.get("file_map", {})
                    else:
                        # Legacy format where the whole json was extraction_metadata
                        self.extraction_metadata = data
                        # Reconstruct recent_runs from unique metadata in extraction_metadata
                        unique_runs = {}
                        for meta in self.extraction_metadata.values():
                            ts = meta.get("timestamp", 0)
                            unique_runs[ts] = meta
                        self.recent_runs = sorted(
                            unique_runs.values(),
                            key=lambda x: x.get("timestamp", 0),
                            reverse=True,
                        )
            except Exception as e:
                print(f"Error loading extraction history: {e}")
                self.extraction_metadata = {}
                self.recent_runs = []
        else:
            self.extraction_metadata = {}
            self.recent_runs = []

        if (
            hasattr(self, "combo_recent_extractions")
            and self.combo_recent_extractions is not None
        ):
            self._update_recent_extractions_ui()

    def _save_extraction_history(self: "VideoExtractorSubTabHostProtocol"):
        """Saves metadata for extracted frames to a central hidden JSON file."""
        history_file = IMAGE_TOOLKIT_DIR / ".extraction_history.json"
        try:
            IMAGE_TOOLKIT_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "recent_runs": self.recent_runs,
                "file_map": self.extraction_metadata,
            }
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving extraction history: {e}")

    def _record_extraction(self: "VideoExtractorSubTabHostProtocol", file_paths: List[str], metadata: dict):
        """Records metadata for a set of extracted files using absolute paths as keys."""
        metadata = copy.deepcopy(metadata)
        # DIAGNOSTIC (Unknown Video bug): an extraction with no video_path is
        # always a bug -- you cannot extract without a source video. Log the
        # full call stack at the instant it happens so a real reproduction
        # pinpoints the exact recording path (queue vs single, add-to-queue vs
        # completion). Remove once the bug is closed.
        if not metadata.get("video_path"):
            import traceback

            print(
                f"[recent-extractions] EMPTY video_path being recorded: "
                f"metadata={metadata!r} files={file_paths!r}",
                flush=True,
            )
            traceback.print_stack(limit=20)
        # 1. Update file_map for the new files
        for path in file_paths:
            abs_path = str(Path(path).absolute())
            self.extraction_metadata[abs_path] = metadata

        # 2. Add to recent runs (avoid duplicate additions based on timestamp)
        run_ts = metadata.get("timestamp")
        if not any(run.get("timestamp") == run_ts for run in self.recent_runs):
            self.recent_runs.append(metadata)

        # 3. Sort recent runs and limit to N
        self.recent_runs.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        self.recent_runs = self.recent_runs[: self.recent_extractions_limit]

        # 4. Prune file_map to only contain files from the N most recent runs
        recent_timestamps = {
            run.get("timestamp") for run in self.recent_runs if run.get("timestamp")
        }
        keys_to_delete = [
            path
            for path, meta in self.extraction_metadata.items()
            if meta.get("timestamp") not in recent_timestamps
        ]
        for key in keys_to_delete:
            del self.extraction_metadata[key]

        self._save_extraction_history()
        self._update_recent_extractions_ui()

    def _apply_new_extractions_limit(self: "VideoExtractorSubTabHostProtocol"):
        """Called when the settings window updates recent_extractions_limit."""
        if hasattr(self, "recent_runs") and self.recent_runs:
            self.recent_runs = self.recent_runs[: self.recent_extractions_limit]

            # Prune file_map too
            recent_timestamps = {
                run.get("timestamp") for run in self.recent_runs if run.get("timestamp")
            }
            keys_to_delete = [
                path
                for path, meta in self.extraction_metadata.items()
                if meta.get("timestamp") not in recent_timestamps
            ]
            for key in keys_to_delete:
                del self.extraction_metadata[key]

            self._save_extraction_history()
            self._update_recent_extractions_ui()

    def _update_recent_extractions_ui(self: "VideoExtractorSubTabHostProtocol"):
        """Updates the dropdown of recent extractions in the Extract tab."""
        if self._recent_combo_connected:
            with contextlib.suppress(RuntimeError, TypeError):
                self.combo_recent_extractions.currentIndexChanged.disconnect(
                    self._on_recent_extraction_selected
                )
            self._recent_combo_connected = False

        self.combo_recent_extractions.clear()
        self.combo_recent_extractions.addItem("Select a previous configuration...")

        # recent_runs is newest-first, so #1 = most recent. "Add Recent to
        # Queue" with a given N loads #1..#N.
        for idx, run in enumerate(self.recent_runs, start=1):
            video_path = run.get("video_path", "")
            video_name = Path(video_path).name if video_path else "Unknown Video"
            start_ms = run.get("start_ms", 0)
            end_ms = run.get("end_ms", 0)
            engine = run.get("engine", "FFmpeg")
            mode = str(run.get("mode") or run.get("type") or "range").upper()

            # Format timestamp nicely
            ts = run.get("timestamp", 0)
            ts_str = (
                time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "N/A"
            )

            start_str = self._format_time(start_ms)
            end_str = self._format_time(end_ms)

            label = (
                f"#{idx}  [{ts_str}] {video_name} "
                f"({start_str} - {end_str}) [{mode} · {engine}]"
            )
            # Set the metadata dictionary as the item data!
            self.combo_recent_extractions.addItem(label, run)

        if hasattr(self, "btn_load_recent") and self.btn_load_recent is not None:
            self.btn_load_recent.setEnabled(
                self.combo_recent_extractions.currentIndex() > 0
            )

        self._refresh_recent_to_queue_controls()

        self.combo_recent_extractions.currentIndexChanged.connect(
            self._on_recent_extraction_selected
        )
        self._recent_combo_connected = True

    def _refresh_recent_to_queue_controls(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Sync the 'Add Recent to Queue' spinbox range + button enabled state."""
        n_runs = len(getattr(self, "recent_runs", []) or [])
        spin = getattr(self, "spin_recent_to_queue_n", None)
        if spin is not None:
            spin.setMaximum(max(1, n_runs))
            if spin.value() == 1 and n_runs:
                spin.setValue(min(5, n_runs))
            n = spin.value()
            spin.setToolTip(
                f"Add the N most recent extractions to the queue "
                f"(loads #1{f'–#{n}' if n > 1 else ''})"
            )
        btn = getattr(self, "btn_add_recent_to_queue", None)
        if btn is not None:
            queue_on = getattr(self, "extraction_queue_enabled", False)
            btn.setEnabled(bool(n_runs) and queue_on)
            btn.setToolTip(
                "Append the N most recent extraction configurations to the extraction queue"
                if queue_on
                else "Enable the Extraction Queue (Settings ▸ Extractor) to use this"
            )

    def _recent_run_to_queue_config(
        self: "VideoExtractorSubTabHostProtocol", run: dict
    ) -> dict:
        """Map a recent-run history entry to an extraction-queue config dict."""
        size_str = run.get("output_size", "Native")
        target_res = None
        if isinstance(size_str, str) and "x" in size_str.lower():
            try:
                w, h = size_str.lower().split("x")
                target_res = (int(w), int(h))
            except ValueError:
                target_res = None
        start_ms = int(run.get("start_ms", 0) or 0)
        end_ms = int(run.get("end_ms", 0) or 0)
        # Preserve the original extraction mode (gif / video / range / single).
        # Older history entries predate the `mode` key — fall back to the
        # start==end heuristic only then.
        mode = str(run.get("mode") or run.get("type") or "").lower()
        _heuristic = "single" if start_ms == end_ms else "range"
        qtype = mode if mode in ("gif", "video", "single", "range") else _heuristic
        return {
            "type": qtype,
            "video_path": run.get("video_path", ""),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "output_dir": run.get("output_dir")
            or str(getattr(self, "extraction_dir", "") or ""),
            "target_resolution": target_res,
            "cuts_ms": copy.deepcopy(run.get("cuts_ms", []) or []),
            "frame_interval": int(run.get("frame_interval", 1) or 1),
            "smart_extract": bool(run.get("smart_extract", False)),
            "smart_method": run.get("smart_method", "") or "",
            "fps": run.get("gif_fps", 24) or 24,
            "mute_audio": bool(run.get("mute_audio", False)),
            "use_ffmpeg": run.get("engine", "FFmpeg") != "MoviePy",
            # Normalize "1x"/"0.5x" combo text -> plain number string; the
            # queue worker also parses either, but keep configs consistent.
            "speed": str(run.get("speed", "1.0")).strip().lower().rstrip("x") or "1.0",
        }

    def _on_recent_extraction_context_menu(
        self: "VideoExtractorSubTabHostProtocol", pos
    ) -> None:
        """Right-click on a Recent Extractions entry: enqueue / load / delete it."""
        from PySide6.QtWidgets import QMenu

        view = self.combo_recent_extractions.view()
        model_index = view.indexAt(pos)
        row = model_index.row()
        # Row 0 is the "Select a previous configuration..." placeholder.
        if row <= 0 or (row - 1) >= len(getattr(self, "recent_runs", []) or []):
            return
        run = self.recent_runs[row - 1]

        menu = QMenu(self.tab)
        act_queue = menu.addAction("➕ Add this to Queue")
        act_queue.setEnabled(bool(getattr(self, "extraction_queue_enabled", False)))
        act_load = menu.addAction("✏️ Load this Config")
        menu.addSeparator()
        act_delete = menu.addAction("🗑️ Delete from Recents")

        chosen = menu.exec(view.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        if chosen is act_queue:
            self._enqueue_recent_run(run)
        elif chosen is act_load:
            self.combo_recent_extractions.hidePopup()
            self._reload_extraction(run)
        elif chosen is act_delete:
            self.combo_recent_extractions.hidePopup()
            self.recent_runs.pop(row - 1)
            self._save_extraction_history()
            self._update_recent_extractions_ui()
            self.extraction_status_label.setText("Removed 1 entry from recent extractions.")
            self.extraction_status_label.show()

    def _enqueue_recent_run(
        self: "VideoExtractorSubTabHostProtocol", run: dict
    ) -> None:
        """Append a single recent-run config to the extraction queue."""
        if not getattr(self, "extraction_queue_enabled", False):
            QMessageBox.information(
                self.tab,
                "Extraction Queue Disabled",
                "Enable the Extraction Queue in Settings ▸ Extractor first.",
            )
            return
        vpath = run.get("video_path", "")
        if not vpath or not Path(vpath).exists():
            QMessageBox.warning(
                self.tab,
                "File Not Found",
                f"The source video '{vpath}' no longer exists.",
            )
            return
        self.combo_recent_extractions.hidePopup()
        self.extraction_queue.append(self._recent_run_to_queue_config(run))
        self._update_queue_ui()
        self.extraction_status_label.setText(
            f"Added 1 recent extraction to the queue. Queue size: {len(self.extraction_queue)}"
        )
        self.extraction_status_label.show()

    @Slot()
    def _add_recent_extractions_to_queue(self: "VideoExtractorSubTabHostProtocol") -> None:
        """Append the N most recent extraction configs to the extraction queue."""
        runs = getattr(self, "recent_runs", []) or []
        if not runs:
            QMessageBox.information(
                self.tab,
                "No Recent Extractions",
                "There are no recent extractions to enqueue yet.",
            )
            return
        if not getattr(self, "extraction_queue_enabled", False):
            QMessageBox.information(
                self.tab,
                "Extraction Queue Disabled",
                "Enable the Extraction Queue in Settings ▸ Extractor first.",
            )
            return

        n = self.spin_recent_to_queue_n.value()
        added = 0
        skipped = 0
        for run in runs[:n]:  # recent_runs is sorted newest-first
            vpath = run.get("video_path", "")
            if not vpath or not Path(vpath).exists():
                skipped += 1
                continue
            self.extraction_queue.append(self._recent_run_to_queue_config(run))
            added += 1

        self._update_queue_ui()
        msg = f"Added {added} recent extraction(s) to the queue."
        if skipped:
            msg += f" Skipped {skipped} (source video missing)."
        self.extraction_status_label.setText(msg)
        self.extraction_status_label.show()

    def _on_recent_extraction_selected(self: "VideoExtractorSubTabHostProtocol", index: int):
        """Enables/disables the load button based on selection."""
        if hasattr(self, "btn_load_recent") and self.btn_load_recent is not None:
            self.btn_load_recent.setEnabled(index > 0)

    def _load_selected_recent_extraction(self: "VideoExtractorSubTabHostProtocol"):
        """Loads the selected recent extraction configuration into the UI."""
        index = self.combo_recent_extractions.currentIndex()
        if index <= 0:
            QMessageBox.warning(
                self.tab, "Error", "Please select a valid configuration from the list."
            )
            return

        run_data = self.combo_recent_extractions.itemData(index)
        if run_data:
            self._reload_extraction(run_data)
            QMessageBox.information(
                self.tab, "Success", "Extraction configuration loaded successfully."
            )

    def _clear_output_gallery(self: "VideoExtractorSubTabHostProtocol"):
        """Clear only the extracted-output gallery (not source media or player state)."""
        output_paths = set(self.gallery_image_paths) | set(
            self.current_extracted_paths
        )
        for path in output_paths:
            self._initial_pixmap_cache.pop(path, None)

        self.current_extracted_paths.clear()
        self.selected_paths.clear()
        self.gallery_image_paths.clear()
        self.clear_gallery_widgets()

    def _clear_gallery(self: "VideoExtractorSubTabHostProtocol"):
        self._clear_output_gallery()
        self._initial_pixmap_cache.clear()
        self.start_time_ms = 0
        self.end_time_ms = 0

        # --- MODIFIED: Reset Snapshot button ---
        self.btn_snapshot.setEnabled(False)
        self.btn_snapshot.setText("📸 Snapshot Frame")
        # ---------------------------------------

        self.btn_set_start.setText("Set Start [00:00:000]")
        self.btn_set_end.setText("Set End [00:00:000]")

        self.btn_set_cut_start.setText("Set Cut Start [00:00]")
        self.btn_set_cut_end.setText("Set Cut End [00:00]")
        self.btn_add_cut.setEnabled(False)
        self.cuts_ms.clear()
        self._update_cuts_label()

        self.btn_add_tag.setEnabled(False)
        self.tags_ms.clear()
        self._update_tags_ui()
        self.btn_extract_range.setEnabled(False)
        self.btn_extract_gif.setEnabled(False)
        self.btn_extract_gif.setEnabled(False)
        self.btn_extract_video.setEnabled(False)
        self.skip_minutes_spinbox.setEnabled(False)
        self.skip_seconds_spinbox.setEnabled(False)
        self.skip_microseconds_spinbox.setEnabled(False)
        self.btn_skip_runtime.setEnabled(False)
        self.btn_jump_backward.setEnabled(False)
        self.btn_extract_range.setText("🎞️ Extract Range")

        self.btn_jump_start.setEnabled(False)
        self.btn_jump_end.setEnabled(False)


__all__ = ["ExtractorExtractionHistoryController"]
