"""Portable theme-pack schema (#437, App Theming & Customization).

Pure data model -- no PySide6/Qt imports, no QApplication needed to
construct or serialize these. The whole point of this module is that its
JSON form is meant to be readable by the other two UI surfaces later
(devtool-app, docs website) without any Python/Qt dependency, so nothing
in here may take a hard dependency on how PySide6 happens to render it.
That rendering (QSS generation, background painting, palette-extraction
math) lives in the four issues that consume this schema (#438-441), not
here.

Design commitments this schema encodes (from the locked roadmap,
docs/moon/roadmaps/app_theming_2026q3.md):

- **Base + override-delta model.** A ``ThemePack`` is a ``base`` (``"dark"``
  or ``"light"``) plus a *sparse* ``color_overrides`` dict -- only the
  tokens the user actually changed, not a full copy of every color. This
  keeps a saved theme small and means switching base (e.g. follow-system)
  re-resolves the unset tokens from the new base while overrides persist.
- **5 core semantic color slots**, per the roadmap's Theme Studio scope:
  accent, surface (card/panel background), window background, text,
  muted text, border -- ``ColorTokens`` below. ``accent_hover``,
  ``accent_pressed``, and ``accent_muted`` are *derived*, not stored (see
  ``resolve.py``) -- one fewer thing for a saved pack to get inconsistent.
- **``asset_ref`` is distinct from a token value** (opencode's round-2
  answer): a background image is either a *linked* filesystem path or an
  *imported* asset id in managed storage, never a value baked into the
  JSON pack itself -- keeps packs small and portable, with the tradeoff
  that a linked-path pack can go stale if the file moves (see
  ``storage.py``'s missing-asset reporting).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

SCHEMA = "image-toolkit.theme-pack"
SCHEMA_VERSION = 1

#: The only two valid base themes. Follow-system is a UI-level concept
#: (switches which base is active) handled by whatever consumes this
#: schema, not a third base value here.
VALID_BASES = ("dark", "light")

#: The 6 stored color token keys (5 UI-facing "slots" -- text/muted are
#: presented together as one Theme Studio slot per the roadmap, but are
#: two distinct stored values). Keys match the existing QSS $VAR suffixes
#: in gui/src/styles/qss/theme.qss (DARK_ACCENT_COLOR etc.) so
#: resolve.to_qss_vars's mapping is a straight rename, not a re-design.
COLOR_TOKEN_KEYS = (
    "accent",
    "surface",
    "window_bg",
    "text",
    "muted_text",
    "border",
)

VALID_FIT_MODES = ("cover", "contain", "center", "tile")
VALID_DENSITY_MODES = ("comfortable", "compact", "spacious")
#: Matches gui/src/windows/main/_theme.py's existing prefs keys/allowed
#: rotation intervals (round-1 Q&A: 1m/5m/15m/1h) plus "off".
VALID_ROTATION_INTERVALS_SEC = (0, 60, 300, 900, 3600)


class ThemeSchemaError(ValueError):
    """A theme pack (or a piece of it) failed schema validation."""


@dataclass(frozen=True)
class ColorTokens:
    """A fully-resolved set of the 6 stored color slots. Hex strings
    (``"#rrggbb"``), no alpha -- alpha/opacity is a background-canvas
    concern (see ``BackgroundTokens.opacity``), not a color-token one."""

    accent: str
    surface: str
    window_bg: str
    text: str
    muted_text: str
    border: str

    def __post_init__(self) -> None:
        for key in COLOR_TOKEN_KEYS:
            _validate_hex_color(getattr(self, key), field_name=key)

    def as_dict(self) -> dict[str, str]:
        return {key: getattr(self, key) for key in COLOR_TOKEN_KEYS}


@dataclass(frozen=True)
class TypographyTokens:
    font_family: Optional[str] = None  # None = inherit system/Qt default
    scale_percent: int = 100  # round-1 Q&A range: 80-150
    weight: str = "normal"  # "normal" | "medium" | "bold"

    def __post_init__(self) -> None:
        if not (80 <= self.scale_percent <= 150):
            raise ThemeSchemaError(f"scale_percent must be 80-150, got {self.scale_percent}")
        if self.weight not in ("normal", "medium", "bold"):
            raise ThemeSchemaError(f"invalid weight {self.weight!r}")


@dataclass(frozen=True)
class CornerTokens:
    #: Sharp=0, Subtle=4, Rounded=8, Pill=16 (gui_ux.md §2.34 Option A) --
    #: any non-negative int is accepted so a future preset isn't blocked
    #: by this schema, but Theme Studio's UI is expected to offer those 4.
    radius_px: int = 4

    def __post_init__(self) -> None:
        if self.radius_px < 0:
            raise ThemeSchemaError(f"radius_px must be >= 0, got {self.radius_px}")


@dataclass(frozen=True)
class ShadowTokens:
    #: 0 = no elevation/shadow. Blur radius in px, matching
    #: QGraphicsDropShadowEffect's own parameter (gui/src/styles/__init__.py
    #: apply_shadow_effect) so a consumer can pass this straight through.
    blur_radius_px: int = 0

    def __post_init__(self) -> None:
        if self.blur_radius_px < 0:
            raise ThemeSchemaError(f"blur_radius_px must be >= 0, got {self.blur_radius_px}")


@dataclass(frozen=True)
class MotionTokens:
    #: Round-2 Q&A: motion needs a reduced-motion/low-performance
    #: fallback as a runtime axis, not a hardcoded assumption.
    reduced_motion: bool = False
    transition_ms: int = 150

    def __post_init__(self) -> None:
        if self.transition_ms < 0:
            raise ThemeSchemaError(f"transition_ms must be >= 0, got {self.transition_ms}")


@dataclass(frozen=True)
class DensityTokens:
    """Folds the existing compact/spacious QSS toggle into Theme Studio
    as an axis (round-1 Q&A) instead of a separate standalone setting."""

    mode: str = "comfortable"

    def __post_init__(self) -> None:
        if self.mode not in VALID_DENSITY_MODES:
            raise ThemeSchemaError(f"invalid density mode {self.mode!r}")


@dataclass(frozen=True)
class BackgroundAssetRef:
    """A reference to a background image -- never the image data itself.

    Exactly one of ``path`` (linked) or ``asset_id`` (imported into
    managed storage, see storage.py's THEME_ASSETS_DIR) must be set,
    matching opencode's round-2 answer that both are first-class.
    """

    kind: str  # "linked" | "imported"
    path: Optional[str] = None
    asset_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.kind not in ("linked", "imported"):
            raise ThemeSchemaError(f"invalid asset_ref kind {self.kind!r}")
        if self.kind == "linked" and not self.path:
            raise ThemeSchemaError("linked asset_ref requires path")
        if self.kind == "imported" and not self.asset_id:
            raise ThemeSchemaError("imported asset_ref requires asset_id")


@dataclass(frozen=True)
class BackgroundTokens:
    #: Ordered playlist; a single image is just a 1-element list. Empty
    #: list = no custom background (solid window_bg color only).
    images: tuple[BackgroundAssetRef, ...] = field(default_factory=tuple)
    opacity: float = 1.0  # round-1 Q&A range: 0.10-1.0
    blur_px: int = 0  # round-1 Q&A: 0-30, off (0) by default
    fit_mode: str = "cover"
    #: Seconds between playlist advances; 0 = no rotation (static image).
    #: One global clock drives this (round-2 Q&A) -- this field describes
    #: the *setting*, not a per-instance running timer.
    rotation_interval_sec: int = 0
    #: "global" or a tab identifier -- round-1 Q&A: global default + a
    #: power-user per-tab override. A per-tab override is a second
    #: BackgroundTokens with scope set to that tab's id, still driven by
    #: the one global clock (round-2 Q&A) -- it does not get its own timer.
    scope: str = "global"

    def __post_init__(self) -> None:
        if not (0.10 <= self.opacity <= 1.0):
            raise ThemeSchemaError(f"opacity must be 0.10-1.0, got {self.opacity}")
        if not (0 <= self.blur_px <= 30):
            raise ThemeSchemaError(f"blur_px must be 0-30, got {self.blur_px}")
        if self.fit_mode not in VALID_FIT_MODES:
            raise ThemeSchemaError(f"invalid fit_mode {self.fit_mode!r}")
        if self.rotation_interval_sec not in VALID_ROTATION_INTERVALS_SEC:
            raise ThemeSchemaError(
                f"rotation_interval_sec must be one of {VALID_ROTATION_INTERVALS_SEC}, "
                f"got {self.rotation_interval_sec}"
            )


@dataclass(frozen=True)
class ThemePack:
    """The portable, saveable/exportable unit -- one theme.

    ``color_overrides`` is intentionally a plain ``dict[str, str]``, not a
    ``ColorTokens`` -- it is a *sparse* set of overrides (possibly empty),
    whereas ``ColorTokens`` (see ``resolve.py``) is always fully resolved.
    Keys must be a subset of ``COLOR_TOKEN_KEYS``.
    """

    name: str
    base: str = "dark"
    color_overrides: dict[str, str] = field(default_factory=dict)
    typography: TypographyTokens = field(default_factory=TypographyTokens)
    corners: CornerTokens = field(default_factory=CornerTokens)
    shadows: ShadowTokens = field(default_factory=ShadowTokens)
    motion: MotionTokens = field(default_factory=MotionTokens)
    density: DensityTokens = field(default_factory=DensityTokens)
    backgrounds: tuple[BackgroundTokens, ...] = field(default_factory=tuple)
    #: Material-You/PyWal-style extraction toggle (round-1 Q&A: off by
    #: default so it never fights a hand-picked palette). Stored per-pack
    #: so re-opening a pack that had it enabled re-derives consistently.
    derive_accent_from_background: bool = False
    #: Expert-mode raw QSS, appended after the generated stylesheet
    #: (round-2 Q&A: safe mode by default, this field is the explicit
    #: opt-in escape hatch). None = not using raw QSS for this pack.
    raw_qss: Optional[str] = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ThemeSchemaError("theme pack name must not be empty")
        if self.base not in VALID_BASES:
            raise ThemeSchemaError(f"invalid base {self.base!r}")
        unknown = set(self.color_overrides) - set(COLOR_TOKEN_KEYS)
        if unknown:
            raise ThemeSchemaError(f"unknown color token key(s) in overrides: {sorted(unknown)}")
        for key, value in self.color_overrides.items():
            _validate_hex_color(value, field_name=f"color_overrides[{key!r}]")
        if self.schema_version != SCHEMA_VERSION:
            raise ThemeSchemaError(
                f"unsupported schema_version {self.schema_version}; this build reads {SCHEMA_VERSION}"
            )


def _validate_hex_color(value: str, *, field_name: str) -> None:
    if not isinstance(value, str) or len(value) != 7 or value[0] != "#":
        raise ThemeSchemaError(f"{field_name} must be a '#rrggbb' hex string, got {value!r}")
    try:
        int(value[1:], 16)
    except ValueError as exc:
        raise ThemeSchemaError(f"{field_name} must be a '#rrggbb' hex string, got {value!r}") from exc


__all__ = [
    "SCHEMA",
    "SCHEMA_VERSION",
    "VALID_BASES",
    "COLOR_TOKEN_KEYS",
    "VALID_FIT_MODES",
    "VALID_DENSITY_MODES",
    "VALID_ROTATION_INTERVALS_SEC",
    "ThemeSchemaError",
    "ColorTokens",
    "TypographyTokens",
    "CornerTokens",
    "ShadowTokens",
    "MotionTokens",
    "DensityTokens",
    "BackgroundAssetRef",
    "BackgroundTokens",
    "ThemePack",
]
