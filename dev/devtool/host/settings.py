"""Settings: capture channels, retention, alert emphasis, privacy.

Settings own the *policy* decisions; plugins declare their configurable
channels. Retention budgets are per-channel strings ("session", "7d", "30d",
"forever"). Persistence is a JSON file under the workspace root.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

SETTINGS_FILENAME = "settings.json"


@dataclass
class Settings:
    """Workspace-level policy. Mutations are human/CLI actions."""

    # channel key -> enabled. Absent key means "use the plugin default".
    channel_enabled: Dict[str, bool] = field(default_factory=dict)
    # channel key -> retention ("session" | "7d" | "30d" | "forever").
    channel_retention: Dict[str, str] = field(default_factory=dict)
    # Which signal the host emphasizes in alert UIs.
    alert_emphasis: str = "orphaned_spans"
    # Privacy defaults: redact absolute home paths in exported reports.
    redact_home_paths: bool = True

    @classmethod
    def load(cls, path: Path) -> "Settings":
        if not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            channel_enabled=data.get("channel_enabled", {}),
            channel_retention=data.get("channel_retention", {}),
            alert_emphasis=data.get("alert_emphasis", "orphaned_spans"),
            redact_home_paths=data.get("redact_home_paths", True),
        )

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def is_channel_enabled(self, key: str, plugin_default: bool = True) -> bool:
        return self.channel_enabled.get(key, plugin_default)

    def retention_for(self, key: str) -> str:
        return self.channel_retention.get(key, "forever")


__all__ = ["Settings", "SETTINGS_FILENAME"]
