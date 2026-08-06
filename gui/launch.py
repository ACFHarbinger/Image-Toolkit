#!/usr/bin/env python3
"""Standalone launcher for the Manga Colorization & Animation tabs — a
minimal QMainWindow hosting the three Manga tabs (Colorization, Animation,
Puppeteering) in a QTabWidget, for isolated testing/demo without the full
Image-Toolkit app. Registers manga/manga_gui the same way Image-Toolkit's
own _submodule_bootstrap.py does.

These tabs import Image-Toolkit's own gui.src.constants/styles/utils/windows
(shared UI constants, not vendored here — same cross-repo coupling
documented in this submodule's own docs), so this only runs when checked
out at Image-Toolkit/submodules/Cel-Shaded-Generator/, same as `just test::gui`.

Usage:
    cd gui && uv run python launch.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_IMAGE_TOOLKIT_ROOT = _REPO_ROOT.parent.parent


def _load_package(alias: str, src_dir: Path) -> None:
    if alias in sys.modules or not src_dir.is_dir():
        return
    spec = importlib.util.spec_from_file_location(
        alias, src_dir / "__init__.py", submodule_search_locations=[str(src_dir)]
    )
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)


def main() -> int:
    if str(_IMAGE_TOOLKIT_ROOT) not in sys.path:
        sys.path.insert(0, str(_IMAGE_TOOLKIT_ROOT))
    _load_package("manga", _REPO_ROOT / "src")
    _load_package("manga_gui", _REPO_ROOT / "gui" / "src")

    from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

    from manga_gui.tabs.animation_tab import MangaAnimationTab
    from manga_gui.tabs.colorization_tab import MangaColorizationTab
    from manga_gui.tabs.puppeteering_tab import MangaPuppeteeringTab

    app = QApplication(sys.argv)
    tabs = QTabWidget()
    tabs.addTab(MangaColorizationTab(), "Colorization")
    tabs.addTab(MangaAnimationTab(), "Animation")
    tabs.addTab(MangaPuppeteeringTab(), "Puppeteering")

    window = QMainWindow()
    window.setWindowTitle("Cel-Shaded-Generator")
    window.setCentralWidget(tabs)
    window.resize(1400, 900)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
