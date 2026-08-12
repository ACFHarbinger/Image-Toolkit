"""Image-Toolkit re-export of the HIE Hybrid Editor tab.

The implementation lives in ``submodules/HIE/gui`` so editor UI work on the
submodule is picked up by the parent app without duplicating tab code.
"""

from __future__ import annotations

from hie_tab import HieEditorTab

__all__ = ["HieEditorTab"]
