"""#742: fixed-seed samples land beside events.jsonl, not only in TensorBoard."""
import json

from PIL import Image

from middleware.src.models.hooks import DiagnosticsLogger


def test_save_sample_writes_png_and_a_relative_event(tmp_path):
    logger = DiagnosticsLogger(
        run_name="samples",
        use_tensorboard=False,
        use_wandb=False,
        jsonl_path=str(tmp_path / "events.jsonl"),
    )
    image = Image.new("RGB", (8, 8), (10, 20, 30))
    relative = logger.save_sample(image, 3, epoch=1)
    logger.close()

    assert relative == "samples/step-000003.png"
    assert (tmp_path / relative).is_file()
    event = json.loads((tmp_path / "events.jsonl").read_text())
    assert event["step"] == 3
    assert event["epoch"] == 1
    assert event["sample"] == relative
    assert "loss" not in event


def test_save_sample_without_a_sink_returns_none(tmp_path):
    logger = DiagnosticsLogger(run_name="legacy", use_tensorboard=False, use_wandb=False)
    image = Image.new("RGB", (4, 4), (0, 0, 0))
    assert logger.save_sample(image, 1) is None
    assert list(tmp_path.iterdir()) == []
