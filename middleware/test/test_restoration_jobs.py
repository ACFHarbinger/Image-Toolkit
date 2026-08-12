import pytest

from hie_middleware.jobs import JobProgress, JobStatus, submit_restoration_job
from hie_middleware.models import ModelUnavailable


def test_restoration_job_uses_injected_runner_and_reports_output():
    def runner(input_ref, options, _token, report):
        report(JobProgress(0.5, "inference"))
        return f"restored:{input_ref}:{options['strength']}"

    result = submit_restoration_job(
        "deblur", "blurred.png", options={"strength": 0.8}, runner=runner
    ).result(5)
    assert result.status is JobStatus.SUCCEEDED
    assert result.value.output_ref == "restored:blurred.png:0.8"


def test_restoration_job_requires_optional_runtime_and_consent():
    with pytest.raises(ModelUnavailable):
        submit_restoration_job("deblur", "blurred.png")
    with pytest.raises(ValueError, match="mask_ref"):
        submit_restoration_job("masked_inpainting", "owned.png", runner=lambda *_: "out.png")
    with pytest.raises(PermissionError):
        submit_restoration_job(
            "masked_inpainting", "owned.png", options={"mask_ref": "logo.png"},
            runner=lambda *_: "out.png",
        )


def test_restoration_job_rejects_empty_runner_output():
    handle = submit_restoration_job("deblur", "blurred.png", runner=lambda *_: "")
    result = handle.result(5)
    assert result.status is JobStatus.FAILED
    assert "output reference" in result.error
