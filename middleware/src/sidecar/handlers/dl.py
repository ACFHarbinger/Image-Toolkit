"""Sidecar handlers for Deep Learning and ComfyUI capabilities (#912, #1111)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.dl.inspect import inspect_run
from middleware.src.services.dl.service import DeepLearningService


def handle_inspect(params: dict[str, Any]) -> dict[str, Any]:
    return inspect_run(str(params["run_dir"]))


def handle_train(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.train(params)


def handle_status(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.status(str(params["run_id"]), params.get("run_dir"))


def handle_cancel(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.cancel(str(params["run_id"]))


def handle_generate(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.generate(params)


def handle_evaluate(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.evaluate(params)


def handle_infer(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.infer(params)


def handle_comfy_status(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.comfy_status(bool(params.get("probe", False)))


def handle_comfy_start(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    port = int(params.get("port") or 8188)
    enable_manager = bool(params.get("enable_manager", False))
    external = bool(params.get("external", False))
    return svc.comfy_start(port=port, enable_manager=enable_manager, external=external)


def handle_comfy_stop(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.comfy_stop()


def handle_comfy_queue(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    workflow = params["workflow"]
    client_id = params.get("client_id")
    overrides = params.get("overrides")
    return svc.comfy_queue(workflow, client_id=client_id, overrides=overrides)


def handle_comfy_run_status(service: DeepLearningService | None, params: dict[str, Any]) -> dict[str, Any]:
    svc = service or DeepLearningService()
    return svc.comfy_run_status(str(params["prompt_id"]))
