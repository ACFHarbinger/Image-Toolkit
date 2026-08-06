# Python packages

The uv workspace builds two distributions:

| Distribution | Import | Responsibility |
| --- | --- | --- |
| `cel-shaded-generator` | `cel_shaded_generator` | Core algorithms, projects, isolated jobs |
| `cel-shaded-generator-gui` | `cel_shaded_generator_gui` | PySide6 demonstration application |

The GUI declares the core distribution as a dependency. The core never imports
Qt or Image-Toolkit. Tests live in `test/` and `gui/test/`; benchmarks live in
`benchmark/`. Both packages require Python 3.11 or newer.
