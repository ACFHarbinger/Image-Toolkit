"""Headless Deep Learning and ComfyUI service (#1111).

Provides training run control, generative synthesis, evaluation,
zero-shot inference, and ComfyUI server/queue management behind
sidecar capability methods without Qt or top-level torch/numpy dependencies.
"""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from typing import Any, Callable

from middleware.src.services.dl.inspect import inspect_run

_TRAINING_MODULE: Any = None


def _get_training_runs_module() -> Any:
    """Load core.training_runs without executing core/__init__.py."""
    global _TRAINING_MODULE
    if _TRAINING_MODULE is not None:
        return _TRAINING_MODULE
    path = Path(__file__).resolve().parents[2] / "core" / "training_runs.py"
    name = "middleware.src.services.dl._training_runs_pure"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    _TRAINING_MODULE = module
    return module


class DeepLearningService:
    """Headless service coordinator for Deep Learning and ComfyUI runs."""

    def __init__(
        self,
        comfy_manager: Any = None,
        *,
        trainer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        generator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        evaluator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        scorer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self._comfy_manager = comfy_manager
        self._trainer = trainer
        self._generator = generator
        self._evaluator = evaluator
        self._scorer = scorer
        self._active_runs: dict[str, dict[str, Any]] = {}
        self._runs_lock = threading.Lock()

    def inspect(self, run_dir: str) -> dict[str, Any]:
        """Inspect a caller run directory."""
        return inspect_run(run_dir)

    def train(self, params: dict[str, Any]) -> dict[str, Any]:
        """Start a training run when a trainer engine is injected."""
        dataset_raw = params.get("dataset_path")
        dataset_path = Path(str(dataset_raw)) if dataset_raw not in (None, "") else None
        if dataset_path is None or not dataset_path.is_dir():
            shown = "" if dataset_raw in (None, "") else str(dataset_raw)
            message = "dataset is missing" if not shown else f"dataset is missing: {shown}"
            return {
                "started": False,
                "status": "unavailable",
                "message": message,
            }
        if self._trainer is None:
            return {
                "started": False,
                "status": "unavailable",
                "message": "training engine is unavailable",
            }
        return self._trainer(params)

    def status(self, run_id: str, run_dir: str | None = None) -> dict[str, Any]:
        """Query execution and telemetry status for a training run."""
        with self._runs_lock:
            active = self._active_runs.get(run_id)
            if active is not None:
                step = active["step"]
                return {
                    "run_id": run_id,
                    "status": active["status"],
                    "step": step,
                    "total_steps": active["total_steps"],
                    "loss": active.get("loss"),
                    "events_count": step + 1,
                    "message": f"Training {active['status']}",
                }

        tr = _get_training_runs_module()
        target_dir = Path(run_dir) if run_dir else None
        if target_dir is None or not target_dir.is_dir():
            target_dir = tr.default_runs_root() / run_id
        if not target_dir.is_dir():
            return {
                "run_id": run_id,
                "status": "not_found",
                "step": 0,
                "total_steps": 0,
                "loss": None,
                "events_count": 0,
                "message": f"Run directory not found for {run_id}",
            }

        record = tr.read_run_record(target_dir) or {}
        events = list(tr.iter_events(target_dir))
        latest_event = events[-1] if events else {}
        step = int(latest_event.get("step") or 0)
        total_steps = int(latest_event.get("total_steps") or record.get("epochs") or 0)
        loss = latest_event.get("loss")
        if loss is not None:
            loss = float(loss)

        return {
            "run_id": run_id,
            "status": str(record.get("status") or "unknown"),
            "step": step,
            "total_steps": total_steps,
            "loss": loss,
            "events_count": len(events),
            "message": f"Run status {record.get('status')}",
        }

    def cancel(self, run_id: str) -> dict[str, Any]:
        """Cancel an in-flight training run."""
        with self._runs_lock:
            active = self._active_runs.get(run_id)
            if active is not None:
                active["cancel"].set()
                active["status"] = "cancel"
                tr = _get_training_runs_module()
                tr.finish_run(active["run_dir"], tr.STATUS_CANCEL)
                return {
                    "run_id": run_id,
                    "canceled": True,
                    "message": f"Run {run_id} canceled",
                }
        return {
            "run_id": run_id,
            "canceled": False,
            "message": f"Run {run_id} is not active",
        }

    def generate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run generative synthesis when a generator engine is injected."""
        if self._generator is None:
            return {
                "status": "unavailable",
                "output_images": [],
                "message": "generation engine is unavailable",
            }
        return self._generator(params)

    def evaluate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Score a model when an evaluator engine is injected."""
        missing: list[str] = []
        model_raw = params.get("model_path")
        dataset_raw = params.get("dataset_path")
        if model_raw in (None, "") or not Path(str(model_raw)).exists():
            missing.append(
                "model path is missing"
                if model_raw in (None, "")
                else f"model path is missing: {model_raw}"
            )
        if dataset_raw in (None, "") or not Path(str(dataset_raw)).exists():
            missing.append(
                "dataset path is missing"
                if dataset_raw in (None, "")
                else f"dataset path is missing: {dataset_raw}"
            )
        if missing:
            return {
                "status": "unavailable",
                "scores": {},
                "message": "; ".join(missing),
            }
        if self._evaluator is None:
            return {
                "status": "unavailable",
                "scores": {},
                "message": "evaluation engine is unavailable",
            }
        return self._evaluator(params)

    def infer(self, params: dict[str, Any]) -> dict[str, Any]:
        """Score prompts for an image when a scorer engine is injected."""
        image_raw = params.get("image_path")
        if image_raw in (None, "") or not Path(str(image_raw)).exists():
            shown = "" if image_raw in (None, "") else str(image_raw)
            message = "image is missing" if not shown else f"image is missing: {shown}"
            return {
                "predictions": [],
                "status": "unavailable",
                "message": message,
            }
        if self._scorer is None:
            return {
                "predictions": [],
                "status": "unavailable",
                "message": "inference engine is unavailable",
            }
        return self._scorer(params)

    # ------------------------------------------------------------------
    # ComfyUI Integration
    # ------------------------------------------------------------------

    def _get_comfy_manager(self) -> Any:
        if self._comfy_manager is not None:
            return self._comfy_manager
        from middleware.src.models.core.comfy_manager import ComfyUIManager

        self._comfy_manager = ComfyUIManager.instance()
        return self._comfy_manager

    def comfy_status(self, probe: bool = False) -> dict[str, Any]:
        """Get ComfyUI server state and readiness."""
        mgr = self._get_comfy_manager()
        if probe:
            mgr.refresh_state(publish=False)
        state_str = mgr.state.value if hasattr(mgr.state, "value") else str(mgr.state)
        return {
            "state": state_str,
            "url": str(mgr.url),
            "port": int(mgr.port),
            "owns_server": bool(mgr.owns_server),
            "ready": state_str.lower() == "ready",
        }

    def comfy_start(
        self,
        port: int = 8188,
        enable_manager: bool = False,
        external: bool = False,
    ) -> dict[str, Any]:
        """Start or connect to a ComfyUI server instance."""
        mgr = self._get_comfy_manager()
        if external:
            mgr.connect(port=port)
        else:
            mgr.start(port=port, enable_manager=enable_manager)
        state_str = mgr.state.value if hasattr(mgr.state, "value") else str(mgr.state)
        return {
            "port": int(mgr.port),
            "url": str(mgr.url),
            "state": state_str,
            "success": True,
            "message": f"ComfyUI server at {mgr.url}",
        }

    def comfy_stop(self) -> dict[str, Any]:
        """Stop the managed ComfyUI server instance."""
        mgr = self._get_comfy_manager()
        mgr.stop()
        return {"stopped": True, "message": "ComfyUI server stopped"}

    def comfy_queue(
        self,
        workflow: dict[str, Any],
        client_id: str | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Queue a ComfyUI workflow graph with optional overrides."""
        mgr = self._get_comfy_manager()
        if overrides:
            workflow = mgr.apply_overrides(workflow, overrides)
        prompt_id = mgr.queue_workflow(workflow, client_id=client_id)
        return {
            "prompt_id": str(prompt_id),
            "queued": True,
            "message": f"Prompt {prompt_id} queued",
        }

    def comfy_run_status(self, prompt_id: str) -> dict[str, Any]:
        """Get execution and output status for a queued ComfyUI prompt."""
        mgr = self._get_comfy_manager()
        run = mgr.get_run(prompt_id)
        if run is None:
            return {
                "prompt_id": prompt_id,
                "status": "Pending",
                "completed": False,
                "output_images": [],
                "message": "Run pending or not found in provenance tracker",
            }
        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
        completed = status_val.lower() == "completed"
        output_images = list(run.output_paths) if hasattr(run, "output_paths") else []
        return {
            "prompt_id": prompt_id,
            "status": status_val,
            "completed": completed,
            "output_images": output_images,
            "message": f"Run status {status_val}",
        }
