"""Allow running the CLI as python -m debugtool."""

from __future__ import annotations

import sys

from .cli.main import main

if __name__ == "__main__":
    sys.exit(main())
