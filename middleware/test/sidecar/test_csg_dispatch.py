"""csg.* reaches the CsgService through the sidecar dispatcher
(E-03 / #916). The service factory is monkeypatched — no CSG solver runs,
no subprocess spawns."""

from __future__ import annotations

import io
from typing import Any

import pytest

from middleware.src.bridge import PROTOCOL_NAME
from middleware.src.services.csg.commands import (
    ArapDeformResult,
    ColorizeReferenceResult,
    ColorizeScribbleResult,
    TemporalPropagateResult,
)
from middleware.src.sidecar import server as server_module
from middleware.src.sidecar.server import SidecarServer


class _FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def colorize_scribble(self, command):
        self.calls.append(("colorize_scribble", command))
        return ColorizeScribbleResult(
            success=True, output_path=command.output_path, width=800, height=1200, elapsed_seconds=0.5
        )

    def colorize_reference(self, command):
        self.calls.append(("colorize_reference", command))
        return ColorizeReferenceResult(
            success=True, output_path=command.output_path, width=800, height=1200, elapsed_seconds=1.5
        )

    def arap_deform(self, command):
        self.calls.append(("arap_deform", command))
        return ArapDeformResult(
            success=True,
            output_path=command.output_path,
            num_vertices=1089,
            num_triangles=2048,
            elapsed_seconds=0.9,
        )

    def propagate_sequence(self, command):
        self.calls.append(("propagate_sequence", command))
        return TemporalPropagateResult(
            success=True,
            output_paths=tuple(f"/out/frame_{i:02}.png" for i in range(len(command.frame_paths))),
            frames_processed=len(command.frame_paths),
            elapsed_seconds=2.0,
        )


@pytest.fixture()
def server(monkeypatch) -> SidecarServer:
    fake = _FakeService()
    monkeypatch.setattr(server_module, "csg_service", lambda: fake)
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "handshake",
    )
    assert "csg" in handshake["result"]["capabilities"]
    return server


def _request(server: SidecarServer, method: str, params: dict[str, Any], request_id: str) -> dict[str, Any]:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})  # type: ignore[return-value]


def test_colorize_scribble_dispatch(server: SidecarServer) -> None:
    response = _request(
        server,
        "csg.colorize_scribble",
        {"lineart_path": "/m/line.png", "scribble_path": "/m/scrib.png", "intensity": 1.5},
        "s",
    )
    result = response["result"]
    assert result["success"] is True
    assert result["width"] == 800
    assert result["height"] == 1200
    assert result["error"] is None


def test_colorize_reference_dispatch(server: SidecarServer) -> None:
    response = _request(
        server,
        "csg.colorize_reference",
        {"lineart_path": "/m/line.png", "reference_path": "/m/ref.png", "max_iter": 250},
        "r",
    )
    assert response["result"]["success"] is True


def test_arap_deform_dispatch_builds_point_tuples(server: SidecarServer) -> None:
    response = _request(
        server,
        "csg.arap_deform",
        {
            "image_path": "/m/char.png",
            "control_points": [[10, 20], [30, 40]],
            "target_points": [[15, 25], [35, 45]],
            "mesh_resolution": 64,
        },
        "a",
    )
    result = response["result"]
    assert result["success"] is True
    assert result["num_vertices"] == 1089


def test_propagate_sequence_dispatch(server: SidecarServer) -> None:
    response = _request(
        server,
        "csg.propagate_sequence",
        {"frame_paths": ["/m/f0.png", "/m/f1.png", "/m/f2.png"], "keyframe_index": 1},
        "p",
    )
    result = response["result"]
    assert result["frames_processed"] == 3
    assert result["output_paths"] == ["/out/frame_00.png", "/out/frame_01.png", "/out/frame_02.png"]


def test_missing_frames_is_invalid_params(server: SidecarServer) -> None:
    response = _request(server, "csg.propagate_sequence", {"frame_paths": []}, "bad")
    assert response["error"]["data"]["code"] == "csg.invalid_params"
    assert response["error"]["data"]["details"]["field"] == "frame_paths"


def test_malformed_points_are_invalid_params(server: SidecarServer) -> None:
    response = _request(
        server,
        "csg.arap_deform",
        {"image_path": "/m/c.png", "control_points": [[1, 2]], "target_points": [[1, 2, 3]]},
        "bad",
    )
    assert response["error"]["data"]["code"] == "csg.invalid_params"
    assert response["error"]["data"]["details"]["field"] == "target_points"


def test_unknown_csg_method_is_method_not_found(server: SidecarServer) -> None:
    response = _request(server, "csg.remesh", {}, "x")
    assert response["error"]["data"]["code"] == "bridge.method_not_found"
