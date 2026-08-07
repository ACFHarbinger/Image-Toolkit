import json
import os
import tempfile
import time
from datetime import datetime
from backend.src.animation.core.pipeline.trace import PipelineTrace, StageEntry

def test_pipeline_trace_initialization():
    trace = PipelineTrace(run_id="run-123", started_at="2026-08-07T00:00:00Z")
    assert trace.run_id == "run-123"
    assert trace.started_at == "2026-08-07T00:00:00Z"
    assert len(trace.stages) == 0

def test_pipeline_trace_stage_recording():
    trace = PipelineTrace(run_id="run-123", started_at="2026-08-07T00:00:00Z")
    trace.begin_stage(1, "preprocessing")
    assert len(trace.stages) == 1
    assert trace.stages[0].stage_name == "preprocessing"
    
    time.sleep(0.01) # Sleep to ensure duration is > 0
    trace.end_stage(1, "ok")
    assert trace.stages[0].status == "ok"
    assert trace.stages[0].duration_ms > 0
    assert trace.stages[0].error is None

def test_pipeline_trace_error_capture():
    trace = PipelineTrace(run_id="run-123", started_at="2026-08-07T00:00:00Z")
    trace.begin_stage(1, "processing")
    trace.end_stage(1, "error", error="Out of memory")
    assert trace.stages[0].status == "error"
    assert trace.stages[0].error == "Out of memory"

def test_pipeline_trace_serialization():
    trace = PipelineTrace(run_id="run-123", started_at="2026-08-07T00:00:00Z")
    trace.begin_stage(1, "processing")
    trace.end_stage(1, "ok")
    
    json_str = trace.to_json()
    data = json.loads(json_str)
    assert data["run_id"] == "run-123"
    assert data["started_at"] == "2026-08-07T00:00:00Z"
    assert len(data["stages"]) == 1
    assert data["stages"][0]["stage_name"] == "processing"
    assert data["stages"][0]["status"] == "ok"

def test_pipeline_trace_save_no_gpu():
    trace = PipelineTrace(run_id="run-123", started_at="2026-08-07T00:00:00Z")
    trace.begin_stage(1, "processing")
    trace.end_stage(1, "ok")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        file_path = os.path.join(temp_dir, "trace.json")
        trace.save(file_path)
        assert os.path.exists(file_path)
        
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["run_id"] == "run-123"
