# Architecture

`Hybrid-Image-Editor (HIE)` is structured as a C++ logic core module.

## Overview

The repository isolates header interfaces, source implementations, unit tests, performance benchmarks, and configuration assets into clear directory boundaries under `logic/`.

## Module Structure

| Directory | Language / Tool | Responsibility |
| --- | --- | --- |
| `logic/include/` | C++ (Headers) | Public C++ logic interfaces |
| `logic/src/` | C++ (Sources) | Implementation of C++ library components and CLI |
| `logic/test/` | C++ / GoogleTest | Automated unit test suite |
| `logic/benchmark/` | C++ / Google Benchmark | Micro-benchmarking suite |
| `middleware/` | Python | Orchestration, C++ bindings, models, RL policies, optimization jobs, and pipelines |
| `frontend/` | TypeScript/Tauri | Web-native desktop UI |
| `gui/` | Python/PySide6 | Native Qt desktop UI |
| `config/` | JSON | Runtime configuration assets |

## Build System

Built using CMake 3.20+ targeting C++17 standard.
- Library target: `hybrid_image_editor_logic`
- CLI executable target: `hybrid_image_editor_cli`
- Unit tests target: `hybrid_image_editor_tests`
- Benchmark target: `hybrid_image_editor_benchmark`

## C4 Diagrams

See [`docs/structurizr/`](structurizr/README.md) for the rendered C4 model.

## Architecture Decision Records

Significant architecture decisions are recorded under [`docs/adr/`](adr/).
