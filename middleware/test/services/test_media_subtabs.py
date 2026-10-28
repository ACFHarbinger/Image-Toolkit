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


def test_sampler_preflights_the_complete_batch_before_writing(tmp_path):
    from middleware.src.services.media.subtabs import resample
    from PIL import Image

    first = tmp_path / "in" / "a.png"
    second = tmp_path / "out" / "a.png"
    first.parent.mkdir()
    second.parent.mkdir()
    with Image.new("RGB", (8, 8), "red") as image:
        image.save(first)
    with Image.new("RGB", (8, 8), "blue") as image:
        image.save(second)
    originals = [path.read_bytes() for path in (first, second)]
    # Relative aliases must also be rejected by the native path check.
    alias = second.parent / ".." / "out" / "a.png"
    result = resample({"input_path": str(first), "output_path": str(alias), "factor": 0.5,
                       "batch": [{"input_path": str(first), "output_path": str(alias)},
                                 {"input_path": str(second), "output_path": str(second)}]})
    assert result["success"] is False
    assert [path.read_bytes() for path in (first, second)] == originals


def test_sampler_rejects_aliased_duplicate_batch_outputs(tmp_path):
    from middleware.src.services.media.subtabs import resample

    output = tmp_path / "out.png"
    result = resample({"input_path": str(tmp_path / "a.png"), "output_path": str(output),
                       "batch": [{"input_path": str(tmp_path / "a.png"), "output_path": str(output)},
                                 {"input_path": str(tmp_path / "b.png"), "output_path": str(tmp_path / ".." / tmp_path.name / "out.png")}]})
    assert result["success"] is False
    assert not output.exists()
