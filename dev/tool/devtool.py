"""tool CLI entry point (the ``devtool`` product, C2).

    python dev/                       # workspace chooser (no daemon)
    python dev/ plugins [--json]
    python dev/ workspace [--json]
    python dev/ list
    python dev/ analyze [path|--pid N] [--tail N] [--category X]
    python dev/ tui [path|--pid N] [--view NAME]
    python dev/ watch [path|--pid N]
    python dev/ export|diff|prune|resolve-offset|repro ...

``dev/__main__.py`` is the ``python dev/`` entry point and calls ``main()``
here. ``cli/parser.py`` owns argument parsing and the individual command
handlers; this module is only the dispatcher.
"""

from __future__ import annotations

import sys
from typing import Optional

from .cli.parser import COMMANDS, build_parser, cmd_workspace


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args.json = False
        return cmd_workspace(args)

    handler = COMMANDS.get(args.command)
    if handler is not None:
        return handler(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
