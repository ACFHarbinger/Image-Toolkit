# Python packages

The uv workspace builds two distributions:

| Distribution | Imports | Responsibility |
| --- | --- | --- |
| `cel-shaded-generator` | `colorization`, `features`, `learning`, `project`, `rigging`, `temporal`, `execution`, `runtime` | Core algorithms, projects, isolated jobs |
| `cel-shaded-generator-gui` | `cel_shaded_generator_gui` | PySide6 demonstration application |

The GUI declares the core distribution as a dependency. The core never imports
Qt or Image-Toolkit. The core package (source, tests, benchmarks, and dev
tooling) lives under `logic/` (`logic/src/`, `logic/test/`, `logic/benchmark/`,
`logic/validation/`, its own `logic/pyproject.toml`); GUI tests live in
`gui/test/`. Both packages require Python 3.11 or newer.
