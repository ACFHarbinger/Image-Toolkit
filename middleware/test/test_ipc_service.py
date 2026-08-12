from hie_middleware import IpcRequest, IpcService


def test_ipc_service_opens_and_exports_a_still_document():
    service = IpcService()
    opened = service.handle(IpcRequest("open-1", "open_media", {"source": "image.png", "document_id": "doc-1"}))
    assert opened.status == "ok"
    assert opened.payload["document_id"] == "doc-1"
    exported = service.handle(IpcRequest("export-1", "export_document", {"document_id": "doc-1"}))
    assert exported.status == "ok"
    assert exported.payload["document"]["sequence"]["frames"][0]["source"] == "image.png"


def test_ipc_service_opens_a_multi_frame_sequence_with_timing():
    service = IpcService()
    response = service.handle(IpcRequest("open-clip", "open_media", {
        "document_id": "clip-1",
        "fps": 24,
        "frames": [
            "frame-1.png",
            {"source": "frame-2.png", "duration_ms": 42, "metadata": {"keyframe": True}},
        ],
    }))
    assert response.status == "ok"
    assert response.payload["frame_count"] == 2
    assert response.payload["fps"] == 24.0
    exported = service.handle(IpcRequest("export-clip", "export_document", {"document_id": "clip-1"}))
    frames = exported.payload["document"]["sequence"]["frames"]
    assert frames[1]["duration_ms"] == 42
    assert frames[1]["metadata"] == {"keyframe": True}


def test_ipc_service_rejects_invalid_multi_frame_payloads():
    service = IpcService()
    for frames in [[], [{"source": ""}], [{"source": "a", "duration_ms": -1}]]:
        response = service.handle(IpcRequest("bad-clip", "open_media", {"frames": frames}))
        assert response.status == "error"


def test_ipc_service_returns_structured_errors_without_raising():
    service = IpcService()
    missing = service.handle(IpcRequest("open-1", "open_media"))
    assert missing.status == "error"
    assert "source" in (missing.error or "")
    unknown = service.handle(IpcRequest("export-1", "export_document", {"document_id": "missing"}))
    assert unknown.status == "error"
    assert "not open" in (unknown.error or "")


def test_ipc_service_acknowledges_notifications():
    response = IpcService().handle(IpcRequest("note-1", "notify", {"message": "ready"}))
    assert response.to_dict()["payload"] == {"acknowledged": True}
