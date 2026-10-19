from PIL import Image, ImageDraw

import pytest

from jobs import generate_restoration_report


def _sharp_image(size=(48, 48)):
    # A checkerboard has strong, evenly-spaced edges -> high Laplacian variance.
    image = Image.new("L", size, 0)
    draw = ImageDraw.Draw(image)
    step = 6
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2 == 0:
                draw.rectangle((x, y, x + step - 1, y + step - 1), fill=255)
    return image.convert("RGB")


def _flat_image(size=(48, 48)):
    # A single flat color has zero Laplacian response everywhere -> ~0 variance.
    return Image.new("RGB", size, "#808080")


def test_generate_restoration_report_computes_sharpness_diagnostics(tmp_path):
    input_path = tmp_path / "input.png"
    output_path = tmp_path / "output.png"
    _sharp_image().save(input_path)
    _flat_image().save(output_path)

    report = generate_restoration_report(str(input_path), str(output_path))

    assert report["schema_version"] == 1
    assert report["preview_only"] is True
    assert report["sharpness_metric"] == "laplacian_variance"
    assert report["input_size"] == [48, 48]
    assert report["output_size"] == [48, 48]
    # Sharp (checkerboard) input vs flat (blurred-to-death) output: sharpness
    # must drop, and the flat image's Laplacian variance must be ~0.
    assert report["input_sharpness"] > report["output_sharpness"]
    assert report["output_sharpness"] == pytest.approx(0.0, abs=1e-6)
    assert report["sharpness_delta"] == pytest.approx(
        report["output_sharpness"] - report["input_sharpness"]
    )


def test_generate_restoration_report_merges_caller_metrics(tmp_path):
    input_path = tmp_path / "input.png"
    output_path = tmp_path / "output.png"
    _flat_image().save(input_path)
    _flat_image().save(output_path)

    report = generate_restoration_report(
        str(input_path), str(output_path), metrics={"operation": "deblur", "backend": "pillow"}
    )

    assert report["operation"] == "deblur"
    assert report["backend"] == "pillow"
    # Caller metrics must not clobber the image-derived fields.
    assert report["sharpness_metric"] == "laplacian_variance"


def test_generate_restoration_report_writes_json_when_requested(tmp_path):
    input_path = tmp_path / "input.png"
    output_path = tmp_path / "output.png"
    _flat_image().save(input_path)
    _flat_image().save(output_path)
    report_path = tmp_path / "report.json"

    report = generate_restoration_report(str(input_path), str(output_path), write_to=str(report_path))

    assert report_path.is_file()
    import json

    on_disk = json.loads(report_path.read_text(encoding="utf-8"))
    assert on_disk == report


def test_generate_restoration_report_raises_for_missing_files(tmp_path):
    output_path = tmp_path / "output.png"
    _flat_image().save(output_path)
    with pytest.raises(FileNotFoundError, match="input"):
        generate_restoration_report(str(tmp_path / "missing.png"), str(output_path))

    input_path = tmp_path / "input.png"
    _flat_image().save(input_path)
    with pytest.raises(FileNotFoundError, match="output"):
        generate_restoration_report(str(input_path), str(tmp_path / "missing-output.png"))
