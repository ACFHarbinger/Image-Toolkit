#!/usr/bin/env python3
"""Resolve a `libQt6*.so.6+0xOFFSET` crash address from an hs_err_pid*.log
(or gdb backtrace) down to the nearest enclosing exported C++ symbol.

Built for Addendum 20 of the gallery-scan crash investigation
(.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md): PySide6 ships
its own private Qt build, fully stripped of the local (.symtab) symbol
table, with no matching system debug-info package (it isn't the system
Qt). `Problematic frame: C [libQt6Core.so.6+0x1e74d5]` in an hs_err log is
as far as the JVM's own fatal-error handler can get on its own.

But the *dynamic* symbol table (.dynsym -- every exported function, which
survives stripping since the linker needs it) is still present. This tool
sorts every exported symbol's address and finds the one immediately
preceding the crash offset -- for a non-exported/static/inlined function
sitting between two exports, this correctly identifies the enclosing
exported function; for a crash landing inside an exported function
directly, it identifies it exactly (mangled + demangled).

This is exactly how Addendum 20 resolved two long-mysterious crash
offsets (`+0x1e74d5`, `+0x1df7c9`) to
`QObjectPrivate::ConnectionData::deleteOrphaned(...)` and
`QObjectPrivate::connect(...)` respectively, confirming this crash class
is a real, still-open QObject connection-list corruption bug rather than
whatever the addressed offset happened to coincide with in past guesses.

Usage:
    python dev/resolve_qt_offset.py libQt6Core.so.6+0x1e74d5
    python dev/resolve_qt_offset.py --lib libQt6Core.so.6 0x1e74d5
    python dev/resolve_qt_offset.py --hs-err ~/path/to/hs_err_pid12345.log

Requires `nm` (binutils) and, for demangling, `c++filt` (also binutils) --
both installed by default alongside gdb/build-essential on most distros.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

_PYSIDE6_QT_LIB_DIR = (
    Path(__file__).resolve().parent.parent
    / ".venv"
    / "lib"
    / "python3.11"
    / "site-packages"
    / "PySide6"
    / "Qt"
    / "lib"
)

_FRAME_RE = re.compile(r"\[(lib\w[\w.]*\.so(?:\.\d+)*)\+(0x[0-9a-fA-F]+)\]")


def find_library(lib_name: str) -> Path:
    """Locate *lib_name* under the PySide6 Qt lib dir (or treat it as a
    direct path if it already exists)."""
    direct = Path(lib_name)
    if direct.exists():
        return direct
    candidate = _PYSIDE6_QT_LIB_DIR / lib_name
    if candidate.exists():
        return candidate
    raise FileNotFoundError(
        f"Could not find {lib_name!r} directly or under {_PYSIDE6_QT_LIB_DIR}. "
        "Pass a full path instead."
    )


def load_dynamic_symbols(lib_path: Path) -> list[tuple[int, str]]:
    """Every defined dynamic symbol's (address, mangled_name), sorted by address."""
    result = subprocess.run(
        ["nm", "-D", "--defined-only", str(lib_path)],
        capture_output=True, text=True, check=True,
    )
    symbols: list[tuple[int, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        addr_str, _kind, name = parts[0], parts[1], parts[2]
        try:
            addr = int(addr_str, 16)
        except ValueError:
            continue
        if addr > 0:
            symbols.append((addr, name))
    symbols.sort()
    return symbols


def demangle(mangled: str) -> str:
    try:
        result = subprocess.run(
            ["c++filt"], input=mangled, capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return mangled


def resolve(lib_path: Path, offset: int) -> Optional[tuple[int, str, int]]:
    """Returns (symbol_address, demangled_name, offset_from_symbol) for the
    nearest exported symbol at or below *offset*, or None if every symbol
    is past it."""
    symbols = load_dynamic_symbols(lib_path)
    best: Optional[tuple[int, str]] = None
    for addr, name in symbols:
        if addr <= offset:
            best = (addr, name)
        else:
            break
    if best is None:
        return None
    addr, mangled = best
    return addr, demangle(mangled), offset - addr


def extract_frames_from_hs_err(path: Path) -> list[tuple[str, int]]:
    """Every unique `libFoo.so.N+0xOFFSET` occurrence in an hs_err log or
    gdb backtrace, in first-seen order (the same frame commonly appears
    twice in an hs_err log: once in the header comment, once in the
    Native frames section)."""
    text = path.read_text(errors="replace")
    seen: set[tuple[str, int]] = set()
    frames: list[tuple[str, int]] = []
    for match in _FRAME_RE.finditer(text):
        lib_name, offset_str = match.group(1), match.group(2)
        frame = (lib_name, int(offset_str, 16))
        if frame not in seen:
            seen.add(frame)
            frames.append(frame)
    return frames


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("frame", nargs="?", help="e.g. 'libQt6Core.so.6+0x1e74d5'")
    parser.add_argument("--lib", help="Library name/path (use with a bare offset)")
    parser.add_argument("offset", nargs="?", help="Bare hex offset, e.g. 0x1e74d5 (use with --lib)")
    parser.add_argument("--hs-err", help="Path to an hs_err_pid*.log (or gdb backtrace) to scan for every frame")
    args = parser.parse_args()

    targets: list[tuple[str, int]] = []

    if args.hs_err:
        targets.extend(extract_frames_from_hs_err(Path(args.hs_err)))
        if not targets:
            print(f"No 'libFoo.so.N+0xOFFSET' frames found in {args.hs_err}", file=sys.stderr)
            return 1
    elif args.frame and "+" in args.frame:
        lib_name, offset_str = args.frame.rsplit("+", 1)
        targets.append((lib_name, int(offset_str, 16)))
    elif args.lib and (args.offset or args.frame):
        offset_str = args.offset or args.frame
        targets.append((args.lib, int(offset_str, 16)))
    else:
        parser.print_help()
        return 1

    for lib_name, offset in targets:
        try:
            lib_path = find_library(lib_name)
        except FileNotFoundError as e:
            print(f"{lib_name}+{hex(offset)}: {e}", file=sys.stderr)
            continue
        resolved = resolve(lib_path, offset)
        if resolved is None:
            print(f"{lib_name}+{hex(offset)}: no symbol found at or before this offset")
            continue
        sym_addr, demangled, delta = resolved
        print(f"{lib_name}+{hex(offset)} -> {demangled} + {hex(delta)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
