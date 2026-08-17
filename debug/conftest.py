"""Make the debug/ directory importable as the debugtool package root.

debugtool lives at debug/debugtool/; putting debug/ on sys.path makes
'import debugtool' work for both the CLI (python -m debugtool from debug/)
and the tests (pytest debug/test/).
"""

from __future__ import annotations

import sys
from pathlib import Path

_DEBUG_ROOT = Path(__file__).resolve().parent
if str(_DEBUG_ROOT) not in sys.path:
    sys.path.insert(0, str(_DEBUG_ROOT))
