"""Fake sibling process used until the real sidecar and daemons exist."""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import sys
import time
from pathlib import Path


def _write_heartbeat(path: Path, role: str, seq: int) -> None:
    payload = {"role": role, "pid": os.getpid(), "seq": seq, "ts": time.time()}
    tmp = path.with_suffix(".heartbeat.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fake_child")
    parser.add_argument("--role", required=True)
    parser.add_argument("--data-dir", required=True)
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    child_dir = data_dir / "supervisor"
    child_dir.mkdir(parents=True, exist_ok=True)
    beat = child_dir / f"{args.role}.heartbeat"

    stopping = False

    def _stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    wait_lease = os.environ.get("IMAGE_TOOLKIT_WAIT_LEASE") == "1"
    if wait_lease:
        # Stay unready until the supervisor delivers a bound lease on stdin.
        first = sys.stdin.readline()
        if not first.strip():
            return 1

    # After the first lease, EOF means the parent dropped the pipe. A durable
    # child stays up across a supervisor restart; SIGTERM is what stops it.
    # Extra lines are renewals and are not written into the heartbeat file.
    stdin_open = wait_lease
    seq = 0
    while not stopping:
        _write_heartbeat(beat, args.role, seq)
        seq += 1
        try:
            if stdin_open:
                ready, _, _ = select.select([sys.stdin], [], [], 0.05)
                if ready and sys.stdin.readline() == "":
                    stdin_open = False
            else:
                time.sleep(0.05)
        except InterruptedError:
            continue
    return 0


if __name__ == "__main__":
    sys.exit(main())
