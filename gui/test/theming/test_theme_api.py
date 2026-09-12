"""Tests for gui.src.theming.theme_api (#564)."""

from __future__ import annotations

import re

import pytest

from gui.src.theming.theme_api import color, qss

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


@pytest.mark.parametrize(
    "token",
    [
        "accent",
        "accent_hover",
        "accent_pressed",
        "surface",
        "window_bg",
        "text",
        "muted_text",
        "border",
        "success",
        "danger",
    ],
)
def test_color_returns_hash_hex(token: str) -> None:
    value = color(token)
    assert value.startswith("#")
    assert _HEX_RE.match(value)


def test_qss_muted_label_substitutes_vars() -> None:
    sheet = qss("muted_label")
    assert sheet.strip()
    assert "$" not in sheet
    assert "color:" in sheet
