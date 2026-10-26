"""Offline, privacy-safe compatibility diagnostics for the Krita adapter."""

from __future__ import annotations

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path

MINIMUM_KRITA = (5, 2)
MINIMUM_PYTHON = (3, 10)


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    """Compatibility facts containing no artwork or document metadata."""

    krita_version: str
    python_version: str
    content_available: bool
    core_available: bool
    compatible: bool
    messages: tuple[str, ...]


def _major_minor(version: str) -> tuple[int, int] | None:
    match = re.search(r"(\d+)\.(\d+)", version)
    return (int(match.group(1)), int(match.group(2))) if match else None


def diagnose(krita_version: str, package_dir: str | Path | None = None) -> DiagnosticReport:
    """Inspect versions, packaged content, and core visibility without network I/O."""
    root = Path(package_dir) if package_dir else Path(__file__).parent
    content_available = (root / "content" / "lesson.json").is_file()
    core_available = importlib.util.find_spec("learning") is not None
    parsed_krita = _major_minor(krita_version)
    krita_ok = parsed_krita is not None and parsed_krita >= MINIMUM_KRITA
    python_ok = sys.version_info[:2] >= MINIMUM_PYTHON
    messages = []
    if not krita_ok:
        messages.append("Krita 5.2 or newer is required.")
    if not python_ok:
        messages.append("Krita must provide Python 3.10 or newer.")
    if not content_available:
        messages.append("Packaged lesson content is missing.")
    if not core_available:
        messages.append(
            "Standalone core is not visible inside Krita; lessons work, but review is unavailable."
        )
    if not messages:
        messages.append("Plugin, content, and standalone core are available.")
    return DiagnosticReport(
        krita_version=krita_version,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        content_available=content_available,
        core_available=core_available,
        compatible=krita_ok and python_ok and content_available,
        messages=tuple(messages),
    )
