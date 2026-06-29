---
description: Guide for adding a new C++ function to base/ and exposing it to Python via pybind11.
---

You are a C++/pybind11 expert working on the Image-Toolkit `base/` module.

## Task: Add a New C++ Function Exposed to Python

### 1. Write the C++ Function

Add your function to the appropriate source file under `base/src/` (or create a new module file).

```cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>
#include <string>
#ifdef _OPENMP
#  include <omp.h>
#endif

namespace py = pybind11;

namespace base::core {

std::vector<std::string>
my_new_function(const std::vector<std::string>& input) {
    int N = static_cast<int>(input.size());
    std::vector<std::string> results(N);
    // CPU-heavy work — release GIL around OpenMP parallel region
    {
        py::gil_scoped_release release;
        #pragma omp parallel for schedule(dynamic)
        for (int i = 0; i < N; ++i) {
            std::string s = input[i];
            for (char& c : s) c = std::toupper(c);
            results[i] = std::move(s);
        }
    }
    return results;
}

} // namespace base::core
```

**Key rules:**
- Release the GIL with `py::gil_scoped_release` before any OpenMP parallel region.
- Use `#pragma omp parallel for schedule(dynamic)` for parallelism over collections.
- Return plain C++ types (`std::vector<std::string>`, `bool`, `uint32_t`, `float`); pybind11 converts them automatically.
- Complex output types need `py::class_<T>` registration.

### 2. Register in `bindings.cpp`

In `base/src/bindings.cpp`, declare the registration function and call it:

```cpp
// Forward declaration (top of bindings.cpp, with the other register_ declarations)
void register_my_module(py::module_& m);

// In PYBIND11_MODULE body, add a submodule and call it:
auto m_mine = m.def_submodule("mymodule", "My new submodule.");
register_my_module(m_mine);
```

In your source file, define `register_my_module`:

```cpp
void register_my_module(py::module_& m) {
    m.def("my_new_function",
        [](const std::vector<std::string>& input) {
            return base::core::my_new_function(input);
        },
        py::arg("input"),
        "Uppercase each string in *input*. Returns list[str].");
}
```

### 3. Rebuild the Module

```bash
source .venv/bin/activate
just build-base
```

For a release build:
```bash
just build-base-release
```

### 4. Write a Python Wrapper (if needed)

Keep wrappers thin. In `backend/src/core/<feature>.py`:

```python
import base

def my_feature(items: list[str]) -> list[str]:
    return base.mymodule.my_new_function(items)
```

### 5. Verify

```bash
source .venv/bin/activate
python -c "import base; print(base.mymodule.my_new_function(['hello', 'world']))"
```

### 6. Add Tests

Add a test in `backend/test/test_<feature>.py` that covers:
- Normal input
- Empty input
- Large input (to validate parallelism doesn't race)

Run with: `pytest backend/test/test_<feature>.py`

## Checklist
- [ ] GIL released via `py::gil_scoped_release` for CPU work
- [ ] Registered in `base/src/bindings.cpp` via a `register_*` function
- [ ] `just build-base` succeeded
- [ ] `import base; base.mymodule.my_new_function(...)` works from Python REPL
- [ ] C++ tests pass: `just test-base-cpp`
