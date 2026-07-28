"""Top-level CLI command router.

`main.py` parses argv into `(command, opts)` via
:mod:`backend.src.utils.io.arg_parser` and hands both to
:func:`dispatch_command` here. Each command group's actual logic lives in its
own sibling module — this file only routes.
"""

from __future__ import annotations

import sys

from backend.controllers.core_dispatch import dispatch_core
from backend.controllers.database_dispatch import dispatch_database
from backend.controllers.model_dispatch import dispatch_model
from backend.controllers.settings_dispatch import dispatch_update_settings
from backend.controllers.stitch_dispatch import dispatch_stitch
from backend.controllers.web_dispatch import dispatch_web
from backend.src.utils.display.slideshow_daemon import run as launch_slideshow


def dispatch_command(command: str, args: dict) -> None:
    if command == "core":
        dispatch_core(args)
    elif command == "stitch":
        dispatch_stitch(args)
    elif command == "web":
        dispatch_web(args)
    elif command == "database":
        dispatch_database(args)
    elif command == "model":
        dispatch_model(args)
    elif command == "slideshow":
        launch_slideshow()
    elif command == "update-settings":
        dispatch_update_settings(args)
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
