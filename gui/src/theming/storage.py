"""Theme-pack JSON load/save and background-asset management (#437).

Storage layout under ``~/.image-toolkit/theming/`` (sibling to the
existing ``~/.image-toolkit/secrets/``, ``recovery/``, ``telemetry/``
directories):

- ``packs/<slug>.json`` -- saved/exported theme packs.
- ``assets/<sha256>.<ext>`` -- imported background images, content-hashed
  so importing the same file twice is a no-op rather than a duplicate.

A "linked" asset_ref is never copied here -- it stays wherever the user's
file already lives, and can go stale if that file moves (see
``missing_assets``).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .schema import (
    SCHEMA,
    BackgroundAssetRef,
    BackgroundTokens,
    ColorTokens,
    CornerTokens,
    DensityTokens,
    MotionTokens,
    ShadowTokens,
    ThemePack,
    ThemeSchemaError,
    TypographyTokens,
)

THEME_DIR = Path.home() / ".image-toolkit" / "theming"
THEME_PACKS_DIR = THEME_DIR / "packs"
THEME_ASSETS_DIR = THEME_DIR / "assets"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "theme"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def theme_pack_to_dict(pack: ThemePack) -> dict[str, Any]:
    # dataclasses.asdict() recurses through nested dataclasses and
    # tuples/lists automatically -- backgrounds (a tuple of
    # BackgroundTokens, each holding a tuple of BackgroundAssetRef) comes
    # out as plain nested dicts/lists already, no manual conversion needed.
    data = asdict(pack)
    data["schema"] = SCHEMA
    return data


def theme_pack_from_dict(data: dict[str, Any]) -> ThemePack:
    data = dict(data)
    schema = data.pop("schema", SCHEMA)
    if schema != SCHEMA:
        raise ThemeSchemaError(f"not an {SCHEMA} document (got schema={schema!r})")

    backgrounds_raw = data.pop("backgrounds", []) or []
    backgrounds = tuple(
        BackgroundTokens(
            images=tuple(BackgroundAssetRef(**img) for img in bg.get("images", [])),
            **{k: v for k, v in bg.items() if k != "images"},
        )
        for bg in backgrounds_raw
    )

    typography = TypographyTokens(**data.pop("typography", {}) or {})
    corners = CornerTokens(**data.pop("corners", {}) or {})
    shadows = ShadowTokens(**data.pop("shadows", {}) or {})
    motion = MotionTokens(**data.pop("motion", {}) or {})
    density = DensityTokens(**data.pop("density", {}) or {})

    return ThemePack(
        typography=typography,
        corners=corners,
        shadows=shadows,
        motion=motion,
        density=density,
        backgrounds=backgrounds,
        **data,
    )


def save_theme_pack(pack: ThemePack, path: Path | None = None) -> Path:
    """Write *pack* as JSON. Defaults to packs/<slug(name)>.json."""
    target = path or (THEME_PACKS_DIR / f"{_slugify(pack.name)}.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(theme_pack_to_dict(pack), indent=2, sort_keys=True), encoding="utf-8")
    return target


def load_theme_pack(path: Path) -> ThemePack:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return theme_pack_from_dict(data)


def list_saved_theme_packs() -> list[Path]:
    if not THEME_PACKS_DIR.is_dir():
        return []
    return sorted(THEME_PACKS_DIR.glob("*.json"))


# ---------------------------------------------------------------------------
# Background asset management
# ---------------------------------------------------------------------------


def import_asset(source_path: Path) -> str:
    """Copy *source_path* into managed storage, content-hashed. Returns the
    asset_id (importing the same bytes twice returns the same id and is a
    cheap no-op, not a duplicate file)."""
    source_path = Path(source_path)
    digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    ext = source_path.suffix.lower()
    asset_id = f"{digest}{ext}"
    THEME_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    dest = THEME_ASSETS_DIR / asset_id
    if not dest.exists():
        shutil.copyfile(source_path, dest)
    return asset_id


def resolve_asset_path(ref: BackgroundAssetRef) -> Path | None:
    """The real filesystem path for *ref*, or None if it can't be found
    (a moved/deleted linked file, or an asset_id never imported here)."""
    if ref.kind == "linked":
        p = Path(ref.path)  # type: ignore[arg-type]
        return p if p.is_file() else None
    p = THEME_ASSETS_DIR / ref.asset_id  # type: ignore[operator]
    return p if p.is_file() else None


def missing_assets(pack: ThemePack) -> list[BackgroundAssetRef]:
    """Every background image reference in *pack* that can't currently be
    resolved to a real file -- per the round-2 answer, packs must report
    missing assets rather than silently dropping/embedding them."""
    missing: list[BackgroundAssetRef] = []
    for bg in pack.backgrounds:
        for ref in bg.images:
            if resolve_asset_path(ref) is None:
                missing.append(ref)
    return missing


__all__ = [
    "THEME_DIR",
    "THEME_PACKS_DIR",
    "THEME_ASSETS_DIR",
    "theme_pack_to_dict",
    "theme_pack_from_dict",
    "save_theme_pack",
    "load_theme_pack",
    "list_saved_theme_packs",
    "import_asset",
    "resolve_asset_path",
    "missing_assets",
]
