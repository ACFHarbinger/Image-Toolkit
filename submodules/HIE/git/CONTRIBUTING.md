# Contributing to Hybrid-Image-Editor (HIE)

[![C++](https://img.shields.io/badge/C%2B%2B-17-00599C?logo=cplusplus&logoColor=white)](https://isocpp.org/)
[![CMake](https://img.shields.io/badge/CMake-Build-064F8C?logo=cmake&logoColor=white)](https://cmake.org/)
[![CI](https://github.com/ACFHarbinger/Hybrid-Image-Editor/actions/workflows/ci.yml/badge.svg)](https://github.com/ACFHarbinger/Hybrid-Image-Editor/actions/workflows/ci.yml)

> **Version**: 1.0
> **Last Updated**: 2026-08-06

Thank you for your interest in contributing to `Hybrid-Image-Editor (HIE)`!

---

## 1. Getting Started

### 1.1 Prerequisites

- C++17 compiler (GCC 9+, Clang 10+, MSVC 2019+)
- CMake 3.20+
- [`just`](https://github.com/casey/just) command runner
- `pre-commit`

### 1.2 Bootstrap

```bash
git clone https://github.com/ACFHarbinger/Hybrid-Image-Editor.git
cd Hybrid-Image-Editor
cp .env.example .env
just setup
```

## 2. Development & Testing

```bash
just build    # Build C++ library & executable
just test     # Run GoogleTest suite
just bench    # Run micro-benchmarks
just lint     # Check formatting
```

## 3. Code Style Guidelines

Follow the C++ guidelines in [`.agent/rules/cpp.md`](../.agent/rules/cpp.md). Format code with `clang-format`.

## 4. Pull Request Process

1. Ensure all tests pass (`just test`) and formatting is checked (`just lint`).
2. Submit PR against `main`.
