# Development Guide

## Prerequisites

- C++17 compatible compiler (GCC 9+, Clang 10+, MSVC 2019+)
- CMake 3.20+
- Git, [`just`](https://github.com/casey/just), `pre-commit`

## Local Setup

```bash
git clone https://github.com/ACFHarbinger/Hybrid-Image-Editor.git
cd Hybrid-Image-Editor
cp .env.example .env
just setup
```

## Build and Test

```bash
# Using Just task runner
just build
just test
just bench
just lint

# Using CMake directly
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DBUILD_BENCHMARK=ON
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

## Containerized Dev Environment

Open the repo in VS Code and choose "Reopen in Container" — see [`.devcontainer/devcontainer.json`](../.devcontainer/devcontainer.json). Or run with:

```bash
docker compose -f infra/global/docker/docker-compose.yml up
```

## Common Tasks

| Task | Command |
| --- | --- |
| Run all tests | `just test` |
| Run linters | `just lint` |
| Run benchmarks | `just bench` |
| Build docs | `just docs` |
| Build & start Docker stack | `just docker-up` |
