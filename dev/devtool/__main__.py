"""Allow running the host CLI as python -m devtool."""

from __future__ import annotations

import sys

from .cli.main import main

if __name__ == "__main__":
    sys.exit(main())
