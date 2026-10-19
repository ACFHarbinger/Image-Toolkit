from PIL import Image, ImageDraw

from jobs import (
    JobStatus,
    cpu_deblur_preview,
    cpu_deblur_runner,
    cpu_masked_inpainting_runner,
    cpu_sharpen_preview,
    opencv_deblur_runner,
    submit_restoration_job,
)
from jobs.cpu_restoration import validate_inpainting_mask
import pytest


def test_cpu_deblur_runner_writes_a_new_preview(tmp_path):
    source = tmp_path / "blurred.png"
    Image.new("RGB", (24, 24), "#aa4477").save(source)
    result = submit_restoration_job("deblur", str(source), runner=cpu_deblur_runner).result(5)
    assert result.status is JobStatus.SUCCEEDED
    assert result.value.output_ref.endswith(".deblur.png")
    assert (tmp_path / "blurred.deblur.png").is_file()


def test_cpu_inpainting_runner_uses_a_mask_and_writes_preview(tmp_path):
    source = tmp_path / "owned.png"
    mask = tmp_path / "logo-mask.png"
    image = Image.new("RGB", (24, 24), "#4477aa")
    ImageDraw.Draw(image).rectangle((8, 8, 15, 15), fill="#dd44aa")
    image.save(source)
    mask_image = Image.new("L", (24, 24), 0)
    ImageDraw.Draw(mask_image).rectangle((8, 8, 15, 15), fill=255)
    mask_image.save(mask)
    result = submit_restoration_job(
        "masked_inpainting", str(source),
        options={"mask_ref": str(mask), "permission_confirmed": True},
        runner=cpu_masked_inpainting_runner,
    ).result(5)
    assert result.status is JobStatus.SUCCEEDED
    assert (tmp_path / "owned.inpaint.png").is_file()


def test_opencv_deblur_runner_writes_preview_when_uv_extra_is_installed(tmp_path):
    pytest.importorskip("cv2")
    source = tmp_path / "blurred.png"
    Image.new("RGB", (20, 20), "#6688aa").save(source)
    result = submit_restoration_job(
        "deblur", str(source), options={"strength": 1.0}, runner=opencv_deblur_runner
    ).result(5)
    assert result.status is JobStatus.SUCCEEDED
    assert (tmp_path / "blurred.opencv-deblur.png").is_file()


def test_opencv_inpainting_runner_writes_preview_when_uv_extra_is_installed(tmp_path):
    pytest.importorskip("cv2")
    from jobs import opencv_masked_inpainting_runner

    source = tmp_path / "owned.png"
    mask = tmp_path / "logo-mask.png"
    Image.new("RGB", (20, 20), "#4477aa").save(source)
    mask_image = Image.new("L", (20, 20), 0)
    ImageDraw.Draw(mask_image).rectangle((8, 8, 11, 11), fill=255)
    mask_image.save(mask)
    result = submit_restoration_job(
        "masked_inpainting", str(source),
        options={"mask_ref": str(mask), "permission_confirmed": True},
        runner=opencv_masked_inpainting_runner,
    ).result(5)
    assert result.status is JobStatus.SUCCEEDED
    assert (tmp_path / "owned.opencv-inpaint.png").is_file()


def test_inpainting_mask_validation_rejects_empty_and_broad_masks():
    empty = Image.new("L", (10, 10), 0)
    with pytest.raises(ValueError, match="at least one"):
        validate_inpainting_mask(empty)

    broad = Image.new("L", (10, 10), 255)
    with pytest.raises(ValueError, match="entire image"):
        validate_inpainting_mask(broad)

    mostly_marked = Image.new("L", (10, 10), 255)
    ImageDraw.Draw(mostly_marked).rectangle((0, 0, 2, 2), fill=0)
    with pytest.raises(ValueError, match="safety limit"):
        validate_inpainting_mask(mostly_marked)


def test_cpu_deblur_preview_returns_an_image_without_writing_a_file(tmp_path):
    source = tmp_path / "blurred.png"
    Image.new("RGB", (24, 24), "#aa4477").save(source)

    result = cpu_deblur_preview(str(source), strength=1.5, radius=1.0)

    assert isinstance(result, Image.Image)
    assert result.size == (24, 24)
    # No output file should appear -- this is the in-memory-only counterpart
    # to cpu_deblur_runner, which does write one.
    assert not (tmp_path / "blurred.deblur.png").exists()


def test_cpu_deblur_preview_validates_strength_and_radius(tmp_path):
    source = tmp_path / "blurred.png"
    Image.new("RGB", (24, 24), "#aa4477").save(source)

    with pytest.raises(ValueError, match="strength must be between 0 and 3"):
        cpu_deblur_preview(str(source), strength=5.0)
    with pytest.raises(ValueError, match="radius must be between 0.1 and 5"):
        cpu_deblur_preview(str(source), radius=10.0)


def test_cpu_sharpen_preview_returns_an_image_without_writing_a_file(tmp_path):
    source = tmp_path / "soft.png"
    Image.new("RGB", (24, 24), "#335577").save(source)

    result = cpu_sharpen_preview(str(source), strength=1.0)

    assert isinstance(result, Image.Image)
    assert result.size == (24, 24)
    assert not (tmp_path / "soft.sharpen.png").exists()


def test_cpu_sharpen_preview_validates_strength(tmp_path):
    source = tmp_path / "soft.png"
    Image.new("RGB", (24, 24), "#335577").save(source)
    with pytest.raises(ValueError, match="sharpen strength must be between 0 and 3"):
        cpu_sharpen_preview(str(source), strength=-1.0)


def test_cpu_preview_functions_raise_for_missing_input():
    with pytest.raises(FileNotFoundError):
        cpu_deblur_preview("/does/not/exist.png")
    with pytest.raises(FileNotFoundError):
        cpu_sharpen_preview("/does/not/exist.png")
