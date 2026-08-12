# Architecture

`Single-Module-Template` is structured as a single C++ module repository.

## Overview

The repository isolates header interfaces, source implementations, unit tests, performance benchmarks, and configuration assets into clear directory boundaries.

## Module Structure

| Directory | Language / Tool | Responsibility |
| --- | --- | --- |
| `include/` | C++ (Headers) | Public C++ header files (`single_module_template/`) |
| `src/` | C++ (Sources) | Implementation of C++ library components and CLI |
| `test/` | C++ / GoogleTest | Automated unit test suite |
| `benchmark/` | C++ / Google Benchmark | Micro-benchmarking suite |
| `config/` | JSON | Runtime configuration assets |

## Build System

Built using CMake 3.20+ targeting C++17 standard.
- Library target: `single_module_template_lib`
- CLI executable target: `single_module_template_cli`
- Unit tests target: `single_module_template_tests`
- Benchmark target: `single_module_template_benchmark`

## C4 Diagrams

See [`docs/structurizr/`](structurizr/README.md) for the rendered C4 model.

## Architecture Decision Records

Significant architecture decisions are recorded under [`docs/adr/`](adr/).
