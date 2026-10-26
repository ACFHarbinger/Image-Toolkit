# Dependencies

`pyproject.toml` defines the core Python distribution and uv workspace;
`gui/pyproject.toml` defines the PySide6 client and its explicit core dependency.
`uv.lock` is the reproducible development lock file.

Current runtime categories are NumPy/SciPy/scikit-image/PyMaxflow for numerical
algorithms, headless OpenCV for image operations, and PySide6 in the GUI only.
Native-heavy built-ins run in isolated local processes. No dependency requires
network access at runtime.

See [DEPENDENCY_POLICY.md](DEPENDENCY_POLICY.md) before adding packages. Do not
add an ML framework until a selected local model and measured use case require
it; consumer NVIDIA support alone is not justification for dependency weight.
