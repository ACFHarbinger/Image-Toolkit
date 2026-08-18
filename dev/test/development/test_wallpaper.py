"""Unit tests for the wallpaper CLI verb (ASP Hero-Cel compositing, #430).

Covers the CLI surface (parser args + defaults) and the --estimate path
(parameter-dependent wall-clock, no clip required). The full pipeline run
is exercised in the ASP submodule's test_wallpaper_pipeline.py.
"""

from __future__ import annotations

from tool.cli.parser import COMMANDS, build_parser


def test_wallpaper_parser_args():
    parser = build_parser()
    args = parser.parse_args(
        ["wallpaper", "/tmp/clip.mov", "--aspect", "9:16", "--quality", "max", "--estimate"]
    )
    assert args.command == "wallpaper"
    assert args.clip == "/tmp/clip.mov"
    assert args.aspect == "9:16"
    assert args.quality == "max"
    assert args.estimate is True


def test_wallpaper_parser_defaults():
    parser = build_parser()
    args = parser.parse_args(["wallpaper", "/tmp/clip.mov"])
    assert args.command == "wallpaper"
    assert args.clip == "/tmp/clip.mov"
    assert args.aspect == "16:9"
    assert args.quality == "balanced"
    assert args.estimate is False


def test_wallpaper_estimate_returns_0_without_clip():
    # --estimate prints the parameter-dependent wall-clock and exits 0; it
    # must not require a real clip (the probe falls back to a default frame
    # count when the clip can't be opened).
    parser = build_parser()
    args = parser.parse_args(
        ["wallpaper", "/tmp/does_not_exist.mov", "--aspect", "21:9", "--quality", "fast", "--estimate"]
    )
    ret = COMMANDS["wallpaper"](args)
    assert ret == 0
