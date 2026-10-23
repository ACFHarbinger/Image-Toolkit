"""``python -m middleware.src.sidecar --data-dir DIR``."""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from pathlib import Path

from middleware.src.sidecar.server import SidecarServer


def _write_heartbeat(path: Path, seq: int) -> None:
    payload = {"role": "sidecar", "pid": os.getpid(), "seq": seq, "ts": time.time()}
    tmp = path.with_suffix(".heartbeat.tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(path)


def _heartbeat_thread(path: Path, stop: threading.Event) -> None:
    seq = 0
    while not stop.is_set():
        _write_heartbeat(path, seq)
        seq += 1
        stop.wait(0.05)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="image-toolkit-sidecar")
    parser.add_argument("--data-dir", help="supervisor data directory for heartbeat files")
    args = parser.parse_args(argv)

    stop = threading.Event()
    heartbeat: threading.Thread | None = None
    if args.data_dir:
        child_dir = Path(args.data_dir) / "supervisor"
        child_dir.mkdir(parents=True, exist_ok=True)
        heartbeat = threading.Thread(
            target=_heartbeat_thread,
            args=(child_dir / "sidecar.heartbeat", stop),
            name="itk-sidecar-heartbeat",
            daemon=True,
        )
        heartbeat.start()
    try:
        SidecarServer().serve()
        return 0
    except Exception as exc:
        # stdout is protocol-only; diagnostics are redacted to the class name.
        print(f"sidecar exited: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        stop.set()
        if heartbeat is not None:
            heartbeat.join(timeout=0.5)


if __name__ == "__main__":
    sys.exit(main())
