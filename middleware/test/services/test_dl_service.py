"""Unit tests for headless Deep Learning and ComfyUI service (#1111)."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from middleware.src.services.dl.service import DeepLearningService
from middleware.src.sidecar.server import SidecarServer


def _running_trainer(params: dict[str, Any]) -> dict[str, Any]:
    epochs = int(params.get("epochs") or 1)
    output_dir = Path(str(params["output_dir"]))
    run_id = "run-basic"
    run_dir = output_dir / run_id
    run_dir.mkdir(parents=True)
    record = {"run_id": run_id, "status": "running", "epochs": epochs}
    (run_dir / "record.json").write_text(json.dumps(record), encoding="utf-8")
    event = {"step": 0, "total_steps": epochs}
    (run_dir / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "running",
        "started": True,
        "message": "training delegated",
    }


def _png_generator(params: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(str(params["output_dir"]))
    output_dir.mkdir(parents=True, exist_ok=True)
    count = int(params.get("num_images") or 1)
    paths: list[str] = []
    for index in range(count):
        path = output_dir / f"out_{index}.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n")
        paths.append(str(path))
    return {"status": "completed", "output_images": paths, "message": "generation delegated"}


def _score_evaluator(params: dict[str, Any]) -> dict[str, Any]:
    scores = {str(metric): 1.5 for metric in params.get("metrics") or []}
    return {"job_id": "eval-double", "status": "completed", "scores": scores, "message": "evaluation delegated"}


def _label_scorer(params: dict[str, Any]) -> dict[str, Any]:
    prompts = list(params.get("prompts") or [])
    predictions = [{"label": str(prompt), "score": 0.75} for prompt in prompts]
    return {"job_id": "infer-double", "predictions": predictions, "message": "inference delegated"}


def test_dl_service_train_and_status(tmp_path: Path) -> None:
    svc = DeepLearningService(trainer=_running_trainer)
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    out_dir = tmp_path / "runs"

    res = svc.train({
        "model_architecture": "basic_gan",
        "dataset_path": str(dataset),
        "output_dir": str(out_dir),
        "epochs": 5,
        "batch_size": 2,
    })

    assert res["started"] is True
    assert res["status"] == "running"
    run_id = res["run_id"]
    run_dir = Path(res["run_dir"])
    assert run_dir.is_dir()
    assert (run_dir / "record.json").is_file()

    status = svc.status(run_id, str(run_dir))
    assert status["run_id"] == run_id
    assert status["total_steps"] == 5
    assert status["status"] in ("running", "success")


def test_dl_service_train_missing_dataset(tmp_path: Path) -> None:
    called = False

    def trainer(_params: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called = True
        return {"started": True, "status": "running", "run_id": "should-not-run"}

    svc = DeepLearningService(trainer=trainer)
    out_dir = tmp_path / "runs"
    res = svc.train({
        "model_architecture": "basic_gan",
        "dataset_path": str(tmp_path / "missing-dataset"),
        "output_dir": str(out_dir),
    })

    assert called is False
    assert res["started"] is False
    assert res["status"] == "unavailable"
    assert "missing" in res["message"]
    assert not out_dir.exists()


def test_dl_service_cancel(tmp_path: Path) -> None:
    svc = DeepLearningService(trainer=_running_trainer)
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    out_dir = tmp_path / "runs"

    res = svc.train({
        "model_architecture": "lora",
        "dataset_path": str(dataset),
        "output_dir": str(out_dir),
        "epochs": 50,
    })
    run_id = res["run_id"]

    cancel_res = svc.cancel(run_id)
    assert cancel_res["canceled"] is False

    status = svc.status(run_id, res["run_dir"])
    assert status["run_id"] == run_id
    assert status["status"] == "running"


def test_dl_service_generate(tmp_path: Path) -> None:
    svc = DeepLearningService(generator=_png_generator)
    out_dir = tmp_path / "gen_out"

    res = svc.generate({
        "model_architecture": "sd3",
        "output_dir": str(out_dir),
        "prompt": "anime girl smiling",
        "num_images": 2,
    })

    assert res["status"] == "completed"
    assert len(res["output_images"]) == 2
    for img_path in res["output_images"]:
        p = Path(img_path)
        assert p.is_file()
        assert p.stat().st_size > 0
        assert p.read_bytes().startswith(b"\x89PNG")


def test_dl_service_evaluate(tmp_path: Path) -> None:
    svc = DeepLearningService(evaluator=_score_evaluator)
    model = tmp_path / "model.pkl"
    model.write_text("weights")
    dataset = tmp_path / "eval_data"
    dataset.mkdir()

    res = svc.evaluate({
        "model_path": str(model),
        "dataset_path": str(dataset),
        "metrics": ["fid", "kid", "precision"],
    })

    assert res["status"] == "completed"
    assert "fid" in res["scores"]
    assert "kid" in res["scores"]
    assert "precision" in res["scores"]
    assert res["scores"]["fid"] > 0


def test_dl_service_infer(tmp_path: Path) -> None:
    svc = DeepLearningService(scorer=_label_scorer)
    img = tmp_path / "input.png"
    img.write_text("fake image")

    res = svc.infer({
        "model_version": "Meta CLIP 2",
        "image_path": str(img),
        "prompts": ["anime", "photo", "sketch"],
    })

    assert len(res["predictions"]) == 3
    assert res["predictions"][0]["label"] == "anime"
    assert res["predictions"][0]["score"] > 0


def test_dl_service_comfy() -> None:
    fake_mgr = MagicMock()
    fake_mgr.state.value = "Ready"
    fake_mgr.url = "http://127.0.0.1:8188"
    fake_mgr.port = 8188
    fake_mgr.owns_server = True
    fake_mgr.queue_workflow.return_value = "prompt-123"

    fake_run = MagicMock()
    fake_run.status.value = "Completed"
    fake_run.output_paths = ("output/image1.png", "output/image2.png")
    fake_mgr.get_run.return_value = fake_run

    svc = DeepLearningService(comfy_manager=fake_mgr)

    st = svc.comfy_status(probe=True)
    assert st["state"] == "Ready"
    assert st["ready"] is True
    assert st["port"] == 8188

    start_res = svc.comfy_start(port=8188)
    assert start_res["success"] is True

    stop_res = svc.comfy_stop()
    assert stop_res["stopped"] is True
    fake_mgr.stop.assert_called_once()

    queue_res = svc.comfy_queue({"3": {"class_type": "KSampler"}})
    assert queue_res["queued"] is True
    assert queue_res["prompt_id"] == "prompt-123"

    run_res = svc.comfy_run_status("prompt-123")
    assert run_res["completed"] is True
    assert len(run_res["output_images"]) == 2


def test_sidecar_dl_dispatch(tmp_path: Path) -> None:
    dataset = tmp_path / "data"
    dataset.mkdir()
    out = tmp_path / "out"
    out.mkdir()
    model = out / "model.pt"
    model.write_text("weights")
    image = out / "img.png"
    image.write_bytes(b"png")

    def trainer(_params: dict[str, Any]) -> dict[str, Any]:
        run_dir = out / "run-dispatch"
        run_dir.mkdir()
        (run_dir / "record.json").write_text(
            json.dumps({"run_id": "run-dispatch", "status": "running", "epochs": 2}),
            encoding="utf-8",
        )
        (run_dir / "events.jsonl").write_text(
            json.dumps({"step": 1, "total_steps": 2, "loss": 0.5}) + "\n",
            encoding="utf-8",
        )
        return {
            "run_id": "run-dispatch",
            "run_dir": str(run_dir),
            "status": "running",
            "started": True,
            "message": "training delegated",
        }

    def generator(_params: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": "gen-dispatch",
            "status": "completed",
            "output_images": [str(out / "gen.png")],
            "message": "generation delegated",
        }

    svc = DeepLearningService(
        trainer=trainer,
        generator=generator,
        evaluator=_score_evaluator,
        scorer=_label_scorer,
    )
    server = SidecarServer(
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        dl_service=svc,
    )

    # Handshake
    handshake_frame = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "system.handshake",
        "params": {
            "protocol": "image-toolkit-bridge",
            "client": {"name": "test", "version": "1.0.0"},
        },
    }
    res = server.handle_frame(handshake_frame)
    assert res.get("result", {}).get("protocol") == "image-toolkit-bridge"

    # dl.train
    train_frame = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "dl.train",
        "params": {
            "model_architecture": "basic_gan",
            "dataset_path": str(dataset),
            "output_dir": str(out),
            "epochs": 2,
        },
    }
    train_res = server.handle_frame(train_frame)
    assert "result" in train_res
    run_id = train_res["result"]["run_id"]

    # dl.status
    status_frame = {
        "jsonrpc": "2.0",
        "id": "3",
        "method": "dl.status",
        "params": {"run_id": run_id, "run_dir": str(out / "run-dispatch")},
    }
    status_res = server.handle_frame(status_frame)
    assert "result" in status_res
    assert status_res["result"]["run_id"] == run_id

    # dl.cancel
    cancel_frame = {
        "jsonrpc": "2.0",
        "id": "4",
        "method": "dl.cancel",
        "params": {"run_id": run_id},
    }
    cancel_res = server.handle_frame(cancel_frame)
    assert "result" in cancel_res
    assert cancel_res["result"]["canceled"] is False

    # dl.generate
    gen_frame = {
        "jsonrpc": "2.0",
        "id": "5",
        "method": "dl.generate",
        "params": {
            "model_architecture": "sd3",
            "output_dir": str(out),
            "num_images": 1,
        },
    }
    gen_res = server.handle_frame(gen_frame)
    assert "result" in gen_res
    assert len(gen_res["result"]["output_images"]) == 1

    # dl.evaluate
    eval_frame = {
        "jsonrpc": "2.0",
        "id": "6",
        "method": "dl.evaluate",
        "params": {
            "model_path": str(out / "model.pt"),
            "dataset_path": str(dataset),
            "metrics": ["fid"],
        },
    }
    eval_res = server.handle_frame(eval_frame)
    assert "result" in eval_res
    assert "fid" in eval_res["result"]["scores"]

    # dl.infer
    infer_frame = {
        "jsonrpc": "2.0",
        "id": "7",
        "method": "dl.infer",
        "params": {
            "model_version": "Meta CLIP 2",
            "image_path": str(out / "img.png"),
            "prompts": ["a", "b"],
        },
    }
    infer_res = server.handle_frame(infer_frame)
    assert "result" in infer_res
    assert len(infer_res["result"]["predictions"]) == 2
