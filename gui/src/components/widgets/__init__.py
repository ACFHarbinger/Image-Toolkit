"""Custom reusable widgets for GUI components -- lazily re-exported.

Kept as a lazy facade (see gui/src/tabs/__init__.py for the same pattern):
importing this package must not eagerly pull in every widget's transitive
dependencies (ui-arch-51 / #573, R3.6 import-graph slimming -- verified by
gui/test/test_import_footprint.py).
"""

from __future__ import annotations

import importlib

_LAZY_EXPORTS = {
    "MetricCard": ".resource_simulator_dashboard",
    "ResourceSimulatorDashboard": ".resource_simulator_dashboard",
    "TelemetryStatusBar": ".telemetry_status_bar",
    "create_telemetry_bridge": ".telemetry_status_bar",
    "ToastWidget": ".toast_widget",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        module = importlib.import_module(_LAZY_EXPORTS[name], __name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
