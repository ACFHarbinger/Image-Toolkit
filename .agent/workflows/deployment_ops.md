---
description: When building executables, managing dependencies, or releasing.
---

You are a **Release Engineer** managing the build and deployment of Image-Toolkit.

## Dependency Management
1.  **Python**:
    - Managed via `uv`. 
    - `bash scripts/setup_env.sh` to sync environment.
    - `source .venv/bin/activate` to enter.
2.  **Rust**:
    - `Cargo.toml` in `base/`.
    - `maturin` for binding.
3.  **Frontend**:
    - `package.json` in `frontend/`.
    - `npm install` to sync.

## Build Pipelines
1.  **Desktop App (Python)**:
    - Command: `pyinstaller --clean ImageToolkit.spec`.
    - Output: `dist/ImageToolkit`.
2.  **Frontend (Electron)**:
    - Command: `npm run start-electron` (Development/Build).
3.  **Mobile (Android)**:
    - Command: `cd app && ./gradlew assembleDebug`.

## Release Checks
- [ ] Run `pytest` for Python backend.
- [ ] Run `cargo test` in `base/` for Rust core.
- [ ] Run `npm run test-frontend` for React UI.
- [ ] Verify `ImageToolkit` executable launches on target OS.