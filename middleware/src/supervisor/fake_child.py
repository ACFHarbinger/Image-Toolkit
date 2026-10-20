"""Fake sibling process used until the real sidecar and daemons exist."""

from __future__ import annotations

import argparse
import json
import os
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

    seq = 0
    while not stopping:
        _write_heartbeat(beat, args.role, seq)
        seq += 1
        time.sleep(0.05)
    return 0


if __name__ == "__main__":
    sys.exit(main())
