"""Monitor name/resolution resolution (EDID parsing) and label text updates.

Extracted from ``monitor_drop_view.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtWidgets import QApplication


class _MonitorInfoMixin:
    """Resolves the real monitor name/resolution (via EDID) and updates labels."""

    def text(self) -> str:
        # Support QTest/Pytest assertions by providing combined text representation
        top_txt = self.top_label.text() if hasattr(self, "top_label") else ""
        return f"{top_txt} {super().text()}"

    def get_real_monitor_name(self) -> Optional[str]:  # noqa: C901
        import platform
        if platform.system() != "Linux":
            return None

        import glob
        import re
        port_name = self.monitor.name
        if not isinstance(port_name, str) or not port_name:
            return None

        def parse_edid(edid_bytes):
            if not edid_bytes or len(edid_bytes) < 128:
                return None
            if edid_bytes[:8] != b'\x00\xff\xff\xff\xff\xff\xff\x00':
                return None
            mfg_id_val = int.from_bytes(edid_bytes[8:10], byteorder='big')
            char1 = chr(((mfg_id_val >> 10) & 0x1F) + 64)
            char2 = chr(((mfg_id_val >> 5) & 0x1F) + 64)
            char3 = chr((mfg_id_val & 0x1F) + 64)
            mfg = f'{char1}{char2}{char3}'

            monitor_name = None
            for offset in (54, 72, 90, 108):
                desc = edid_bytes[offset:offset+18]
                if desc[0:2] == b'\x00\x00' and desc[2] == 0x00 and desc[3] == 0xfc:
                    name_bytes = desc[5:]
                    name_len = 0
                    for b in name_bytes:
                        if b in (0x0a, 0x00):
                            break
                        name_len += 1
                    monitor_name = name_bytes[:name_len].decode('ascii', errors='ignore').strip()
                    break

            if monitor_name:
                mfg_map = {
                    'LGD': 'LG Electronics',
                    'GSM': 'LG Electronics',
                    'SAM': 'Samsung',
                    'SEC': 'Samsung',
                    'DEL': 'Dell',
                    'ACR': 'Acer',
                    'BEN': 'BenQ',
                    'AOC': 'AOC',
                    'HPQ': 'HP',
                    'HWP': 'HP',
                    'LEN': 'Lenovo',
                    'PHL': 'Philips',
                    'SNY': 'Sony',
                    'APP': 'Apple',
                    'ASU': 'ASUS',
                    'MSI': 'MSI',
                }
                mfg_full = mfg_map.get(mfg, mfg)
                return f'{mfg_full} {monitor_name}'
            return None

        # Try exact match first
        matches = glob.glob(f'/sys/class/drm/*-{port_name}')
        if matches:
            edid_path = os.path.join(matches[0], 'edid')
            if os.path.exists(edid_path):
                try:
                    with open(edid_path, 'rb') as f:
                        edid = f.read()
                    parsed = parse_edid(edid)
                    if parsed:
                        return parsed
                except Exception:
                    pass

        # Try normalized matching (e.g. HDMI-1 -> HDMI-A-1)
        m = re.match(r'([a-zA-Z]+)-?(\d+)', port_name)
        if m:
            prefix, num = m.groups()
            for p in glob.glob('/sys/class/drm/*'):
                dir_name = os.path.basename(p)
                if prefix.lower() in dir_name.lower() and (dir_name.endswith(f'-{num}') or dir_name.endswith(f'-A-{num}')):
                    edid_path = os.path.join(p, 'edid')
                    if os.path.exists(edid_path):
                        try:
                            with open(edid_path, 'rb') as f:
                                edid = f.read()
                            parsed = parse_edid(edid)
                            if parsed:
                                return parsed
                        except Exception:
                            pass
        return None

    def get_resolved_dimensions(self) -> tuple[float | int, float | int]:
        # Try to resolve physical screen size from EDID (highest accuracy)
        edid_res = self.get_real_monitor_resolution()
        if edid_res:
            h_active, v_active = edid_res
            active_is_portrait = False
            # Check Qt screens for rotation
            if self.monitor.name:
                for s in QApplication.screens():
                    if s.name() == self.monitor.name:
                        if s.size().width() < s.size().height():
                            active_is_portrait = True
                        break
            # Fallback to monitor object for rotation
            if not active_is_portrait:
                w = getattr(self.monitor, "width", None)
                h = getattr(self.monitor, "height", None)
                if w and h and w < h:
                    active_is_portrait = True

            # Align parsed native resolution with current active orientation
            if active_is_portrait and h_active > v_active or not active_is_portrait and h_active < v_active:
                width, height = v_active, h_active
            else:
                width, height = h_active, v_active
        else:
            # Fallback to logical size from Qt screen if active, otherwise screeninfo
            width = getattr(self.monitor, "width", None)
            height = getattr(self.monitor, "height", None)
            if self.monitor.name:
                for s in QApplication.screens():
                    if s.name() == self.monitor.name:
                        width = s.size().width()
                        height = s.size().height()
                        break
        # Ensure we don't return MagicMocks in test environments
        if width is not None and not isinstance(width, (int, float)):
            width = None
        if height is not None and not isinstance(height, (int, float)):
            height = None
        return width or 1920, height or 1080

    def update_text(self):
        monitor_name = f"Monitor {self.monitor_id}"
        if self.monitor.name:
            monitor_name = f"{monitor_name} ({self.monitor.name})"

        self.top_label.setText(monitor_name)

        real_name = self.hardware_name or self.get_real_monitor_name()

        if not real_name:
            real_name = "Generic Display"

        width, height = self.get_resolved_dimensions()
        if width and height:
            real_name = f"{real_name} ({width}x{height})"

        self.bottom_label.setText(real_name)

        # Center text inside the main label
        self.setText("\n\nDrag and Drop Image Here")

    def set_hardware_name(self, name: str):
        self.hardware_name = name
        self.update_text()

    def get_real_monitor_resolution(self) -> Optional[tuple[int, int]]:  # noqa: C901
        import platform
        if platform.system() != "Linux":
            return None

        import glob
        import re
        port_name = self.monitor.name
        if not isinstance(port_name, str) or not port_name:
            return None

        def parse_resolution(edid_bytes):
            if not edid_bytes or len(edid_bytes) < 128:
                return None
            # Check timing descriptor at offset 54 (Preferred Timing Mode)
            block = edid_bytes[54:72]
            if block[0:2] != b'\x00\x00':  # Pixel clock is non-zero
                h_active = ((block[4] & 0xf0) << 4) | block[2]
                v_active = ((block[7] & 0xf0) << 4) | block[5]
                if h_active > 0 and v_active > 0:
                    return h_active, v_active
            return None

        # Helper to read from path
        def read_resolution(p):
            edid_path = os.path.join(p, 'edid')
            if os.path.exists(edid_path):
                try:
                    with open(edid_path, 'rb') as f:
                        edid = f.read()
                    return parse_resolution(edid)
                except Exception:
                    pass
            return None

        # Try exact match first
        matches = glob.glob(f'/sys/class/drm/*-{port_name}')
        if matches:
            res = read_resolution(matches[0])
            if res:
                return res

        # Try normalized matching
        m = re.match(r'([a-zA-Z]+)-?(\d+)', port_name)
        if m:
            prefix, num = m.groups()
            for p in glob.glob('/sys/class/drm/*'):
                dir_name = os.path.basename(p)
                if prefix.lower() in dir_name.lower() and (dir_name.endswith(f'-{num}') or dir_name.endswith(f'-A-{num}')):
                    res = read_resolution(p)
                    if res:
                        return res
        return None


__all__ = ["_MonitorInfoMixin"]
