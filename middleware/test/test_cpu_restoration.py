from PIL import Image, ImageDraw

from hie_middleware.jobs import (
    JobStatus,
    cpu_deblur_runner,
    cpu_masked_inpainting_runner,
    submit_restoration_job,
)


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
