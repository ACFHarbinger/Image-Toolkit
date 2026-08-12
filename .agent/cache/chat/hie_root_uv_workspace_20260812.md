# HIE Root UV Workspace — Chat

Date: 2026-08-12

The OpenCV dependencies are now visible from the HIE root project manifest:

- Added `middleware` to `[tool.uv.workspace].members`.
- Added the root `restoration-opencv` dependency group.
- Generated `submodules/HIE/uv.lock`.

Install from the HIE root with:

```bash
uv sync --group restoration-opencv
```

The middleware package remains the canonical owner of the `restoration-opencv`
optional extra and the `hie-restore` entry point.
