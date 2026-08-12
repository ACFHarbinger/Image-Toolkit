# HIE Middleware Logic Bridge (`middleware/logic_bridge/`)

The `logic_bridge` package contains C++ pybind11 and C-ABI wrapper bindings interfacing Python middleware with performance-critical native modules in `logic/`.

## Key Bindings

- **DAG Evaluator Wrapper (`logic_bridge/render_graph.cpp` / `.py`):** Exposes C++ topological render graph evaluation and dirty-region caching to Python.
- **Document Data Model Bridge (`logic_bridge/document.cpp` / `.py`):** Zero-copy NumPy / PyTorch tensor memory sharing for multi-modal `Sequence[Frame]` raster buffers.
- **Solvers Bridge (`logic_bridge/solvers.cpp` / `.py`):** Exposes C++ Min-Cut/Max-Flow DP seam routing, GNC-TLS alignment, PSO, and Differential Evolution solvers.

## Memory & Threading Rules

1. Zero-copy buffer views must be used wherever possible when transferring image data between NumPy / PyTorch arrays and C++ Eigen / OpenCV matrices.
2. GIL (Global Interpreter Lock) must be released (`py::gil_scoped_release`) during intensive C++ computation.
