"""WCAG 2.1 AA contrast advisories (#437).

Advisory only, never a hard gate (Harbinger's round-2 answer: "the user
may save an intentional low-contrast aesthetic, with the risk made
visible"). Callers (Theme Studio, #438) are expected to surface these as
warnings naming the affected token pair, not block saving.
"""

from __future__ import annotations

from dataclasses import dataclass

from .schema import ColorTokens

#: WCAG 2.1 AA minimum contrast ratio for normal-size text.
WCAG_AA_NORMAL_TEXT = 4.5
#: WCAG 2.1 AA minimum contrast ratio for large-scale text (roadmap's
#: typography scale axis can cross this threshold; checked at the normal
#: ratio here since callers own the font-size context this module doesn't have).
WCAG_AA_LARGE_TEXT = 3.0


@dataclass(frozen=True)
class ContrastWarning:
    token_a: str
    token_b: str
    ratio: float
    minimum: float

    @property
    def message(self) -> str:
        return (
            f"{self.token_a}/{self.token_b} contrast is {self.ratio:.2f}:1, "
            f"below the WCAG AA minimum of {self.minimum:.1f}:1"
        )


def _relative_luminance(hex_color: str) -> float:
    """WCAG relative luminance (https://www.w3.org/TR/WCAG21/#dfn-relative-luminance)."""
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (1, 3, 5))

    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = channel(r), channel(g), channel(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """WCAG contrast ratio between two colors, always >= 1.0."""
    l1 = _relative_luminance(hex_a)
    l2 = _relative_luminance(hex_b)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def contrast_warnings(resolved: ColorTokens, *, minimum: float = WCAG_AA_NORMAL_TEXT) -> list[ContrastWarning]:
    """Advisory warnings for the token pairs that actually need to be
    readable against each other: text-on-window, text-on-surface,
    muted_text-on-window, muted_text-on-surface, accent-on-window (for
    accent-colored text/icons), border-on-surface (for a border to be
    visible at all against its own panel)."""
    pairs = (
        ("text", "window_bg"),
        ("text", "surface"),
        ("muted_text", "window_bg"),
        ("muted_text", "surface"),
        ("accent", "window_bg"),
        ("border", "surface"),
    )
    warnings: list[ContrastWarning] = []
    for a, b in pairs:
        ratio = contrast_ratio(getattr(resolved, a), getattr(resolved, b))
        if ratio < minimum:
            warnings.append(ContrastWarning(token_a=a, token_b=b, ratio=ratio, minimum=minimum))
    return warnings


__all__ = [
    "WCAG_AA_NORMAL_TEXT",
    "WCAG_AA_LARGE_TEXT",
    "ContrastWarning",
    "contrast_ratio",
    "contrast_warnings",
]
