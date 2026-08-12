"""Compatibility entry: prefer ``python -m hie_gui.main`` / ``hie-gui``."""

from hie_gui.main import create_window, main

__all__ = ["create_window", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
