"""Picklable fakes for tests that drive the spawn-based parallel queue pool.

A spawn pool re-imports the callable by module path in each child process, so
the fake must live at module level in an importable module -- a closure or a
patch applied only in the parent never reaches the children.
"""

from __future__ import annotations

import time


def sleepy_extract(cfg: dict) -> dict:
    time.sleep(0.4)
    return {"status": "success", "output_path": f"{cfg['id']}.gif"}
