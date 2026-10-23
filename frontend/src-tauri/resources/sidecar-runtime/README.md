Linux sidecar resource layout: `python/` contains a standalone interpreter,
standard library and copied venv dependencies; `middleware/`, `contracts/` and
the native `backend*.so` live beside it. Generated copies are gitignored.

Run `python scripts/stage_sidecar_runtime.py --venv /path/to/project/.venv`
from `frontend/src-tauri` before building. Use a uv-managed standalone Python;
system Python installations are rejected. The script validates catalog loading
and interpreter relocation before replacing an existing resource directory.
`--destination` can stage an inspection bundle under `~/Downloads/Data/Tests/`.
