"""Frozen-entry ``--version`` / ``--help`` short-circuit.

Kept Qt-free so ``gui/__main__.py`` can exit before submodule bootstrap,
file-dialog patch, or ``launch_app``.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

_USAGE = """\
usage: ImageToolkit [-h] [-v]

Image Toolkit desktop application.

options:
  -h, --help     show this help message and exit
  -v, --version  print version and exit
"""


def handle_cli_flags(argv: Sequence[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if "-h" in args or "--help" in args:
        print(_USAGE, end="")
        raise SystemExit(0)
    if "-v" in args or "--version" in args:
        from backend.src._version import __version__

        print(f"Image Toolkit {__version__}")
        raise SystemExit(0)
