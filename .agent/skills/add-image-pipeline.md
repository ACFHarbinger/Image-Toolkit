---
description: Guide for adding a new multi-step image processing pipeline (like anime_stitch_pipeline.py).
---

You are building a new image processing pipeline for Image-Toolkit. Pipelines orchestrate multiple Rust/Python/ML steps into a single callable flow.

## Architecture

```
GUI Tab  →  QRunnable Worker  →  Pipeline Class  →  Rust (base.*) / ML Model
```

- **Pipeline class** lives in `backend/src/core/<name>_pipeline.py`.
- **Worker** lives in `gui/src/helpers/core/<name>_pipeline_worker.py`.
- **Tab** lives in `gui/src/tabs/core/<name>_tab.py` (or as a subtab).

Reference implementation: `backend/src/core/anime_stitch_pipeline.py`.

---

## 1. Create the Pipeline Class

`backend/src/core/my_pipeline.py`:

```python
from pathlib import Path
from typing import Callable

class MyPipeline:
    """
    Multi-step image pipeline: [describe what it does].
    """

    def __init__(self, config: dict):
        self.config = config

    def run(
        self,
        input_paths: list[str],
        output_dir: str,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        """
        Returns list of output file paths.
        progress_cb(current, total) is called after each step.
        """
        output_paths = []
        total = len(input_paths)

        for i, path in enumerate(input_paths):
            result = self._process_one(path, output_dir)
            if result:
                output_paths.append(result)
            if progress_cb:
                progress_cb(i + 1, total)

        return output_paths

    def _process_one(self, path: str, output_dir: str) -> str | None:
        import base
        # call Rust functions here
        return base.convert_single_image(path, output_dir, "png")
```

Rules:
- No Qt imports inside pipeline classes.
- Use `progress_cb` for progress reporting — the worker will wire this to a Signal.
- Catch and log per-image errors; don't abort the whole batch.

---

## 2. Create the Worker

`gui/src/helpers/core/my_pipeline_worker.py`:

```python
from PySide6.QtCore import QRunnable, QObject, Signal
from backend.src.core.my_pipeline import MyPipeline

class MyPipelineSignals(QObject):
    progress = Signal(int, int)   # current, total
    finished = Signal(list)       # output_paths
    error    = Signal(str)

class MyPipelineWorker(QRunnable):
    def __init__(self, input_paths: list[str], output_dir: str, config: dict):
        super().__init__()
        self.input_paths = input_paths
        self.output_dir  = output_dir
        self.config      = config
        self.signals     = MyPipelineSignals()
        self.setAutoDelete(True)

    def run(self):
        try:
            pipeline = MyPipeline(self.config)
            results  = pipeline.run(
                self.input_paths,
                self.output_dir,
                progress_cb=lambda c, t: self.signals.progress.emit(c, t),
            )
            self.signals.finished.emit(results)
        except Exception as e:
            self.signals.error.emit(str(e))
```

---

## 3. Wire Up in the Tab

```python
def _run_pipeline(self):
    paths      = self._get_selected_paths()
    output_dir = self._output_dir
    config     = self._build_config()

    worker = MyPipelineWorker(paths, output_dir, config)
    worker.signals.progress.connect(self._on_progress)
    worker.signals.finished.connect(self._on_finished)
    worker.signals.error.connect(self._on_error)
    QThreadPool.globalInstance().start(worker)
    self._active_workers.add(worker)

@Slot(int, int)
def _on_progress(self, current: int, total: int):
    self.progress_bar.setValue(int(current / total * 100))

@Slot(list)
def _on_finished(self, paths: list[str]):
    self._active_workers.discard(...)
    self._load_gallery(paths)
```

---

## 4. Export

Add to `backend/src/core/__init__.py`:
```python
from .my_pipeline import MyPipeline
```

Add to `gui/src/helpers/core/__init__.py`:
```python
from .my_pipeline_worker import MyPipelineWorker
```

## Checklist
- [ ] Pipeline class has no Qt imports
- [ ] Worker emits `QImage` (not `QPixmap`) if returning image data
- [ ] `progress_cb` wired to Signal for UI updates
- [ ] `_active_workers` set prevents GC of running workers
- [ ] Pipeline tested standalone: `python -c "from backend.src.core.my_pipeline import MyPipeline; ..."`
- [ ] Full app tested: pipeline runs end-to-end without UI freeze
