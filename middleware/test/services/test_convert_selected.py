from __future__ import annotations

import io
import time

import pytest
from middleware.src.bridge import PROTOCOL_NAME, Cancelled
from middleware.src.services.convert.commands import ConvertSingleResult
from middleware.src.services.convert.selected import list_directory, run_selected
from middleware.src.sidecar.server import SidecarServer
from PIL import Image


def _png(path, color: tuple[int, int, int] = (10, 20, 30), size: tuple[int, int] = (4, 4)) -> None:
    with Image.new("RGB", size, color) as image:
        image.save(path)


def _request(server: SidecarServer, method: str, params: dict, request_id: str) -> dict:
    return server.handle_frame({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})


def test_list_directory_skips_non_media(tmp_path) -> None:
    (tmp_path / "notes.txt").write_text("x")
    _png(tmp_path / "b.png")
    _png(tmp_path / "a.png")
    result = list_directory(str(tmp_path))
    assert result["error"] == ""
    assert result["files"] == [str(tmp_path / "a.png"), str(tmp_path / "b.png")]


def test_missing_directory_lists_nothing(tmp_path) -> None:
    result = list_directory(str(tmp_path / "missing"))
    assert result == {"files": [], "error": "not a directory"}


def test_cancel_stops_between_files(tmp_path) -> None:
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    _png(source / "a.png")
    _png(source / "b.png")

    def before_file(done: int, total: int) -> None:
        assert total == 2
        if done >= 1:
            raise Cancelled("stop")

    with pytest.raises(Cancelled):
        run_selected(
            {
                "input_dir": str(source),
                "output_dir": str(output),
                "action": "resample",
                "paths": [str(source / "a.png"), str(source / "b.png")],
                "width": 2,
                "height": 2,
                "output_format": "png",
            },
            before_file,
        )
    assert (output / "a.png").is_file()
    assert not (output / "b.png").exists()


def test_selected_file_outside_the_directory_is_refused(tmp_path) -> None:
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    other = tmp_path / "other.png"
    _png(other)
    with pytest.raises(ValueError, match="outside"):
        run_selected(
            {
                "input_dir": str(source),
                "output_dir": str(output),
                "action": "resample",
                "paths": [str(other)],
                "width": 1,
                "height": 1,
            },
            lambda _done, _total: None,
        )


def test_resample_keeps_alpha_for_png_and_drops_it_for_jpeg(tmp_path) -> None:
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    with Image.new("RGBA", (4, 4), (0, 0, 0, 0)) as image:
        image.save(source / "clear.png")
    png = run_selected(
        {
            "input_dir": str(source),
            "output_dir": str(output),
            "action": "resample",
            "paths": [str(source / "clear.png")],
            "width": 2,
            "height": 2,
            "output_format": "png",
        },
        lambda _done, _total: None,
    )
    assert png["succeeded"] == 1
    with Image.open(png["output_paths"][0]) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
    jpeg = run_selected(
        {
            "input_dir": str(source),
            "output_dir": str(output),
            "action": "reencode",
            "paths": [str(source / "clear.png")],
            "output_format": "jpg",
        },
        lambda _done, _total: None,
    )
    assert jpeg["succeeded"] == 1
    with Image.open(jpeg["output_paths"][0]) as image:
        assert image.mode == "RGB"


def test_image_reencode_writes_jpeg_without_ffmpeg(tmp_path) -> None:
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    _png(source / "a.png", (1, 2, 3), (3, 3))
    result = run_selected(
        {
            "input_dir": str(source),
            "output_dir": str(output),
            "action": "reencode",
            "paths": [str(source / "a.png")],
            "output_format": "jpg",
        },
        lambda _done, _total: None,
    )
    assert result["succeeded"] == 1
    assert result["failed"] == 0
    with Image.open(result["output_paths"][0]) as image:
        assert image.format == "JPEG"
        assert image.size == (3, 3)


def test_video_reencode_uses_ffmpeg_and_does_not_fake_output(tmp_path, monkeypatch) -> None:
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    video = source / "clip.mp4"
    video.write_bytes(b"not a video")
    monkeypatch.setattr("middleware.src.services.convert.selected.shutil.which", lambda name: None)
    result = run_selected(
        {
            "input_dir": str(source),
            "output_dir": str(output),
            "action": "reencode",
            "paths": [str(video)],
            "video_codec": "h264",
            "audio_codec": "aac",
        },
        lambda _done, _total: None,
    )
    assert result["failed"] == 1
    assert "ffmpeg is not available" in result["errors"][0]
    assert list(output.iterdir()) == []


def test_convert_action_calls_the_single_converter(tmp_path, monkeypatch) -> None:
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    _png(source / "a.png")
    seen: list[str] = []

    class FakeHandler:
        def handle(self, command):  # noqa: ANN001
            seen.append(command.input_path)
            Path = __import__("pathlib").Path
            Path(command.output_path).write_bytes(b"png")
            return ConvertSingleResult(
                input_path=command.input_path,
                output_path=command.output_path,
                success=True,
            )

    monkeypatch.setattr("middleware.src.services.convert.handlers.ConvertSingleHandler", FakeHandler)
    result = run_selected(
        {
            "input_dir": str(source),
            "output_dir": str(output),
            "action": "convert",
            "paths": [str(source / "a.png")],
            "output_format": "png",
            "quality": 95,
        },
        lambda _done, _total: None,
    )
    assert seen == [str((source / "a.png").resolve())]
    assert result["succeeded"] == 1


def test_sidecar_lists_and_resamples_one_file(tmp_path) -> None:
    source = tmp_path / "in"
    output = tmp_path / "out"
    source.mkdir()
    output.mkdir()
    _png(source / "a.png", (8, 8, 8), (4, 4))
    server = SidecarServer(stdout=io.StringIO())
    handshake = _request(
        server,
        "system.handshake",
        {"protocol": PROTOCOL_NAME, "client": {"name": "pytest", "version": "1.0.0"}},
        "hs",
    )
    assert handshake["result"]["protocol"] == PROTOCOL_NAME
    listed = _request(server, "convert.list_dir", {"directory": str(source)}, "list")
    assert listed["result"]["files"] == [str(source / "a.png")]
    started = _request(
        server,
        "convert.convert_batch",
        {
            "input_dir": str(source),
            "output_dir": str(output),
            "action": "resample",
            "paths": [str(source / "a.png")],
            "width": 2,
            "height": 1,
            "output_format": "png",
            "algorithm": "nearest",
        },
        "batch",
    )
    job_id = started["result"]["job_id"]
    state = "queued"
    progress = None
    for _ in range(50):
        status = _request(server, "jobs.status", {"job_id": job_id}, "status")["result"]
        state = status["state"]
        progress = status.get("progress")
        if state in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.05)
    assert state == "completed"
    assert progress == {"done": 1, "total": 1}
    with Image.open(output / "a.png") as image:
        assert image.size == (2, 1)
