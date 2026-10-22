"""``python -m middleware.src.sidecar [--data-dir DIR]``.

The argv shape the W0-13 supervisor hands to ``children.spawn()`` (cwd =
repo root, ``PYTHONPATH`` = repo root — see ``supervisor.children``).
stdin/stdout are the framed protocol channel; with ``--data-dir`` the
sidecar also writes the heartbeat file the supervisor readiness gate
waits on. No heavy imports happen here — Torch/cv2 load lazily inside
service handlers (later waves), never at startup.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="image-toolkit-sidecar")
    parser.add_argument("--data-dir", default=None, help="supervisor data dir; enables the heartbeat file")
    args = parser.parse_args(argv)

    # Deferred so `--help` and import of this module stay lightweight.
    from .heartbeat import Heartbeat
    from .server import SidecarServer

    heartbeat = Heartbeat(Path(args.data_dir)) if args.data_dir else None
    if heartbeat is not None:
        heartbeat.start()
    try:
        return SidecarServer().serve(sys.stdin, sys.stdout, sys.stderr)
    finally:
        if heartbeat is not None:
            heartbeat.stop()


if __name__ == "__main__":
    sys.exit(main())
