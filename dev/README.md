# `dev/` — Development Tool

Modular host for telemetry, crash forensics, benchmarks, and plugins.

Plan: [`docs/moon/roadmaps/development_tool.md`](../docs/moon/roadmaps/development_tool.md)

```bash
PYTHONPATH=dev:debug python -m devtool            # workspace chooser (canonical)
PYTHONPATH=dev:debug python -m devtool plugins
PYTHONPATH=dev:debug python -m devtool list       # same verbs as debugtool
PYTHONPATH=dev:debug python -m debugtool list     # C2 alias of the same CLI
```

```python
from devtool import open_session, Host, WorkspaceStore
session = open_session(pid=1234)
```

`debug/debugtool` still holds the Session engine and TUI. C2 makes
`devtool` the public name; `debugtool` keeps working.
