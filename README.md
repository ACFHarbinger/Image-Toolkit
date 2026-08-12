<div align="center">

# Hybrid-Image-Editor (HIE)

**Core hybrid image editing C++ logic and polyglot module for Image-Toolkit.**

</br>

<a href="https://github.com/ACFHarbinger/Hybrid-Image-Editor/releases"><img alt="Release" src="https://img.shields.io/git/v/release/ACFHarbinger/Hybrid-Image-Editor?include_prereleases&logo=github&color=blue"></a>
<a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-AGPL_v3-blue.svg"></a>
<a href="https://isocpp.org/"><img alt="C++" src="https://img.shields.io/badge/C%2B%2B-17-00599C?logo=cplusplus&logoColor=white"></a>
<a href="https://cmake.org/"><img alt="CMake" src="https://img.shields.io/badge/CMake-Build-064F8C?logo=cmake&logoColor=white"></a>
<a href="https://github.com/casey/just"><img alt="Just" src="https://img.shields.io/badge/Just-Task_Runner-black"></a>
<a href="https://github.com/features/actions"><img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub_Actions-CI%2FCD-2088FF?logo=githubactions&logoColor=white"></a>

</div>

## About

`Hybrid-Image-Editor (HIE)` is the high-performance C++ logic engine and polyglot workspace for the Image-Toolkit ecosystem. It provides modern C++ (C++17) algorithm implementations, CMake build files, unit testing (GoogleTest), micro-benchmarking (Google Benchmark), CI/CD pipelines, containerized dev environments, pre-commit hooks, and LLM coding-agent instructions.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `logic/include/` | Public C++ header files |
| `logic/src/` | C++ implementation files (`greet.cpp`, `main.cpp`) |
| `logic/test/` | GoogleTest unit tests (`greet_test.cpp`) |
| `logic/benchmark/` | Google Benchmark micro-benchmarks (`greet_benchmark.cpp`) |
| `config/` | Runtime JSON configuration (`default.json`) |
| `.agent/` | LLM coding-agent prompts, rules, and workflows (`AGENTS.md`) |
| `.devcontainer/` | VS Code Dev Container definition |
| `.git/` | Issue/PR templates, GitHub Actions CI workflows |
| `infra/` | Docker containerization, Kubernetes/Helm/Terraform/Ansible manifests |
| `docs/` | Architecture notes, design documentation, MkDocs material site |
| `middleware/` | Python orchestration, bindings, and ML integrations |
| `frontend/` | Tauri UI, embeddable in Image-Toolkit or runnable standalone |
| `gui/` | PySide6 UI, embeddable in Image-Toolkit or runnable standalone |
| `tools/` | Automation task scripts backing the root `justfile` |

## Quick Start

### Build and Run

```bash
# Configure build directory with CMake
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBUILD_BENCHMARK=ON

# Build all targets
cmake --build build --parallel

# Run executable
./build/hybrid_image_editor_cli

# Run tests
ctest --test-dir build --output-on-failure
```

### Task Runner (Just)

If you have `just` installed:

```bash
just build    # Build C++ project
just test     # Run test suite
just bench    # Run micro-benchmarks
just lint     # Check code formatting
just docs     # Build documentation site
```

## License

This project is dual-licensed:

- **Open source (free) — GNU AGPL-3.0.** See [LICENSE](LICENSE).
- **Commercial (paid).** See [LICENSE](LICENSE).
