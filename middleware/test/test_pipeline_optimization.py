import pytest

from pipeline import OptimizationPipeline, OptimizationUnavailable


def test_optimization_pipeline_defaults_to_cancellable_reference_jobs():
    pipeline = OptimizationPipeline()
    result = pipeline.pso(lambda values: sum(value * value for value in values), [(-1, 1)], max_iter=3, seed=7).result(5)
    assert result.ok
    assert len(result.value) == 1
    assert pipeline.capabilities()["reference"] is True


def test_native_backend_is_explicit_and_reports_when_extension_is_unavailable():
    pipeline = OptimizationPipeline()
    if pipeline.capabilities()["native"]:
        pytest.skip("native base.hie extension is available in this environment")
    with pytest.raises(OptimizationUnavailable, match="base.hie"):
        pipeline.differential_evolution(lambda values: sum(value * value for value in values), [(-1, 1)], backend="native")
