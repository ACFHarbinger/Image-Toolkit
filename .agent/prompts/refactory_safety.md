# Refactoring Safety Prompt

**Intent:** Safely modify core logic using the Constraint pattern in Image-Toolkit.

## The Prompt

I need to modify the following core component: `[INSERT COMPONENT/FILE]`.

**Current Goal:** [Brief description of change, e.g., "Add new image filter to C++ core"].

**Strict Constraints:**
1.  **Safety**: If C++, avoid raw owning pointers; use RAII and `std::unique_ptr`. If Python, ensure no blocking I/O.
2.  **Compatibility**: Do NOT change pybind11 function signatures without updating the Python wrapper.
3.  **Severity**: According to `AGENTS.md`, this is a [CRITICAL/HIGH/MEDIUM/LOW] severity change.
4.  **Tests**: List which tests in `base/tests/` (C++) or `backend/test/` (Python) must be run.

Provide the modified code snippet and the verification plan.
