# Architectural Analysis Prompt

**Intent:** Use Chain-of-Thought reasoning to explore the Python/Rust boundary in Image-Toolkit.

## The Prompt

I need to understand the interface between the high-performance Rust core and the Python backend.

Using **Chain-of-Thought reasoning**, analyze the relationship between:
- The Rust bindings in `base/src/lib.rs` (specifically image processing or scanning functions).
- The Python wrapper in `backend/src/core/` (e.g., `wallpaper_manager.py` or image service).
- The data structures passed: Paths, Image Buffers (PyBytes), or NumPy arrays.

Explain potential bottlenecks in data marshalling (e.g., is image data being copied unnecessarily?) and suggest if `PyO3` usage is optimized (e.g., using `PyBuffer` protocol) based on the provided code.