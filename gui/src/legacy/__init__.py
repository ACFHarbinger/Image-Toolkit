"""Legacy Qt GUI components from relocated submodules (ASP, CSG, HIE).

These components are preserved until PySide6 retirement in #921.
"""

from __future__ import annotations

import sys
from pathlib import Path

_legacy_root = Path(__file__).resolve().parent

for _subdir in [str(_legacy_root), str(_legacy_root / "hie_gui")]:
    if _subdir not in sys.path:
        sys.path.insert(0, _subdir)

if "asp_backend" not in sys.modules:
    try:
        import middleware.src.stitching as _stitching
        sys.modules["asp_backend"] = _stitching
    except ImportError:
        pass

if "csg_backend" not in sys.modules:
    try:
        import middleware.src.csg as _csg
        sys.modules["csg_backend"] = _csg
    except ImportError:
        pass

if "hie_tab" not in sys.modules:
    try:
        import hie_gui.hie_tab as _hie_tab
        sys.modules["hie_tab"] = _hie_tab
    except ImportError:
        pass
