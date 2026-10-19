import json

from PIL import Image

from restore_cli import build_parser, main


def test_restore_cli_parses_deblur_and_inpaint_commands():
    parser = build_parser()
    deblur = parser.parse_args(["deblur", "blurred.png", "--strength", "1.5"])
    assert deblur.operation == "deblur"
    assert deblur.strength == 1.5
    inpaint = parser.parse_args(["inpaint", "owned.png", "--mask", "mask.png", "--permission-confirmed"])
    assert inpaint.operation == "inpaint"
    assert inpaint.permission_confirmed is True
    assert inpaint.max_mask_coverage == 0.5


def test_restore_cli_writes_deblur_preview_report(tmp_path):
    source = tmp_path / "blur.png"
    output = tmp_path / "restored.png"
    report = tmp_path / "report.json"
    Image.new("RGB", (10, 12), "#6688aa").save(source)
    assert main(["deblur", str(source), "--output", str(output), "--report", str(report)]) == 0
    data = json.loads(report.read_text())
    assert data["preview_only"] is True
    assert data["input_size"] == [10, 12]
    assert data["operation"] == "deblur"
    assert "sharpness_delta" in data
