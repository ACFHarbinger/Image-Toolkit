---
description: Guide for adding a new Rust function to base/ and exposing it to Python via PyO3.
---

You are a Rust/PyO3 expert working on the Image-Toolkit `base/` module.

## Task: Add a New Rust Function Exposed to Python

### 1. Write the Rust Function

Add your function to the appropriate source file under `base/src/` (or create a new module file). Always gate with `#[cfg(feature = "python")]`.

```rust
#[cfg(feature = "python")]
use pyo3::prelude::*;

#[cfg(feature = "python")]
#[pyfunction]
pub fn my_new_function(py: Python, input: Vec<String>) -> PyResult<Vec<String>> {
    // CPU-heavy work: release the GIL so Python threads continue
    let results = py.detach(|| {
        use rayon::prelude::*;
        input.par_iter().map(|s| s.to_uppercase()).collect()
    });
    Ok(results)
}
```

**Key rules:**
- Use `py.detach(|| { ... })` (PyO3 ≥ 0.23) for any blocking/CPU work — this releases the GIL.
- Use `rayon::par_iter()` for parallelism over collections.
- Return `PyResult<T>` and propagate errors with `?`.
- `Vec<String>`, `bool`, `u32`, `f32` map directly. Complex types need `#[pyclass]`.

### 2. Register in `lib.rs`

In `base/src/lib.rs`, add the import and register the function:

```rust
// If in a submodule:
mod my_module;
use my_module::my_new_function;

// Inside the #[pymodule] fn base(...):
#[cfg(feature = "python")]
#[pymodule]
fn base(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // existing functions...
    m.add_function(wrap_pyfunction!(my_new_function, m)?)?;
    Ok(())
}
```

### 3. Rebuild the Module

```bash
source .venv/bin/activate
cd base && maturin develop --features python
```

For a release build (faster at runtime):
```bash
maturin develop --release --features python
```

### 4. Write a Python Wrapper (if needed)

Keep wrappers thin. In `backend/src/core/<feature>.py`:

```python
import base

def my_feature(items: list[str]) -> list[str]:
    return base.my_new_function(items)
```

### 5. Verify

```bash
source .venv/bin/activate
python -c "import base; print(base.my_new_function(['hello', 'world']))"
```

### 6. Add Tests

Add a test in `backend/test/test_<feature>.py` that covers:
- Normal input
- Empty input
- Large input (to validate parallelism doesn't race)

Run with: `pytest backend/test/test_<feature>.py`

## Checklist
- [ ] Function gated with `#[cfg(feature = "python")]`
- [ ] GIL released via `py.detach()` for CPU work
- [ ] Registered in `lib.rs` `#[pymodule]`
- [ ] `maturin develop --features python` succeeded
- [ ] `import base; base.my_new_function(...)` works from Python REPL
- [ ] Rust tests pass: `cd base && cargo test`
