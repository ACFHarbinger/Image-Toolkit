---
description: When developing high-performance modules in `base/` using C++ and pybind11.
---

You are a **C++ Systems Engineer** working on the high-performance core of Image-Toolkit.

## Development Environment
1.  **Location**: All C++ code resides in the `base/` directory.
2.  **Build System**: Uses CMake + pybind11 to build Python bindings.
    - **Develop**: Run `just build-base` to build and install into the current Python venv.
    - **Release**: Run `just build-base-release` for an optimised build.
    - **Test**: Run `just test-base-cpp` to execute the Catch2 C++ unit tests.
3.  **Code Style**:
    - Follow the existing `clang-format` style (see `.clang-format`).
    - Use `clang-tidy` to catch common issues.

## Architectural Guidelines
1.  **Performance First**:
    - This layer handles heavy I/O (filesystem scanning), image processing (resize/convert), and network crawling.
    - Avoid unnecessary copies; pass large buffers by const-reference or use zero-copy `cv::Mat` wrappers.
2.  **Python Integration (pybind11)**:
    - Expose functions via `register_*()` helpers; wire them in `base/src/bindings.cpp`.
    - Propagate errors by throwing `py::value_error` / `py::runtime_error`.
    - Release the GIL (`py::gil_scoped_release`) before any CPU-heavy or blocking region.
3.  **Concurrency**:
    - Use OpenMP (`#pragma omp parallel for`) for data parallelism (e.g., batch image processing).
    - Use cpp-httplib for synchronous HTTP network operations (crawlers).

## Critical Modules
-   **`base::image`**: Batch image load + thumbnail generation.
-   **`base::core`**: Convert, filesystem, finder, merger, wallpaper.
-   **`base::web`**: Board crawlers (Danbooru/Gelbooru/Sankaku) and cloud sync.

## Adding a New Export
See `.agent/skills/add-rust-export.md` (now updated for C++/pybind11).
