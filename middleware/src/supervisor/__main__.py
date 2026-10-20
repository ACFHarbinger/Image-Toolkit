"""``python -m middleware.src.supervisor --data-dir DIR --foreground``."""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from middleware.src.supervisor.supervisor import Supervisor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="image-toolkit-supervisor")
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--foreground", action="store_true")
    args = parser.parse_args(argv)

    supervisor = Supervisor(Path(args.data_dir))
    supervisor.start()
    supervisor.wait_until_ready()

    stopping = False

    def _stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    try:
        while not stopping:
            time.sleep(0.2)
    finally:
        # SIGTERM restarts the supervisor. Leave siblings for reattach.
        supervisor.stop(reap_children=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
