from PIL import Image, ImageDraw

from hie_middleware.jobs import (
    JobStatus,
    cpu_deblur_runner,
    cpu_masked_inpainting_runner,
    opencv_deblur_runner,
    submit_restoration_job,
)
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
    from hie_middleware.jobs import opencv_masked_inpainting_runner

    source = tmp_path / "owned.png"
    mask = tmp_path / "logo-mask.png"
    Image.new("RGB", (20, 20), "#4477aa").save(source)
    Image.new("L", (20, 20), 0).save(mask)
    result = submit_restoration_job(
        "masked_inpainting", str(source),
        options={"mask_ref": str(mask), "permission_confirmed": True},
        runner=opencv_masked_inpainting_runner,
    ).result(5)
    assert result.status is JobStatus.SUCCEEDED
    assert (tmp_path / "owned.opencv-inpaint.png").is_file()
