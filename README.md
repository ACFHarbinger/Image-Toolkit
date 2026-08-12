<div align="center">

# Single-Module-Template

**A modern, production-ready template repository for C++ projects.**

</br>

<a href="https://github.com/ACFHarbinger/Single-Module-Template/releases"><img alt="Release" src="https://img.shields.io/git/v/release/ACFHarbinger/Single-Module-Template?include_prereleases&logo=github&color=blue"></a>
<a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-AGPL_v3-blue.svg"></a>
<a href="https://isocpp.org/"><img alt="C++" src="https://img.shields.io/badge/C%2B%2B-17-00599C?logo=cplusplus&logoColor=white"></a>
<a href="https://cmake.org/"><img alt="CMake" src="https://img.shields.io/badge/CMake-Build-064F8C?logo=cmake&logoColor=white"></a>
<a href="https://github.com/casey/just"><img alt="Just" src="https://img.shields.io/badge/Just-Task_Runner-black"></a>
<a href="https://github.com/features/actions"><img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub_Actions-CI%2FCD-2088FF?logo=githubactions&logoColor=white"></a>

</div>

## About

`Single-Module-Template` is a GitHub template repository for standalone C++ projects. It ships with standard modern C++ (C++17) scaffolding including CMake build files, unit testing (GoogleTest), micro-benchmarking (Google Benchmark), CI/CD pipelines, containerized dev environments, pre-commit hooks, and LLM coding-agent instructions.

Use **"Use this template"** on GitHub to start a new C++ project immediately.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `include/` | Public C++ header files (`single_module_template/greet.hpp`) |
| `src/` | C++ implementation files (`greet.cpp`, `main.cpp`) |
| `test/` | GoogleTest unit tests (`greet_test.cpp`) |
| `benchmark/` | Google Benchmark micro-benchmarks (`greet_benchmark.cpp`) |
| `config/` | Runtime JSON configuration (`default.json`) |
| `.agent/` | LLM coding-agent prompts, rules, and workflows (`AGENTS.md`) |
| `.devcontainer/` | VS Code Dev Container definition |
| `.git/` | Issue/PR templates, GitHub Actions CI workflows |
| `infra/` | Docker containerization, Kubernetes/Helm/Terraform/Ansible manifests |
| `docs/` | Architecture notes, design documentation, MkDocs material site |
| `tools/` | Automation task scripts backing the root `justfile` |

## Quick Start

### Build and Run

```bash
# Configure build directory with CMake
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBUILD_BENCHMARK=ON

# Build all targets
cmake --build build --parallel

# Run executable
./build/single_module_template_cli

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
