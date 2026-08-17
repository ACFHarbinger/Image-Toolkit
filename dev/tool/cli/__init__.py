"""tool CLI (C1): argument parser + command handlers.

``main()`` lives in ``tool.devtool``, not here — this package only builds
the parser and the individual command handlers it dispatches to.
"""

from .parser import COMMANDS, build_parser

__all__ = ["COMMANDS", "build_parser"]
