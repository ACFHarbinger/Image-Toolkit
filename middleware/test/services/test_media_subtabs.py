"""Codec re-encode uses VideoFormatConverter and keeps diagnostics off stdout."""

from __future__ import annotations

import io
import json

from middleware.src.services.media.subtabs import main, reencode


def test_reencode_imports_the_format_converter(tmp_path) -> None:
    missing = tmp_path / "missing.mp4"
    result = reencode(
        {
            "input_path": str(missing),
            "output_path": str(tmp_path / "out.mp4"),
            "video_codec": "h264",
            "audio_codec": "aac",
        }
    )
    assert result["success"] is False
    assert "ImportError" not in result["message"]
    assert "VideoConverter" not in result["message"]


def test_converter_diagnostics_are_not_in_the_json_stdout(monkeypatch, capsys) -> None:
    def noisy(*_args: object, **_kwargs: object) -> bool:
        print("Converting 'clip.mp4' to 'out.mp4' using Native Backend (ffmpeg)...")
        return True

    monkeypatch.setattr(
        "middleware.src.core.video.video_converter.VideoFormatConverter.convert_video",
        noisy,
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({
        "action": "convert_file",
        "input_path": "in.mp4",
        "output_path": "out.mp4",
        "output_format": "mp4",
    })))
    assert main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["success"] is True
    assert "Converting" not in captured.out
    assert "Converting" in captured.err


def test_lossless_crf_zero_is_forwarded(monkeypatch, tmp_path):
    seen = {}

    def convert(*args, **kwargs):
        seen.update(kwargs)
        return True

    monkeypatch.setattr("middleware.src.core.video.video_converter.VideoFormatConverter.convert_codec", convert)
    assert reencode({"input_path": str(tmp_path / "in.mp4"), "output_path": str(tmp_path / "out.mp4"), "crf": 0})["success"]
    assert seen["crf"] == 0


def test_preview_uses_bounded_pixels_and_preserves_source_dimensions(tmp_path):
    import base64

    from middleware.src.services.media.subtabs import dispatch
    from PIL import Image

    source = tmp_path / "source.png"
    with Image.new("RGBA", (800, 600), (255, 0, 0, 128)) as image:
        image.save(source)
    result = dispatch({"action": "preview", "path": str(source)})
    assert result["error"] == ""
    assert (result["width"], result["height"]) == (800, 600)
    with Image.open(io.BytesIO(base64.b64decode(result["png_base64"]))) as preview:
        assert preview.size == (512, 384)
        assert preview.getpixel((0, 0))[3] == 128
