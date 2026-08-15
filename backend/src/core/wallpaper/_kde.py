"""KDE Plasma wallpaper setting (D-Bus scripting + plasma-apply-wallpaperimage fallback)."""

import contextlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from screeninfo import Monitor

from backend.src.constants import SUPPORTED_VIDEO_FORMATS, WALLPAPER_STYLES

from ._dbus import evaluate_kde_script_with_fallback

logger = logging.getLogger(__name__)


class _KDEWallpaperMixin:
    """KDE Plasma wallpaper setting methods for ``WallpaperManager``."""

    @staticmethod
    def get_best_video_plugin() -> Optional[str]:
        REBORN_PLUGIN = "luisbocanegra.smart.video.wallpaper.reborn"
        ZREN_PLUGIN = "com.github.zren.smartvideowallpaper"
        SMARTER_PLUGIN = "smartervideowallpaper"
        search_paths = [
            Path.home() / ".local/share/plasma/wallpapers",
            Path("/usr/share/plasma/wallpapers"),
        ]
        for base_path in search_paths:
            if (base_path / REBORN_PLUGIN).exists():
                return REBORN_PLUGIN
        for base_path in search_paths:
            if (base_path / SMARTER_PLUGIN).exists():
                return SMARTER_PLUGIN
        for base_path in search_paths:
            if (base_path / ZREN_PLUGIN).exists():
                return ZREN_PLUGIN
        return None

    @staticmethod
    def get_kde_desktops(qdbus: Optional[str]) -> List[Dict[str, int]]:
        script = """
        var ds = desktops();
        var output = [];
        for (var i = 0; i < ds.length; i++) {
            var d = ds[i];
            var s = d.screen;
            if (s < 0) continue;
            try {
                var rect = screenGeometry(s);
                output.push(i + ":" + s + ":" + rect.x + ":" + rect.y);
            } catch(e) {}
        }
        print(output.join("\\n"));
        """
        desktops = []
        try:
            result = evaluate_kde_script_with_fallback(qdbus, script)
            for line in result.strip().split("\n"):
                if not line.strip():
                    continue
                parts = line.split(":")
                if len(parts) >= 4:
                    desktops.append(
                        {
                            "index": int(parts[0]),
                            "screen": int(parts[1]),
                            "x": int(parts[2]),
                            "y": int(parts[3]),
                        }
                    )
            return desktops
        except Exception as e:
            logger.error("Failed to get KDE desktops: %s", e)
            return desktops

    @staticmethod
    def _map_monitors_to_kde(
        monitors: List[Monitor], kde_desktops: List[Dict]
    ) -> Dict[int, Dict]:
        """
        Maps the index of 'monitors' list to the corresponding KDE desktop object.
        Uses topological sorting (Top/Left -> Bottom/Right) to handle HiDPI scaling mismatches.
        """
        if not monitors or not kde_desktops:
            return {}

        # Sort both lists by (Y, X)
        # Note: We use a small tolerance for Y in case of slight misalignments, but usually integer sort is fine
        sorted_monitors = sorted(
            list(enumerate(monitors)), key=lambda p: (p[1].y, p[1].x)
        )
        sorted_kde = sorted(kde_desktops, key=lambda d: (d["y"], d["x"]))

        mapping = {}
        # Zip them together based on visual order
        for (m_idx, _), k_desktop in zip(sorted_monitors, sorted_kde, strict=False):
            mapping[m_idx] = k_desktop

        return mapping

    @staticmethod
    def _set_wallpaper_kde(path_map: Dict[str, str], style_name: str, qdbus: str):
        video_fill_mode = 2
        video_mode_active = False

        if style_name.startswith("SmartVideoWallpaper") and "::" in style_name:
            video_mode_active = True
            try:
                parts = style_name.split("::")
                if len(parts) > 1:
                    v_style_str = parts[1].strip()
                    # Normalized mapping
                    v_style_lower = v_style_str.lower()
                    if "keep proportions" in v_style_lower:
                        video_fill_mode = 1  # PreserveAspectFit
                    elif "scaled and cropped" in v_style_lower:
                        video_fill_mode = 2  # PreserveAspectCrop
                    elif "stretch" in v_style_lower:
                        video_fill_mode = 0  # Stretch
                    else:
                        video_fill_mode = 2  # Default to crop
            except Exception:
                pass
            style_name = "Fill"

        fill_mode = WALLPAPER_STYLES["KDE"].get(
            style_name, WALLPAPER_STYLES["KDE"]["Scaled, Keep Proportions"]
        )
        target_plugin = _KDEWallpaperMixin.get_best_video_plugin()
        logger.info(
            "[WallpaperManager] style_name=%r video_mode_active=%s target_plugin=%r",
            style_name,
            video_mode_active,
            target_plugin,
        )
        if video_mode_active and not target_plugin:
            raise RuntimeError(
                "No supported KDE video wallpaper plugin found. Please install a plugin such as 'Smart Video Wallpaper Reborn' to enable video wallpaper support."
            )

        script_parts = []
        video_config_parts = []
        for monitor_id, path in path_map.items():
            if not path:
                continue
            try:
                i = int(monitor_id)
            except ValueError:
                continue

            # KDE Plasma 6 (and some 5 versions) prefers raw paths for org.kde.image
            resolved_path = Path(path).resolve()
            file_uri = str(resolved_path)
            # Unlike org.kde.image's "Image" key above, the video wallpaper
            # plugins' "VideoUrls"/"VideoWallpaperBackgroundVideo" keys are
            # QUrl-typed (QML MediaPlayer.source-style) and need an actual
            # file:// URI, not a bare filesystem path — a raw "/home/..."
            # string has no URI scheme, so QUrl parsing of it is
            # inconsistent across Qt/plugin versions and can silently
            # resolve to "nothing to play" (i.e. a black background) even
            # though writeConfig() itself never errors. as_uri() also
            # percent-encodes spaces/special characters that a naive
            # "file://" + path concatenation would leave broken.
            video_file_uri = resolved_path.as_uri()

            ext = Path(path).suffix.lower()
            takes_video_branch = ext in SUPPORTED_VIDEO_FORMATS and video_mode_active
            logger.info(
                "[WallpaperManager] monitor=%s ext=%r video_branch=%s path=%r",
                i,
                ext,
                takes_video_branch,
                path,
            )

            if takes_video_branch:
                is_smarter = target_plugin == "smartervideowallpaper"
                video_key = (
                    "VideoWallpaperBackgroundVideo" if is_smarter else "VideoUrls"
                )

                # Smart Video Wallpaper Reborn does not store VideoUrls as a
                # single QUrl.  Its configuration UI serializes a list of
                # video records (including the enabled flag) to JSON.  A
                # bare file:// URI is displayed by its settings page but is
                # not a valid current configuration value, leaving the newly
                # selected plugin with no playable item until the user clicks
                # Apply there.  Keep the older plugins' single-value format,
                # but write Reborn's native schema so it can play immediately.
                if target_plugin == "luisbocanegra.smart.video.wallpaper.reborn":
                    video_value = json.dumps(
                        [
                            {
                                "filename": video_file_uri,
                                "enabled": True,
                                "duration": 0,
                                "customDuration": 0,
                                "playbackRate": 0.0,
                                "alternativePlaybackRate": 0.0,
                                "loop": False,
                            }
                        ],
                        separators=(",", ":"),
                    )
                else:
                    video_value = video_file_uri
                # json.dumps again produces a correctly escaped JavaScript
                # string literal for paths containing quotes or backslashes.
                video_value_js = json.dumps(video_value)

                # Only assign wallpaperPlugin when it's actually changing. Plasma
                # tears down and recreates the wallpaper QML delegate whenever this
                # property is *set*, even to its current value — for a video plugin
                # that means destroying and rebuilding its GPU-backed video surface.
                # The slideshow daemon calls this every playback interval (as low as
                # single-digit seconds in video-runtime mode), so an unconditional
                # assignment here was forcing that teardown/recreate cycle every few
                # seconds for as long as the slideshow ran — a plausible way to wedge
                # a GPU buffer import/fence over a long session. Advancing to the next
                # video below only needs writeConfig()+reloadConfig(); it never needed
                # the plugin itself to be reassigned once it's already active.
                #
                # Splitting this into two D-Bus round-trips (switch, then — after a
                # short delay — write the video config) is deliberate, not an
                # oversight: freshly (re)created QML wallpaper delegates (e.g.
                # luisbocanegra.smart.video.wallpaper.reborn's main.qml) start with
                # an internal `isLoading = true` guard that a 100ms startTimer clears.
                # Their onVideoUrlsChanged-style handler that actually starts playback
                # bails out silently while isLoading is still true, and nothing
                # re-triggers it later — so writing the video config in the *same*
                # script as the plugin switch races that timer and, most of the time,
                # loses: the config is written correctly (confirmed via logs/dbus)
                # but the delegate never picks it up, producing a black screen that
                # only resolves if the user manually reopens Wallpaper Settings and
                # clicks Apply (which writes the config through a different path,
                # after the delegate has finished loading). Monitors that already
                # have the target plugin active never hit this race and don't need
                # the delay.
                script_parts.append(
                    f"""
                {{
                    var d = desktops()[{i}];
                    if (d && d.screen >= 0) {{
                        if (d.wallpaperPlugin !== "{target_plugin}") {{
                            d.wallpaperPlugin = "{target_plugin}";
                        }}
                        if (d.wallpaperPlugin !== "{target_plugin}") {{
                            // The plugin switch didn't take (e.g. the plugin isn't actually
                            // registered with Plasma despite being found on disk). Bail out
                            // WITHOUT touching org.kde.image's config below — previously this
                            // fell through and blanked org.kde.image's Color to transparent
                            // black, which is what actually renders when the plugin switch
                            // silently fails, producing a black screen instead of the video.
                            print("ERROR: monitor {i} failed to switch to video wallpaper plugin '{target_plugin}' (still on '" + d.wallpaperPlugin + "').");
                        }}
                    }} else {{
                        print("ERROR: monitor {i} has no valid KDE desktop/screen.");
                    }}
                }}
                """
                )
                video_config_parts.append(
                    f"""
                {{
                    var d = desktops()[{i}];
                    if (d && d.screen >= 0) {{
                        if (d.wallpaperPlugin !== "{target_plugin}") {{
                            print("ERROR: monitor {i} still not on video wallpaper plugin '{target_plugin}' (on '" + d.wallpaperPlugin + "') when writing video config.");
                        }} else {{
                            d.currentConfigGroup = Array("Wallpaper", "{target_plugin}", "General");
                            d.writeConfig("FillMode", {video_fill_mode});
                            d.writeConfig("fillMode", {video_fill_mode});
                            {"d.writeConfig('overridePause', true);" if is_smarter else ""}
                            d.writeConfig("{video_key}", {video_value_js});
                            d.reloadConfig();
                            print("OK: monitor {i} switched to '" + d.wallpaperPlugin + "', wrote {video_key}='{video_file_uri}'.");
                        }}
                    }}
                }}
                """
                )
            else:
                script_parts.append(
                    f'{{ var d = desktops()[{i}]; if (d && d.screen >= 0) {{ d.wallpaperPlugin = "org.kde.image"; d.currentConfigGroup = Array("Wallpaper", "org.kde.image", "General"); d.writeConfig("Image", "{file_uri}"); d.writeConfig("FillMode", {fill_mode}); d.reloadConfig(); }} }}'
                )

        if not script_parts:
            return

        errors: List[str] = []

        full_script = "".join(script_parts)
        try:
            result = evaluate_kde_script_with_fallback(qdbus, full_script)
        except Exception as e:
            raise RuntimeError(f"KDE method failed: {e}") from e
        logger.info("[WallpaperManager] evaluateScript raw result (phase 1): %r", result)
        errors.extend(
            line for line in (result or "").splitlines() if line.startswith("ERROR:")
        )

        if video_config_parts and not errors:
            # Skip the video-config phase entirely if the plugin switch already
            # failed — nothing meaningful to write config for, and no reason to
            # pay the delay/round-trip on a path that's already erroring out.
            #
            # Give freshly-switched QML wallpaper delegates time to clear their
            # isLoading guard (100ms in the Reborn plugin) before writing the
            # config their onVideoUrlsChanged-equivalent handler depends on to
            # actually start playback — see the comment above. Monitors that
            # were already on the target plugin pay this same small one-time
            # delay too (config write is scoped to the video branch either
            # way), rather than threading a second conditional through Python.
            time.sleep(0.3)
            video_script = "".join(video_config_parts)
            try:
                video_result = evaluate_kde_script_with_fallback(qdbus, video_script)
            except Exception as e:
                raise RuntimeError(f"KDE method failed (video config phase): {e}") from e
            logger.info(
                "[WallpaperManager] evaluateScript raw result (phase 2, video config): %r",
                video_result,
            )
            errors.extend(
                line
                for line in (video_result or "").splitlines()
                if line.startswith("ERROR:")
            )

        # evaluateScript() over D-Bus returns exit code 0 for any successful
        # D-Bus round-trip, even when the JS itself threw or one of our own
        # print("ERROR: ...") diagnostics fired — the qdbus/D-Bus layer never
        # raises for that. Without this check, a failed plugin switch (see
        # the video branch above) silently reported Success: True while
        # showing a black screen instead of the video.
        if errors:
            raise RuntimeError("KDE wallpaper script reported errors: " + "; ".join(errors))

    @staticmethod
    def _set_wallpaper_kde_plasma_apply(
        path_map: Dict[str, str], style_name: str
    ) -> bool:
        cmd = shutil.which("plasma-apply-wallpaperimage")
        if not cmd:
            return False

        path = path_map.get("0") or next(iter(path_map.values()), None)
        if not path or not os.path.exists(path):
            return False

        fill_mode = "preserveAspectCrop"
        style_lower = style_name.lower()
        if "stretch" in style_lower:
            fill_mode = "stretch"
        elif (
            "keep proportions" in style_lower
            or "fit" in style_lower
            or "scalled" in style_lower
        ):
            fill_mode = "preserveAspectFit"
        elif "crop" in style_lower or "zoom" in style_lower or "spanned" in style_lower:
            fill_mode = "preserveAspectCrop"
        elif "tile" in style_lower or "wallpaper" in style_lower:
            fill_mode = "tile"
        elif "center" in style_lower or "pad" in style_lower:
            fill_mode = "pad"

        try:
            subprocess.run(
                [cmd, "--fill-mode", fill_mode, str(Path(path).resolve())], check=True
            )
            return True
        except Exception as e:
            logging.error(
                f"Failed to set wallpaper via plasma-apply-wallpaperimage: {e}"
            )
            return False

    @staticmethod
    def get_current_system_wallpaper_path_kde(
        monitors: List[Monitor], qdbus: str
    ) -> Dict[str, Optional[str]]:
        path_map = {}
        path_map = {}

        # We need the full desktop objects to map back to monitors
        kde_desktops = _KDEWallpaperMixin.get_kde_desktops(qdbus)
        if not kde_desktops:
            return {}

        # Get mapping: MonitorIndex -> KDEDesktop
        # We need the reverse: KDEDesktopIndex -> MonitorIndex
        mapping = _KDEWallpaperMixin._map_monitors_to_kde(monitors, kde_desktops)
        kde_idx_to_monitor_idx = {v["index"]: k for k, v in mapping.items()}

        script = "var out = [];\n"
        # We iterate through ALL detected KDE desktops to find their paths
        # Then we assign them to the correct monitor ID based on our mapping
        for d in kde_desktops:
            i = d["index"]
            script += f"""
            (function() {{
                try {{
                    var d = desktops()[{i}];
                    var plugin = d.wallpaperPlugin;
                    d.currentConfigGroup = Array("Wallpaper", plugin, "General");
                    var path = d.readConfig("Image") || d.readConfig("VideoUrls") || d.readConfig("Video") || "NONE";
                    if (path.indexOf(",") !== -1) path = path.split(",")[0];
                    out.push("DESKTOP_{i}:" + path);
                }} catch (e) {{ out.push("DESKTOP_{i}:NONE"); }}
            }})();
            """
        script += '\nprint(out.join("\\n===SEP===\\n"));'

        try:
            result = evaluate_kde_script_with_fallback(qdbus, script)
            for line in result.split("===SEP==="):
                line = line.strip()
                m = re.match(r"DESKTOP_(\d+):(.+)", line)
                if m:
                    kde_idx_str, path = m.groups()
                    kde_idx = int(kde_idx_str)

                    if path != "NONE":
                        # Fix file URI formatting
                        if path.startswith("file:/") and not path.startswith("file://"):
                            path = "file://" + path[5:]
                        if path.startswith("file://"):
                            path = path[7:]

                        # Resolve path
                        final_path = path
                        with contextlib.suppress(Exception):
                            final_path = str(Path(path).resolve())

                        # Map back to monitor ID
                        if kde_idx in kde_idx_to_monitor_idx:
                            monitor_mid = str(kde_idx_to_monitor_idx[kde_idx])
                            path_map[monitor_mid] = final_path

        except Exception as e:
            logger.error("[WallpaperManager] Error in get_current: %s", e)
        return path_map


__all__ = ["_KDEWallpaperMixin"]
