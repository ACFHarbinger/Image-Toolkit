#!/usr/bin/env python3
"""Launch the standalone Qt demonstration application.

Installed packages need no path setup. The two source roots are added only
when this file is run directly from a repository checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
for source_root in (_REPO_ROOT / "src", _REPO_ROOT / "gui" / "src"):
    source = str(source_root)
    if source not in sys.path:
        sys.path.insert(0, source)


def main() -> int:
    from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

    from cel_shaded_generator_gui.tabs.animation_tab import MangaAnimationTab
    from cel_shaded_generator_gui.tabs.colorization_tab import MangaColorizationTab
    from cel_shaded_generator_gui.tabs.puppeteering_tab import MangaPuppeteeringTab

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
    raise SystemExit(main())
