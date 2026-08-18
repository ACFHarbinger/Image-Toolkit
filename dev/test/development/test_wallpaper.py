"""Unit tests for the wallpaper CLI verb (ASP Hero-Cel compositing, issue #430).

The real pipeline is not yet implemented; this covers the CLI surface and
the stub handler that returns exit code 2.
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


def test_wallpaper_cmd_returns_exit_code_2():
    parser = build_parser()
    args = parser.parse_args(
        ["wallpaper", "/tmp/clip.mov", "--aspect", "21:9", "--quality", "fast", "--estimate"]
    )
    ret = COMMANDS["wallpaper"](args)
    assert ret == 2
