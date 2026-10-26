# 2. One top-level directory per language

Date: 2026-07-30

## Status

Accepted

## Context

HIE combines Python for orchestration/ML, TypeScript for the Tauri UI, and C++ for performance-critical image operations. Each language ecosystem has its own dependency manifest and directory conventions.

## Decision

HIE keeps C++ performance code under `logic/`, Python orchestration under `middleware/`, the Tauri UI under `frontend/`, and the PySide6 UI under `gui/`. Cross-language contracts live under `middleware/` or a shared `schemas/` directory, never duplicated in each UI.

## Consequences

- CI, `.pre-commit-config.yaml`, and `justfile` recipes can all key off the top-level directory name to dispatch to the right toolchain.
- A project that doesn't need a given language simply deletes that directory.
