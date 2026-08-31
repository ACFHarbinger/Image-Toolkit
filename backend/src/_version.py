"""Runtime app version — single truthful source for About / ``--version``.

The canonical version is the root ``pyproject.toml`` ``[project].version``;
``just release::bump <semver>`` keeps every derived source in sync. At runtime
we read the installed ``image-toolkit-backend`` dist metadata first (what
editable installs and the PyInstaller bundle report), falling back to the
canonical root file when running from an uninstalled checkout.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from pathlib import Path

_DIST_NAME = "image-toolkit-backend"


def _read_version() -> str:
    try:
        return _dist_version(_DIST_NAME)
    except PackageNotFoundError:
        pass

    import tomllib

    root = Path(__file__).resolve().parents[2]
    try:
        with (root / "pyproject.toml").open("rb") as fh:
            return tomllib.load(fh)["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "0.0.0+unknown"


__version__: str = _read_version()
