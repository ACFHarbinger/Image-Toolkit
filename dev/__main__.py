"""Allow running the Development Tool as ``python dev/`` (or ``python dev/__main__.py``).

Running a directory with Python adds that directory to ``sys.path[0]``, so
``tool`` (a subdirectory of ``dev/``) resolves without any PYTHONPATH.
"""

from __future__ import annotations

import sys

from tool.devtool import main

if __name__ == "__main__":
    sys.exit(main())
