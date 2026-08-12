# Testing Guide

Unit tests are written in C++ using **GoogleTest** and registered with **CTest**.

| Component | Framework | Command |
| --- | --- | --- |
| C++ Unit Tests | GoogleTest | `just test` or `ctest --test-dir build --output-on-failure` |
| Micro-benchmarks | Google Benchmark | `just bench` |

## Running Tests

```bash
# Configure with testing enabled
cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTING=ON

# Build test executable
cmake --build build --target hybrid_image_editor_tests

# Run test suite via CTest
ctest --test-dir build --output-on-failure
```

## Test Structure

Tests live in `logic/test/greet_test.cpp` and are discovered automatically using GoogleTest's `gtest_discover_tests`.

## Coverage

CI uploads coverage reports to [Codecov](https://codecov.io/); thresholds are configured in [`git/codecov.yaml`](../git/codecov.yaml).
