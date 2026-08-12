# HIE Root Restoration CLI — Chat

Date: 2026-08-12

Verified that the root workspace can invoke the middleware CLI directly:

```bash
cd submodules/HIE
uv sync --group restoration-opencv
uv run --package hie-middleware hie-restore --help
```

Documented root-level `deblur` and permission-gated `inpaint` commands in the
HIE README. `middleware/` remains the package owner; `--package hie-middleware`
selects its console entry point from the root workspace.
