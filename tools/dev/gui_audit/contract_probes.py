"""Read-only GUI contract probes; fake vault only, no desktop or user settings.

Run from the repository root: python tools/dev/gui_audit/contract_probes.py
True means the reported failure mechanism is present, not a passing invariant.
"""

from __future__ import annotations

import gc
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from gui.src.preferences.adapters.vault_adapter import VaultPreferenceAdapter
    from gui.src.qt_event_bridge import QtEventBridge
    from PySide6.QtCore import QCoreApplication

    # Load the real guard without importing the eager helpers barrel.
    spec = importlib.util.spec_from_file_location(
        "audit_gc_safe", ROOT / "gui/src/helpers/gc_safe.py"
    )
    assert spec is not None and spec.loader is not None
    guard_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard_module)
    original_gc = gc.isenabled()
    try:
        gc.enable()
        first = guard_module.gc_disabled()
        second = guard_module.gc_disabled()
        first.__enter__()
        second.__enter__()
        first.__exit__(None, None, None)
        overlap_failure = gc.isenabled()
        second.__exit__(None, None, None)
    finally:
        gc.enable() if original_gc else gc.disable()

    class FakeVault:
        def __init__(self) -> None:
            self.saved: list[dict] = []

        def save_data(self, text: str) -> None:
            self.saved.append(json.loads(text))

    initial = {"theme": "old", "preferences": {"recursive_scan": False}}
    vault = FakeVault()
    adapter = VaultPreferenceAdapter(initial, vault, "fake-account")
    vault.save_data(json.dumps({**initial, "theme": "new"}))
    adapter.set("preferences/recursive_scan", True)

    class FailingVault:
        def save_data(self, text: str) -> None:
            raise OSError("simulated persistence failure")

    failing = VaultPreferenceAdapter(initial, FailingVault(), "fake-account")
    suppressed = False
    try:
        failing.set("preferences/recursive_scan", True)
        suppressed = failing.get("preferences/recursive_scan") is True
    except OSError:
        pass

    app = QCoreApplication.instance() or QCoreApplication([])
    received: list[str] = []
    bridge = QtEventBridge(received.append)
    bridge.post("old-session-result")
    bridge.detach()
    app.processEvents()
    print(json.dumps({
        "gc_enabled_during_second_guard": overlap_failure,
        "stale_vault_snapshot_overwrites_new_theme": vault.saved[-1]["theme"] == "old",
        "persistence_failure_suppressed_and_memory_advanced": suppressed,
        "queued_event_delivered_after_detach": received == ["old-session-result"],
    }, indent=2))


if __name__ == "__main__":
    main()
