"""Make dev/ and debug/ importable for devtool tests.

devtool lives at dev/devtool/ and imports its Session model from debugtool
(debug/debugtool/) until the C2 migration. Put both roots on sys.path so
`import devtool` and `import debugtool` resolve in pytest.
"""

from __future__ import annotations

import sys
from pathlib import Path

_DEV_ROOT = Path(__file__).resolve().parent
_DEBUG_ROOT = _DEV_ROOT.parent / "debug"

for _root in (_DEV_ROOT, _DEBUG_ROOT):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))
