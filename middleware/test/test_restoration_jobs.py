import pytest

from hie_middleware.jobs import JobProgress, JobStatus, submit_restoration_job
from hie_middleware.models import ModelUnavailable
from hie_middleware.pipeline import RestorationPipeline


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


def test_restoration_pipeline_dispatches_injected_backend():
    calls = []

    def runner(input_ref, options, _token, _report):
        calls.append((input_ref, options["backend"]))
        return "preview.png"

    pipeline = RestorationPipeline(runners={"deblur:pillow": runner})
    result = pipeline.submit("deblur", "input.png").result(5)
    assert result.status is JobStatus.SUCCEEDED
    assert result.value.output_ref == "preview.png"
    assert calls == [("input.png", "pillow")]


def test_restoration_pipeline_reports_capabilities_and_validates_backend():
    pipeline = RestorationPipeline(runners={"deblur:pillow": lambda *_: "out.png"})
    assert pipeline.capabilities() == {"deblur": ["pillow"]}
    with pytest.raises(ValueError, match="unsupported restoration backend"):
        pipeline.submit("deblur", "input.png", backend="remote")
