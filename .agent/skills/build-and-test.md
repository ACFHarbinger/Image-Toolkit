---
description: How to rebuild the C++ base module, run tests, and verify the full app after changes.
---

You are working on Image-Toolkit. After any code change, follow this skill to verify correctness.

## After C++ Changes (`base/`)

```bash
source .venv/bin/activate

# Fast dev build (debug mode, faster compile):
just build-base

# Release build (slower compile, faster at runtime):
just build-base-release

# Run C++ unit tests:
just test-base-cpp

# Verify the Python binding:
python -c "import base; print(dir(base))"
```

## After Python Backend Changes (`backend/`)

```bash
source .venv/bin/activate

# Run all Python tests:
pytest

# Run a specific test file:
pytest backend/test/test_image_converter.py -v

# Run with output visible:
pytest -s backend/test/
```

## After GUI Changes (`gui/`)

```bash
source .venv/bin/activate

# Launch the full app (visual check required):
python main.py
```

Check:
- [ ] Target tab opens without freeze
- [ ] File dialogs open (with `DontUseNativeDialog`)
- [ ] Workers complete and results appear in the gallery
- [ ] No `SIGSEGV` / `hs_err_pid*.log` written

## After Frontend Changes (`frontend/`)

```bash
# Dev server:
npm run start-all

# Electron build:
npm run start-electron

# Tests:
npm run test-frontend
```

## After Android Changes (`app/`)

```bash
./gradlew assembleDebug
```

## Full Pre-Commit Checklist

```bash
source .venv/bin/activate

# 1. C++ tests
just test-base-cpp

# 2. Python lint (if configured)
# ruff check . or flake8

# 3. Python tests
pytest

# 4. Quick smoke-test the app
python main.py &
sleep 5
kill %1
```

## Common Build Failures

| Error | Fix |
|---|---|
| `cmake: command not found` | Install cmake: `sudo apt install cmake` |
| `ImportError: base` at runtime | Run `just build-base` again |
| `pytest` can't find `base` | Activate venv first: `source .venv/bin/activate` |
| `pybind11 not found` in CMake | Run `pip install pybind11` inside venv |
